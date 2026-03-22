import client from './client';
import type { AuthUser } from './authApi';
import { AuditLogEntry } from '../types';

export const listUsers = () =>
  client.get<AuthUser[]>('/users');

export const inviteUser = (email: string, role: string = 'user') =>
  client.post<AuthUser>('/users', { email, role });

export const updateUser = (userId: string, data: { role?: string; is_active?: boolean; name?: string }) =>
  client.put<AuthUser>(`/users/${userId}`, data);

export const deleteUser = (userId: string) =>
  client.delete(`/users/${userId}`);

export const getAuditLogs = (params?: { resource_type?: string; user_id?: string; limit?: number }) =>
  client.get<AuditLogEntry[]>('/admin/audit-logs', { params });
