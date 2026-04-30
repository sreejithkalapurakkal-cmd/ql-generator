import client from './client';
import { PipelineRun, PipelineLogEntry } from '../types';

export const startPipeline = (data: {
  icp_config_id: string;
  options?: { max_companies?: number; max_contacts_per_company?: number };
  discovery_mode?: 'qlgen_only' | 'sales_navigator_only' | 'sales_navigator_plus_qlgen';
  sales_navigator_url?: string;
  expected_result_count?: number;
}) => client.post<PipelineRun>('/pipeline/run', data);

export const getPipelineStatus = (runId: string) =>
  client.get<PipelineRun>(`/pipeline/${runId}`);

export const listPipelineRuns = () =>
  client.get<PipelineRun[]>('/pipeline/history/list');

export const getPipelineLogs = (runId: string) =>
  client.get<PipelineLogEntry[]>(`/pipeline/${runId}/logs`);

export const deletePipelineRun = (runId: string) =>
  client.delete(`/pipeline/${runId}`);

export const cancelPipeline = (runId: string) =>
  client.post(`/pipeline/${runId}/cancel`);

// Stage 2 review: promote companies with signal mode selection
export const promoteFirmographic = (runId: string, companyIds: string[], signalMode: string) =>
  client.post<PipelineRun>(`/pipeline/${runId}/promote-firmographic`, {
    company_ids: companyIds,
    signal_mode: signalMode,
  });

// Serial mode: promote after 1st signal review
export const promoteFirstSignal = (runId: string, companyIds: string[]) =>
  client.post<PipelineRun>(`/pipeline/${runId}/promote-first-signal`, {
    company_ids: companyIds,
  });

// Final signal review: promote to contact discovery
export const promoteSignals = (runId: string, companyIds: string[]) =>
  client.post<PipelineRun>(`/pipeline/${runId}/promote-signals`, {
    company_ids: companyIds,
  });

// Get companies filtered by stage
export const getCompaniesByStage = (runId: string, stage?: string) =>
  client.get<unknown[]>(`/pipeline/${runId}/companies-by-stage`, {
    params: stage ? { stage } : {},
  });

export interface ICPStat {
  icp_id: string;
  icp_name: string;
  run_count: number;
  total_companies: number;
  total_contacts: number;
  runs: Array<{
    id: string;
    status: string;
    companies_found: number;
    contacts_found: number;
    started_at: string | null;
    completed_at: string | null;
  }>;
}

export const getPipelineStatsByICP = () =>
  client.get<ICPStat[]>('/pipeline/stats/by-icp');

import { AdminActivityResponse } from '../types';

export const getAdminActivity = () =>
  client.get<AdminActivityResponse>('/admin/activity');
