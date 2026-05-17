import client from './client';
import { Notification } from '../types';

export interface NotificationsResponse {
  notifications: Notification[];
  total: number;
}

export const getUnreadCount = () =>
  client.get<{ unread_count: number }>('/notifications/unread-count');

export const getNotifications = (params?: {
  unread_only?: boolean;
  limit?: number;
  offset?: number;
}) => client.get<NotificationsResponse>('/notifications', { params });

export const markRead = (notificationIds: string[]) =>
  client.post('/notifications/mark-read', { notification_ids: notificationIds });

export const markAllRead = () =>
  client.post('/notifications/mark-all-read');
