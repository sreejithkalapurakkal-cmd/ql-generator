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

export interface EvabootStatus {
  configured: boolean;
  quota: {
    credits?: number;
    daily_limit?: number;
    used_today?: number;
    remaining?: number;
    error?: string;
  } | null;
  sales_nav_sessions: { id: string; status: string }[];
  my_credits_used: number;
  my_run_count: number;
  total_credits_used: number;
  recent_runs: {
    id: string;
    user_name: string;
    discovery_mode: string;
    credits_used: number;
    companies_found: number;
    started_at: string | null;
  }[];
}

export const getEvabootStatus = () =>
  client.get<EvabootStatus>('/tools/evaboot/status');
