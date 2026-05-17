import client from './client';

export interface CustomSignalRule {
  id: string;
  user_id: string;
  tracking_list_id: string | null;
  name: string;
  description: string | null;
  rule_type: 'keyword' | 'pattern' | 'composite';
  rule_config: Record<string, unknown>;
  signal_type_output: string;
  priority_output: string;
  is_active: boolean;
  last_triggered_at: string | null;
  trigger_count: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface SignalRulesListResponse {
  rules: CustomSignalRule[];
  total: number;
}

export interface CreateRuleData {
  name: string;
  description?: string;
  rule_type: 'keyword' | 'pattern' | 'composite';
  rule_config: Record<string, unknown>;
  tracking_list_id?: string;
  signal_type_output?: string;
  priority_output?: string;
}

export interface UpdateRuleData {
  name?: string;
  description?: string;
  rule_config?: Record<string, unknown>;
  signal_type_output?: string;
  priority_output?: string;
  is_active?: boolean;
}

export const getSignalRules = (params?: { tracking_list_id?: string; active_only?: boolean }) =>
  client.get<SignalRulesListResponse>('/signal-rules', { params });

export const createSignalRule = (data: CreateRuleData) =>
  client.post<CustomSignalRule>('/signal-rules', data);

export const getSignalRule = (ruleId: string) =>
  client.get<CustomSignalRule>(`/signal-rules/${ruleId}`);

export const updateSignalRule = (ruleId: string, data: UpdateRuleData) =>
  client.put<CustomSignalRule>(`/signal-rules/${ruleId}`, data);

export const deleteSignalRule = (ruleId: string) =>
  client.delete(`/signal-rules/${ruleId}`);

export const toggleSignalRule = (ruleId: string) =>
  client.post<CustomSignalRule>(`/signal-rules/${ruleId}/toggle`);

export const evaluateRules = (companyKbId: string, searchText?: string) =>
  client.post<{ triggered_rules: { rule_id: string; rule_name: string; rule_type: string }[]; total_triggered: number }>(
    '/signal-rules/evaluate',
    { company_kb_id: companyKbId, search_text: searchText || '' },
  );

export const configureMonitoring = (trackingListId: string, data: {
  enabled: boolean;
  frequency_days?: number;
  signal_types?: string[];
  alert_threshold?: string;
}) => client.put(`/signals/monitoring/${trackingListId}`, data);

export const checkMonitoring = (dryRun?: boolean) =>
  client.post(`/signals/monitoring/check`, null, { params: { dry_run: dryRun || false } });
