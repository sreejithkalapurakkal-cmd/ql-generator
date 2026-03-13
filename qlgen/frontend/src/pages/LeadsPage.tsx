import React, { useEffect, useState, useMemo } from 'react';
import {
  Card, Table, Tag, Button, Space, Tooltip, Descriptions, Select, Typography,
  Popconfirm, message, Badge, Collapse,
} from 'antd';
import {
  DownloadOutlined, ToolOutlined, DeleteOutlined, PlayCircleOutlined,
  ThunderboltOutlined, DatabaseOutlined,
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
// Cache indicator
// ---------------------------------------------------------------------------

const CacheIndicator: React.FC<{ company: Company }> = ({ company }) => {
  if (!company.cached_from_run_id) return null;
  const freshness = company.data_freshness || 'cached';
  const color = freshness === 'fresh' ? 'green' : freshness === 'stale' ? 'orange' : 'blue';
  return (
    <Tooltip title={`Cached from previous run. Freshness: ${freshness}`}>
      <Tag color={color} style={{ fontSize: 10, padding: '0 4px', lineHeight: '16px', marginLeft: 4 }}>
        <DatabaseOutlined style={{ marginRight: 2 }} />
        {freshness}
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
        {revenueStr && (
          <div>
            <Text type="secondary" style={{ fontSize: 11 }}>Revenue Est.</Text>
            <div style={{ fontWeight: 600, fontSize: 14 }}>{revenueStr}</div>
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

const ICPConfigPanel: React.FC<{ config: Record<string, unknown> }> = ({ config }) => {
  const cfg = config as any;
  return (
    <Descriptions bordered size="small" column={2}>
      <Descriptions.Item label="Target Offerings" span={2}>
        {cfg?.target_offering?.join(', ') || cfg?.target_capability?.offerings?.join(', ') || '-'}
      </Descriptions.Item>
      <Descriptions.Item label="Countries" span={2}>
        {cfg?.regions?.countries?.join(', ') || cfg?.firmographic_details?.geography?.countries?.join(', ') || '-'}
      </Descriptions.Item>
      <Descriptions.Item label="Industries" span={2}>
        {(cfg?.industry_types || cfg?.firmographic_details?.industry_types)?.map((i: any) =>
          `${i.vertical}${i.sub_vertical ? ` / ${i.sub_vertical}` : ''}`
        ).join(', ') || '-'}
      </Descriptions.Item>
      <Descriptions.Item label="Employees">
        {cfg?.company_size?.employees_min?.toLocaleString() || cfg?.firmographic_details?.employee_range?.min?.toLocaleString() || '?'}
        &ndash;
        {cfg?.company_size?.employees_max?.toLocaleString() || cfg?.firmographic_details?.employee_range?.max?.toLocaleString() || '?'}
      </Descriptions.Item>
      <Descriptions.Item label="Revenue">
        {cfg?.company_size?.revenue_currency || cfg?.firmographic_details?.revenue_range?.currency || 'USD'}{' '}
        {cfg?.company_size?.revenue_min?.toLocaleString() || cfg?.firmographic_details?.revenue_range?.min?.toLocaleString() || '?'}
        &ndash;
        {cfg?.company_size?.revenue_max?.toLocaleString() || cfg?.firmographic_details?.revenue_range?.max?.toLocaleString() || '?'}
      </Descriptions.Item>
      <Descriptions.Item label="Tech Signals (Positive)">
        {cfg?.technology_maturity?.signals?.join(', ') || cfg?.firmographic_details?.technology_maturity?.positive_signals?.join(', ') || '-'}
      </Descriptions.Item>
      <Descriptions.Item label="Tech Signals (Negative)">
        {cfg?.technology_maturity?.negative_signals?.join(', ') || cfg?.firmographic_details?.technology_maturity?.negative_signals?.join(', ') || '-'}
      </Descriptions.Item>
      <Descriptions.Item label="Infrastructure" span={2}>
        {cfg?.infrastructure_readiness?.indicators?.join(', ') || cfg?.firmographic_details?.infrastructure_readiness?.indicators?.join(', ') || '-'}
      </Descriptions.Item>
      <Descriptions.Item label="Budget Signals" span={2}>
        {cfg?.budget_signals?.signals?.join(', ') || '-'}
      </Descriptions.Item>
      <Descriptions.Item label="Urgency Signals" span={2}>
        {cfg?.urgency_signals?.signals?.join(', ') || '-'}
      </Descriptions.Item>
      <Descriptions.Item label="Target Roles" span={2}>
        {cfg?.leadership_traits?.target_roles?.join(', ') || cfg?.authority_roles?.target_roles?.join(', ') || '-'}
      </Descriptions.Item>
    </Descriptions>
  );
};

// ---------------------------------------------------------------------------
// Pipeline Funnel Tab
// ---------------------------------------------------------------------------

const FUNNEL_COLORS: Record<string, string> = {
  company_discovery: '#1677ff',
  firmographic_filter: '#722ed1',
  budget_signal: '#52c41a',
  urgency_signal: '#fa8c16',
  contact_discovery: '#13c2c2',
  contact_enrichment: '#eb2f96',
  scoring: '#f5222d',
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
            {item.source_url && (
              <a href={item.source_url} target="_blank" rel="noreferrer" style={{ fontSize: 11, color: 'var(--purple)' }}>
                <LinkOutlined style={{ marginRight: 4 }} />
                {item.source_url.length > 60 ? item.source_url.substring(0, 60) + '...' : item.source_url}
              </a>
            )}
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

  return (
    <div>
      {/* Header info */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 24, flexWrap: 'wrap' }}>
        {data.signal_mode && (
          <div style={{
            background: 'var(--g50, #fafafa)', borderRadius: 8,
            padding: '10px 16px', border: '1px solid var(--g100, #f0f0f0)',
          }}>
            <Text type="secondary" style={{ fontSize: 11 }}>Signal Mode</Text>
            <div style={{ fontWeight: 600, fontSize: 14 }}>
              <Tag color="purple">{data.signal_mode}</Tag>
            </div>
          </div>
        )}
        {data.cached_companies > 0 && (
          <div style={{
            background: 'var(--g50, #fafafa)', borderRadius: 8,
            padding: '10px 16px', border: '1px solid var(--g100, #f0f0f0)',
          }}>
            <Text type="secondary" style={{ fontSize: 11 }}>Cached Companies</Text>
            <div style={{ fontWeight: 600, fontSize: 14 }}>
              <Badge count={data.cached_companies} style={{ backgroundColor: '#1677ff' }} />
            </div>
          </div>
        )}
      </div>

      {/* Funnel visualization */}
      <div style={{ maxWidth: 700 }}>
        {data.stages.map((stage, idx) => {
          const display = getStageDisplay(stage.stage);
          const barWidth = Math.max((stage.total / maxTotal) * 100, 8);
          const passRate = stage.total > 0 ? Math.round((stage.passed / stage.total) * 100) : 0;
          const funnelColor = FUNNEL_COLORS[stage.stage] || '#8c8c8c';
          const isExpanded = expandedStage === stage.stage;

          return (
            <div key={stage.stage} style={{ marginBottom: 20 }}>
              {/* Stage header */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{
                    width: 24, height: 24, borderRadius: '50%', background: funnelColor,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    color: '#fff', fontWeight: 700, fontSize: 11,
                  }}>
                    {idx + 1}
                  </div>
                  <Text style={{ fontWeight: 600, fontSize: 13, color: 'var(--g800)' }}>
                    {display.label}
                  </Text>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  {stage.avg_score != null && (
                    <Text style={{ fontSize: 12, color: getScoreColor(stage.avg_score) }}>
                      Avg Score: {Math.round(stage.avg_score)}
                    </Text>
                  )}
                </div>
              </div>

              {/* Funnel bar (clickable) */}
              <div
                onClick={() => handleExpandStage(stage.stage)}
                style={{
                  width: `${barWidth}%`, background: funnelColor, borderRadius: 6,
                  padding: '8px 14px', color: '#fff', fontSize: 12, fontWeight: 600,
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  minHeight: 36, transition: 'width 0.3s ease',
                  marginLeft: `${((100 - barWidth) / 2)}%`,
                  cursor: 'pointer',
                  opacity: isExpanded ? 1 : 0.85,
                  boxShadow: isExpanded ? `0 2px 8px ${funnelColor}40` : 'none',
                }}
              >
                <span>{stage.total} companies</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  {passRate}% passed
                  {isExpanded ? <UpOutlined style={{ fontSize: 10 }} /> : <DownOutlined style={{ fontSize: 10 }} />}
                </span>
              </div>

              {/* Stage metrics */}
              <div style={{
                display: 'flex', gap: 16, marginTop: 6, justifyContent: 'center', flexWrap: 'wrap',
              }}>
                <Text style={{ fontSize: 11, color: '#52c41a' }}>
                  Passed: {stage.passed}
                </Text>
                <Text style={{ fontSize: 11, color: '#ff4d4f' }}>
                  Failed: {stage.failed}
                </Text>
                {stage.promoted > 0 && (
                  <Text style={{ fontSize: 11, color: '#1677ff' }}>
                    Promoted: {stage.promoted}
                  </Text>
                )}
                {stage.excluded > 0 && (
                  <Text style={{ fontSize: 11, color: '#8c8c8c' }}>
                    Excluded: {stage.excluded}
                  </Text>
                )}
              </div>

              {/* Expanded stage detail */}
              {isExpanded && (
                <div style={{
                  marginTop: 12,
                  padding: '12px 0',
                  borderTop: `2px solid ${funnelColor}20`,
                }}>
                  {stageCompaniesLoading ? (
                    <div style={{ textAlign: 'center', padding: 20, color: 'var(--g400)' }}>
                      Loading companies...
                    </div>
                  ) : (
                    <StageCompanyList companies={stageCompanies} stageKey={stage.stage} />
                  )}
                </div>
              )}

              {/* Connector arrow */}
              {idx < data.stages.length - 1 && (
                <div style={{ textAlign: 'center', color: 'var(--g300)', fontSize: 16, margin: '4px 0' }}>
                  |
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
  const [expandedRowKeys, setExpandedRowKeys] = useState<(string | number)[]>([]);
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
        if (res.data.length > 0) {
          const firstCompany = res.data[0];
          if (firstCompany.contacts.length > 0) {
            setExpandedRowKeys([`${firstCompany.id}-${firstCompany.contacts[0].id}`]);
          } else {
            setExpandedRowKeys([firstCompany.id]);
          }
        }
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

  // Flatten companies + contacts into rows for the main table
  const flatRows: Array<{
    key: string | number;
    serial: number;
    company_name: string;
    website: string | null;
    industry: string | null;
    country: string | null;
    final_score: number | null | undefined;
    final_rank: number | null | undefined;
    budget_signal_score: number | null | undefined;
    urgency_signal_score: number | null | undefined;
    contact_name: string;
    designation: string | null;
    linkedin: string | null;
    email: string | null;
    phone: string | null;
    qualification: string | null;
    source: string | null;
    company: Company;
    contact: any;
  }> = [];
  let serial = 1;
  filteredCompanies.forEach((company) => {
    if (company.contacts.length > 0) {
      company.contacts.forEach((contact) => {
        flatRows.push({
          key: `${company.id}-${contact.id}`,
          serial: serial++,
          company_name: company.name,
          website: company.website,
          industry: company.industry,
          country: company.country,
          final_score: company.final_score,
          final_rank: company.final_rank,
          budget_signal_score: company.budget_signal_score,
          urgency_signal_score: company.urgency_signal_score,
          contact_name: contact.full_name || '',
          designation: contact.designation,
          linkedin: contact.linkedin_url,
          email: contact.email,
          phone: contact.phone,
          qualification: company.qualification,
          source: contact.source || company.source,
          company,
          contact,
        });
      });
    } else {
      flatRows.push({
        key: company.id,
        serial: serial++,
        company_name: company.name,
        website: company.website,
        industry: company.industry,
        country: company.country,
        final_score: company.final_score,
        final_rank: company.final_rank,
        budget_signal_score: company.budget_signal_score,
        urgency_signal_score: company.urgency_signal_score,
        contact_name: '-',
        designation: '-',
        linkedin: null,
        email: null,
        phone: null,
        qualification: company.qualification,
        source: company.source,
        company,
        contact: null,
      });
    }
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
      render: (name: string, record: any) => (
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <Text style={{ fontWeight: 600, fontSize: 13 }}>{name}</Text>
          {record.company?.cached_from_run_id && (
            <CacheIndicator company={record.company} />
          )}
        </div>
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
      title: 'Contact',
      dataIndex: 'contact_name',
      width: 140,
      render: (name: string) => name === '-' ? <Text type="secondary">--</Text> : name,
    },
    { title: 'Title', dataIndex: 'designation', width: 150, render: (v: string | null) => v || '-' },
    {
      title: 'Email',
      dataIndex: 'email',
      width: 180,
      render: (e: string | null) => e || '-',
    },
    {
      title: 'LinkedIn',
      dataIndex: 'linkedin',
      width: 90,
      render: (url: string | null) =>
        url ? (
          <a href={url} target="_blank" rel="noreferrer" style={{ color: 'var(--purple)', fontSize: 12 }}>
            Profile
          </a>
        ) : '-',
    },
    {
      title: 'Phone',
      dataIndex: 'phone',
      width: 120,
      render: (p: string | null) =>
        p ? (
          <a href={`tel:${p}`} style={{ color: 'var(--purple)', fontSize: 12 }}>
            {p}
          </a>
        ) : '-',
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
                <Select.Option value="qualification">Sort by Category</Select.Option>
                <Select.Option value="company_name">Sort by Company</Select.Option>
              </Select>
              <Button icon={<DownloadOutlined />} onClick={() => window.open(getExportUrl(runId!, 'csv'))}>
                CSV
              </Button>
              <Button type="primary" icon={<DownloadOutlined />} onClick={() => window.open(getExportUrl(runId!, 'xlsx'))}>
                Export Excel
              </Button>
            </Space>
          }
        >
          <Table
            columns={columns}
            dataSource={flatRows}
            loading={loading}
            pagination={{ pageSize: 50, showSizeChanger: true }}
            scroll={{ x: 1560 }}
            expandable={{
              expandedRowKeys,
              onExpandedRowsChange: (keys) => {
                setExpandedRowKeys(keys as (string | number)[]);
                const lastKey = keys.length > 0 ? String(keys[keys.length - 1]) : null;
                if (lastKey) {
                  const companyId = lastKey.includes('-') ? lastKey.split('-')[0] : lastKey;
                  setCompanyId(companyId);
                } else {
                  setCompanyId(null);
                }
              },
              expandedRowRender: (record) => (
                <div>
                  {record.company && <CompanyInsightsPanel company={record.company} />}
                  <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 8, marginTop: 12, color: 'var(--g800)' }}>
                    Stage Results
                  </div>
                  {record.company?.stage_results && record.company.stage_results.length > 0 ? (
                    <SignalDetailPanel company={record.company} />
                  ) : (
                    <Text type="secondary">No stage-level results available for this company.</Text>
                  )}
                </div>
              ),
            }}
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
            <ICPConfigPanel config={pipelineRun.icp_config as unknown as Record<string, unknown>} />
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
