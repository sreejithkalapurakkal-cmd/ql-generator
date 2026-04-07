import client from './client';
import type { FeedbackItem, FeedbackListItem, FeedbackReplyItem, FeedbackType, FeedbackStatus } from '../types';

export function createFeedback(data: { type: FeedbackType; subject: string; description: string }) {
  return client.post<FeedbackItem>('/feedback', data);
}

export function listFeedback(params?: {
  type_filter?: FeedbackType;
  status_filter?: FeedbackStatus;
  limit?: number;
  offset?: number;
}) {
  return client.get<FeedbackListItem[]>('/feedback', { params });
}

export function getFeedback(id: string) {
  return client.get<FeedbackItem>(`/feedback/${id}`);
}

export function updateFeedbackStatus(id: string, status: FeedbackStatus) {
  return client.put<FeedbackItem>(`/feedback/${id}/status`, { status });
}

export function replyToFeedback(id: string, message: string) {
  return client.post<FeedbackReplyItem>(`/feedback/${id}/reply`, { message });
}
