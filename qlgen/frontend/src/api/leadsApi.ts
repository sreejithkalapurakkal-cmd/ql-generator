import client, { API_BASE } from './client';
import { Company, StageSummaryResponse } from '../types';

export const getLeadCompanies = (runId: string, params?: {
  min_final_score?: number;
  industry_filter?: string;
  stage_filter?: string;
  sort_by?: string;
}) => client.get<Company[]>(`/leads/${runId}/companies`, { params });

export const getDisqualifiedCompanies = (runId: string) =>
  client.get<Company[]>(`/leads/${runId}/disqualified`);

export const getStageSummary = (runId: string) =>
  client.get<StageSummaryResponse>(`/leads/${runId}/stage-summary`);

export const getExportUrl = (runId: string, format: 'xlsx' | 'csv' = 'xlsx') =>
  `${API_BASE}/leads/${runId}/export?format=${format}`;
