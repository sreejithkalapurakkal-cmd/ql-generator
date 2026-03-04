import client from './client';
import { ICPConfig } from '../types';

export const createICP = (data: { name: string; description?: string; config: Record<string, unknown> }) =>
  client.post<ICPConfig>('/icp', data);

export const listICPs = () => client.get<ICPConfig[]>('/icp');

export const getICP = (id: string) => client.get<ICPConfig>(`/icp/${id}`);

export const updateICP = (id: string, data: Partial<{ name: string; description: string; config: Record<string, unknown> }>) =>
  client.put<ICPConfig>(`/icp/${id}`, data);

export const deleteICP = (id: string) => client.delete(`/icp/${id}`);

export const getICPTemplateURL = () => {
  const base = client.defaults.baseURL || '/api/v1';
  return `${base}/icp/template/download`;
};

export interface ParsedICP {
  name: string;
  description: string;
  config: Record<string, unknown>;
  warnings: string[];
}

export const parseICPUpload = (file: File) => {
  const formData = new FormData();
  formData.append('file', file);
  return client.post<ParsedICP[]>('/icp/import/parse', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};
