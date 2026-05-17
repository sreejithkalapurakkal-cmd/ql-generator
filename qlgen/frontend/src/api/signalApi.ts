import client, { API_BASE } from './client';
import { getAccessToken } from '../context/AuthContext';
import { SignalEvent } from '../types';

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
  limit?: number;
  offset?: number;
}) => client.get<SignalFeedResponse>('/signals/feed', { params });

export const dismissSignal = (signalId: string) =>
  client.post(`/signals/${signalId}/dismiss`);

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
