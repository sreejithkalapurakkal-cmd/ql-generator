import React, { useEffect, useState, useMemo } from 'react';
import {
  Card, Table, Tag, Button, Space, Tooltip, Descriptions, Select, Typography,
  Popconfirm, message, Badge, Collapse, Dropdown,
} from 'antd';
import {
  DownloadOutlined, ToolOutlined, DeleteOutlined, PlayCircleOutlined,
  ThunderboltOutlined, DatabaseOutlined, FireOutlined,
  DownOutlined, UpOutlined, LinkOutlined, CheckCircleOutlined,
  CloseCircleOutlined, ArrowUpOutlined, MinusOutlined,
} from '@ant-design/icons';
import { useParams, useNavigate } from 'react-router-dom';
import { getLeadCompanies, getStageSummary, getExportUrl } from '../api/leadsApi';
import { getPipelineStatus, getPipelineLogs, deletePipelineRun, startPipeline, getCompaniesByStage } from '../api/pipelineApi';
import {
  Company, CompanyStageResult, PipelineRun, PipelineLogEntry,
  StageSummaryResponse, StageSummary,
} from '../types';
import { usePageContext } from '../context/PageContextProvider';

const { Text } = Typography;

// ---------------------------------------------------------------------------
// Score helpers
// ---------------------------------------------------------------------------

const getScoreColor = (score: number | null | undefined): string => {
  if (score == null) return '#d9d9d9';
  if (score >= 75) return '#52c41a';
  if (score >= 50) return '#faad14';
  if (score >= 25) return '#fa8c16';
  return '#ff4d4f';
};

const getScoreLabel = (score: number | null | undefined): string => {
  if (score == null) return 'N/A';
  if (score >= 75) return 'High';
  if (score >= 50) return 'Medium';
  if (score >= 25) return 'Low';
  return 'Very Low';
};

const getScoreTagColor = (score: number | null | undefined): string => {
  if (score == null) return 'default';
  if (score >= 75) return 'green';
  if (score >= 50) return 'gold';
  if (score >= 25) return 'orange';
  return 'red';
};

const FinalScoreDisplay: React.FC<{ score: number | null | undefined; rank?: number | null }> = ({ score, rank }) => {
  if (score == null) return <Tag>N/A</Tag>;
  const color = getScoreTagColor(score);
  const label = getScoreLabel(score);
  return (
    <Tooltip title={rank != null ? `Rank #${rank} -- ${label}` : label}>
      <Tag color={color} style={{ fontWeight: 'bold', fontSize: 13 }}>
        {Math.round(score)}/100
      </Tag>
    </Tooltip>
  );
};

const SignalScoreBar: React.FC<{ score: number | null | undefined; label: string }> = ({ score, label }) => {
  if (score == null) return <Text type="secondary" style={{ fontSize: 11 }}>--</Text>;
  const rounded = Math.round(score);
  return (
    <Tooltip title={`${label}: ${rounded}/100`}>
      <div style={{ minWidth: 60 }}>
        <div style={{ fontSize: 11, fontWeight: 600, marginBottom: 2, color: getScoreColor(score) }}>
          {rounded}
        </div>
        <div style={{ background: 'var(--g100, #f0f0f0)', borderRadius: 3, height: 4, overflow: 'hidden' }}>
          <div style={{
            width: `${rounded}%`, height: '100%',
            background: getScoreColor(score), borderRadius: 3,
          }} />
        </div>
      </div>
    </Tooltip>
  );
};

// ---------------------------------------------------------------------------
// Deal Hotness helpers
// ---------------------------------------------------------------------------

const HOTNESS_CONFIG: Record<string, { color: string; label: string; tagColor: string }> = {
  hot: { color: '#f5222d', label: 'Hot', tagColor: 'red' },
  warm: { color: '#fa8c16', label: 'Warm', tagColor: 'orange' },
  cool: { color: '#1677ff', label: 'Cool', tagColor: 'blue' },
  cold: { color: '#8c8c8c', label: 'Cold', tagColor: 'default' },
};

const getRecencyBadge = (months: number | null | undefined): { label: string; color: string } => {
  if (months == null) return { label: '', color: 'default' };
  if (months < 1) return { label: 'Fresh', color: 'green' };
  if (months <= 3) return { label: 'Recent', color: 'blue' };
  if (months <= 6) return { label: 'Aging', color: 'orange' };
  return { label: 'Stale', color: 'red' };
};

const HotnessIndicator: React.FC<{ tier: string | null | undefined; score: number | null | undefined }> = ({ tier, score }) => {
  if (!tier || score == null) return <Text type="secondary" style={{ fontSize: 11 }}>--</Text>;
  const cfg = HOTNESS_CONFIG[tier] || HOTNESS_CONFIG.cold;
  return (
    <Tooltip title={`Deal Hotness: ${Math.round(score)}/100 (${cfg.label})`}>
      <Tag color={cfg.tagColor} style={{ fontWeight: 600, fontSize: 11 }} icon={tier === 'hot' ? <FireOutlined /> : undefined}>
        {cfg.label} {Math.round(score)}
      </Tag>
    </Tooltip>
  );
};

// ---------------------------------------------------------------------------
// Signal Detail Panel (replaces BANTDetailPanel)
// ---------------------------------------------------------------------------

const STAGE_DISPLAY: Record<string, { label: string; color: string; icon: string }> = {
  company_discovery: { label: 'Company Discovery', color: '#1677ff', icon: 'search' },
  industry_discovery: { label: 'Industry Discovery', color: '#1677ff', icon: 'search' },
  firmographic_filter: { label: 'Firmographic Filter', color: '#722ed1', icon: 'filter' },
  firmographic_fit: { label: 'Firmographic Fit', color: '#722ed1', icon: 'filter' },
  budget_signal: { label: 'Budget Signal', color: '#52c41a', icon: 'dollar' },
  budget_signals: { label: 'Budget Signals', color: '#52c41a', icon: 'dollar' },
  urgency_signal: { label: 'Urgency Signal', color: '#fa8c16', icon: 'clock' },
  urgency_signals: { label: 'Urgency Signals', color: '#fa8c16', icon: 'clock' },
  budget_urgency_signals: { label: 'Budget & Urgency Signals', color: '#389e0d', icon: 'dollar' },
  contact_discovery: { label: 'Contact Discovery', color: '#13c2c2', icon: 'team' },
  contact_enrichment: { label: 'Contact Enrichment', color: '#eb2f96', icon: 'mail' },
  scoring: { label: 'Final Scoring', color: '#f5222d', icon: 'trophy' },
  final_scoring: { label: 'Final Scoring', color: '#f5222d', icon: 'trophy' },
};

const getStageDisplay = (stage: string) =>
  STAGE_DISPLAY[stage] || { label: stage.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()), color: '#8c8c8c', icon: 'info' };

const SignalDetailPanel: React.FC<{ company: Company }> = ({ company }) => {
  const stageResults = company.stage_results || [];

  if (stageResults.length === 0) {
    return (
      <div style={{ padding: 16 }}>
        <Text type="secondary">No stage results available for this company.</Text>
      </div>
    );
  }

  // Sort by created_at or by a logical stage order
  const stageOrder = [
    'industry_discovery', 'firmographic_fit', 'budget_signals',
    'urgency_signals', 'budget_urgency_signals', 'contact_discovery', 'final_scoring',
    'company_discovery', 'firmographic_filter', 'budget_signal',
    'urgency_signal', 'contact_enrichment', 'scoring',
  ];
  const sorted = [...stageResults].sort((a, b) => {
    const ai = stageOrder.indexOf(a.stage);
    const bi = stageOrder.indexOf(b.stage);
    return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
  });

  return (
    <Collapse
      defaultActiveKey={sorted.map(r => r.id)}
      style={{ background: 'transparent' }}
      items={sorted.map((result) => {
        const display = getStageDisplay(result.stage);
        const statusColor = result.status === 'passed' ? 'green' :
          result.status === 'failed' ? 'red' :
            result.status === 'skipped' ? 'default' : 'blue';

        return {
          key: result.id,
          label: (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%' }}>
              <Tag color={display.color} style={{ fontSize: 11 }}>{display.label}</Tag>
              <Tag color={statusColor} style={{ fontSize: 11 }}>
                {result.status.charAt(0).toUpperCase() + result.status.slice(1)}
              </Tag>
              {result.score != null && (
                <Text style={{ fontSize: 12, fontWeight: 600, color: getScoreColor(result.score) }}>
                  Score: {Math.round(result.score)}/100
                </Text>
              )}
              {result.user_override && (
                <Tag color="purple" style={{ fontSize: 10 }}>Override</Tag>
              )}
            </div>
          ),
          children: (
            <div>
              {result.reasoning && (
                <div style={{
                  background: 'var(--g50, #fafafa)', padding: '10px 14px',
                  borderRadius: 6, fontSize: 12, color: 'var(--g700)',
                  lineHeight: 1.7, marginBottom: 10,
                  borderLeft: `3px solid ${display.color}`,
                }}>
                  <Text type="secondary" style={{ fontSize: 11, fontWeight: 600 }}>Reasoning: </Text>
                  {result.reasoning}
                </div>
              )}
              {result.evidence != null && (
                <div style={{ marginBottom: 10 }}>
                  <Text type="secondary" style={{ fontSize: 11, fontWeight: 600, marginBottom: 6, display: 'block' }}>
                    Evidence
                  </Text>
                  <EvidenceDisplay evidence={result.evidence} />
                </div>
              )}
            </div>
          ),
        };
      })}
    />
  );
};

// ---------------------------------------------------------------------------
// Company Insights Panel
// ---------------------------------------------------------------------------

const DIMENSION_LABELS: Record<string, string> = {
  offering_fit: 'Offering',
  geography_fit: 'Geography',
  industry_fit: 'Industry',
  size_fit: 'Size',
  tech_maturity: 'Tech',
  infra_readiness: 'Infra',
  transformation_drivers: 'Transformation',
  leadership_fit: 'Leadership',
  priority_areas: 'Priority Areas',
};

const DimensionScoreTags: React.FC<{ rawData: Record<string, unknown> | null | undefined }> = ({ rawData }) => {
  if (!rawData) return null;
  const evidence = (rawData.dimension_evidence || rawData) as Record<string, unknown>;
  const dims = Object.entries(DIMENSION_LABELS);
  const rendered: React.ReactNode[] = [];
  dims.forEach(([key, label]) => {
    const dim = evidence[key] as Record<string, unknown> | undefined;
    if (!dim) return;
    const score = typeof dim.score === 'number' ? dim.score : null;
    const dimEvidence = (dim.evidence || dim.reasoning || '') as string;
    if (score === null) return;
    const color = score === 2 ? 'green' : score === 1 ? 'gold' : 'default';
    rendered.push(
      <Tooltip key={key} title={dimEvidence || `${label}: ${score}/2`}>
        <Tag color={color} style={{ fontSize: 11, marginBottom: 3 }}>{label} ({score}/2)</Tag>
      </Tooltip>
    );
  });
  if (rendered.length === 0) return null;
  return (
    <div style={{ marginTop: 8 }}>
      <Text type="secondary" style={{ fontSize: 11 }}>Dimension Scores: </Text>
      {rendered}
    </div>
  );
};

const CompanyInsightsPanel: React.FC<{ company: Company }> = ({ company }) => {
  const matchScore = company.icp_match_score;
  const matchColor = matchScore != null
    ? (matchScore >= 70 ? '#52c41a' : matchScore >= 50 ? '#faad14' : '#ff4d4f')
    : '#999';
  const scoreDisplay = matchScore != null ? `${Math.round(matchScore)}/100` : 'N/A';
  const techStack = company.tech_stack_json;
  const techItems: string[] = Array.isArray(techStack) ? techStack.map(String) : [];
  const revenue = company.revenue_estimate;
  const revenueStr = revenue
    ? (revenue >= 1_000_000_000
      ? `$${(revenue / 1_000_000_000).toFixed(1)}B`
      : revenue >= 1_000_000
        ? `$${(revenue / 1_000_000).toFixed(0)}M`
        : `$${revenue.toLocaleString()}`)
    : null;

  const assetValue = company.asset_value;
  const assetStr = assetValue
    ? (assetValue >= 1_000_000_000
      ? `$${(assetValue / 1_000_000_000).toFixed(1)}B`
      : assetValue >= 1_000_000
        ? `$${(assetValue / 1_000_000).toFixed(0)}M`
        : `$${assetValue.toLocaleString()}`)
    : null;

  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 8, color: 'var(--g800)' }}>Company Insights</div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, marginBottom: 12 }}>
        {matchScore != null && (
          <div>
            <Text type="secondary" style={{ fontSize: 11 }}>Match Score</Text>
            <div style={{ fontWeight: 700, fontSize: 16, color: matchColor }}>{scoreDisplay}</div>
          </div>
        )}
        {company.final_score != null && (
          <div>
            <Text type="secondary" style={{ fontSize: 11 }}>Final Score</Text>
            <div style={{ fontWeight: 700, fontSize: 16, color: getScoreColor(company.final_score) }}>
              {Math.round(company.final_score)}/100
            </div>
          </div>
        )}
        {company.budget_signal_score != null && (
          <div>
            <Text type="secondary" style={{ fontSize: 11 }}>Budget Signal</Text>
            <div style={{ fontWeight: 700, fontSize: 16, color: getScoreColor(company.budget_signal_score) }}>
              {Math.round(company.budget_signal_score)}/100
            </div>
          </div>
        )}
        {company.urgency_signal_score != null && (
          <div>
            <Text type="secondary" style={{ fontSize: 11 }}>Urgency Signal</Text>
            <div style={{ fontWeight: 700, fontSize: 16, color: getScoreColor(company.urgency_signal_score) }}>
              {Math.round(company.urgency_signal_score)}/100
            </div>
          </div>
        )}
        {company.deal_hotness_score != null && (
          <div>
            <Text type="secondary" style={{ fontSize: 11 }}>Deal Hotness</Text>
            <div style={{ fontWeight: 700, fontSize: 16, color: HOTNESS_CONFIG[company.deal_hotness_tier || 'cold']?.color || '#8c8c8c' }}>
              {Math.round(company.deal_hotness_score)}/100
              <Tag color={HOTNESS_CONFIG[company.deal_hotness_tier || 'cold']?.tagColor || 'default'}
                style={{ fontSize: 10, marginLeft: 6 }}>
                {HOTNESS_CONFIG[company.deal_hotness_tier || 'cold']?.label || 'Cold'}
              </Tag>
            </div>
          </div>
        )}
        {company.avg_evidence_age_months != null && (
          <div>
            <Text type="secondary" style={{ fontSize: 11 }}>Avg Evidence Age</Text>
            <div style={{ fontWeight: 600, fontSize: 14 }}>
              {company.avg_evidence_age_months < 1 ? '<1 mo' : `${company.avg_evidence_age_months.toFixed(1)} mo`}
              {(() => {
                const badge = getRecencyBadge(company.avg_evidence_age_months);
                return badge.label ? <Tag color={badge.color} style={{ fontSize: 10, marginLeft: 6 }}>{badge.label}</Tag> : null;
              })()}
            </div>
          </div>
        )}
        {revenueStr && (
          <div>
            <Text type="secondary" style={{ fontSize: 11 }}>Revenue Est.</Text>
            <div style={{ fontWeight: 600, fontSize: 14 }}>{revenueStr}</div>
          </div>
        )}
        {assetStr && (
          <div>
            <Text type="secondary" style={{ fontSize: 11 }}>Asset Value</Text>
            <div style={{ fontWeight: 600, fontSize: 14 }}>{assetStr}</div>
          </div>
        )}
        {company.employee_count != null && (
          <div>
            <Text type="secondary" style={{ fontSize: 11 }}>Employees</Text>
            <div style={{ fontWeight: 600, fontSize: 14 }}>{company.employee_count.toLocaleString()}</div>
          </div>
        )}
      </div>
      {techItems.length > 0 && (
        <div style={{ marginBottom: 10 }}>
          <Text type="secondary" style={{ fontSize: 11 }}>Tech Stack: </Text>
          {techItems.map((t, i) => <Tag key={i} color="blue" style={{ fontSize: 11, marginBottom: 3 }}>{t}</Tag>)}
        </div>
      )}
      <DimensionScoreTags rawData={company.raw_data_json} />
      {company.match_reasoning && (
        <div style={{
          background: 'var(--g50, #fafafa)', padding: '8px 12px', borderRadius: 6,
          fontSize: 12, color: 'var(--g700)', lineHeight: 1.6,
        }}>
          <Text type="secondary" style={{ fontSize: 11 }}>Overview: </Text>
          {company.match_reasoning}
        </div>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// ICP Config Panel
// ---------------------------------------------------------------------------

const ICPConfigPanel: React.FC<{ config: Record<string, unknown>; name?: string | null; description?: string | null }> = ({ config, name, description }) => {
  const cfg = config as any;
  const fd = cfg?.firmographic_details ?? {};
  const offerings: string[] = cfg?.target_capability?.offerings ?? [];
  const offeringCondition: string = cfg?.target_capability?.condition ?? '';
  const urgencySignals: string[] = cfg?.urgency_signals?.signals ?? [];
  const urgencyCondition: string = cfg?.urgency_signals?.condition ?? '';
  const budgetSignals: string[] = cfg?.budget_signals?.signals ?? [];
  const budgetCondition: string = cfg?.budget_signals?.condition ?? '';
  const targetRoles: string[] = cfg?.authority_roles?.target_roles ?? [];
  const industries: any[] = fd?.industry_types ?? [];
  const countries: string[] = fd?.geography?.countries ?? [];

  return (
    <Descriptions bordered size="small" column={2}>
      {name && (
        <Descriptions.Item label="Name" span={2}>{name}</Descriptions.Item>
      )}
      {description && (
        <Descriptions.Item label="Description" span={2}>{description}</Descriptions.Item>
      )}
      <Descriptions.Item label="Industries" span={2}>
        {industries.map((i: any) => `${i.vertical}${i.sub_vertical ? ` / ${i.sub_vertical}` : ''}`).join(', ') || '-'}
      </Descriptions.Item>
      <Descriptions.Item label="Countries">
        {countries.join(', ') || '-'}
      </Descriptions.Item>
      <Descriptions.Item label="Employees">
        {fd?.employee_range?.min?.toLocaleString() ?? '?'}&ndash;{fd?.employee_range?.max?.toLocaleString() ?? '?'}
      </Descriptions.Item>
      <Descriptions.Item label="Revenue">
        {fd?.revenue_range?.currency ?? 'USD'}{' '}
        {fd?.revenue_range?.min?.toLocaleString() ?? '?'}&ndash;{fd?.revenue_range?.max?.toLocaleString() ?? '?'}
      </Descriptions.Item>
      <Descriptions.Item label="Low Cost Center">
        {fd?.low_cost_center ? 'Yes' : 'No'}
      </Descriptions.Item>
      <Descriptions.Item label="Target Offerings" span={2}>
        {offerings.join(', ') || '-'}
        {offerings.length > 1 && offeringCondition && (
          <Tag color="purple" style={{ marginLeft: 8 }}>{offeringCondition}</Tag>
        )}
      </Descriptions.Item>
      <Descriptions.Item label="Urgency Signals" span={2}>
        {urgencySignals.join(', ') || '-'}
        {urgencySignals.length > 1 && urgencyCondition && (
          <Tag color="orange" style={{ marginLeft: 8 }}>{urgencyCondition}</Tag>
        )}
      </Descriptions.Item>
      <Descriptions.Item label="Budget Signals" span={2}>
        {budgetSignals.join(', ') || '-'}
        {budgetSignals.length > 1 && budgetCondition && (
          <Tag color="green" style={{ marginLeft: 8 }}>{budgetCondition}</Tag>
        )}
      </Descriptions.Item>
      <Descriptions.Item label="Target Roles" span={2}>
        {targetRoles.join(', ') || '-'}
      </Descriptions.Item>
    </Descriptions>
  );
};

// ---------------------------------------------------------------------------
// Pipeline Funnel Tab
// ---------------------------------------------------------------------------

const FUNNEL_COLORS: Record<string, string> = {
  company_discovery:   '#1677ff',
  firmographic_filter: '#5C2D8F',
  firmographic_fit:    '#5C2D8F',
  budget_signal:       '#1E9B6B',
  budget_signals:      '#1E9B6B',
  urgency_signal:      '#E0820A',
  urgency_signals:     '#E0820A',
  contact_discovery:   '#0891B2',
  contact_enrichment:  '#7C3AED',
  scoring:             '#D93025',
};

// ---------------------------------------------------------------------------
// Evidence Display sub-component
// ---------------------------------------------------------------------------

const EvidenceDisplay: React.FC<{ evidence: unknown }> = ({ evidence }) => {
  if (!evidence) return null;

  // Handle array of signal objects
  if (Array.isArray(evidence)) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {evidence.map((item: any, idx: number) => (
          <div key={idx} style={{
            background: '#f6f8fa', padding: '10px 16px', borderRadius: 8,
            fontSize: 12, lineHeight: 1.6,
            borderLeft: `3px solid ${item.score != null ? (item.score >= 4 ? '#52c41a' : item.score >= 2 ? '#faad14' : '#ff4d4f') : '#d9d9d9'}`,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              {item.signal_name || item.name ? (
                <Text style={{ fontWeight: 600, fontSize: 12 }}>
                  {item.signal_name || item.name}
                </Text>
              ) : null}
              {item.score != null && (
                <Tag color={item.score >= 4 ? 'green' : item.score >= 2 ? 'gold' : 'red'} style={{ fontSize: 10 }}>
                  {item.score}/5
                </Tag>
              )}
            </div>
            {item.description && (
              <div style={{ color: 'var(--g600)' }}>{item.description}</div>
            )}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              {item.source_url && (
                <a href={item.source_url} target="_blank" rel="noreferrer" style={{ fontSize: 11, color: 'var(--purple)' }}>
                  <LinkOutlined style={{ marginRight: 4 }} />
                  {item.source_url.length > 60 ? item.source_url.substring(0, 60) + '...' : item.source_url}
                </a>
              )}
              {item.evidence_date && (
                <Tag style={{ fontSize: 10 }}>
                  {new Date(item.evidence_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                </Tag>
              )}
              {item.recency_months != null && (() => {
                const badge = getRecencyBadge(item.recency_months);
                return badge.label ? <Tag color={badge.color} style={{ fontSize: 10 }}>{badge.label}</Tag> : null;
              })()}
            </div>
          </div>
        ))}
      </div>
    );
  }

  // Handle object evidence (e.g. firmographic per_criterion)
  if (typeof evidence === 'object' && evidence !== null) {
    const obj = evidence as Record<string, unknown>;
    const keys = Object.keys(obj);

    // Known firmographic criterion keys
    const firmographicKeys = new Set([
      'revenue', 'employees', 'capability_fit', 'low_cost_center',
      'industry', 'geography', 'employee_count', 'revenue_range',
    ]);
    const isFirmographic = keys.some(k => firmographicKeys.has(k));

    const formatCriterionValue = (key: string, val: unknown): React.ReactNode => {
      if (val == null) return <Text type="secondary">N/A</Text>;
      if (typeof val !== 'object') return <Text>{String(val)}</Text>;

      const criterion = val as Record<string, unknown>;

      // capability_fit shape: { match: bool, reasoning: string }
      if ('match' in criterion) {
        const matched = Boolean(criterion.match);
        return (
          <div style={{
            background: '#f6f8fa', padding: '8px 12px', borderRadius: 6,
            fontSize: 12, lineHeight: 1.6, display: 'flex', flexDirection: 'column', gap: 4,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Text style={{ fontWeight: 600, fontSize: 12 }}>
                {key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
              </Text>
              <Tag color={matched ? 'green' : 'red'} style={{ fontSize: 10 }}>
                {matched ? 'Match' : 'No Match'}
              </Tag>
            </div>
            {!!criterion.reasoning && (
              <Text style={{ color: 'var(--g600)', fontSize: 12 }}>{String(criterion.reasoning)}</Text>
            )}
          </div>
        );
      }

      // Numeric criterion shape: { value: number, in_range: bool, source: string }
      if ('value' in criterion) {
        const inRange = 'in_range' in criterion ? Boolean(criterion.in_range) : null;
        const value = criterion.value;
        const source = criterion.source ? String(criterion.source) : null;

        let displayValue = String(value);
        if (typeof value === 'number') {
          if (key.toLowerCase().includes('revenue')) {
            displayValue = value >= 1_000_000_000
              ? `$${(value / 1_000_000_000).toFixed(1)}B`
              : value >= 1_000_000
                ? `$${(value / 1_000_000).toFixed(0)}M`
                : `$${value.toLocaleString()}`;
          } else {
            displayValue = value.toLocaleString();
          }
        }

        return (
          <div style={{
            background: '#f6f8fa', padding: '8px 12px', borderRadius: 6,
            fontSize: 12, lineHeight: 1.6, display: 'flex', alignItems: 'center', gap: 8,
          }}>
            <Text style={{ fontWeight: 600, fontSize: 12 }}>
              {key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}:
            </Text>
            <Text style={{ fontSize: 12 }}>{displayValue}</Text>
            {inRange != null && (
              <Tag color={inRange ? 'green' : 'red'} style={{ fontSize: 10 }}>
                {inRange ? 'In Range' : 'Out of Range'}
              </Tag>
            )}
            {source && <Tag style={{ fontSize: 10 }}>{source}</Tag>}
          </div>
        );
      }

      // Boolean criterion shape: { has_center: bool, source: string } or similar
      const boolKey = Object.keys(criterion).find(k => typeof criterion[k] === 'boolean');
      if (boolKey) {
        const boolVal = Boolean(criterion[boolKey]);
        const source = criterion.source ? String(criterion.source) : null;
        return (
          <div style={{
            background: '#f6f8fa', padding: '8px 12px', borderRadius: 6,
            fontSize: 12, lineHeight: 1.6, display: 'flex', alignItems: 'center', gap: 8,
          }}>
            <Text style={{ fontWeight: 600, fontSize: 12 }}>
              {key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}:
            </Text>
            <Tag color={boolVal ? 'green' : 'default'} style={{ fontSize: 10 }}>
              {boolVal ? 'Yes' : 'No'}
            </Tag>
            {source && <Tag style={{ fontSize: 10 }}>{source}</Tag>}
          </div>
        );
      }

      // Unknown nested object — render as labeled key-value pairs
      return (
        <div style={{
          background: '#f6f8fa', padding: '8px 12px', borderRadius: 6,
          fontSize: 12, lineHeight: 1.6,
        }}>
          <Text style={{ fontWeight: 600, fontSize: 12, display: 'block', marginBottom: 4 }}>
            {key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
          </Text>
          {Object.entries(criterion).map(([subKey, subVal]) => (
            <div key={subKey} style={{ display: 'flex', gap: 6, marginBottom: 2 }}>
              <Text type="secondary" style={{ fontSize: 11 }}>{subKey.replace(/_/g, ' ')}:</Text>
              <Text style={{ fontSize: 11 }}>{typeof subVal === 'object' ? JSON.stringify(subVal) : String(subVal)}</Text>
            </div>
          ))}
        </div>
      );
    };

    if (isFirmographic || keys.length > 0) {
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {keys.map((key) => (
            <React.Fragment key={key}>
              {formatCriterionValue(key, obj[key])}
            </React.Fragment>
          ))}
        </div>
      );
    }
  }

  // Fallback: formatted JSON
  return (
    <pre style={{
      margin: 0, fontSize: 11, whiteSpace: 'pre-wrap',
      wordBreak: 'break-word', background: '#f6f8fa',
      padding: '8px 12px', borderRadius: 6,
    }}>
      {typeof evidence === 'string' ? evidence : JSON.stringify(evidence, null, 2)}
    </pre>
  );
};

// ---------------------------------------------------------------------------
// Company Stage Timeline sub-component
// ---------------------------------------------------------------------------

const CompanyStageTimeline: React.FC<{ stageResults: CompanyStageResult[] }> = ({ stageResults }) => {
  if (!stageResults || stageResults.length === 0) return null;

  const statusConfig: Record<string, { color: string; icon: React.ReactNode; symbol: string }> = {
    passed: { color: 'green', icon: <CheckCircleOutlined />, symbol: '\u2713' },
    failed: { color: 'red', icon: <CloseCircleOutlined />, symbol: '\u2717' },
    promoted: { color: 'blue', icon: <ArrowUpOutlined />, symbol: '\u2191' },
    excluded: { color: 'default', icon: <MinusOutlined />, symbol: '\u2014' },
    skipped: { color: 'default', icon: <MinusOutlined />, symbol: '\u2014' },
  };

  return (
    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 8 }}>
      {stageResults.map((sr) => {
        const cfg = statusConfig[sr.status] || statusConfig.passed;
        const display = getStageDisplay(sr.stage);
        return (
          <Tooltip
            key={sr.id}
            title={
              <div>
                <div>{display.label}: {sr.status}</div>
                {sr.reasoning && <div style={{ fontSize: 11, marginTop: 4 }}>{sr.reasoning}</div>}
              </div>
            }
          >
            <Tag
              color={cfg.color}
              style={{ fontSize: 11, cursor: 'help' }}
              icon={cfg.icon}
            >
              {display.label}
              {sr.score != null && ` (${Math.round(sr.score)})`}
              {sr.user_override && ' [override]'}
            </Tag>
          </Tooltip>
        );
      })}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Stage Company List sub-component
// ---------------------------------------------------------------------------

const StageCompanyList: React.FC<{ companies: Company[]; stageKey: string }> = ({ companies, stageKey }) => {
  if (companies.length === 0) {
    return <div style={{ padding: 16, color: 'var(--g400)', textAlign: 'center' }}>No companies at this stage.</div>;
  }

  const funnelColor = FUNNEL_COLORS[stageKey] || '#8c8c8c';

  const items = companies.map((company) => {
    const stageResults = company.stage_results || [];
    const relevantResult = stageResults.find((sr) => sr.stage === stageKey);
    const statusTag = relevantResult
      ? (() => {
        const color = relevantResult.status === 'passed' ? 'green'
          : relevantResult.status === 'failed' ? 'red'
            : relevantResult.status === 'promoted' ? 'blue'
              : relevantResult.status === 'excluded' ? 'default'
                : 'gold';
        return <Tag color={color} style={{ fontSize: 11 }}>{relevantResult.status}</Tag>;
      })()
      : <Tag style={{ fontSize: 11 }}>unknown</Tag>;

    return {
      key: company.id,
      label: (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%' }}>
          <Text style={{ fontWeight: 600, fontSize: 13 }}>{company.name}</Text>
          {statusTag}
          {relevantResult?.score != null && (
            <Text style={{ fontSize: 12, fontWeight: 600, color: getScoreColor(relevantResult.score) }}>
              {Math.round(relevantResult.score)}/100
            </Text>
          )}
          {relevantResult?.user_override && (
            <Tag color="purple" style={{ fontSize: 10 }}>Override</Tag>
          )}
        </div>
      ),
      children: (
        <div>
          {/* Reasoning */}
          {!!relevantResult?.reasoning && (
            <div style={{
              background: 'var(--g50, #fafafa)', padding: '10px 14px',
              borderRadius: 6, fontSize: 12, color: 'var(--g700)',
              lineHeight: 1.7, marginBottom: 10,
              borderLeft: `3px solid ${funnelColor}`,
            }}>
              <Text type="secondary" style={{ fontSize: 11, fontWeight: 600 }}>Reasoning: </Text>
              {relevantResult.reasoning}
            </div>
          )}

          {/* Evidence */}
          {relevantResult?.evidence != null && (
            <div style={{ marginBottom: 10 }}>
              <Text type="secondary" style={{ fontSize: 11, fontWeight: 600, marginBottom: 6, display: 'block' }}>Evidence</Text>
              <EvidenceDisplay evidence={relevantResult.evidence} />
            </div>
          )}

          {/* Company metadata */}
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 8, fontSize: 12 }}>
            {company.industry && (
              <div>
                <Text type="secondary" style={{ fontSize: 11 }}>Industry: </Text>
                <Text>{company.industry}</Text>
              </div>
            )}
            {company.employee_count != null && (
              <div>
                <Text type="secondary" style={{ fontSize: 11 }}>Employees: </Text>
                <Text>{company.employee_count.toLocaleString()}</Text>
              </div>
            )}
            {company.country && (
              <div>
                <Text type="secondary" style={{ fontSize: 11 }}>Country: </Text>
                <Text>{company.country}</Text>
              </div>
            )}
            {company.website && (
              <div>
                <a href={company.website.startsWith('http') ? company.website : `https://${company.website}`}
                  target="_blank" rel="noreferrer" style={{ fontSize: 11, color: 'var(--purple)' }}>
                  <LinkOutlined style={{ marginRight: 4 }} />
                  {company.website}
                </a>
              </div>
            )}
          </div>

          {/* Full stage timeline */}
          {stageResults.length > 1 && (
            <div>
              <Text type="secondary" style={{ fontSize: 11, fontWeight: 600 }}>Pipeline Journey</Text>
              <CompanyStageTimeline stageResults={stageResults} />
            </div>
          )}
        </div>
      ),
    };
  });

  return <Collapse items={items} style={{ background: 'transparent' }} />;
};

// ---------------------------------------------------------------------------
// Pipeline Funnel Tab (interactive)
// ---------------------------------------------------------------------------

const PipelineFunnelTab: React.FC<{ runId: string }> = ({ runId }) => {
  const [data, setData] = useState<StageSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [expandedStage, setExpandedStage] = useState<string | null>(null);
  const [stageCompanies, setStageCompanies] = useState<Company[]>([]);
  const [stageCompaniesLoading, setStageCompaniesLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    getStageSummary(runId)
      .then((res) => setData(res.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [runId]);

  const handleExpandStage = async (stageKey: string) => {
    if (expandedStage === stageKey) {
      setExpandedStage(null);
      setStageCompanies([]);
      return;
    }
    setExpandedStage(stageKey);
    setStageCompaniesLoading(true);
    try {
      const res = await getCompaniesByStage(runId, stageKey);
      setStageCompanies(res.data as Company[]);
    } catch {
      setStageCompanies([]);
    } finally {
      setStageCompaniesLoading(false);
    }
  };

  if (loading) {
    return <div style={{ textAlign: 'center', padding: 40, color: 'var(--g400)' }}>Loading funnel data...</div>;
  }

  if (!data || data.stages.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: 40, color: 'var(--g400)' }}>
        No stage summary data available. Stage-level tracking is available for pipeline runs using the signal-based pipeline.
      </div>
    );
  }

  const maxTotal = Math.max(...data.stages.map(s => s.total), 1);
  const firstTotal = data.stages[0]?.total ?? 0;
  const lastPassed = data.stages[data.stages.length - 1]?.passed ?? 0;
  const overallRate = firstTotal > 0 ? Math.round((lastPassed / firstTotal) * 100) : 0;

  return (
    <div>
      {/* ── Summary header ── */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 28, flexWrap: 'wrap', alignItems: 'stretch' }}>
        {[
          { label: 'DISCOVERED', value: firstTotal, color: 'var(--g800)', unit: 'companies' },
          { label: 'QUALIFIED', value: lastPassed, color: 'var(--green)', unit: 'companies' },
          {
            label: 'CONVERSION',
            value: `${overallRate}%`,
            color: overallRate >= 50 ? 'var(--green)' : overallRate >= 25 ? 'var(--amber)' : 'var(--red)',
            unit: 'overall',
          },
        ].map((stat) => (
          <div key={stat.label} style={{
            background: 'var(--g50)', borderRadius: 'var(--radius)',
            border: '1px solid var(--g200)', padding: '12px 20px', minWidth: 110,
          }}>
            <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--g400)', letterSpacing: '0.06em', marginBottom: 4 }}>
              {stat.label}
            </div>
            <div style={{ fontSize: 22, fontWeight: 700, color: stat.color, lineHeight: 1 }}>{stat.value}</div>
            <div style={{ fontSize: 11, color: 'var(--g400)', marginTop: 3 }}>{stat.unit}</div>
          </div>
        ))}
        {data.signal_mode && (
          <div style={{
            background: 'var(--g50)', borderRadius: 'var(--radius)',
            border: '1px solid var(--g200)', padding: '12px 20px', minWidth: 110,
          }}>
            <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--g400)', letterSpacing: '0.06em', marginBottom: 4 }}>
              SIGNAL MODE
            </div>
            <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--purple)', lineHeight: 1 }}>
              {data.signal_mode.charAt(0).toUpperCase() + data.signal_mode.slice(1)}
            </div>
            <div style={{ fontSize: 11, color: 'var(--g400)', marginTop: 3 }}>pipeline type</div>
          </div>
        )}
        {data.cached_companies > 0 && (
          <div style={{
            background: 'var(--g50)', borderRadius: 'var(--radius)',
            border: '1px solid var(--g200)', padding: '12px 20px', minWidth: 110,
          }}>
            <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--g400)', letterSpacing: '0.06em', marginBottom: 4 }}>
              CACHED
            </div>
            <div style={{ fontSize: 22, fontWeight: 700, color: '#1677ff', lineHeight: 1 }}>{data.cached_companies}</div>
            <div style={{ fontSize: 11, color: 'var(--g400)', marginTop: 3 }}>companies</div>
          </div>
        )}
      </div>

      {/* ── Funnel stages ── */}
      <div style={{ maxWidth: 860 }}>
        {data.stages.map((stage, idx) => {
          const display = getStageDisplay(stage.stage);
          const barWidth = Math.max((stage.total / maxTotal) * 100, 4);
          const passRate = stage.total > 0 ? Math.round((stage.passed / stage.total) * 100) : 0;
          const stageColor = FUNNEL_COLORS[stage.stage] || '#8c8c8c';
          const isExpanded = expandedStage === stage.stage;
          const nextStage = idx < data.stages.length - 1 ? data.stages[idx + 1] : null;
          const droppedOff = nextStage ? Math.max(stage.passed - nextStage.total, 0) : 0;
          const continuedRate = stage.passed > 0 && nextStage
            ? Math.round((nextStage.total / stage.passed) * 100) : 0;

          return (
            <div key={stage.stage}>
              {/* ── Stage row ── */}
              <div
                onClick={() => handleExpandStage(stage.stage)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 14,
                  padding: '12px 14px', borderRadius: 'var(--radius)',
                  border: `1px solid ${isExpanded ? 'var(--g200)' : 'transparent'}`,
                  background: isExpanded ? 'var(--g50)' : 'transparent',
                  cursor: 'pointer', transition: 'all 0.15s',
                }}
              >
                {/* Step badge */}
                <div style={{
                  width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
                  background: stageColor, color: '#fff',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontWeight: 700, fontSize: 11,
                }}>
                  {idx + 1}
                </div>

                {/* Stage name + bar */}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                    <span style={{ fontWeight: 600, fontSize: 13, color: 'var(--g800)' }}>{display.label}</span>
                    <span style={{ fontSize: 12, fontWeight: 700, color: stageColor }}>{stage.total}</span>
                    {stage.avg_score != null && (
                      <span style={{
                        fontSize: 11, color: getScoreColor(stage.avg_score),
                        background: 'var(--g100)', padding: '1px 7px', borderRadius: 10,
                      }}>
                        avg {Math.round(stage.avg_score)}
                      </span>
                    )}
                  </div>
                  {/* Track */}
                  <div style={{ height: 8, background: 'var(--g100)', borderRadius: 4, overflow: 'hidden', position: 'relative' }}>
                    {/* Pass fill */}
                    <div style={{
                      position: 'absolute', left: 0, top: 0, height: '100%',
                      width: `${barWidth * (stage.passed / Math.max(stage.total, 1))}%`,
                      background: stageColor, borderRadius: 4, transition: 'width 0.4s ease',
                    }} />
                    {/* Fail fill */}
                    {stage.failed > 0 && (
                      <div style={{
                        position: 'absolute', top: 0, height: '100%',
                        left: `${barWidth * (stage.passed / Math.max(stage.total, 1))}%`,
                        width: `${barWidth * (stage.failed / Math.max(stage.total, 1))}%`,
                        background: 'var(--red)', opacity: 0.55,
                      }} />
                    )}
                  </div>
                </div>

                {/* Stat pills */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
                  <span style={{
                    fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 10,
                    background: '#E6F7F0', color: 'var(--green)',
                  }}>✓ {stage.passed}</span>
                  {stage.failed > 0 && (
                    <span style={{
                      fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 10,
                      background: '#FDECEA', color: 'var(--red)',
                    }}>✗ {stage.failed}</span>
                  )}
                  {stage.promoted > 0 && (
                    <span style={{
                      fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 10,
                      background: '#EEF2FF', color: '#4F46E5',
                    }}>↑ {stage.promoted}</span>
                  )}
                  {stage.excluded > 0 && (
                    <span style={{
                      fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 10,
                      background: 'var(--g100)', color: 'var(--g500)',
                    }}>— {stage.excluded}</span>
                  )}
                  <span style={{
                    fontSize: 12, fontWeight: 700, minWidth: 40, textAlign: 'right',
                    color: passRate >= 75 ? 'var(--green)' : passRate >= 50 ? 'var(--amber)' : 'var(--red)',
                  }}>{passRate}%</span>
                  <span style={{ color: 'var(--g300)', fontSize: 10, marginLeft: 2 }}>
                    {isExpanded ? <UpOutlined /> : <DownOutlined />}
                  </span>
                </div>
              </div>

              {/* ── Expanded company list ── */}
              {isExpanded && (
                <div style={{
                  margin: '0 14px 4px 56px',
                  paddingLeft: 16,
                  borderLeft: `2px solid ${stageColor}30`,
                }}>
                  {stageCompaniesLoading ? (
                    <div style={{ textAlign: 'center', padding: 20, color: 'var(--g400)' }}>Loading companies…</div>
                  ) : (
                    <StageCompanyList companies={stageCompanies} stageKey={stage.stage} />
                  )}
                </div>
              )}

              {/* ── Drop-off connector ── */}
              {nextStage && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '2px 14px 2px 56px' }}>
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                    <div style={{ width: 1, height: 6, background: 'var(--g200)' }} />
                    <span style={{ color: 'var(--g300)', fontSize: 11, lineHeight: 1 }}>↓</span>
                    <div style={{ width: 1, height: 6, background: 'var(--g200)' }} />
                  </div>
                  <span style={{ fontSize: 11, color: 'var(--green)', fontWeight: 600 }}>
                    {nextStage.total} continued ({continuedRate}%)
                  </span>
                  {droppedOff > 0 && (
                    <span style={{ fontSize: 11, color: 'var(--g400)' }}>
                      · {droppedOff} dropped off
                    </span>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Run Summary Panel
// ---------------------------------------------------------------------------

const SOURCE_FRIENDLY_NAMES: Record<string, string> = {
  apollo_company_search: 'B2B Company Database',
  apollo_people_search: 'Professional Contact Database',
  exa_search: 'Business Intelligence',
  tavily_search: 'Market Research',
  duckduckgo_search: 'Web Research',
  hunter_domain_search: 'Email Discovery',
  hunter_email_finder: 'Email Verification',
  lusha_person_search: 'Phone Number Lookup',
  scrape_webpage: 'Company Website Analysis',
};

const SOURCE_DESCRIPTIONS: Record<string, string> = {
  apollo_company_search: 'Company profiles, industry data, and firmographics',
  apollo_people_search: 'Contact names, job titles, and professional details',
  exa_search: 'News coverage, funding rounds, and company intelligence',
  tavily_search: 'Press releases, financial data, and market trends',
  duckduckgo_search: 'LinkedIn profiles, job postings, and public web data',
  hunter_domain_search: 'Email patterns and domain-level contact discovery',
  hunter_email_finder: 'Verified professional email addresses',
  lusha_person_search: 'Direct phone numbers and mobile contacts',
  scrape_webpage: 'About pages, team pages, and careers information',
};

const SOURCE_COLORS: Record<string, string> = {
  apollo_company_search: '#1677ff', apollo_people_search: '#1677ff',
  exa_search: '#722ed1', tavily_search: '#fa8c16', duckduckgo_search: '#52c41a',
  hunter_domain_search: '#13c2c2', hunter_email_finder: '#13c2c2',
  lusha_person_search: '#eb2f96', scrape_webpage: '#fa541c',
};

const STEP_FRIENDLY: Record<string, { label: string; desc: string }> = {
  company_discovery: { label: 'Finding Companies', desc: 'Identified companies matching your criteria' },
  contact_discovery: { label: 'Finding Contacts', desc: 'Located decision-makers at each company' },
  enrichment: { label: 'Verifying Details', desc: 'Confirmed emails, phones, and LinkedIn profiles' },
  scoring: { label: 'Qualifying Leads', desc: 'Scored each company on signal strength' },
};

const RunSummaryPanel: React.FC<{ logs: PipelineLogEntry[]; companies: Company[] }> = ({ logs, companies }) => {
  const summary = useMemo(() => {
    const toolCalls = logs.filter(l => l.event_type === 'tool_start');

    const toolCounts: Record<string, number> = {};
    toolCalls.forEach(l => {
      const name = l.event_data.tool_name as string;
      toolCounts[name] = (toolCounts[name] || 0) + 1;
    });
    const sourceBreakdown = Object.entries(toolCounts).sort(([, a], [, b]) => b - a);
    const maxCount = sourceBreakdown.length > 0 ? sourceBreakdown[0][1] : 1;

    const stageCounts: Record<string, number> = {};
    toolCalls.forEach(l => {
      const stage = l.event_data.stage as string;
      if (stage) stageCounts[stage] = (stageCounts[stage] || 0) + 1;
    });

    let durationStr = '--';
    if (logs.length >= 2) {
      const first = new Date(logs[0].created_at).getTime();
      const last = new Date(logs[logs.length - 1].created_at).getTime();
      const diffMs = last - first;
      const diffMin = Math.floor(diffMs / 60000);
      const diffSec = Math.floor((diffMs % 60000) / 1000);
      durationStr = diffMin > 0 ? `${diffMin}m ${diffSec}s` : `${diffSec}s`;
    }

    const companiesWithScores = companies.filter(c => c.final_score != null || (c.bant_score && c.bant_score.total_score)).length;
    const companiesWithContacts = companies.filter(c => c.contacts.length > 0).length;
    const allContacts = companies.flatMap(c => c.contacts);
    const contactsWithEmail = allContacts.filter(c => c.email).length;
    const contactsWithPhone = allContacts.filter(c => c.phone).length;
    const contactsWithLinkedin = allContacts.filter(c => c.linkedin_url).length;

    let completedAt = '';
    if (logs.length > 0) {
      completedAt = new Date(logs[logs.length - 1].created_at).toLocaleString('en-US', {
        month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit',
      });
    }

    return {
      totalLookups: toolCalls.length,
      sourcesUsed: Object.keys(toolCounts).length,
      durationStr,
      completedAt,
      sourceBreakdown,
      maxCount,
      stageCounts,
      companiesWithScores,
      companiesWithContacts,
      contactsWithEmail,
      contactsWithPhone,
      contactsWithLinkedin,
      totalContacts: allContacts.length,
    };
  }, [logs, companies]);

  if (logs.length === 0) {
    return <div style={{ textAlign: 'center', padding: 20, color: 'var(--g400)' }}>No summary available.</div>;
  }

  const pctScored = companies.length > 0 ? Math.round((summary.companiesWithScores / companies.length) * 100) : 0;
  const pctWithContacts = companies.length > 0 ? Math.round((summary.companiesWithContacts / companies.length) * 100) : 0;
  const pctWithEmail = summary.totalContacts > 0 ? Math.round((summary.contactsWithEmail / summary.totalContacts) * 100) : 0;

  return (
    <div>
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
        gap: 12, marginBottom: 20,
      }}>
        <div style={{ background: 'var(--g50, #fafafa)', borderRadius: 8, padding: '14px 16px', border: '1px solid var(--g100, #f0f0f0)' }}>
          <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--purple)', letterSpacing: '-0.5px' }}>{summary.durationStr}</div>
          <Text type="secondary" style={{ fontSize: 11 }}>Time Taken</Text>
        </div>
        <div style={{ background: 'var(--g50, #fafafa)', borderRadius: 8, padding: '14px 16px', border: '1px solid var(--g100, #f0f0f0)' }}>
          <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--purple)', letterSpacing: '-0.5px' }}>{summary.sourcesUsed}</div>
          <Text type="secondary" style={{ fontSize: 11 }}>Sources Searched</Text>
        </div>
        <div style={{ background: 'var(--g50, #fafafa)', borderRadius: 8, padding: '14px 16px', border: '1px solid var(--g100, #f0f0f0)' }}>
          <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--purple)', letterSpacing: '-0.5px' }}>{summary.totalLookups}</div>
          <Text type="secondary" style={{ fontSize: 11 }}>Lookups Performed</Text>
        </div>
        <div style={{ background: 'var(--g50, #fafafa)', borderRadius: 8, padding: '14px 16px', border: '1px solid var(--g100, #f0f0f0)' }}>
          <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--g800)', letterSpacing: '-0.5px' }}>{pctScored}%</div>
          <Text type="secondary" style={{ fontSize: 11 }}>Companies Scored</Text>
        </div>
      </div>

      {summary.completedAt && (
        <div style={{ fontSize: 12, color: 'var(--g400)', marginBottom: 16 }}>
          Completed on {summary.completedAt}
        </div>
      )}

      <div style={{ display: 'flex', gap: 32, flexWrap: 'wrap' }}>
        <div style={{ flex: '1 1 300px' }}>
          <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 10, color: 'var(--g700)' }}>Where Your Data Came From</div>
          {summary.sourceBreakdown.map(([source, count]) => (
            <div key={source} style={{ marginBottom: 8 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 2 }}>
                <Text style={{ fontSize: 12, fontWeight: 600, color: 'var(--g700)' }}>
                  {SOURCE_FRIENDLY_NAMES[source] || source}
                </Text>
                <Text style={{ fontSize: 11, color: 'var(--g400)' }}>{count} {count === 1 ? 'lookup' : 'lookups'}</Text>
              </div>
              <div style={{ flex: 1, background: 'var(--g100, #f0f0f0)', borderRadius: 3, height: 6, overflow: 'hidden' }}>
                <div style={{
                  width: `${(count / summary.maxCount) * 100}%`,
                  height: '100%',
                  background: SOURCE_COLORS[source] || '#8c8c8c',
                  borderRadius: 3,
                }} />
              </div>
              <Text style={{ fontSize: 11, color: 'var(--g400)', lineHeight: 1.4 }}>
                {SOURCE_DESCRIPTIONS[source] || ''}
              </Text>
            </div>
          ))}
        </div>

        <div style={{ flex: '1 1 250px' }}>
          <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 10, color: 'var(--g700)' }}>What Was Done</div>
          {['company_discovery', 'contact_discovery', 'enrichment', 'scoring'].map(stage => {
            const info = STEP_FRIENDLY[stage];
            const count = summary.stageCounts[stage] || 0;
            return (
              <div key={stage} style={{ marginBottom: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Text style={{ fontSize: 12, fontWeight: 600, color: 'var(--g700)' }}>{info?.label || stage}</Text>
                  <Text style={{ fontSize: 11, color: 'var(--g400)' }}>{count} {count === 1 ? 'lookup' : 'lookups'}</Text>
                </div>
                <Text style={{ fontSize: 11, color: 'var(--g400)' }}>{info?.desc || ''}</Text>
              </div>
            );
          })}

          <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 8, marginTop: 16, color: 'var(--g700)' }}>Data Completeness</div>
          <div style={{ fontSize: 12, display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
                <Text type="secondary">Companies with contacts</Text>
                <Text style={{ fontWeight: 600 }}>{summary.companiesWithContacts}/{companies.length}</Text>
              </div>
              <div style={{ background: 'var(--g100, #f0f0f0)', borderRadius: 3, height: 4, overflow: 'hidden' }}>
                <div style={{ width: `${pctWithContacts}%`, height: '100%', background: 'var(--purple)', borderRadius: 3 }} />
              </div>
            </div>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
                <Text type="secondary">Contacts with email</Text>
                <Text style={{ fontWeight: 600 }}>{summary.contactsWithEmail}/{summary.totalContacts}</Text>
              </div>
              <div style={{ background: 'var(--g100, #f0f0f0)', borderRadius: 3, height: 4, overflow: 'hidden' }}>
                <div style={{ width: `${pctWithEmail}%`, height: '100%', background: '#13c2c2', borderRadius: 3 }} />
              </div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <Text type="secondary">Contacts with phone</Text>
              <Text style={{ fontWeight: 600 }}>{summary.contactsWithPhone}/{summary.totalContacts}</Text>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <Text type="secondary">Contacts with LinkedIn</Text>
              <Text style={{ fontWeight: 600 }}>{summary.contactsWithLinkedin}/{summary.totalContacts}</Text>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Main LeadsPage Component
// ---------------------------------------------------------------------------

const LeadsPage: React.FC = () => {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const { setCompanyId } = usePageContext();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [sortBy, setSortBy] = useState('final_score');
  const [pipelineRun, setPipelineRun] = useState<PipelineRun | null>(null);
  const [agentLogs, setAgentLogs] = useState<PipelineLogEntry[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<'companies' | 'funnel' | 'criteria' | 'summary'>('companies');
  const [promotedFilter, setPromotedFilter] = useState<'promoted' | 'all' | 'skipped'>('promoted');

  useEffect(() => {
    if (runId) {
      getPipelineStatus(runId).then(res => setPipelineRun(res.data));
      setLogsLoading(true);
      getPipelineLogs(runId)
        .then((res) => setAgentLogs(Array.isArray(res.data) ? res.data : []))
        .catch(() => setAgentLogs([]))
        .finally(() => setLogsLoading(false));
    }
  }, [runId]);

  useEffect(() => {
    if (!runId) return;
    setLoading(true);
    getLeadCompanies(runId, { sort_by: sortBy })
      .then((res) => {
        setCompanies(res.data);
      })
      .finally(() => setLoading(false));
  }, [runId, sortBy]);

  // Filter companies by promoted status for multi-step runs
  const isMultiStepRun = pipelineRun?.pipeline_mode === 'multi_step';
  const filteredCompanies = useMemo(() => {
    if (!isMultiStepRun) return companies;
    switch (promotedFilter) {
      case 'promoted':
        return companies.filter((c) => c.promoted === true);
      case 'skipped':
        return companies.filter((c) => c.promoted === false);
      case 'all':
      default:
        return companies;
    }
  }, [companies, promotedFilter, isMultiStepRun]);

  // One row per company — contacts are shown in the company detail view
  const flatRows: Array<{
    key: string | number;
    serial: number;
    company_name: string;
    website: string | null;
    industry: string | null;
    country: string | null;
    revenue_estimate: number | null;
    asset_value: number | null;
    final_score: number | null | undefined;
    final_rank: number | null | undefined;
    budget_signal_score: number | null | undefined;
    urgency_signal_score: number | null | undefined;
    deal_hotness_score: number | null | undefined;
    deal_hotness_tier: string | null | undefined;
    contacts_count: number;
    qualification: string | null;
    source: string | null;
    company: Company;
  }> = [];
  let serial = 1;
  filteredCompanies.forEach((company) => {
    flatRows.push({
      key: company.id,
      serial: serial++,
      company_name: company.name,
      website: company.website,
      industry: company.industry,
      country: company.country,
      revenue_estimate: company.revenue_estimate,
      asset_value: company.asset_value,
      final_score: company.final_score,
      final_rank: company.final_rank,
      budget_signal_score: company.budget_signal_score,
      urgency_signal_score: company.urgency_signal_score,
      deal_hotness_score: company.deal_hotness_score,
      deal_hotness_tier: company.deal_hotness_tier,
      contacts_count: company.contacts.length,
      qualification: company.qualification,
      source: company.source,
      company,
    });
  });

  // Summary stats
  const totalContacts = filteredCompanies.reduce((s, c) => s + c.contacts.length, 0);
  const avgFinalScore = filteredCompanies.length > 0
    ? (filteredCompanies.reduce((s, c) => s + (c.final_score || 0), 0) / filteredCompanies.length).toFixed(1)
    : '0';
  const highScoreCount = filteredCompanies.filter(c => (c.final_score || 0) >= 75).length;
  const medScoreCount = filteredCompanies.filter(c => {
    const s = c.final_score || 0;
    return s >= 50 && s < 75;
  }).length;
  const lowScoreCount = filteredCompanies.filter(c => {
    const s = c.final_score || 0;
    return s > 0 && s < 50;
  }).length;

  const cachedCount = filteredCompanies.filter(c => c.cached_from_run_id).length;

  const hotLeadCount = filteredCompanies.filter(c => c.deal_hotness_tier === 'hot').length;
  const warmLeadCount = filteredCompanies.filter(c => c.deal_hotness_tier === 'warm').length;

  // Multi-step summary counts
  const promotedCount = isMultiStepRun ? companies.filter((c) => c.promoted === true).length : 0;
  const totalDiscovered = isMultiStepRun ? companies.length : 0;

  const columns = [
    {
      title: '#',
      dataIndex: 'final_rank',
      width: 55,
      render: (rank: number | null | undefined, record: any) => {
        if (rank != null) return <Text style={{ fontWeight: 600, fontSize: 12 }}>#{rank}</Text>;
        return <Text type="secondary" style={{ fontSize: 12 }}>{record.serial}</Text>;
      },
    },
    {
      title: 'Company',
      dataIndex: 'company_name',
      width: 180,
      render: (name: string) => (
        <Text style={{ fontWeight: 600, fontSize: 13 }}>{name}</Text>
      ),
    },
    {
      title: 'Industry',
      dataIndex: 'industry',
      width: 130,
      render: (v: string | null) => v || '-',
    },
    {
      title: 'Country',
      dataIndex: 'country',
      width: 90,
      render: (v: string | null) => v || '-',
    },
    {
      title: 'Revenue',
      dataIndex: 'revenue_estimate',
      width: 100,
      sorter: (a: typeof flatRows[0], b: typeof flatRows[0]) => (a.revenue_estimate || 0) - (b.revenue_estimate || 0),
      render: (revenue: number | null) => {
        if (!revenue) return '-';
        if (revenue >= 1_000_000_000) return `$${(revenue / 1_000_000_000).toFixed(1)}B`;
        if (revenue >= 1_000_000) return `$${(revenue / 1_000_000).toFixed(0)}M`;
        return `$${revenue.toLocaleString()}`;
      },
    },
    {
      title: 'Asset Value',
      dataIndex: 'asset_value',
      width: 110,
      sorter: (a: typeof flatRows[0], b: typeof flatRows[0]) => (a.asset_value || 0) - (b.asset_value || 0),
      render: (assetValue: number | null) => {
        if (!assetValue) return '-';
        if (assetValue >= 1_000_000_000) return `$${(assetValue / 1_000_000_000).toFixed(1)}B`;
        if (assetValue >= 1_000_000) return `$${(assetValue / 1_000_000).toFixed(0)}M`;
        return `$${assetValue.toLocaleString()}`;
      },
    },
    {
      title: 'Final Score',
      dataIndex: 'final_score',
      width: 110,
      render: (score: number | null | undefined, record: any) => (
        <FinalScoreDisplay score={score} rank={record.final_rank} />
      ),
    },
    {
      title: 'Budget',
      dataIndex: 'budget_signal_score',
      width: 85,
      render: (score: number | null | undefined) => (
        <SignalScoreBar score={score} label="Budget Signal" />
      ),
    },
    {
      title: 'Urgency',
      dataIndex: 'urgency_signal_score',
      width: 85,
      render: (score: number | null | undefined) => (
        <SignalScoreBar score={score} label="Urgency Signal" />
      ),
    },
    {
      title: 'Hotness',
      dataIndex: 'deal_hotness_tier',
      width: 100,
      render: (_tier: string | null | undefined, record: any) => (
        <HotnessIndicator tier={record.deal_hotness_tier} score={record.deal_hotness_score} />
      ),
    },
    {
      title: 'Contacts',
      dataIndex: 'contacts_count',
      width: 90,
      render: (count: number) =>
        count > 0
          ? <Tag color="blue" style={{ fontSize: 12 }}>{count}</Tag>
          : <Text type="secondary">--</Text>,
    },
  ];

  return (
    <div style={{ padding: '28px 32px', maxWidth: 1400, margin: '0 auto', width: '100%' }}>
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <div className="section-label">Lead Generation</div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <Button size="small" onClick={() => navigate('/dashboard')} style={{ fontSize: 12 }}>
              &larr; Back
            </Button>
            <h1 className="page-title">Search Results</h1>
            {pipelineRun?.icp_name && (
              <Tag color="purple" style={{ fontSize: 13, padding: '2px 12px' }}>{pipelineRun.icp_name}</Tag>
            )}
          </div>
          <Space>
            {pipelineRun?.icp_config_id && (
              <Button
                icon={<PlayCircleOutlined />}
                size="small"
                onClick={async () => {
                  try {
                    const res = await startPipeline({
                      icp_config_id: pipelineRun.icp_config_id,
                      options: { max_contacts_per_company: 5 },
                    });
                    message.success('New search started with same criteria');
                    navigate(`/pipeline/${res.data.id}`);
                  } catch (err: any) {
                    message.error(err?.response?.data?.detail || 'Failed to start search');
                  }
                }}
              >
                Run Again
              </Button>
            )}
            {runId && (
              <Popconfirm
                title="Delete this search result?"
                description="This will permanently remove all companies, contacts, and scores."
                onConfirm={async () => {
                  try {
                    await deletePipelineRun(runId);
                    message.success('Search result deleted');
                    navigate('/dashboard');
                  } catch {
                    message.error('Failed to delete search result');
                  }
                }}
                okText="Delete"
                cancelText="Cancel"
                okButtonProps={{ danger: true }}
              >
                <Button danger icon={<DeleteOutlined />} size="small">
                  Delete
                </Button>
              </Popconfirm>
            )}
          </Space>
        </div>
      </div>

      {/* Summary Bar */}
      <div className="summary-bar" style={{ marginBottom: 24 }}>
        <div className="summary-item">
          <div className="val">{filteredCompanies.length}</div>
          <div className="lbl">Companies</div>
        </div>
        {pipelineRun?.match_strictness && pipelineRun.match_strictness !== 'moderate' && (
          <div className="summary-item">
            <div className="val">
              <Tag color={pipelineRun.match_strictness === 'strict' ? 'red' : 'blue'} style={{ fontSize: 13, padding: '2px 10px', margin: 0 }}>
                {pipelineRun.match_strictness === 'strict' ? 'Strict' : 'Relaxed'}
              </Tag>
            </div>
            <div className="lbl">Match Mode</div>
          </div>
        )}
        {isMultiStepRun && (
          <div className="summary-item">
            <div className="val" style={{ fontSize: 15, fontWeight: 600 }}>
              {promotedCount} / {totalDiscovered}
            </div>
            <div className="lbl">Promoted / Discovered</div>
          </div>
        )}
        <div className="summary-item">
          <div className="val">{totalContacts}</div>
          <div className="lbl">Contacts</div>
        </div>
        <div className="summary-item">
          <div className="val">{avgFinalScore}</div>
          <div className="lbl">Avg Final Score</div>
        </div>
        <div className="summary-item">
          <div className="val" style={{ fontSize: 15, fontWeight: 600 }}>
            <span style={{ color: '#52c41a' }}>{highScoreCount}</span>
            {' / '}
            <span style={{ color: '#faad14' }}>{medScoreCount}</span>
            {' / '}
            <span style={{ color: '#ff4d4f' }}>{lowScoreCount}</span>
          </div>
          <div className="lbl">High / Med / Low</div>
        </div>
        {(hotLeadCount > 0 || warmLeadCount > 0) && (
          <div className="summary-item">
            <div className="val" style={{ fontSize: 15, fontWeight: 600 }}>
              <span style={{ color: '#f5222d' }}>{hotLeadCount}</span>
              {' / '}
              <span style={{ color: '#fa8c16' }}>{warmLeadCount}</span>
            </div>
            <div className="lbl">Hot / Warm Leads</div>
          </div>
        )}
        {cachedCount > 0 && (
          <div className="summary-item">
            <div className="val">
              <Badge count={cachedCount} style={{ backgroundColor: '#1677ff' }} />
            </div>
            <div className="lbl">Cached</div>
          </div>
        )}
      </div>

      {/* Tabs Navigation */}
      <div className="tabs">
        <div
          className={`tab ${activeTab === 'companies' ? 'active' : ''}`}
          onClick={() => setActiveTab('companies')}
        >
          Companies
        </div>
        <div
          className={`tab ${activeTab === 'funnel' ? 'active' : ''}`}
          onClick={() => setActiveTab('funnel')}
        >
          Pipeline Funnel
        </div>
        <div
          className={`tab ${activeTab === 'criteria' ? 'active' : ''}`}
          onClick={() => setActiveTab('criteria')}
        >
          Search Criteria
        </div>
        <div
          className={`tab ${activeTab === 'summary' ? 'active' : ''}`}
          onClick={() => setActiveTab('summary')}
        >
          Search Summary
        </div>
      </div>

      {/* Tab: Companies */}
      {activeTab === 'companies' && (
        <Card
          title="Qualified Leads"
          extra={
            <Space>
              {isMultiStepRun && (
                <Select value={promotedFilter} onChange={setPromotedFilter} style={{ width: 160 }}>
                  <Select.Option value="promoted">Promoted Only</Select.Option>
                  <Select.Option value="all">All Discovered</Select.Option>
                  <Select.Option value="skipped">Skipped</Select.Option>
                </Select>
              )}
              <Select value={sortBy} onChange={setSortBy} style={{ width: 170 }}>
                <Select.Option value="final_score">Sort by Final Score</Select.Option>
                <Select.Option value="budget_signal_score">Sort by Budget Score</Select.Option>
                <Select.Option value="urgency_signal_score">Sort by Urgency Score</Select.Option>
                <Select.Option value="deal_hotness_score">Sort by Deal Hotness</Select.Option>
                <Select.Option value="qualification">Sort by Category</Select.Option>
                <Select.Option value="company_name">Sort by Company</Select.Option>
              </Select>
              <Dropdown.Button
                icon={<DownOutlined />}
                onClick={() => window.open(getExportUrl(runId!, 'csv', 'final'))}
                menu={{
                  items: [
                    { key: 'csv-all', label: 'All Companies (CSV)', onClick: () => window.open(getExportUrl(runId!, 'csv', 'all')) },
                  ],
                }}
              >
                <DownloadOutlined /> CSV
              </Dropdown.Button>
              <Dropdown.Button
                type="primary"
                icon={<DownOutlined />}
                onClick={() => window.open(getExportUrl(runId!, 'xlsx', 'final'))}
                menu={{
                  items: [
                    { key: 'xlsx-all', label: 'All Companies (Excel)', onClick: () => window.open(getExportUrl(runId!, 'xlsx', 'all')) },
                  ],
                }}
              >
                <DownloadOutlined /> Export Excel
              </Dropdown.Button>
            </Space>
          }
        >
          <Table
            columns={columns}
            dataSource={flatRows}
            loading={loading}
            pagination={{ pageSize: 50, showSizeChanger: true }}
            scroll={{ x: 1200 }}
            onRow={(record) => ({
              onClick: () => {
                const companyId = record.company.id;
                setCompanyId(companyId);
                navigate(`/leads/${runId}/company/${companyId}`, { state: { company: record.company, icp_name: pipelineRun?.icp_name ?? null } });
              },
              style: { cursor: 'pointer' },
            })}
            size="small"
          />
        </Card>
      )}

      {/* Tab: Pipeline Funnel */}
      {activeTab === 'funnel' && (
        <Card title="Pipeline Funnel" extra={
          <Tag color="purple" icon={<ThunderboltOutlined />} style={{ fontSize: 12 }}>
            Stage-by-Stage Breakdown
          </Tag>
        }>
          {runId ? (
            <PipelineFunnelTab runId={runId} />
          ) : (
            <div style={{ textAlign: 'center', padding: 40, color: 'var(--g400)' }}>
              No pipeline run selected.
            </div>
          )}
        </Card>
      )}

      {/* Tab: Search Criteria */}
      {activeTab === 'criteria' && (
        <Card title="Search Criteria">
          {pipelineRun?.icp_config ? (
            <ICPConfigPanel
              config={pipelineRun.icp_config as unknown as Record<string, unknown>}
              name={pipelineRun.icp_name ?? null}
              description={(pipelineRun.icp_config as any)?.description ?? null}
            />
          ) : (
            <div style={{ textAlign: 'center', padding: 40, color: 'var(--g400)' }}>
              No search criteria available
            </div>
          )}
        </Card>
      )}

      {/* Tab: Search Summary */}
      {activeTab === 'summary' && (
        <Card
          title="Search Summary"
          extra={
            runId && (
              <Button type="link" size="small" icon={<ToolOutlined />}
                onClick={() => navigate(`/pipeline/${runId}`)}>
                View detailed agent logs &rarr;
              </Button>
            )
          }
        >
          {logsLoading ? (
            <div style={{ textAlign: 'center', padding: 40, color: 'var(--g400)' }}>Loading summary...</div>
          ) : (
            <RunSummaryPanel logs={agentLogs} companies={companies} />
          )}
        </Card>
      )}

    </div>
  );
};

export default LeadsPage;
