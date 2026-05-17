import client from './client';

export interface ActivityEvent {
  id: string;
  event_type: string;
  event_category: string | null;
  narrative: string;
  milestone: boolean;
  confidence: number | null;
  narrative_detail?: string | null;
  technical_detail?: Record<string, unknown> | null;
  research_job_id?: string | null;
  created_at: string | null;
}

export interface ActivityFeedResponse {
  events: ActivityEvent[];
  total: number;
  verbosity: string;
  offset: number;
  limit: number;
}

export interface ActivityStatsResponse {
  total_events: number;
  milestones: number;
  by_category: Record<string, number>;
}

export type VerbosityLevel = 'summary' | 'detailed' | 'technical';

export const getActivityFeed = (companyKbId: string, params?: {
  verbosity?: VerbosityLevel;
  category?: string;
  limit?: number;
  offset?: number;
}) => client.get<ActivityFeedResponse>(`/activity/${companyKbId}`, { params });

export const getActivityStats = (companyKbId: string) =>
  client.get<ActivityStatsResponse>(`/activity/${companyKbId}/stats`);
