import client, { API_BASE } from './client';
import { getAccessToken } from '../context/AuthContext';
import type { FirmographicFilter, IngestBatchStatus, IngestBatchLogEntry } from '../types';

export interface UploadResponse {
  batch_id: string;
  filename: string;
  file_type: string;
  total_rows: number;
  headers: string[];
  column_mapping: Record<string, string>;
  preview_rows: Record<string, string>[];
}

export interface PasteResponse {
  batch_id: string;
  file_type: string;
  total_rows: number;
  headers: string[];
  column_mapping: Record<string, string>;
  preview_rows: Record<string, string>[];
}

export const uploadFile = (file: File, name?: string, targetListId?: string) => {
  const formData = new FormData();
  formData.append('file', file);
  if (name) formData.append('name', name);
  if (targetListId) formData.append('target_tracking_list_id', targetListId);
  return client.post<UploadResponse>('/ingest/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};

export const pasteText = (text: string, name?: string, targetListId?: string) =>
  client.post<PasteResponse>('/ingest/paste', {
    text,
    name: name || undefined,
    target_tracking_list_id: targetListId || undefined,
  });

export const confirmIngest = (
  batchId: string,
  columnMapping: Record<string, string>,
  targetListId?: string,
  filterConfig?: FirmographicFilter,
) =>
  client.post('/ingest/confirm', {
    batch_id: batchId,
    column_mapping: columnMapping,
    target_tracking_list_id: targetListId || undefined,
    filter_config: filterConfig || undefined,
  });

export interface IngestBatchSummary {
  batch_id: string;
  name: string;
  status: string;
  total_rows: number;
  has_filter: boolean;
  evaluation_status: string;
  enriched_count: number | null;
  created_at: string | null;
  target_tracking_list_id: string | null;
}

export const listBatches = (trackingListId?: string, hasFilter?: boolean, limit?: number) => {
  const params = new URLSearchParams();
  if (trackingListId) params.set('tracking_list_id', trackingListId);
  if (hasFilter !== undefined) params.set('has_filter', String(hasFilter));
  if (limit) params.set('limit', String(limit));
  return client.get<IngestBatchSummary[]>(`/ingest/batches?${params.toString()}`);
};

export const getBatchStatus = (batchId: string) =>
  client.get<IngestBatchStatus>(`/ingest/batch/${batchId}`);

export const dismissBatch = (batchId: string) =>
  client.post<{ status: string; batch_id: string }>(`/ingest/batch/${batchId}/dismiss`);

export const getIngestBatchLogs = (batchId: string) =>
  client.get<IngestBatchLogEntry[]>(`/ingest/${batchId}/logs`);

export const getIngestStreamUrl = (batchId: string) => {
  const token = getAccessToken();
  return `${API_BASE}/ingest/stream/${batchId}?token=${token}`;
};

export const addSelectedCompanies = (
  batchId: string,
  companyKbIds: string[],
  targetTrackingListId: string,
) =>
  client.post<{ added: number; batch_id: string }>(
    `/ingest/${batchId}/add-selected`,
    { company_kb_ids: companyKbIds, target_tracking_list_id: targetTrackingListId },
  );
