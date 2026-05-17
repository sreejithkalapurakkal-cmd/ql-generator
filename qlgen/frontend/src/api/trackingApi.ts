import client, { API_BASE } from './client';
import { getAccessToken } from '../context/AuthContext';
import { TrackingList, TrackingListMember, SignalHints, EnrichedContact } from '../types';

// ── List CRUD ──

export const createTrackingList = (data: { name: string; description?: string; signal_hints?: SignalHints }) =>
  client.post<TrackingList>('/tracking/lists', data);

export const getTrackingLists = () =>
  client.get<{ lists: TrackingList[] }>('/tracking/lists');

export const getTrackingList = (listId: string) =>
  client.get<TrackingList>(`/tracking/lists/${listId}`);

export const updateTrackingList = (listId: string, data: {
  name?: string;
  description?: string;
  monitoring_config?: Record<string, unknown>;
  signal_hints?: SignalHints;
}) => client.put<TrackingList>(`/tracking/lists/${listId}`, data);

export const deleteTrackingList = (listId: string) =>
  client.delete(`/tracking/lists/${listId}`);

// ── Members ──

export interface GetMembersParams {
  outreach_status?: string;
  search?: string;
  industry_filter?: string;
  sort_by?: string;
  sort_order?: string;
  limit?: number;
  offset?: number;
}

export interface MembersResponse {
  members: TrackingListMember[];
  total: number;
  offset: number;
  limit: number;
}

export const getListMembers = (listId: string, params?: GetMembersParams) =>
  client.get<MembersResponse>(`/tracking/lists/${listId}/members`, { params });

export const addListMembers = (listId: string, data: {
  company_kb_ids: string[];
  added_from?: string;
}) => client.post<{ added: number; membership_ids: string[] }>(
  `/tracking/lists/${listId}/members`, data,
);

export const promoteFromPipeline = (listId: string, companyIds: string[]) =>
  client.post<{ promoted: number; kb_records_created_or_updated: number; membership_ids: string[] }>(
    `/tracking/lists/${listId}/promote-from-pipeline`,
    { company_ids: companyIds },
  );

export const removeListMembers = (listId: string, membershipIds: string[]) =>
  client.delete<{ removed: number }>(`/tracking/lists/${listId}/members`, {
    data: { membership_ids: membershipIds },
  });

export const updateMember = (listId: string, membershipId: string, data: {
  outreach_status?: string;
  notes?: string;
  tags?: string[];
  snoozed_until?: string;
}) => client.patch(`/tracking/lists/${listId}/members/${membershipId}`, data);

// ── Outreach summary (for Kanban) ──

export const getOutreachSummary = (listId: string) =>
  client.get<{ summary: Record<string, number> }>(`/tracking/lists/${listId}/outreach-summary`);

// ── Enrichment ──

export interface EnrichResponse {
  list_id: string;
  companies_processed: number;
  companies_enriched: number;
  total_contacts_found: number;
  results: { company_kb_id: string; status: string; contacts_found?: number; total_contacts?: number }[];
}

export interface EnrichSingleResponse {
  company_kb_id: string;
  company_name: string;
  contacts_found: number;
  total_contacts: number;
  contacts: EnrichedContact[];
}

export interface MemberContactsResponse {
  company_kb_id: string;
  company_name: string;
  enrichment_status: string;
  contacts: EnrichedContact[];
  total: number;
  last_enriched_at: string | null;
}

export const enrichList = (listId: string, data?: {
  target_roles?: string[];
  max_companies?: number;
}) => client.post<EnrichResponse>(`/tracking/lists/${listId}/enrich`, data || {});

export const enrichMember = (listId: string, membershipId: string, data?: {
  target_roles?: string[];
}) => client.post<EnrichSingleResponse>(
  `/tracking/lists/${listId}/members/${membershipId}/enrich`, data || {},
);

export const getMemberContacts = (listId: string, membershipId: string) =>
  client.get<MemberContactsResponse>(
    `/tracking/lists/${listId}/members/${membershipId}/contacts`,
  );

// ── Signal detection (background task) ──

export interface DetectSignalsForListResponse {
  run_id: string;
  status: string;
  total_companies: number;
}

export interface SignalDetectionRunResponse {
  run_id: string;
  status: string;
  total_companies: number;
  processed_companies: number;
  signals_detected: number;
  use_agent: boolean;
  started_at: string | null;
  completed_at: string | null;
  created_at: string | null;
}

export const detectSignalsForList = (listId: string, companyKbIds?: string[]) =>
  client.post<DetectSignalsForListResponse>(
    `/tracking/lists/${listId}/detect-signals`,
    companyKbIds?.length ? { company_kb_ids: companyKbIds } : {},
  );

export const getSignalDetectionRun = (listId: string, runId: string) =>
  client.get<SignalDetectionRunResponse>(`/tracking/lists/${listId}/signal-detection/${runId}`);

export const getLatestSignalDetection = (listId: string) =>
  client.get<{ run: SignalDetectionRunResponse | null }>(`/tracking/lists/${listId}/signal-detection/latest`);

export const cancelSignalDetection = (listId: string, runId: string) =>
  client.post(`/tracking/lists/${listId}/signal-detection/${runId}/cancel`);

export const getSignalDetectionStreamUrl = (listId: string, runId: string) => {
  const token = getAccessToken() || '';
  return `${API_BASE}/tracking/lists/${listId}/signal-detection/${runId}/stream?token=${token}`;
};

export interface SignalDetectionLogEntry {
  event_type: string;
  event_data: Record<string, unknown>;
  sequence_number: number;
  created_at: string | null;
}

export const getSignalDetectionLogs = (listId: string, runId: string) =>
  client.get<SignalDetectionLogEntry[]>(
    `/tracking/lists/${listId}/signal-detection/${runId}/logs`,
  );

// ── Async Enrichment ──

export interface EnrichAsyncResponse {
  run_id: string;
  status: string;
  total_companies: number;
}

export interface EnrichmentRunResponse {
  run_id: string;
  status: string;
  total_companies: number;
  processed_companies: number;
  contacts_found: number;
  started_at: string | null;
  completed_at: string | null;
}

export interface EnrichmentLogEntry {
  event_type: string;
  event_data: Record<string, unknown>;
  sequence_number: number;
  created_at: string | null;
}

export const enrichListAsync = (listId: string, data?: {
  target_roles?: string[];
  max_companies?: number;
}) => client.post<EnrichAsyncResponse>(
  `/tracking/lists/${listId}/enrich-async`, data || {},
);

export const getLatestEnrichment = (listId: string) =>
  client.get<{ run: EnrichmentRunResponse | null }>(
    `/tracking/lists/${listId}/enrichment/latest`,
  );

export const getEnrichmentRun = (listId: string, runId: string) =>
  client.get<EnrichmentRunResponse>(
    `/tracking/lists/${listId}/enrichment/${runId}`,
  );

export const getEnrichmentLogs = (listId: string, runId: string) =>
  client.get<EnrichmentLogEntry[]>(
    `/tracking/lists/${listId}/enrichment/${runId}/logs`,
  );

export const cancelEnrichment = (listId: string, runId: string) =>
  client.post(`/tracking/lists/${listId}/enrichment/${runId}/cancel`);

export const getEnrichmentStreamUrl = (listId: string, runId: string) => {
  const token = getAccessToken() || '';
  return `${API_BASE}/tracking/lists/${listId}/enrichment/${runId}/stream?token=${token}`;
};
