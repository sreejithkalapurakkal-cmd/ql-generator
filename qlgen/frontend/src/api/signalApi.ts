import client, { API_BASE } from './client';
import { getAccessToken } from '../context/AuthContext';
import { SignalEvent, SignalFeedTab } from '../types';

export interface DetectSignalsResponse {
  company_kb_id: string;
  signals_detected: number;
  signal_heat_score: number;
  signals: {
    id: string;
    signal_type: string;
    priority: string;
    strength: number;
    title: string;
    summary: string | null;
    source_url: string | null;
  }[];
}

export interface CompanySignalsResponse {
  company_kb_id: string;
  count: number;
  signals: SignalEvent[];
}

export interface SignalFeedResponse {
  signals: (SignalEvent & { company_name: string | null; domain: string | null })[];
  total: number;
  offset: number;
  limit: number;
  snoozed_returned_count: number;
}

export interface DashboardSignalStats {
  total_active: number;
  this_week: number;
  saved_count: number;
  snoozed_count: number;
  correlations_this_week?: number;
  active_rules_count?: number;
  top_signals: {
    id: string;
    company_kb_id: string;
    company_name: string | null;
    domain: string | null;
    signal_type: string;
    priority: string;
    title: string;
    summary: string | null;
    source_url: string | null;
    detected_at: string | null;
    evidence_date: string | null;
  }[];
  by_type: Record<string, number>;
}

export const detectSignals = (companyKbId: string, signalTypes?: string[], signalHints?: Record<string, string[]>) =>
  client.post<DetectSignalsResponse>(`/signals/detect/${companyKbId}`, {
    signal_types: signalTypes || undefined,
    signal_hints: signalHints || undefined,
  });

export const getCompanySignals = (companyKbId: string, params?: {
  limit?: number;
  include_archived?: boolean;
}) => client.get<CompanySignalsResponse>(`/signals/company/${companyKbId}`, { params });

export const getSignalFeed = (params?: {
  signal_type?: string;
  priority?: string;
  tab?: SignalFeedTab;
  limit?: number;
  offset?: number;
}) => client.get<SignalFeedResponse>('/signals/feed', { params });

export const dismissSignal = (signalId: string) =>
  client.post(`/signals/${signalId}/dismiss`);

export const saveSignal = (signalId: string) =>
  client.post(`/signals/${signalId}/save`);

export const unsaveSignal = (signalId: string) =>
  client.delete(`/signals/${signalId}/save`);

export const snoozeSignal = (signalId: string, durationHours: number = 24) =>
  client.post(`/signals/${signalId}/snooze`, { duration_hours: durationHours });

export const getDashboardSignalStats = () =>
  client.get<DashboardSignalStats>('/signals/dashboard-stats');

export const archiveExpired = () =>
  client.post('/signals/archive-expired');

// Streaming signal detection (SSE)

export interface StartDetectResponse {
  run_id: string;
  status: string;
}

export const startDetectSignals = (companyKbId: string, signalTypes?: string[], signalHints?: Record<string, string[]>) =>
  client.post<StartDetectResponse>(`/signals/detect/${companyKbId}/start`, {
    signal_types: signalTypes || undefined,
    signal_hints: signalHints || undefined,
  });

export const getSignalDetectionStreamUrl = (companyKbId: string, runId: string) => {
  const token = getAccessToken() || '';
  return `${API_BASE}/signals/detect/${companyKbId}/stream/${runId}?token=${token}`;
};

// ─── Account Profile APIs ──────────────────────────────────────────────────

export const getAccountDetail = (id: string) => client.get(`/accounts/${id}`);

export const updateAccount = (id: string, data: any) => client.patch(`/accounts/${id}`, data);

export const getCompanyDrafts = (companyKbId: string) => client.get(`/briefs/drafts/${companyKbId}`);

export const markSignalActedOn = (signalId: string) => client.post(`/signals/${signalId}/acted-on`);
