import client, { API_BASE } from './client';
import { getAccessToken } from '../context/AuthContext';
import { Company, StageSummaryResponse, ToolAttributionResponse } from '../types';

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

export const getExportUrl = (runId: string, format: 'xlsx' | 'csv' = 'xlsx', scope: 'all' | 'final' = 'all') => {
  const token = getAccessToken();
  return `${API_BASE}/leads/${runId}/export?format=${format}&scope=${scope}&token=${token}`;
};

export const getToolAttribution = (runId: string) =>
  client.get<ToolAttributionResponse>(`/leads/${runId}/tool-attribution`);
