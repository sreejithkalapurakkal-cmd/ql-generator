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
  status: string;
  current_stage: string | null;
  companies_found: number;
  contacts_found: number;
  started_at: string | null;
  completed_at: string | null;
  error_log?: string | null;
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
  authority_score: number | null;
  authority_reason: string | null;
  need_score: number | null;
  need_reason: string | null;
  timing_score: number | null;
  timing_reason: string | null;
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
  created_at: string;
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
