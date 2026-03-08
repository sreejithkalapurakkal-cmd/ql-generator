import json
import logging
from typing import Optional

import boto3
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.company import Company

logger = logging.getLogger(__name__)
settings = get_settings()

_bedrock_client = None


def _get_bedrock_client():
    global _bedrock_client
    if _bedrock_client is None:
        _bedrock_client = boto3.client(
            "bedrock-runtime",
            region_name=settings.AWS_REGION,
        )
    return _bedrock_client


def _build_embedding_text(company: Company) -> str:
    """Combine company fields into a single text document for embedding."""
    parts = []

    if company.name:
        parts.append(f"Company: {company.name}")
    if company.industry:
        parts.append(f"Industry: {company.industry}")
    if company.sub_industry:
        parts.append(f"Sub-industry: {company.sub_industry}")
    if company.description:
        parts.append(f"Description: {company.description}")
    if company.city or company.state_region or company.country:
        location = ", ".join(filter(None, [company.city, company.state_region, company.country]))
        parts.append(f"Location: {location}")
    if company.employee_count:
        parts.append(f"Employees: {company.employee_count}")
    if company.revenue_estimate:
        parts.append(f"Revenue estimate: ${company.revenue_estimate:,}")
    if company.website:
        parts.append(f"Website: {company.website}")

    # Tech stack
    tech = company.tech_stack_json
    if tech:
        if isinstance(tech, list):
            parts.append(f"Tech stack: {', '.join(str(t) for t in tech)}")
        elif isinstance(tech, dict):
            parts.append(f"Tech stack: {json.dumps(tech)}")

    # Match reasoning
    if company.match_reasoning:
        parts.append(f"ICP match reasoning: {company.match_reasoning}")

    # BANT score details (if loaded)
    if company.bant_score:
        bant = company.bant_score
        if bant.budget_reason:
            parts.append(f"Budget: {bant.budget_reason}")
        if bant.authority_reason:
            parts.append(f"Authority: {bant.authority_reason}")
        if bant.need_reason:
            parts.append(f"Need: {bant.need_reason}")
        if bant.timing_reason:
            parts.append(f"Timing: {bant.timing_reason}")
        if bant.overall_summary:
            parts.append(f"BANT summary: {bant.overall_summary}")

    # Contact titles
    if company.contacts:
        titles = [c.designation for c in company.contacts if c.designation]
        if titles:
            parts.append(f"Key contacts: {', '.join(titles)}")

    text_doc = "\n".join(parts)
    # Titan v2 limit is ~8192 tokens; truncate text to ~8000 chars as safety margin
    return text_doc[:8000]


def generate_embedding(text: str) -> Optional[list[float]]:
    """Generate a 1024-dim embedding using Bedrock Titan Text Embeddings v2."""
    try:
        client = _get_bedrock_client()
        body = json.dumps({
            "inputText": text,
            "dimensions": settings.EMBEDDING_DIMENSION,
        })
        response = client.invoke_model(
            modelId=settings.BEDROCK_EMBEDDING_MODEL_ID,
            body=body,
            contentType="application/json",
            accept="application/json",
        )
        result = json.loads(response["body"].read())
        return result["embedding"]
    except Exception as e:
        logger.error(f"Failed to generate embedding: {e}")
        return None


async def embed_company(company: Company, db: AsyncSession) -> None:
    """Generate and save embedding for a single company."""
    text_doc = _build_embedding_text(company)
    embedding = generate_embedding(text_doc)
    if embedding:
        company.embedding = embedding
        await db.flush()


async def embed_all_companies(db: AsyncSession, batch_size: int = 50) -> int:
    """Backfill embeddings for companies that don't have one yet."""
    count = 0
    offset = 0

    while True:
        result = await db.execute(
            select(Company)
            .where(Company.embedding.is_(None))
            .order_by(Company.created_at)
            .offset(offset)
            .limit(batch_size)
        )
        companies = result.scalars().all()
        if not companies:
            break

        for company in companies:
            text_doc = _build_embedding_text(company)
            embedding = generate_embedding(text_doc)
            if embedding:
                company.embedding = embedding
                count += 1

        await db.commit()
        offset += batch_size

    return count
