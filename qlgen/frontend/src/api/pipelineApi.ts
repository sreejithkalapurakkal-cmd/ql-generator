import client from './client';
import { PipelineRun, PipelineLogEntry } from '../types';

export const startPipeline = (data: {
  icp_config_id: string;
  options?: { max_companies?: number; max_contacts_per_company?: number; pipeline_mode?: string; match_strictness?: 'strict' | 'moderate' | 'relaxed'; bant_weights?: { budget: number; authority: number; need: number; timing: number } };
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

export const promoteCompanies = (runId: string, companyIds: string[]) =>
  client.post<PipelineRun>(`/pipeline/${runId}/promote`, { company_ids: companyIds });

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
