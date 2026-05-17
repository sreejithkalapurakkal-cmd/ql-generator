import client from './client';

export interface BriefResponse {
  company_kb_id: string;
  brief: string;
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

export const generateBrief = (companyKbId: string) =>
  client.post<BriefResponse>(`/briefs/generate/${companyKbId}`);

export const generateOutreachDraft = (companyKbId: string, data?: {
  contact_name?: string;
  context?: string;
}) => client.post<OutreachDraftResponse>(`/briefs/outreach/${companyKbId}`, data || {});

export const researchCompany = (companyKbId: string) =>
  client.post<ResearchResponse>(`/briefs/research/${companyKbId}`);
