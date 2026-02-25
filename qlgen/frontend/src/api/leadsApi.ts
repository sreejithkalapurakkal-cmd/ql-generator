import client, { API_BASE } from './client';
import { Company } from '../types';

export const getLeadCompanies = (runId: string, params?: {
  min_bant_score?: number;
  industry_filter?: string;
  sort_by?: string;
}) => client.get<Company[]>(`/leads/${runId}/companies`, { params });

export const getExportUrl = (runId: string, format: 'xlsx' | 'csv' = 'xlsx') =>
  `${API_BASE}/leads/${runId}/export?format=${format}`;
