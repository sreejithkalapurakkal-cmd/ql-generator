import client, { API_BASE } from './client';
import type { ChatSession, ChatMessage, PageContext, RecommendationItem } from '../types';

export function listChatSessions() {
  return client.get<ChatSession[]>('/chat/sessions');
}

export function getSessionMessages(sessionId: string) {
  return client.get<ChatMessage[]>(`/chat/sessions/${sessionId}/messages`);
}

export function deleteChatSession(sessionId: string) {
  return client.delete(`/chat/sessions/${sessionId}`);
}

export function getRecommendations(pageContext?: PageContext) {
  return client.post<{ recommendations: RecommendationItem[] }>('/chat/recommendations', {
    page_context: pageContext || null,
  });
}

export interface StreamCallbacks {
  onSession?: (sessionId: string) => void;
  onTextDelta?: (content: string) => void;
  onToolUse?: (toolName: string, displayName: string) => void;
  onToolResult?: (toolName: string, success: boolean) => void;
  onDone?: (sessionId: string) => void;
  onError?: (message: string) => void;
}

export async function sendChatMessageStream(
  message: string,
  sessionId: string | null,
  pageContext: PageContext | null,
  callbacks: StreamCallbacks,
) {
  const body = {
    message,
    session_id: sessionId || undefined,
    page_context: pageContext || undefined,
  };

  try {
    const response = await fetch(`${API_BASE}/chat/send`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      callbacks.onError?.(`HTTP error ${response.status}`);
      return;
    }

    const reader = response.body?.getReader();
    if (!reader) {
      callbacks.onError?.('No response stream');
      return;
    }

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Parse SSE events from buffer
      const lines = buffer.split('\n');
      buffer = lines.pop() || ''; // Keep incomplete last line in buffer

      let eventType = '';
      let eventData = '';

      for (const line of lines) {
        if (line.startsWith('event: ')) {
          eventType = line.slice(7).trim();
        } else if (line.startsWith('data: ')) {
          eventData = line.slice(6);
        } else if (line === '' && eventType && eventData) {
          // Complete event
          try {
            const data = JSON.parse(eventData);
            switch (eventType) {
              case 'session':
                callbacks.onSession?.(data.session_id);
                break;
              case 'text_delta':
                callbacks.onTextDelta?.(data.content);
                break;
              case 'tool_use':
                callbacks.onToolUse?.(data.tool_name, data.display_name);
                break;
              case 'tool_result':
                callbacks.onToolResult?.(data.tool_name, data.success);
                break;
              case 'done':
                callbacks.onDone?.(data.session_id);
                break;
              case 'error':
                callbacks.onError?.(data.message);
                break;
            }
          } catch {
            // Skip malformed JSON
          }
          eventType = '';
          eventData = '';
        }
      }
    }
  } catch (err) {
    callbacks.onError?.(err instanceof Error ? err.message : 'Stream failed');
  }
}
