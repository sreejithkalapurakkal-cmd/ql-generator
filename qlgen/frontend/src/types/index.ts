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
  target_offering: string[];
  regions: {
    countries: string[];
    priority_areas: string[];
  };
  industry_types: { vertical: string; sub_vertical?: string | null }[];
  company_size: {
    employees_min: number;
    employees_max: number;
    revenue_min: number;
    revenue_max: number;
    revenue_currency: string;
  };
  technology_maturity: {
    signals: string[];
    negative_signals: string[];
  };
  infrastructure_readiness: {
    indicators: string[];
  };
  digital_transformation_drivers: {
    growth_triggers: string[];
    operational_pains: string[];
    competitive_pressures: string[];
    strategic_initiatives: string[];
  };
  leadership_traits: {
    target_roles: string[];
    behavioral_traits: string[];
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
  estimated_duration_seconds?: number | null;
  pipeline_mode?: string | null;
  match_strictness?: 'strict' | 'moderate' | 'relaxed' | null;
  bant_weights?: BANTWeights | null;
  stage_details?: {
    total_discovered?: number;
    promoted_count?: number;
    promoted_company_ids?: string[];
    discovery_completed_at?: string;
    contacts_found?: number;
  } | null;
}

export interface BANTWeights {
  budget: number;
  authority: number;
  need: number;
  timing: number;
}

export const DEFAULT_BANT_WEIGHTS: BANTWeights = {
  budget: 3,
  authority: 3,
  need: 3,
  timing: 3,
};

export interface PipelineLogEntry {
  id: string;
  event_type: string;
  event_data: Record<string, unknown>;
  sequence_number: number;
  created_at: string;
}

export interface BANTSourceCitation {
  url: string;
  title?: string | null;
  tool?: string | null;
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

export interface BANTScore {
  id: string;
  budget_score: number | null;
  budget_reason: string | null;
  budget_sources?: BANTSourceCitation[] | null;
  authority_score: number | null;
  authority_reason: string | null;
  authority_sources?: BANTSourceCitation[] | null;
  need_score: number | null;
  need_reason: string | null;
  need_sources?: BANTSourceCitation[] | null;
  timing_score: number | null;
  timing_reason: string | null;
  timing_sources?: BANTSourceCitation[] | null;
  total_score: number | null;
  overall_summary: string | null;
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
  bant_score: BANTScore | null;
  promoted?: boolean | null;
  description?: string | null;
  raw_data_json?: Record<string, unknown> | null;
  created_at: string;
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
  target_offering: [],
  regions: { countries: [], priority_areas: [] },
  industry_types: [],
  company_size: {
    employees_min: 50,
    employees_max: 1500,
    revenue_min: 10000000,
    revenue_max: 500000000,
    revenue_currency: 'USD',
  },
  technology_maturity: { signals: [], negative_signals: [] },
  infrastructure_readiness: { indicators: [] },
  digital_transformation_drivers: {
    growth_triggers: [],
    operational_pains: [],
    competitive_pressures: [],
    strategic_initiatives: [],
  },
  leadership_traits: { target_roles: [], behavioral_traits: [] },
};
