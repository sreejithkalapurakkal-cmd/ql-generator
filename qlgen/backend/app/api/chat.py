import asyncio
import json
import logging
import queue
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db, async_session
from app.models.chat_session import ChatSession
from app.models.chat_message import ChatMessage
from app.models.user import User
from app.schemas.chat import (
    ChatMessageRequest,
    ChatMessageResponse,
    ChatSessionResponse,
    RecommendationsRequest,
    RecommendationsResponse,
    RecommendationItem,
)
from app.agent.copilot_agent import create_copilot_agent, create_copilot_callback_handler
from app.auth.dependencies import get_current_user, decode_token
from app.auth.authorization import is_admin, ownership_filter, check_resource_access, check_delete_permission
from app.auth.context import current_user_id, current_user_is_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


def _build_agent_prompt(
    user_message: str,
    conversation_history: list[dict],
    page_context: dict | None = None,
) -> str:
    """Build the full prompt for the co-pilot agent including context and history."""
    parts = []

    # Page context
    if page_context:
        ctx_lines = ["[Current Page Context]"]
        if page_context.get("page_type"):
            ctx_lines.append(f"Page: {page_context['page_type']}")
        if page_context.get("run_id"):
            ctx_lines.append(f"Pipeline Run ID: {page_context['run_id']}")
        if page_context.get("company_id"):
            ctx_lines.append(f"Company ID: {page_context['company_id']}")
        if page_context.get("icp_id"):
            ctx_lines.append(f"ICP ID: {page_context['icp_id']}")
        parts.append("\n".join(ctx_lines))

    # Conversation history (last 20 messages)
    if conversation_history:
        parts.append("[Conversation History]")
        for msg in conversation_history[-20:]:
            role = msg["role"].capitalize()
            content = msg["content"]
            # Truncate long history messages
            if len(content) > 500:
                content = content[:500] + "..."
            parts.append(f"{role}: {content}")

    # Current user message
    parts.append(f"[Current Message]\nUser: {user_message}")

    return "\n\n".join(parts)


@router.post("/send")
async def send_chat_message(request: ChatMessageRequest, http_request: Request):
    """Send a message and receive a streaming SSE response from the co-pilot agent."""
    # Validate auth before entering generator
    auth_header = http_request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = auth_header.split(" ", 1)[1]
    payload = decode_token(token)
    user_id_str = payload.get("sub")
    if not user_id_str or payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token")

    async def event_generator():
        try:
            async with async_session() as db:
                # Verify user exists
                from uuid import UUID as _UUID
                user_result = await db.execute(select(User).where(User.id == _UUID(user_id_str)))
                user = user_result.scalar_one_or_none()
                if not user or not user.is_active:
                    yield f"event: error\ndata: {json.dumps({'message': 'Unauthorized'})}\n\n"
                    return

                # Get or create session
                session_id = request.session_id
                if session_id:
                    result = await db.execute(
                        select(ChatSession).where(
                            ChatSession.id == session_id,
                            ChatSession.is_active == True,
                            ChatSession.user_id == user.id,
                        )
                    )
                    chat_session = result.scalar_one_or_none()
                    if not chat_session:
                        yield f"event: error\ndata: {json.dumps({'message': 'Session not found'})}\n\n"
                        return
                else:
                    chat_session = ChatSession(
                        title=request.message[:100],
                        page_context=request.page_context.model_dump() if request.page_context else None,
                        user_id=user.id,
                    )
                    db.add(chat_session)
                    await db.flush()
                    session_id = chat_session.id

                # Emit session info
                yield f"event: session\ndata: {json.dumps({'session_id': str(session_id)})}\n\n"

                # Save user message
                user_msg = ChatMessage(
                    session_id=session_id,
                    role="user",
                    content=request.message,
                    page_context=request.page_context.model_dump() if request.page_context else None,
                )
                db.add(user_msg)
                await db.flush()

                # Load conversation history
                history_result = await db.execute(
                    select(ChatMessage)
                    .where(ChatMessage.session_id == session_id)
                    .order_by(ChatMessage.created_at)
                )
                history_messages = history_result.scalars().all()
                conversation_history = [
                    {"role": m.role, "content": m.content}
                    for m in history_messages[:-1]  # Exclude the just-added message
                ]

                # Build prompt
                page_ctx = request.page_context.model_dump() if request.page_context else None
                prompt = _build_agent_prompt(
                    request.message,
                    conversation_history,
                    page_ctx,
                )

                # Fetch disabled tools for copilot
                from app.services.tool_registry_service import get_disabled_tool_names
                try:
                    disabled_tools = await get_disabled_tool_names(db)
                except Exception:
                    disabled_tools = set()

                # Set context vars for co-pilot DB tools (propagated to thread by asyncio.to_thread)
                current_user_id.set(user.id)
                current_user_is_admin.set(is_admin(user))

                # Create agent with callback handler
                event_queue = queue.Queue()
                callback_handler = create_copilot_callback_handler(event_queue)
                agent = create_copilot_agent(callback_handler=callback_handler, disabled_tools=disabled_tools)

                # Run agent in thread pool
                full_response = ""
                tool_calls_log = []

                async def run_agent():
                    return await asyncio.to_thread(agent, prompt)

                agent_task = asyncio.create_task(run_agent())

                # Drain events from the queue while agent runs
                while not agent_task.done():
                    try:
                        event = event_queue.get_nowait()
                        if event["type"] == "text_delta":
                            full_response_part = event["content"]
                            yield f"event: text_delta\ndata: {json.dumps({'content': full_response_part})}\n\n"
                            full_response += full_response_part
                        elif event["type"] == "tool_use":
                            tool_calls_log.append({
                                "tool_name": event["tool_name"],
                                "display_name": event["display_name"],
                            })
                            yield f"event: tool_use\ndata: {json.dumps(event)}\n\n"
                        elif event["type"] == "tool_result":
                            yield f"event: tool_result\ndata: {json.dumps(event)}\n\n"
                    except queue.Empty:
                        await asyncio.sleep(0.05)

                # Get the agent result
                try:
                    result = await agent_task
                    # Drain remaining events
                    while not event_queue.empty():
                        try:
                            event = event_queue.get_nowait()
                            if event["type"] == "text_delta":
                                full_response += event["content"]
                                yield f"event: text_delta\ndata: {json.dumps({'content': event['content']})}\n\n"
                            elif event["type"] == "tool_use":
                                tool_calls_log.append({
                                    "tool_name": event["tool_name"],
                                    "display_name": event["display_name"],
                                })
                                yield f"event: tool_use\ndata: {json.dumps(event)}\n\n"
                            elif event["type"] == "tool_result":
                                yield f"event: tool_result\ndata: {json.dumps(event)}\n\n"
                        except queue.Empty:
                            break

                    # If we got text from the agent result but not from streaming
                    result_text = str(result)
                    if not full_response and result_text:
                        full_response = result_text
                        yield f"event: text_delta\ndata: {json.dumps({'content': result_text})}\n\n"

                except Exception as agent_err:
                    logger.error(f"Agent execution failed: {agent_err}")
                    error_msg = f"I encountered an error while processing your request. Please try again."
                    full_response = error_msg
                    yield f"event: text_delta\ndata: {json.dumps({'content': error_msg})}\n\n"

                # Save assistant message
                assistant_msg = ChatMessage(
                    session_id=session_id,
                    role="assistant",
                    content=full_response or "I wasn't able to generate a response.",
                    tool_calls=tool_calls_log if tool_calls_log else None,
                )
                db.add(assistant_msg)
                await db.commit()

                yield f"event: done\ndata: {json.dumps({'session_id': str(session_id)})}\n\n"

        except Exception as e:
            logger.error(f"Chat stream error: {e}")
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/sessions")
async def list_chat_sessions(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """List all active chat sessions, most recent first."""
    query = (
        select(ChatSession)
        .where(
            ChatSession.is_active == True,
            ownership_filter(ChatSession.user_id, user),
        )
        .order_by(ChatSession.created_at.desc())
        .limit(50)
    )
    result = await db.execute(query)
    sessions = result.scalars().all()

    response = []
    for session in sessions:
        # Get message count and last message
        count_result = await db.execute(
            select(func.count(ChatMessage.id)).where(ChatMessage.session_id == session.id)
        )
        msg_count = count_result.scalar() or 0

        last_msg_result = await db.execute(
            select(ChatMessage.content)
            .where(ChatMessage.session_id == session.id)
            .order_by(ChatMessage.created_at.desc())
            .limit(1)
        )
        last_msg = last_msg_result.scalar()

        response.append(ChatSessionResponse(
            id=session.id,
            title=session.title,
            page_context=session.page_context,
            created_at=session.created_at,
            updated_at=session.updated_at,
            message_count=msg_count,
            last_message_preview=last_msg[:100] if last_msg else None,
        ))

    return response


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Get all messages for a chat session."""
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.is_active == True,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    check_resource_access(session.user_id, user)

    msg_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    messages = msg_result.scalars().all()

    return [
        ChatMessageResponse(
            id=m.id,
            session_id=m.session_id,
            role=m.role,
            content=m.content,
            tool_calls=m.tool_calls,
            created_at=m.created_at,
        )
        for m in messages
    ]


@router.delete("/sessions/{session_id}")
async def delete_chat_session(session_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Soft-delete a chat session."""
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    check_delete_permission(session.user_id, user)

    session.is_active = False
    await db.commit()
    return {"status": "deleted"}


@router.post("/recommendations")
async def get_recommendations(request: RecommendationsRequest, _user: User = Depends(get_current_user)):
    """Get context-aware recommendation cards based on current page."""
    page_type = request.page_context.page_type if request.page_context else None

    recommendations_map = {
        "LeadsPage": [
            RecommendationItem(
                icon="fire",
                text="Show hottest leads",
                prompt="Show me the top leads with the highest BANT scores from this pipeline run. Rank them and explain why they're hot.",
            ),
            RecommendationItem(
                icon="bar-chart",
                text="Analyze BANT patterns",
                prompt="Analyze the BANT score patterns across companies in this run. What dimensions are strongest/weakest? Any patterns?",
            ),
            RecommendationItem(
                icon="search",
                text="Find similar companies",
                prompt="Based on the top-scoring companies in this run, find similar companies I might be missing.",
            ),
            RecommendationItem(
                icon="contacts",
                text="Best reachable contacts",
                prompt="Which contacts in this run have the most complete information (email + phone + LinkedIn)? Who should I reach out to first?",
            ),
        ],
        "DashboardPage": [
            RecommendationItem(
                icon="database",
                text="Data overview",
                prompt="Give me a complete overview of all my lead data — total companies, contacts, BANT distribution, top industries.",
            ),
            RecommendationItem(
                icon="trophy",
                text="Best leads across all runs",
                prompt="What are my best leads across all pipeline runs? Show me the top 10 by BANT score.",
            ),
            RecommendationItem(
                icon="pie-chart",
                text="Industry breakdown",
                prompt="Show me a breakdown of companies by industry across all my data. Which industries have the highest average BANT scores?",
            ),
            RecommendationItem(
                icon="global",
                text="Geographic distribution",
                prompt="Show me the geographic distribution of my leads. Which countries and cities have the most companies?",
            ),
        ],
        "ICPConfigPage": [
            RecommendationItem(
                icon="experiment",
                text="How did this ICP perform?",
                prompt="Analyze the performance of this ICP configuration. How many leads were generated? What were the BANT scores?",
            ),
            RecommendationItem(
                icon="bulb",
                text="Suggest improvements",
                prompt="Based on the results from this ICP, what improvements would you suggest to the criteria to find better leads?",
            ),
        ],
        "ICPListPage": [
            RecommendationItem(
                icon="swap",
                text="Compare my ICPs",
                prompt="Compare all my ICP configurations side by side. Which one generated the best leads?",
            ),
            RecommendationItem(
                icon="plus-circle",
                text="Suggest new ICP",
                prompt="Based on my best-performing leads across all runs, suggest a new ICP configuration that would find similar companies.",
            ),
        ],
    }

    default_recommendations = [
        RecommendationItem(
            icon="question-circle",
            text="What can you help with?",
            prompt="What can you help me with? What kind of questions can I ask about my leads and data?",
        ),
        RecommendationItem(
            icon="database",
            text="Summarize my data",
            prompt="Give me a summary of all the lead data I have. How many companies, contacts, and what are the key metrics?",
        ),
    ]

    recs = recommendations_map.get(page_type, default_recommendations)
    return RecommendationsResponse(recommendations=recs)


@router.post("/embed-backfill")
async def embed_backfill(_user: User = Depends(get_current_user)):
    """Generate embeddings for all companies that don't have one yet."""
    from app.services.embedding_service import embed_all_companies

    async with async_session() as db:
        count = await embed_all_companies(db)
        return {"status": "completed", "companies_embedded": count}
