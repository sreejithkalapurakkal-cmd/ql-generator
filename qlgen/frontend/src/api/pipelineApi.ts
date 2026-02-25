import client from './client';
import { PipelineRun } from '../types';

export const startPipeline = (data: {
  icp_config_id: string;
  options?: { max_companies?: number; max_contacts_per_company?: number };
}) => client.post<PipelineRun>('/pipeline/run', data);

export const getPipelineStatus = (runId: string) =>
  client.get<PipelineRun>(`/pipeline/${runId}`);

export const listPipelineRuns = () =>
  client.get<PipelineRun[]>('/pipeline/history/list');
