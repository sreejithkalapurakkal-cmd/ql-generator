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
  data_freshness?: string | null;
  stage_results?: CompanyStageResult[];
  bant_score?: { total_score?: number } | null;
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
