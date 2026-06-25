import client, { API_BASE } from './client';
import { getAccessToken } from '../context/AuthContext';
import type { BriefRevision, OutreachDraft } from '../types';

// ─── Brief Response Types ───────────────────────────────────────────────────

export interface StructuredBriefResponse {
  company_kb_id: string;
  brief: BriefRevision | null;
}

export interface BriefVersionsResponse {
  company_kb_id: string;
  revisions: BriefRevision[];
}

export interface BriefResponse {
  company_kb_id: string;
  brief: string;
}

export interface DraftGenerateResponse {
  id: string;
  company_kb_id: string;
  format: string;
  tone: string;
  subject: string | null;
  body: string;
  status: string;
  created_at: string | null;
  raw_markdown: string;
}

export interface DraftListResponse {
  company_kb_id: string;
  drafts: OutreachDraft[];
}

export interface DraftUpdateResponse {
  id: string;
  status: string;
  updated_at: string | null;
}

export interface OutreachDraftResponse {
  company_kb_id: string;
  draft: string;
}

export interface ResearchResponse {
  company_kb_id: string;
  company_name: string;
  fields_updated: string[];
  updated_data: Record<string, unknown>;
  current_data: {
    domain: string | null;
    industry: string | null;
    sub_industry: string | null;
    country: string | null;
    city: string | null;
    state_region: string | null;
    employee_count: number | null;
    revenue_estimate: number | null;
    description: string | null;
    tech_stack: string[] | null;
  };
}

// ─── Structured Brief APIs ──────────────────────────────────────────────────

/** Get the latest research brief for a company */
export const getLatestBrief = (companyKbId: string) =>
  client.get<StructuredBriefResponse>(`/briefs/${companyKbId}`);

/** List all brief versions for a company */
export const getBriefVersions = (companyKbId: string) =>
  client.get<BriefVersionsResponse>(`/briefs/${companyKbId}/versions`);

/** Get a specific brief version */
export const getBriefVersion = (companyKbId: string, version: number) =>
  client.get<StructuredBriefResponse>(`/briefs/${companyKbId}/versions/${version}`);

/** Generate a new structured research brief */
export const generateStructuredBrief = (companyKbId: string, triggerSignalId?: string) =>
  client.post<StructuredBriefResponse>(`/briefs/${companyKbId}/generate`, {
    trigger_signal_id: triggerSignalId || null,
  });

// ─── Legacy Brief API ───────────────────────────────────────────────────────

export const generateBrief = (companyKbId: string) =>
  client.post<BriefResponse>(`/briefs/generate/${companyKbId}`);

// ─── Outreach Draft APIs ────────────────────────────────────────────────────

/** Generate and persist an outreach draft */
export const generateDraft = (companyKbId: string, data?: {
  contact_name?: string;
  contact_title?: string;
  context?: string;
  format?: string;
  tone?: string;
  signal_id?: string;
}) => client.post<DraftGenerateResponse>(`/briefs/outreach/${companyKbId}`, data || {});

/** List all drafts for a company */
export const getCompanyDrafts = (companyKbId: string) =>
  client.get<DraftListResponse>(`/briefs/drafts/${companyKbId}`);

/** List recent drafts across all companies (for dashboard) */
export interface RecentDraft {
  id: string;
  company_kb_id: string;
  company_name: string | null;
  domain: string | null;
  signal_id: string | null;
  contact_name: string | null;
  format: string;
  tone: string;
  subject: string | null;
  body: string | null;
  status: string;
  created_at: string | null;
}

export interface RecentDraftsResponse {
  drafts: RecentDraft[];
  total: number;
}

export const getRecentDrafts = (params?: { limit?: number; status?: string }) =>
  client.get<RecentDraftsResponse>('/briefs/drafts/recent', { params });

/** Update a draft (status, content) */
export const updateDraft = (draftId: string, data: {
  subject?: string;
  body?: string;
  status?: string;
}) => client.patch<DraftUpdateResponse>(`/briefs/drafts/${draftId}`, data);

export const generateOutreachDraft = (companyKbId: string, data?: {
  contact_name?: string;
  context?: string;
}) => client.post<OutreachDraftResponse>(`/briefs/outreach/${companyKbId}`, data || {});

// ─── Export APIs ────────────────────────────────────────────────────────────

/** Get brief as print-ready HTML (open in new tab, browser print to PDF) */
export const getBriefExportUrl = (companyKbId: string, version?: number) => {
  const base = `/briefs/${companyKbId}/export/html`;
  return version ? `${base}?version=${version}` : base;
};

/** Get signal report as XLSX download */
export const getSignalReportExportUrl = (companyKbId: string) =>
  `/briefs/${companyKbId}/export/signals`;

// ─── Company Research ───────────────────────────────────────────────────────

export const researchCompany = (companyKbId: string) =>
  client.post<ResearchResponse>(`/briefs/research/${companyKbId}`);

// ─── Async Streaming APIs (SSE) ────────────────────────────────────────────

export interface StartStreamResponse {
  run_id: string;
  status: string;
  company_kb_id: string;
}

/** Start async brief generation → returns run_id for SSE */
export const startBriefGeneration = (companyKbId: string, triggerSignalId?: string) =>
  client.post<StartStreamResponse>(`/briefs/${companyKbId}/generate/start`, {
    trigger_signal_id: triggerSignalId || null,
  });

/** Get SSE stream URL for brief generation progress */
export const getBriefGenerationStreamUrl = (companyKbId: string, runId: string) => {
  const token = getAccessToken() || '';
  return `${API_BASE}/briefs/${companyKbId}/generate/stream/${runId}?token=${token}`;
};

/** Start async outreach draft generation → returns run_id for SSE */
export const startOutreachGeneration = (companyKbId: string, data?: {
  contact_name?: string;
  contact_title?: string;
  context?: string;
  format?: string;
  tone?: string;
  signal_id?: string;
}) => client.post<StartStreamResponse>(`/briefs/outreach/${companyKbId}/start`, data || {});

/** Get SSE stream URL for outreach draft generation */
export const getOutreachStreamUrl = (companyKbId: string, runId: string) => {
  const token = getAccessToken() || '';
  return `${API_BASE}/briefs/outreach/${companyKbId}/stream/${runId}?token=${token}`;
};

/** Start async company research → returns run_id for SSE */
export const startCompanyResearch = (companyKbId: string) =>
  client.post<StartStreamResponse>(`/briefs/research/${companyKbId}/start`);

/** Get SSE stream URL for company research progress */
export const getResearchStreamUrl = (companyKbId: string, runId: string) => {
  const token = getAccessToken() || '';
  return `${API_BASE}/briefs/research/${companyKbId}/stream/${runId}?token=${token}`;
};

// ─── Contact Enrichment Streaming ──────────────────────────────────────────

export interface ContactEnrichStartResponse {
  status: string;
  run_id: string;
  company_kb_id: string;
}

/** Start async single-company contact enrichment → returns run_id for SSE */
export const startContactEnrichment = (companyKbId: string) =>
  client.post<ContactEnrichStartResponse>(`/contacts/${companyKbId}/enrich`);

/** Get SSE stream URL for contact enrichment progress */
export const getContactEnrichmentStreamUrl = (companyKbId: string, runId: string) => {
  const token = getAccessToken() || '';
  return `${API_BASE}/contacts/${companyKbId}/enrich/stream/${runId}?token=${token}`;
};
