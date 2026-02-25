import client from './client';
import { ICPConfig } from '../types';

export const createICP = (data: { name: string; description?: string; config: Record<string, unknown> }) =>
  client.post<ICPConfig>('/icp', data);

export const listICPs = () => client.get<ICPConfig[]>('/icp');

export const getICP = (id: string) => client.get<ICPConfig>(`/icp/${id}`);

export const updateICP = (id: string, data: Partial<{ name: string; description: string; config: Record<string, unknown> }>) =>
  client.put<ICPConfig>(`/icp/${id}`, data);

export const deleteICP = (id: string) => client.delete(`/icp/${id}`);
