import client from './client';
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
