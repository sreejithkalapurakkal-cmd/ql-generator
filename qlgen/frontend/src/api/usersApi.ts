import client from './client';
import type { AuthUser } from './authApi';

export const listUsers = () =>
  client.get<AuthUser[]>('/users');

export const inviteUser = (email: string, role: string = 'user') =>
  client.post<AuthUser>('/users', { email, role });

export const updateUser = (userId: string, data: { role?: string; is_active?: boolean; name?: string }) =>
  client.put<AuthUser>(`/users/${userId}`, data);

export const deleteUser = (userId: string) =>
  client.delete(`/users/${userId}`);
