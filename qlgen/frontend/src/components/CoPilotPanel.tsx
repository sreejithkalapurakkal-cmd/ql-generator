import React, { useState, useEffect, useRef, useCallback } from 'react';
import { usePageContext } from '../context/PageContextProvider';
import {
  sendChatMessageStream,
  listChatSessions,
  getSessionMessages,
  deleteChatSession,
  getRecommendations,
} from '../api/chatApi';
import CoPilotMessageBubble from './CoPilotMessageBubble';
import CoPilotRecommendations from './CoPilotRecommendations';
import type { ChatMessage, ChatSession, RecommendationItem } from '../types';

const CoPilotPanel: React.FC = () => {
  const { pageContext } = usePageContext();

  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [streamingContent, setStreamingContent] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [recommendations, setRecommendations] = useState<RecommendationItem[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [activeTools, setActiveTools] = useState<string[]>([]);
  const [showSessionList, setShowSessionList] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingContent, activeTools, scrollToBottom]);

  const loadRecommendations = useCallback(() => {
    getRecommendations(pageContext)
      .then((res) => setRecommendations(res.data.recommendations))
      .catch(() => {});
  }, [pageContext]);

  // Load sessions when panel opens
  useEffect(() => {
    if (isOpen) {
      listChatSessions()
        .then((res) => setSessions(res.data))
        .catch(() => {});
      loadRecommendations();
    }
  }, [isOpen, pageContext.page_type, loadRecommendations]);

  // Load session messages
  const loadSession = useCallback(async (sessionId: string) => {
    try {
      const res = await getSessionMessages(sessionId);
      setMessages(res.data);
      setCurrentSessionId(sessionId);
      setShowSessionList(false);
    } catch {
      // Session may have been deleted
    }
  }, []);

  // Start a new chat
  const startNewChat = useCallback(() => {
    setMessages([]);
    setCurrentSessionId(null);
    setStreamingContent('');
    setActiveTools([]);
    setShowSessionList(false);
    loadRecommendations();
  }, [loadRecommendations]);

  // Send a message
  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || isStreaming) return;

    const userMessage: ChatMessage = {
      id: `temp-${Date.now()}`,
      session_id: currentSessionId || '',
      role: 'user',
      content: text.trim(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue('');
    setIsStreaming(true);
    setStreamingContent('');
    setActiveTools([]);
    setRecommendations([]);

    await sendChatMessageStream(
      text.trim(),
      currentSessionId,
      pageContext,
      {
        onSession: (sessionId) => {
          setCurrentSessionId(sessionId);
        },
        onTextDelta: (content) => {
          setStreamingContent((prev) => prev + content);
        },
        onToolUse: (_toolName, displayName) => {
          setActiveTools((prev) => [...prev, displayName]);
        },
        onToolResult: () => {
          // Tool completed — could update UI but keep it simple
        },
        onDone: (sessionId) => {
          setStreamingContent((prev) => {
            if (prev) {
              const assistantMsg: ChatMessage = {
                id: `msg-${Date.now()}`,
                session_id: sessionId,
                role: 'assistant',
                content: prev,
              };
              setMessages((msgs) => [...msgs, assistantMsg]);
            }
            return '';
          });
          setIsStreaming(false);
          setActiveTools([]);
          // Refresh session list
          listChatSessions()
            .then((res) => setSessions(res.data))
            .catch(() => {});
        },
        onError: (message) => {
          const errorMsg: ChatMessage = {
            id: `err-${Date.now()}`,
            session_id: currentSessionId || '',
            role: 'assistant',
            content: `Something went wrong: ${message}. Please try again.`,
          };
          setMessages((prev) => [...prev, errorMsg]);
          setIsStreaming(false);
          setStreamingContent('');
          setActiveTools([]);
        },
      },
    );
  }, [currentSessionId, isStreaming, pageContext]);

  // Handle enter key
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(inputValue);
    }
  };

  // Delete a session
  const handleDeleteSession = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await deleteChatSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      if (currentSessionId === sessionId) {
        startNewChat();
      }
    } catch {
      // ignore
    }
  };

  // Context chip text
  const contextChipText = (() => {
    const parts: string[] = [];
    if (pageContext.page_type && pageContext.page_type !== 'Unknown') {
      parts.push(pageContext.page_type.replace('Page', ''));
    }
    if (pageContext.run_id) parts.push(`Run: ${pageContext.run_id.slice(0, 8)}...`);
    if (pageContext.company_id) parts.push(`Company: ${pageContext.company_id.slice(0, 8)}...`);
    return parts;
  })();

  const hasMessages = messages.length > 0 || streamingContent;

  return (
    <>
      {/* Floating Action Button */}
      <button
        className="copilot-fab"
        onClick={() => setIsOpen(!isOpen)}
        title="Co-pilot Assistant"
      >
        {isOpen ? '\u2715' : '\u2728'}
      </button>

      {/* Slide-out Panel */}
      <div className={`copilot-panel ${isOpen ? 'open' : ''}`}>
        {/* Header */}
        <div className="copilot-header">
          <div className="copilot-header-left">
            <div className="copilot-header-title">Co-pilot</div>
            <button
              className="copilot-header-btn"
              onClick={() => setShowSessionList(!showSessionList)}
              title="Chat history"
            >
              {'\u{1F4AC}'}
            </button>
          </div>
          <div className="copilot-header-right">
            <button className="copilot-header-btn" onClick={startNewChat} title="New chat">
              +
            </button>
            <button className="copilot-header-btn" onClick={() => setIsOpen(false)} title="Close">
              {'\u2715'}
            </button>
          </div>
        </div>

        {/* Session List Dropdown */}
        {showSessionList && (
          <div className="copilot-session-list">
            {sessions.length === 0 ? (
              <div className="copilot-session-empty">No previous chats</div>
            ) : (
              sessions.map((s) => (
                <div
                  key={s.id}
                  className={`copilot-session-item ${s.id === currentSessionId ? 'active' : ''}`}
                  onClick={() => loadSession(s.id)}
                >
                  <div className="copilot-session-title">{s.title || 'Untitled'}</div>
                  <div className="copilot-session-meta">
                    {s.message_count} messages
                    <button
                      className="copilot-session-delete"
                      onClick={(e) => handleDeleteSession(s.id, e)}
                      title="Delete"
                    >
                      {'\u2715'}
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* Context Chips */}
        {contextChipText.length > 0 && (
          <div className="copilot-context-chips">
            {contextChipText.map((text, i) => (
              <span key={i} className="copilot-context-chip">{text}</span>
            ))}
          </div>
        )}

        {/* Messages Area */}
        <div className="copilot-messages">
          {!hasMessages && (
            <div className="copilot-welcome">
              <div className="copilot-welcome-icon">{'\u2728'}</div>
              <div className="copilot-welcome-title">qlGen Co-pilot</div>
              <div className="copilot-welcome-sub">
                Ask me about your leads, companies, or get AI-powered research.
              </div>
            </div>
          )}

          {!hasMessages && (
            <CoPilotRecommendations
              recommendations={recommendations}
              onSelect={(prompt) => sendMessage(prompt)}
            />
          )}

          {messages.map((msg) => (
            <CoPilotMessageBubble key={msg.id} role={msg.role} content={msg.content} />
          ))}

          {/* Active tool indicators */}
          {activeTools.length > 0 && (
            <div className="copilot-tool-indicators">
              {activeTools.map((tool, i) => (
                <span key={i} className="copilot-tool-indicator">
                  <span className="spinner" style={{ width: 10, height: 10, borderWidth: 1.5 }} /> {tool}
                </span>
              ))}
            </div>
          )}

          {/* Streaming message */}
          {streamingContent && (
            <CoPilotMessageBubble role="assistant" content={streamingContent} isStreaming />
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="copilot-input-area">
          <textarea
            ref={inputRef}
            className="copilot-input"
            placeholder="Ask about your leads..."
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isStreaming}
            rows={1}
          />
          <button
            className="copilot-send-btn"
            onClick={() => sendMessage(inputValue)}
            disabled={isStreaming || !inputValue.trim()}
          >
            {isStreaming ? (
              <span className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} />
            ) : (
              '\u2191'
            )}
          </button>
        </div>
      </div>
    </>
  );
};

export default CoPilotPanel;
