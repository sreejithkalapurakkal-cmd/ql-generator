export interface AuthUser {
  id: string;
  email: string;
  name: string | null;
  picture_url: string | null;
  role: string;
  is_active: boolean;
  created_at: string | null;
  last_login_at: string | null;
}

export interface ICPConfig {
  id?: string;
  name: string;
  description?: string;
  config: ICPDefinition;
  created_at?: string;
  updated_at?: string;
  is_active?: boolean;
  user_name?: string | null;
  user_email?: string | null;
}

export interface ICPDefinition {
  firmographic_details: {
    industry_types: { vertical: string; sub_vertical?: string | null }[];
    geography: {
      countries: string[];
    };
    revenue_range: {
      min: number;
      max: number;
      currency: string;
    };
    employee_range: {
      min: number;
      max: number;
    };
    low_cost_center: boolean;
  };
  target_capability: {
    offerings: string[];
    condition: 'AND' | 'OR';
  };
  urgency_signals: {
    signals: string[];
    condition: 'AND' | 'OR';
  };
  budget_signals: {
    signals: string[];
    condition: 'AND' | 'OR';
  };
  authority_roles: {
    target_roles: string[];
  };
}

export interface PipelineRun {
  id: string;
  icp_config_id: string;
  icp_name?: string | null;
  icp_description?: string | null;
  icp_config?: ICPDefinition | null;
  status: string;
  current_stage: string | null;
  companies_found: number;
  contacts_found: number;
  started_at: string | null;
  completed_at: string | null;
  error_log?: string | null;
  signal_mode?: string | null;
  signal_phase?: string | null;
  pipeline_mode?: string | null;
  match_strictness?: string | null;
  estimated_duration_seconds?: number | null;
  user_name?: string | null;
  stage_details?: {
    total_discovered?: number;
    pre_filter_passed?: number;
    pre_filter_failed?: number;
    agent_passed?: number;
    agent_failed?: number;
    promoted_count?: number;
    contacts_found?: number;
    current_company_index?: number;
    total_companies_in_stage?: number;
    current_company_name?: string;
    contacts_found_so_far?: number;
    newly_discovered?: number;
    carried_forward?: number;
  } | null;
}

export interface PipelineLogEntry {
  id: string;
  event_type: string;
  event_data: Record<string, unknown>;
  sequence_number: number;
  created_at: string;
}

export interface CompanyStageResult {
  id: string;
  stage: string;
  status: string;
  score: number | null;
  reasoning: string | null;
  evidence: unknown | null;
  user_override: boolean | null;
  created_at: string | null;
}

export interface Contact {
  id: string;
  full_name: string | null;
  first_name: string | null;
  last_name: string | null;
  designation: string | null;
  role_category: string | null;
  email: string | null;
  phone: string | null;
  linkedin_url: string | null;
  city: string | null;
  source: string | null;
  confidence: number | null;
  enrichment_status: string | null;
}

export interface Company {
  id: string;
  name: string;
  website: string | null;
  industry: string | null;
  sub_industry: string | null;
  city: string | null;
  state_region: string | null;
  country: string | null;
  employee_count: number | null;
  revenue_estimate: number | null;
  asset_value: number | null;
  tech_stack_json: Record<string, unknown> | null;
  source: string | null;
  qualification: string | null;
  icp_match_score: number | null;
  match_reasoning: string | null;
  contacts: Contact[];
  promoted?: boolean | null;
  description?: string | null;
  raw_data_json?: Record<string, unknown> | null;
  rejection_reason?: string | null;
  disqualification_stage?: string | null;
  created_at: string;
  // v2 fields
  current_stage?: string | null;
  budget_signal_score?: number | null;
  urgency_signal_score?: number | null;
  final_score?: number | null;
  final_rank?: number | null;
  cached_from_run_id?: string | null;
  carried_forward?: boolean | null;
  data_freshness?: string | null;
  stage_results?: CompanyStageResult[];
  bant_score?: { total_score?: number } | null;
  // Recency-adjusted scoring
  recency_adjusted_budget_score?: number | null;
  recency_adjusted_urgency_score?: number | null;
  deal_hotness_score?: number | null;
  deal_hotness_tier?: string | null;
  avg_evidence_age_months?: number | null;

  // Cross-run context (populated by /all/companies endpoint)
  pipeline_run_id?: string | null;
  run_icp_name?: string | null;
}

export interface StageSummary {
  stage: string;
  total: number;
  passed: number;
  failed: number;
  promoted: number;
  excluded: number;
  avg_score: number | null;
}

export interface StageSummaryResponse {
  run_id: string;
  signal_mode: string | null;
  stages: StageSummary[];
  cached_companies: number;
}

// Tool Attribution types
export interface ToolAttribution {
  tool_name: string;
  companies_discovered: number;
  companies_qualified: number;
  companies_disqualified: number;
  high_fit_count: number;
  medium_fit_count: number;
  low_fit_count: number;
  avg_icp_match_score: number | null;
  efficiency: number | null;
  sample_companies: string[];
  total_calls: number;
  successful_calls: number;
  failed_calls: number;
  success_rate: number | null;
}

export interface ToolAttributionResponse {
  run_id: string;
  tools: ToolAttribution[];
}

// Tool Effectiveness aggregate types (cross-run)
export interface ToolEffectivenessAggregate {
  tool_name: string;
  industry: string;
  country: string;
  total_companies_sourced: number;
  companies_passed_stage2: number;
  pass_rate: number;
  avg_score: number;
  effectiveness_score: number;
  total_runs_used: number;
}

export interface ToolEffectivenessResponse {
  tools: ToolEffectivenessAggregate[];
}

// Co-pilot Chat types
export interface PageContext {
  route: string;
  page_type: string;
  run_id?: string;
  company_id?: string;
  icp_id?: string;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  role: 'user' | 'assistant';
  content: string;
  tool_calls?: { tool_name: string; display_name: string }[];
  created_at?: string;
}

export interface ChatSession {
  id: string;
  title: string | null;
  page_context: Record<string, unknown> | null;
  created_at: string;
  updated_at: string | null;
  message_count: number;
  last_message_preview: string | null;
}

export interface RecommendationItem {
  icon: string;
  text: string;
  prompt: string;
}

// Tool registry types
export interface ToolRegistryItem {
  id: string;
  tool_name: string;
  display_name: string;
  category: string;
  requires_api_key: boolean;
  api_key_env_var: string | null;
  base_url: string | null;
  is_enabled: boolean;
  health_status: string;
  last_health_check_at: string | null;
  last_health_message: string | null;
  notes: string | null;
  rate_limit_info: string | null;
  created_at: string | null;
  updated_at: string | null;
  total_calls: number;
  successful_calls: number;
  failed_calls: number;
  success_rate: number | null;
  last_used_at: string | null;
  last_error: string | null;
  // Effectiveness-based priority
  priority: number | null;
  effectiveness_threshold: number | null;
  auto_disabled: boolean | null;
}

export interface ToolMetricsSummary {
  total_tools: number;
  healthy_count: number;
  unhealthy_count: number;
  disabled_count: number;
  no_api_key_count: number;
  unknown_count: number;
}

export interface ToolHealthCheckResult {
  tool_name: string;
  status: string;
  message: string;
  checked_at: string;
}

// Admin types
export interface AdminUserSummary {
  user_id: string;
  user_name: string | null;
  user_email: string | null;
  role: string;
  icp_count: number;
  pipeline_count: number;
  last_activity: string | null;
}

export interface AdminActivityResponse {
  user_summaries: AdminUserSummary[];
  recent_runs: {
    id: string;
    icp_name: string | null;
    user_name: string | null;
    status: string;
    companies_found: number;
    contacts_found: number;
    started_at: string | null;
  }[];
  recent_icps: {
    id: string;
    name: string;
    user_name: string | null;
    created_at: string | null;
  }[];
}

export interface AuditLogEntry {
  id: string;
  user_id: string | null;
  user_name: string | null;
  user_email: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  details: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string | null;
}

// ──────────────────────────────────────────────────────────────────
// Signal Research & Track types
// ──────────────────────────────────────────────────────────────────

export interface TrackingList {
  id: string;
  name: string;
  description: string | null;
  company_count: number;
  monitoring_config: MonitoringConfig;
  signal_hints: SignalHints;
  last_monitored_at: string | null;
  is_active?: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface MonitoringConfig {
  enabled?: boolean;
  frequency_days?: number;
  signal_types?: string[];
  alert_threshold?: string;
}

export interface SignalHints {
  budget_signals?: string[];
  urgency_signals?: string[];
  custom_hints?: string[];
  target_roles?: string[];
}

export interface EnrichedContact {
  full_name: string;
  first_name?: string;
  last_name?: string;
  designation: string | null;
  email: string | null;
  phone: string | null;
  linkedin_url: string | null;
  city: string | null;
  source: string | null;
  confidence: number;
}

export interface TrackingListMember {
  membership_id: string;
  company_kb_id: string;
  company_name: string | null;
  domain: string | null;
  industry: string | null;
  country: string | null;
  city: string | null;
  employee_count: number | null;
  revenue_estimate: number | null;
  best_final_score: number | null;
  best_deal_hotness_tier: string | null;
  signal_heat_score: number;
  outreach_status: string;
  outreach_history: OutreachHistoryEntry[];
  notes: string | null;
  tags: string[];
  added_from: string;
  added_at: string | null;
  snoozed_until: string | null;
  latest_signal: SignalEventSummary | null;
  enrichment_status: string;
  best_known_contacts: EnrichedContact[] | null;
  last_enriched_at: string | null;
}

export interface OutreachHistoryEntry {
  status: string;
  previous_status?: string;
  timestamp: string;
  note?: string;
}

export interface SignalEvent {
  id: string;
  company_kb_id: string;
  signal_type: string;
  signal_subtype: string | null;
  signal_category: string | null;
  priority: string;
  strength: number;
  title: string;
  summary: string | null;
  evidence: Record<string, unknown> | null;
  source_tool: string | null;
  source_url: string | null;
  detected_at: string | null;
  evidence_date: string | null;
  expires_at: string | null;
  is_archived: boolean;
  is_dismissed: boolean;
  is_saved?: boolean;
  is_snoozed?: boolean;
  snoozed_until?: string | null;
  created_at: string | null;
}

export type SignalFeedTab = 'all' | 'today' | 'week' | 'saved';

export interface SignalEventSummary {
  id: string;
  signal_type: string;
  priority: string;
  title: string;
  detected_at: string | null;
  evidence_date?: string | null;
  source_url?: string | null;
}

export interface Notification {
  id: string;
  user_id: string;
  signal_event_id: string | null;
  notification_type: string;
  title: string;
  body: string | null;
  link: string | null;
  is_read: boolean;
  created_at: string | null;
}

export interface Tag {
  id: string;
  name: string;
  color: string;
}

export const OUTREACH_STATUSES = [
  'not_started',
  'drafted',
  'sent',
  'replied',
  'meeting_booked',
  'won',
  'lost',
] as const;

export type OutreachStatus = typeof OUTREACH_STATUSES[number];

export const OUTREACH_STATUS_LABELS: Record<string, string> = {
  not_started: 'Not Started',
  drafted: 'Drafted',
  sent: 'Sent',
  replied: 'Replied',
  meeting_booked: 'Meeting Booked',
  won: 'Won',
  lost: 'Lost',
};

export const OUTREACH_STATUS_COLORS: Record<string, string> = {
  not_started: '#8c8c8c',
  drafted: '#1890ff',
  sent: '#722ed1',
  replied: '#faad14',
  meeting_booked: '#13c2c2',
  won: '#52c41a',
  lost: '#f5222d',
};

export const SIGNAL_TYPE_LABELS: Record<string, string> = {
  funding: 'Funding',
  hiring_surge: 'Hiring Surge',
  executive_change: 'Executive Change',
  champion_job_change: 'Champion Job Change',
  tech_adoption: 'Tech Adoption',
  product_launch: 'Product Launch',
  earnings_report: 'Earnings Report',
  press_mention: 'Press Mention',
  partnership: 'Partnership',
  expansion: 'Expansion',
  competitor_adoption: 'Competitor Adoption',
  competitor_churn: 'Competitor Churn',
  budget_signal: 'Budget Signal',
  urgency_signal: 'Urgency Signal',
  custom_signal: 'Custom Signal',
};

export const SIGNAL_PRIORITY_COLORS: Record<string, string> = {
  critical: '#f5222d',
  high: '#fa541c',
  medium: '#faad14',
  low: '#8c8c8c',
};

export const DEFAULT_ICP: ICPDefinition = {
  firmographic_details: {
    industry_types: [],
    geography: { countries: [] },
    revenue_range: { min: 10000000, max: 500000000, currency: 'USD' },
    employee_range: { min: 50, max: 1500 },
    low_cost_center: false,
  },
  target_capability: { offerings: [], condition: 'OR' },
  urgency_signals: { signals: [], condition: 'OR' },
  budget_signals: { signals: [], condition: 'OR' },
  authority_roles: { target_roles: [] },
};

// ── Firmographic Filter (ingest pipeline) ──

export interface FirmographicFilter {
  industry_types: { vertical: string; sub_vertical?: string | null }[];
  countries: string[];
  employee_range: { min: number; max: number };
  revenue_range: { min: number; max: number; currency: string };
}

export const DEFAULT_FIRMOGRAPHIC_FILTER: FirmographicFilter = {
  industry_types: [],
  countries: [],
  employee_range: { min: 50, max: 5000 },
  revenue_range: { min: 1000000, max: 500000000, currency: 'USD' },
};

export interface ScoreBreakdownEntry {
  score: number;
  reasoning: string;
}

export interface ScoredCompany {
  company_kb_id: string;
  company_name: string;
  domain: string | null;
  industry: string | null;
  country: string | null;
  employee_count: number | null;
  revenue_estimate: number | null;
  score: number;
  justification: string;
  score_breakdown: {
    industry: ScoreBreakdownEntry;
    geography: ScoreBreakdownEntry;
    employees: ScoreBreakdownEntry;
    revenue: ScoreBreakdownEntry;
  };
}

export interface IngestActivityEntry {
  id: number;
  type: 'company_start' | 'tool_start' | 'tool_result' | 'agent_reasoning' | 'company_result';
  timestamp: Date;
  company_name?: string;
  tool_name?: string;
  display_name?: string;
  context?: string;
  text?: string;
  score?: number;
  justification?: string;
  result_preview?: string;
  success?: boolean;
  company_index?: number;
  total?: number;
  fields_found?: string[];
}

export interface IngestBatchStatus {
  batch_id: string;
  name: string | null;
  filename: string | null;
  file_type: string;
  status: string;
  total_rows: number;
  processed_rows: number;
  matched_kb: number;
  newly_created: number;
  enriched_count: number;
  filtered_count: number;
  errors: { row?: number; error: string }[];
  has_filter: boolean;
  evaluation_status: string;
  filter_config: FirmographicFilter | null;
  target_tracking_list_id: string | null;
  created_at: string | null;
}

export interface IngestBatchLogEntry {
  event_type: string;
  event_data: Record<string, unknown>;
  sequence_number: number;
  created_at: string | null;
}

// ─── Research Brief Types ─────────────────────────────────────────────────

export interface BriefSectionSource {
  label: string;
  source_class: string;
  url?: string | null;
  date?: string | null;
}

export interface BriefSection {
  id: string;
  heading: string;
  body: string;
  bullets?: string[];
  sources?: BriefSectionSource[];
  insufficient?: boolean;
  confidence?: number;
}

export interface BriefRevision {
  id: string;
  company_kb_id: string;
  version: number;
  sections: BriefSection[];
  word_count: number | null;
  generated_by: string | null;
  trigger_signal_id: string | null;
  trigger_signal_headline: string | null;
  model_id: string | null;
  created_at: string | null;
}

// ─── Draft Types ──────────────────────────────────────────────────────────

export type DraftFormat = 'email' | 'linkedin';
export type DraftTone = 'direct' | 'consultative' | 'formal' | 'casual';
export type DraftStatus = 'in_progress' | 'sent' | 'discarded';

export interface OutreachDraft {
  id: string;
  company_kb_id?: string;
  signal_id: string | null;
  contact_name: string | null;
  contact_title: string | null;
  format: DraftFormat;
  tone: DraftTone;
  subject: string | null;
  body: string;
  hooks_used: string[];
  status: DraftStatus;
  sent_at: string | null;
  created_at: string | null;
}

// ─── Account Profile Types ────────────────────────────────────────────────

export type ConfidenceTier = 'high' | 'medium' | 'low';

export type AccountStatus = 'monitored' | 'paused' | 'archived';

export type IcpFit = 'strong' | 'moderate' | 'weak';

export interface AccountProfile {
  id: string;
  name: string;
  domain: string;
  industry: string | null;
  employee_count: number | null;
  revenue_estimate: number | null;
  country: string | null;
  city: string | null;
  region: string | null;
  status: AccountStatus;
  icp_fit: IcpFit;
  icp_score: number;
  signal_count: number;
  has_brief: boolean;
  open_draft_count: number;
  tags: string[];
  latest_brief_version: number | null;
  best_known_contacts: Record<string, unknown>[];
}

// ─── Brief Section IDs ────────────────────────────────────────────────────

export const BRIEF_SECTION_IDS = [
  'overview', 'org', 'signals', 'competitive',
  'tech', 'budget', 'why-now', 'angle',
] as const;

export const BRIEF_SECTION_ICONS: Record<string, string> = {
  'overview': '🏢',
  'org': '👥',
  'signals': '⚡',
  'competitive': '🎯',
  'tech': '⚙️',
  'budget': '💰',
  'why-now': '⏱️',
  'angle': '💬',
};
