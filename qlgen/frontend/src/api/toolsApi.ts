import client from './client';
import { ToolRegistryItem, ToolMetricsSummary, ToolHealthCheckResult } from '../types';

export const listTools = () =>
  client.get<ToolRegistryItem[]>('/tools');

export const getToolsSummary = () =>
  client.get<ToolMetricsSummary>('/tools/summary');

export const updateTool = (id: string, data: { is_enabled?: boolean; notes?: string }) =>
  client.patch<ToolRegistryItem>(`/tools/${id}`, data);

export const checkToolHealth = (id: string) =>
  client.post<ToolHealthCheckResult>(`/tools/${id}/health-check`);

export const checkAllToolsHealth = () =>
  client.post<ToolHealthCheckResult[]>('/tools/health-check-all');

export const deleteTool = (id: string) =>
  client.delete(`/tools/${id}`);
