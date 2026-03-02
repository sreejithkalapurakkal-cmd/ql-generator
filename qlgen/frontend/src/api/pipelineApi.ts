import client from './client';
import { PipelineRun, PipelineLogEntry } from '../types';

export const startPipeline = (data: {
  icp_config_id: string;
  options?: { max_companies?: number; max_contacts_per_company?: number };
}) => client.post<PipelineRun>('/pipeline/run', data);

export const getPipelineStatus = (runId: string) =>
  client.get<PipelineRun>(`/pipeline/${runId}`);

export const listPipelineRuns = () =>
  client.get<PipelineRun[]>('/pipeline/history/list');

export const getPipelineLogs = (runId: string) =>
  client.get<PipelineLogEntry[]>(`/pipeline/${runId}/logs`);

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
