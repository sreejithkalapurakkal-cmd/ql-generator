import React, { useEffect, useState, useRef, useCallback, useMemo } from 'react';
import {
  Card, Steps, Result, Button, Typography, Tag, Timeline, Badge, Table,
  Checkbox, message, Collapse, Tooltip, Popconfirm, Radio, Space, Drawer, Tabs,
} from 'antd';
import type { RadioChangeEvent } from 'antd';
import {
  SearchOutlined,
  TeamOutlined,
  DatabaseOutlined,
  BarChartOutlined,
  LoadingOutlined,
  ToolOutlined,
  BulbOutlined,
  RocketOutlined,
  ApiOutlined,
  GlobalOutlined,
  MailOutlined,
  PhoneOutlined,
  FileSearchOutlined,
  ClockCircleOutlined,
  CheckCircleOutlined,
  EyeOutlined,
  StopOutlined,
  DollarOutlined,
  ThunderboltOutlined,
  SafetyCertificateOutlined,
  AuditOutlined,
} from '@ant-design/icons';
import { useParams, useNavigate } from 'react-router-dom';
import {
  getPipelineStatus,
  getPipelineLogs,
  cancelPipeline,
  promoteFirmographic,
  promoteFirstSignal,
  promoteSignals,
  getCompaniesByStage,
} from '../api/pipelineApi';
import { PipelineRun, PipelineLogEntry, Company } from '../types';
import { API_BASE } from '../api/client';
import { getAccessToken } from '../context/AuthContext';
import { EvidenceDisplay, EvidenceSignalSummary } from '../components/EvidenceDisplay';

const { Text, Paragraph } = Typography;

// ════════════════════════════════════════════════════════════════
// Constants & Helpers
// ════════════════════════════════════════════════════════════════

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

const DimensionTags: React.FC<{ rawData: Record<string, unknown> | null | undefined; showCount?: boolean }> = ({ rawData, showCount }) => {
  if (!rawData) return null;
  const evidence = (rawData.dimension_evidence || rawData) as Record<string, unknown>;
  const dims = Object.entries(DIMENSION_LABELS);
  const rendered: React.ReactNode[] = [];
  let matchedCount = 0;
  dims.forEach(([key, label]) => {
    const dim = evidence[key] as Record<string, unknown> | undefined;
    if (!dim) return;
    const score = typeof dim.score === 'number' ? dim.score : null;
    const dimEvidence = (dim.evidence || dim.reasoning || '') as string;
    if (score === null) return;
    if (score > 0) matchedCount++;
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
      <Text type="secondary" style={{ fontSize: 11 }}>Dimension Scores</Text>
      <div style={{ marginTop: 4 }}>{rendered}</div>
      {showCount && rendered.length > 0 && (
        <div style={{ fontSize: 11, color: 'var(--g500)', marginTop: 4 }}>
          {matchedCount} of {rendered.length} dimensions matched
        </div>
      )}
    </div>
  );
};

// ════════════════════════════════════════════════════════════════
// Live Company Dashboard (shown in Companies tab during running)
// ════════════════════════════════════════════════════════════════

const STAGE_LABELS: Record<string, string> = {
  industry_discovery: 'Industry Discovery',
  firmographic_fit: 'Firmographic Fit',
  budget_signals: 'Budget Signals',
  urgency_signals: 'Urgency Signals',
  contact_discovery: 'Contact Discovery',
  final_scoring: 'Final Scoring',
};

// Stages that process companies one-by-one (emit company_start SSE events)
const PER_COMPANY_STAGES = new Set(['budget_signals', 'urgency_signals', 'contact_discovery']);

interface LiveCompanyDashboardProps {
  companies: Company[];
  currentCompany: { name: string; index: number; total: number; stage: string } | null;
  stageFilter: string;
  onStageFilterChange: (stage: string) => void;
}

const LiveCompanyDashboard: React.FC<LiveCompanyDashboardProps> = ({
  companies,
  currentCompany,
  stageFilter,
  onStageFilterChange,
}) => {
  // Derive which stages have data
  const stagesWithData = React.useMemo(() => {
    const seen = new Set<string>();
    companies.forEach((c) => {
      (c.stage_results || []).forEach((sr) => seen.add(sr.stage));
    });
    // Always include industry_discovery if there are any companies
    if (companies.length > 0) seen.add('industry_discovery');
    const order = ['industry_discovery', 'firmographic_fit', 'budget_signals', 'urgency_signals', 'contact_discovery', 'final_scoring'];
    return order.filter((s) => seen.has(s));
  }, [companies]);

  // ── "All Companies" view ──────────────────────────────────────
  const allViewColumns = React.useMemo(() => {
    const hasICP = companies.some((c) => c.icp_match_score != null);
    const hasBudget = companies.some((c) => c.budget_signal_score != null);
    const hasUrgency = companies.some((c) => c.urgency_signal_score != null);
    const hasContacts = companies.some((c) => c.contacts && c.contacts.length > 0);

    const cols: object[] = [
      {
        title: 'Company',
        dataIndex: 'name',
        width: 180,
        render: (name: string, record: Company) => (
          <div>
            <div style={{ fontWeight: 600, fontSize: 13 }}>{name}</div>
            {record.website && (
              <a
                href={record.website.startsWith('http') ? record.website : `https://${record.website}`}
                target="_blank"
                rel="noreferrer"
                style={{ fontSize: 11, color: 'var(--purple)' }}
              >
                {record.website}
              </a>
            )}
          </div>
        ),
      },
      {
        title: 'Stage',
        dataIndex: 'current_stage',
        width: 140,
        render: (stage: string | null) => {
          if (!stage) return <Tag style={{ fontSize: 11 }}>Discovered</Tag>;
          const color = stageColors[stage] || '#8c8c8c';
          return (
            <Tag style={{ fontSize: 11, color, borderColor: color, background: `${color}18` }}>
              {STAGE_LABELS[stage] || stage.replace(/_/g, ' ')}
            </Tag>
          );
        },
      },
    ];

    if (hasICP) {
      cols.push({
        title: 'ICP Score',
        dataIndex: 'icp_match_score',
        width: 90,
        sorter: (a: Company, b: Company) => (a.icp_match_score || 0) - (b.icp_match_score || 0),
        render: (score: number | null) => {
          if (score == null) return <span style={{ color: 'var(--g300)' }}>—</span>;
          const color = score >= 70 ? '#52c41a' : score >= 50 ? '#faad14' : '#ff4d4f';
          return <span style={{ fontWeight: 700, color }}>{Math.round(score)}</span>;
        },
      });
    }

    if (hasBudget) {
      cols.push({
        title: 'Budget',
        dataIndex: 'budget_signal_score',
        width: 80,
        render: (score: number | null) => {
          if (score == null) return <span style={{ color: 'var(--g300)' }}>—</span>;
          const color = score >= 70 ? '#52c41a' : score >= 50 ? '#faad14' : '#ff4d4f';
          return <span style={{ fontWeight: 600, color }}>{Math.round(score)}</span>;
        },
      });
    }

    if (hasUrgency) {
      cols.push({
        title: 'Urgency',
        dataIndex: 'urgency_signal_score',
        width: 80,
        render: (score: number | null) => {
          if (score == null) return <span style={{ color: 'var(--g300)' }}>—</span>;
          const color = score >= 70 ? '#52c41a' : score >= 50 ? '#faad14' : '#ff4d4f';
          return <span style={{ fontWeight: 600, color }}>{Math.round(score)}</span>;
        },
      });
    }

    if (hasContacts) {
      cols.push({
        title: 'Contacts',
        key: 'contacts_count',
        width: 80,
        render: (_: unknown, record: Company) => {
          const count = record.contacts?.length || 0;
          return count > 0 ? <Tag color="green" style={{ fontSize: 11 }}>{count}</Tag> : <span style={{ color: 'var(--g300)' }}>—</span>;
        },
      });
    }

    cols.push({
      title: 'Status',
      key: 'status',
      width: 120,
      render: (_: unknown, record: Company) => {
        const isInProgress = currentCompany?.name === record.name;
        if (isInProgress) {
          return (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--purple)' }}>
              <LoadingOutlined style={{ fontSize: 12 }} />
              <span style={{ fontSize: 12, fontWeight: 600 }}>In Progress</span>
            </div>
          );
        }
        const latestResult = (record.stage_results || []).slice().reverse()[0];
        if (!latestResult) {
          return <Tag style={{ fontSize: 11, color: 'var(--g400)', borderColor: 'var(--g200)' }}>Pending</Tag>;
        }
        if (latestResult.status === 'passed') {
          return <Tag color="success" style={{ fontSize: 11 }}>Passed</Tag>;
        }
        if (latestResult.status === 'failed') {
          return <Tag color="error" style={{ fontSize: 11 }}>Failed</Tag>;
        }
        return <Tag style={{ fontSize: 11 }}>{latestResult.status}</Tag>;
      },
    });

    return cols;
  }, [companies, currentCompany]);

  // ── "By Stage" view ───────────────────────────────────────────
  const renderByStage = () => {
    const selectedStage = stageFilter;
    const isPerCompany = PER_COMPANY_STAGES.has(selectedStage);

    // Partition companies
    const inProgress: Company[] = [];
    const processed: Company[] = [];
    const pending: Company[] = [];

    companies.forEach((c) => {
      const isActiveCompany = isPerCompany && currentCompany?.name === c.name;
      const hasResult = (c.stage_results || []).some((sr) => sr.stage === selectedStage);

      if (isActiveCompany) {
        inProgress.push(c);
      } else if (hasResult) {
        processed.push(c);
      } else {
        pending.push(c);
      }
    });

    const stageLabel = STAGE_LABELS[selectedStage] || selectedStage.replace(/_/g, ' ');

    // Score column for the selected stage
    const getStageScore = (c: Company): number | null => {
      const sr = (c.stage_results || []).find((r) => r.stage === selectedStage);
      return sr?.score ?? null;
    };
    const getStageStatus = (c: Company): string | null => {
      const sr = (c.stage_results || []).find((r) => r.stage === selectedStage);
      return sr?.status ?? null;
    };
    const getStageReasoning = (c: Company): string | null => {
      const sr = (c.stage_results || []).find((r) => r.stage === selectedStage);
      return sr?.reasoning ?? null;
    };

    const priorScoreCols = () => {
      const cols: object[] = [];
      if (selectedStage !== 'industry_discovery') {
        cols.push({
          title: 'ICP Score',
          key: 'icp',
          width: 90,
          render: (_: unknown, record: Company) => {
            const s = record.icp_match_score;
            if (s == null) return <span style={{ color: 'var(--g300)' }}>—</span>;
            const color = s >= 70 ? '#52c41a' : s >= 50 ? '#faad14' : '#ff4d4f';
            return <span style={{ fontWeight: 600, color }}>{Math.round(s)}</span>;
          },
        });
      }
      if (['urgency_signals', 'contact_discovery', 'final_scoring'].includes(selectedStage)) {
        cols.push({
          title: 'Budget',
          key: 'budget',
          width: 80,
          render: (_: unknown, record: Company) => {
            const s = record.budget_signal_score;
            if (s == null) return <span style={{ color: 'var(--g300)' }}>—</span>;
            const color = s >= 70 ? '#52c41a' : s >= 50 ? '#faad14' : '#ff4d4f';
            return <span style={{ fontWeight: 600, color }}>{Math.round(s)}</span>;
          },
        });
      }
      if (['contact_discovery', 'final_scoring'].includes(selectedStage)) {
        cols.push({
          title: 'Urgency',
          key: 'urgency',
          width: 80,
          render: (_: unknown, record: Company) => {
            const s = record.urgency_signal_score;
            if (s == null) return <span style={{ color: 'var(--g300)' }}>—</span>;
            const color = s >= 70 ? '#52c41a' : s >= 50 ? '#faad14' : '#ff4d4f';
            return <span style={{ fontWeight: 600, color }}>{Math.round(s)}</span>;
          },
        });
      }
      return cols;
    };

    const baseCompanyCol = {
      title: 'Company',
      dataIndex: 'name',
      width: 160,
      render: (name: string, record: Company) => (
        <div>
          <div style={{ fontWeight: 600, fontSize: 13 }}>{name}</div>
          {record.website && (
            <a
              href={record.website.startsWith('http') ? record.website : `https://${record.website}`}
              target="_blank"
              rel="noreferrer"
              style={{ fontSize: 11, color: 'var(--purple)' }}
            >
              {record.website}
            </a>
          )}
        </div>
      ),
    };

    const stageScoreCol = {
      title: `${stageLabel} Score`,
      key: 'stage_score',
      width: 120,
      render: (_: unknown, record: Company) => {
        const score = getStageScore(record);
        const status = getStageStatus(record);
        const reasoning = getStageReasoning(record);
        if (score == null) return <span style={{ color: 'var(--g300)' }}>—</span>;
        const color = score >= 70 ? '#52c41a' : score >= 50 ? '#faad14' : '#ff4d4f';
        return (
          <Tooltip title={reasoning || undefined}>
            <span>
              <span style={{ fontWeight: 700, color }}>{Math.round(score)}</span>
              {' '}
              {status === 'passed'
                ? <Tag color="success" style={{ fontSize: 10 }}>Passed</Tag>
                : <Tag color="error" style={{ fontSize: 10 }}>Failed</Tag>}
            </span>
          </Tooltip>
        );
      },
    };

    const collapseItems = [];

    // In Progress section (only for per-company stages)
    if (isPerCompany && inProgress.length > 0) {
      collapseItems.push({
        key: 'in-progress',
        label: (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <LoadingOutlined style={{ color: 'var(--purple)' }} />
            <span style={{ fontWeight: 600, color: 'var(--purple)' }}>In Progress (1)</span>
          </div>
        ),
        children: (
          <Table
            columns={[baseCompanyCol, ...priorScoreCols()]}
            dataSource={inProgress}
            rowKey="id"
            pagination={false}
            size="small"
            showHeader={true}
          />
        ),
      });
    }

    // Processed section
    collapseItems.push({
      key: 'processed',
      label: (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <CheckCircleOutlined style={{ color: '#52c41a' }} />
          <span style={{ fontWeight: 600 }}>Processed ({processed.length})</span>
        </div>
      ),
      children: processed.length > 0 ? (
        <Table
          columns={[baseCompanyCol, ...priorScoreCols(), stageScoreCol]}
          dataSource={processed}
          rowKey="id"
          pagination={false}
          size="small"
        />
      ) : (
        <div style={{ padding: '16px 0', color: 'var(--g400)', textAlign: 'center', fontSize: 13 }}>
          No companies have completed this stage yet.
        </div>
      ),
    });

    // Pending section
    if (pending.length > 0) {
      collapseItems.push({
        key: 'pending',
        label: (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <ClockCircleOutlined style={{ color: 'var(--g400)' }} />
            <span style={{ fontWeight: 600, color: 'var(--g500)' }}>Pending ({pending.length})</span>
          </div>
        ),
        children: (
          <Table
            columns={[baseCompanyCol, ...priorScoreCols()]}
            dataSource={pending}
            rowKey="id"
            pagination={false}
            size="small"
            rowClassName={() => 'pending-company-row'}
          />
        ),
      });
    }

    return (
      <Collapse
        defaultActiveKey={isPerCompany ? ['in-progress', 'processed'] : ['processed']}
        items={collapseItems}
        size="small"
        style={{ background: 'transparent' }}
      />
    );
  };

  if (companies.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--g400)' }}>
        Waiting for companies to be discovered...
      </div>
    );
  }

  return (
    <div>
      {/* Stage filter strip */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 12 }}>
        <Tag
          color={stageFilter === 'all' ? 'purple' : undefined}
          style={{ cursor: 'pointer', fontWeight: stageFilter === 'all' ? 600 : 400 }}
          onClick={() => onStageFilterChange('all')}
        >
          All ({companies.length})
        </Tag>
        {stagesWithData.map((stage) => (
          <Tag
            key={stage}
            color={stageFilter === stage ? 'purple' : undefined}
            style={{
              cursor: 'pointer',
              fontWeight: stageFilter === stage ? 600 : 400,
              borderColor: stageFilter === stage ? undefined : stageColors[stage],
              color: stageFilter === stage ? undefined : stageColors[stage],
            }}
            onClick={() => onStageFilterChange(stage)}
          >
            {STAGE_LABELS[stage] || stage.replace(/_/g, ' ')}
          </Tag>
        ))}
      </div>

      {stageFilter === 'all' ? (
        <Table
          columns={allViewColumns as Parameters<typeof Table>[0]['columns']}
          dataSource={companies}
          rowKey="id"
          pagination={false}
          size="small"
          scroll={{ x: 500 }}
          rowClassName={(record: any) =>
            currentCompany?.name === record.name ? 'live-company-active-row' : ''
          }
        />
      ) : (
        renderByStage()
      )}
    </div>
  );
};

// Map tool names to icons for the activity log
const toolIcons: Record<string, React.ReactNode> = {
  apollo_company_search: <SearchOutlined />,
  apollo_people_search: <TeamOutlined />,
  exa_search: <GlobalOutlined />,
  tavily_search: <FileSearchOutlined />,
  duckduckgo_search: <GlobalOutlined />,
  hunter_domain_search: <MailOutlined />,
  hunter_email_finder: <MailOutlined />,
  lusha_person_search: <PhoneOutlined />,
  scrape_webpage: <ApiOutlined />,
};

// Map tool names to tag colors
const toolColors: Record<string, string> = {
  apollo_company_search: 'blue',
  apollo_people_search: 'blue',
  exa_search: 'purple',
  tavily_search: 'orange',
  duckduckgo_search: 'green',
  hunter_domain_search: 'cyan',
  hunter_email_finder: 'cyan',
  lusha_person_search: 'magenta',
  scrape_webpage: 'volcano',
};

const stageColors: Record<string, string> = {
  industry_discovery: '#1890ff',
  firmographic_fit: '#722ed1',
  budget_signals: '#fa8c16',
  urgency_signals: '#eb2f96',
  contact_discovery: '#52c41a',
  final_scoring: '#13c2c2',
  completed: '#52c41a',
};

const friendlyResultSummary = (toolName: string, preview: string): string => {
  if (!preview) return 'Done';
  const orgMatch = preview.match(/"organizations"\s*:\s*\[/);
  const peopleMatch = preview.match(/"people"\s*:\s*\[/);
  if (orgMatch) {
    const count = (preview.match(/"name"/g) || []).length;
    return count > 0 ? `Found ${count} matching companies` : 'Search complete';
  }
  if (peopleMatch) {
    const count = (preview.match(/"name"/g) || []).length;
    return count > 0 ? `Found ${count} contacts` : 'Search complete';
  }
  if (toolName.includes('hunter_email')) return 'Email verification complete';
  if (toolName.includes('lusha')) return 'Phone lookup complete';
  if (toolName.includes('scrape')) return 'Website analysis complete';
  return 'Data collected successfully';
};

const friendlyErrorMessage = (_toolName: string, error: string): string => {
  const lower = (error || '').toLowerCase();
  if (lower.includes('rate limit') || lower.includes('429') || lower.includes('quota'))
    return 'Data source rate limit reached -- switching to alternative source';
  if (lower.includes('404') || lower.includes('not found'))
    return 'No data found at this source -- trying another approach';
  if (lower.includes('timeout') || lower.includes('timed out'))
    return 'Source took too long to respond -- moving on';
  if (lower.includes('unauthorized') || lower.includes('401') || lower.includes('403'))
    return 'Access issue with data source -- using backup source';
  return 'Data source temporarily unavailable -- trying alternative';
};

// ════════════════════════════════════════════════════════════════
// Types
// ════════════════════════════════════════════════════════════════

type SignalMode = 'both' | 'budget_first' | 'urgency_first';

type ReviewGateType =
  | 'firmographic'       // Gate 1: after firmographic fit
  | 'first_signal'       // Gate 2a: after first signal in serial mode
  | 'second_signal'      // Gate 2b: after second signal in serial mode
  | 'signal_review';     // Gate 2: after both signals (parallel mode)

interface ActivityEntry {
  id: number;
  type: 'tool_start' | 'agent_reasoning' | 'stage_update' | 'tool_result' | 'tool_error' | 'company_start' | 'company_stage_result';
  timestamp: Date;
  toolName?: string;
  displayName?: string;
  context?: string;
  toolCallNumber?: number;
  text?: string;
  stage?: string;
  progress?: number;
  message?: string;
  resultPreview?: string;
  success?: boolean;
  errorMessage?: string;
  companyName?: string;
  companyIndex?: number;
  totalCompanies?: number;
  // company_stage_result fields
  score?: number;
  status?: string;
  reasoning?: string;
}

// ════════════════════════════════════════════════════════════════
// Dynamic Stepper Configuration
// ════════════════════════════════════════════════════════════════

interface StepDef {
  key: string;
  title: string;
  icon: React.ReactNode;
}

function getStepperStages(signalMode: SignalMode | null): StepDef[] {
  const base: StepDef[] = [
    { key: 'industry_discovery', title: 'Industry Discovery', icon: <SearchOutlined /> },
    { key: 'firmographic_fit', title: 'Firmographic Fit', icon: <DatabaseOutlined /> },
    { key: 'review_firmographic', title: 'Review & Select', icon: <EyeOutlined /> },
  ];

  if (!signalMode) {
    // Before mode selection: show generic remaining steps
    return [
      ...base,
      { key: 'signal_research', title: 'Signal Research', icon: <BulbOutlined /> },
      { key: 'contact_discovery', title: 'Contact Discovery', icon: <TeamOutlined /> },
      { key: 'final_scoring', title: 'Final Ranking', icon: <BarChartOutlined /> },
    ];
  }

  if (signalMode === 'both') {
    return [
      ...base,
      { key: 'budget_urgency_signals', title: 'Budget + Urgency Signals', icon: <DollarOutlined /> },
      { key: 'review_signals', title: 'Review Signals', icon: <AuditOutlined /> },
      { key: 'contact_discovery', title: 'Contact Discovery', icon: <TeamOutlined /> },
      { key: 'final_scoring', title: 'Final Ranking', icon: <BarChartOutlined /> },
    ];
  }

  if (signalMode === 'budget_first') {
    return [
      ...base,
      { key: 'budget_signals', title: 'Budget Signals', icon: <DollarOutlined /> },
      { key: 'review_budget_signals', title: 'Review Budget', icon: <AuditOutlined /> },
      { key: 'urgency_signals', title: 'Urgency Signals', icon: <ThunderboltOutlined /> },
      { key: 'review_urgency_signals', title: 'Review Urgency', icon: <AuditOutlined /> },
      { key: 'contact_discovery', title: 'Contact Discovery', icon: <TeamOutlined /> },
      { key: 'final_scoring', title: 'Final Ranking', icon: <BarChartOutlined /> },
    ];
  }

  // urgency_first
  return [
    ...base,
    { key: 'urgency_signals', title: 'Urgency Signals', icon: <ThunderboltOutlined /> },
    { key: 'review_urgency_signals', title: 'Review Urgency', icon: <AuditOutlined /> },
    { key: 'budget_signals', title: 'Budget Signals', icon: <DollarOutlined /> },
    { key: 'review_budget_signals', title: 'Review Budget', icon: <AuditOutlined /> },
    { key: 'contact_discovery', title: 'Contact Discovery', icon: <TeamOutlined /> },
    { key: 'final_scoring', title: 'Final Ranking', icon: <BarChartOutlined /> },
  ];
}

/** Map the current SSE stage name to a stepper key for index matching */
function mapStageToStepKey(sseStage: string, signalMode: SignalMode | null): string {
  // Direct match for most cases
  const directMapping: Record<string, string> = {
    industry_discovery: 'industry_discovery',
    firmographic_fit: 'firmographic_fit',
    review_firmographic: 'review_firmographic',
    contact_discovery: 'contact_discovery',
    final_scoring: 'final_scoring',
    completed: 'completed',
    review_signals: 'review_signals',
    review_budget_signals: 'review_budget_signals',
    review_urgency_signals: 'review_urgency_signals',
  };

  if (directMapping[sseStage]) return directMapping[sseStage];

  // Budget/urgency stages
  if (sseStage === 'budget_signals') {
    return signalMode === 'both' ? 'budget_urgency_signals' : 'budget_signals';
  }
  if (sseStage === 'urgency_signals') {
    return signalMode === 'both' ? 'budget_urgency_signals' : 'urgency_signals';
  }

  // Generic signal research (before mode is chosen)
  if (sseStage === 'signal_research') return 'signal_research';

  return sseStage;
}

// ════════════════════════════════════════════════════════════════
// Main Component
// ════════════════════════════════════════════════════════════════

const PipelinePage: React.FC = () => {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();

  // Core state
  const [run, setRun] = useState<PipelineRun | null>(null);
  const [sseMessage, setSseMessage] = useState('Starting search...');
  const [sseStage, setSseStage] = useState('pending');
  const [activityLog, setActivityLog] = useState<ActivityEntry[]>([]);
  const [toolCallCount, setToolCallCount] = useState(0);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const eventSourceRef = useRef<EventSource | null>(null);
  const logContainerRef = useRef<HTMLDivElement | null>(null);
  const entryIdRef = useRef(0);
  const startTimeRef = useRef<Date>(new Date());
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Review gate state
  const [activeReviewGate, setActiveReviewGate] = useState<ReviewGateType | null>(null);
  const [reviewCompanies, setReviewCompanies] = useState<Company[]>([]);
  const [selectedCompanyIds, setSelectedCompanyIds] = useState<Set<string>>(new Set());
  const [promoting, setPromoting] = useState(false);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [cancelling, setCancelling] = useState(false);

  // Signal mode selection (Gate 1)
  const [signalMode, setSignalMode] = useState<SignalMode | null>(null);
  const [selectedSignalMode, setSelectedSignalMode] = useState<SignalMode>('both');

  // Signal type context for first/second signal reviews
  const [currentSignalType, setCurrentSignalType] = useState<string | null>(null);

  // Live progress tracking
  const [currentCompany, setCurrentCompany] = useState<{
    name: string;
    index: number;
    total: number;
    stage: string;
  } | null>(null);

  // Left panel resize
  const [leftPanelWidth, setLeftPanelWidth] = useState(300);
  const isResizingRef = useRef(false);
  const startXRef = useRef(0);
  const startWidthRef = useRef(300);

  // Live companies tab
  const [liveCompanies, setLiveCompanies] = useState<Company[]>([]);
  const [rightTab, setRightTab] = useState<'log' | 'companies'>('log');
  const [stageFilter, setStageFilter] = useState<string>('all');

  // Stage history drawer
  const [viewingStageHistory, setViewingStageHistory] = useState<string | null>(null);
  const [stageHistoryCompanies, setStageHistoryCompanies] = useState<Company[]>([]);
  const [stageHistoryLoading, setStageHistoryLoading] = useState(false);

  // ════════════════════════════════════════
  // Activity log helpers
  // ════════════════════════════════════════

  const addEntry = useCallback((entry: Omit<ActivityEntry, 'id' | 'timestamp'>) => {
    const newEntry: ActivityEntry = {
      ...entry,
      id: ++entryIdRef.current,
      timestamp: new Date(),
    };
    setActivityLog((prev) => [...prev, newEntry]);
  }, []);

  // Merge consecutive agent_reasoning entries
  const mergedActivityLog = useMemo(() => {
    const result: ActivityEntry[] = [];
    for (const entry of activityLog) {
      if (
        entry.type === 'agent_reasoning' &&
        result.length > 0 &&
        result[result.length - 1].type === 'agent_reasoning'
      ) {
        const prev = result[result.length - 1];
        result[result.length - 1] = {
          ...prev,
          text: (prev.text || '') + ' ' + (entry.text || ''),
        };
      } else {
        result.push(entry);
      }
    }
    return result;
  }, [activityLog]);

  // Auto-scroll log to bottom
  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [activityLog]);

  // ════════════════════════════════════════
  // Left panel resize handlers
  // ════════════════════════════════════════

  const handleResizeStart = useCallback((e: React.MouseEvent) => {
    isResizingRef.current = true;
    startXRef.current = e.clientX;
    startWidthRef.current = leftPanelWidth;
    e.preventDefault();
  }, [leftPanelWidth]);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizingRef.current) return;
      const delta = e.clientX - startXRef.current;
      const newWidth = Math.min(600, Math.max(240, startWidthRef.current + delta));
      setLeftPanelWidth(newWidth);
    };
    const handleMouseUp = () => {
      isResizingRef.current = false;
    };
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, []);

  // ════════════════════════════════════════
  // Data loading
  // ════════════════════════════════════════

  const loadCompaniesForReview = useCallback(async (stage?: string) => {
    if (!runId) return;
    setReviewLoading(true);
    try {
      const res = await getCompaniesByStage(runId, stage);
      const companies = res.data as Company[];
      setReviewCompanies(companies);
      // Pre-select all by default
      setSelectedCompanyIds(new Set(companies.map((c) => c.id)));
    } catch {
      message.error('Failed to load companies for review');
    } finally {
      setReviewLoading(false);
    }
  }, [runId]);

  // ════════════════════════════════════════
  // SSE Connection
  // ════════════════════════════════════════

  const connectSSE = useCallback((targetRunId: string) => {
    const token = getAccessToken();
    const es = new EventSource(`${API_BASE}/pipeline/${targetRunId}/stream?token=${token}`);
    eventSourceRef.current = es;

    es.addEventListener('stage_update', (event) => {
      const data = JSON.parse(event.data);
      setSseStage(data.stage);
      setSseMessage(data.message || 'Agent is working...');
      setCurrentCompany(null);
      addEntry({
        type: 'stage_update',
        stage: data.stage,
        progress: data.progress,
        message: data.message,
      });
    });

    es.addEventListener('tool_start', (event) => {
      const data = JSON.parse(event.data);
      setToolCallCount(data.tool_call_number || 0);
      addEntry({
        type: 'tool_start',
        toolName: data.tool_name,
        displayName: data.display_name,
        context: data.context,
        toolCallNumber: data.tool_call_number,
        stage: data.stage,
      });
    });

    es.addEventListener('agent_reasoning', (event) => {
      const data = JSON.parse(event.data);
      addEntry({
        type: 'agent_reasoning',
        text: data.text,
        stage: data.stage,
      });
    });

    es.addEventListener('tool_result', (event) => {
      const data = JSON.parse(event.data);
      addEntry({
        type: 'tool_result',
        toolName: data.tool_name,
        resultPreview: data.result_preview,
        success: data.success,
        stage: data.stage,
        toolCallNumber: data.tool_call_number,
      });
    });

    es.addEventListener('tool_error', (event) => {
      const data = JSON.parse(event.data);
      addEntry({
        type: 'tool_error',
        toolName: data.tool_name,
        errorMessage: data.error_message,
        stage: data.stage,
      });
    });

    es.addEventListener('company_start', (event) => {
      const data = JSON.parse(event.data);
      setSseMessage(`Processing ${data.company_name} (${data.company_index}/${data.total_companies})...`);
      setCurrentCompany({
        name: data.company_name,
        index: data.company_index,
        total: data.total_companies,
        stage: data.stage || '',
      });
      addEntry({
        type: 'company_start',
        companyName: data.company_name,
        companyIndex: data.company_index,
        totalCompanies: data.total_companies,
        progress: data.progress,
      });
    });

    es.addEventListener('company_stage_result', (event) => {
      const data = JSON.parse(event.data);
      addEntry({
        type: 'company_stage_result',
        companyName: data.company_name,
        stage: data.stage,
        score: data.score,
        status: data.status,
        reasoning: data.reasoning,
      });
    });

    // ── Review Gate Events ──

    es.addEventListener('awaiting_firmographic_review', (event) => {
      const data = JSON.parse(event.data);
      setSseStage('review_firmographic');
      setSseMessage(`Firmographic fit complete: ${data.companies_passed ?? data.total ?? 0} companies passed. Review and select companies to continue.`);
      setActiveReviewGate('firmographic');
      loadCompaniesForReview('firmographic_fit');
      getPipelineStatus(targetRunId).then((res) => setRun(res.data));
      es.close();
    });

    es.addEventListener('awaiting_first_signal_review', (event) => {
      const data = JSON.parse(event.data);
      const sigType = data.signal_type || '';
      setCurrentSignalType(sigType);
      setSseStage(`review_${sigType}`);
      setSseMessage(`${sigType.replace(/_/g, ' ')} analysis complete for ${data.companies_scored} companies. Review results.`);
      setActiveReviewGate('first_signal');
      loadCompaniesForReview(sigType);
      getPipelineStatus(targetRunId).then((res) => {
        setRun(res.data);
        if (res.data.signal_mode) setSignalMode(res.data.signal_mode as SignalMode);
      });
      es.close();
    });

    es.addEventListener('awaiting_second_signal_review', (event) => {
      const data = JSON.parse(event.data);
      const sigType = data.signal_type || '';
      setCurrentSignalType(sigType);
      setSseStage(`review_${sigType}`);
      setSseMessage(`${sigType.replace(/_/g, ' ')} analysis complete for ${data.companies_scored} companies. Final signal review.`);
      setActiveReviewGate('second_signal');
      loadCompaniesForReview(sigType);
      getPipelineStatus(targetRunId).then((res) => {
        setRun(res.data);
        if (res.data.signal_mode) setSignalMode(res.data.signal_mode as SignalMode);
      });
      es.close();
    });

    es.addEventListener('awaiting_signal_review', (event) => {
      const data = JSON.parse(event.data);
      setSseStage('review_signals');
      setSseMessage(`Signal analysis complete. Budget avg: ${data.avg_budget ?? 'N/A'}, Urgency avg: ${data.avg_urgency ?? 'N/A'}. Review results.`);
      setActiveReviewGate('signal_review');
      loadCompaniesForReview('signals');
      getPipelineStatus(targetRunId).then((res) => {
        setRun(res.data);
        if (res.data.signal_mode) setSignalMode(res.data.signal_mode as SignalMode);
      });
      es.close();
    });

    // ── Terminal Events ──

    es.addEventListener('completed', (event) => {
      const data = JSON.parse(event.data);
      setSseStage('completed');
      setSseMessage(`Completed: ${data.companies_found} companies, ${data.contacts_found} contacts`);
      setActiveReviewGate(null);
      addEntry({
        type: 'stage_update',
        stage: 'completed',
        progress: 100,
        message: `Search complete -- found ${data.companies_found} companies and ${data.contacts_found} contacts`,
      });
      getPipelineStatus(targetRunId).then((res) => setRun(res.data));
      es.close();
    });

    es.addEventListener('cancelled', (event) => {
      const data = JSON.parse(event.data);
      setSseStage('cancelled');
      setSseMessage(`Cancelled: ${data.companies_found} companies found before cancellation`);
      setCancelling(false);
      setActiveReviewGate(null);
      addEntry({
        type: 'stage_update',
        stage: 'cancelled',
        message: `Pipeline cancelled -- ${data.companies_found} companies found before cancellation`,
      });
      getPipelineStatus(targetRunId).then((res) => setRun(res.data));
      es.close();
    });

    es.addEventListener('error', (event) => {
      try {
        const data = JSON.parse((event as MessageEvent).data);
        setSseMessage(`Error: ${data.message}`);
        addEntry({
          type: 'stage_update',
          stage: 'error',
          message: `Error: ${data.message}`,
        });
      } catch {
        // SSE connection error
      }
      es.close();
    });

    es.onerror = () => {
      es.close();
      const interval = setInterval(() => {
        getPipelineStatus(targetRunId).then((res) => {
          setRun(res.data);
          if (res.data.status === 'completed' || res.data.status === 'failed' || res.data.status === 'cancelled') {
            clearInterval(interval);
          } else if (res.data.status === 'awaiting_review') {
            clearInterval(interval);
            // Determine which review gate based on current_stage
            const cs = res.data.current_stage;
            if (res.data.signal_mode) setSignalMode(res.data.signal_mode as SignalMode);
            if (cs === 'review_firmographic') {
              setActiveReviewGate('firmographic');
              setSseStage('review_firmographic');
              loadCompaniesForReview('firmographic_fit');
            } else if (cs === 'review_signals') {
              setActiveReviewGate('signal_review');
              setSseStage('review_signals');
              loadCompaniesForReview('signals');
            } else if (cs?.startsWith('review_')) {
              const sigType = cs.replace('review_', '');
              setCurrentSignalType(sigType);
              setSseStage(cs);
              const phase = res.data.signal_phase;
              if (phase === 'first_signal_done') {
                setActiveReviewGate('first_signal');
              } else {
                setActiveReviewGate('second_signal');
              }
              loadCompaniesForReview(sigType);
            } else {
              setActiveReviewGate('firmographic');
              setSseStage('review_firmographic');
              loadCompaniesForReview('firmographic_fit');
            }
          }
        });
      }, 5000);
    };

    return es;
  }, [addEntry, loadCompaniesForReview]);

  // ════════════════════════════════════════
  // Load persisted logs for terminal states
  // ════════════════════════════════════════

  useEffect(() => {
    if (!runId || !run) return;
    const isTerminal = ['completed', 'failed', 'cancelled', 'awaiting_review'].includes(run.status);
    if (isTerminal) {
      getPipelineLogs(runId).then((res) => {
        const entries: ActivityEntry[] = res.data.map((log: PipelineLogEntry, i: number) => ({
          id: i + 1,
          type: (log.event_data.type as ActivityEntry['type']) || 'stage_update',
          timestamp: new Date(log.created_at),
          toolName: log.event_data.tool_name as string | undefined,
          displayName: log.event_data.display_name as string | undefined,
          context: log.event_data.context as string | undefined,
          toolCallNumber: log.event_data.tool_call_number as number | undefined,
          text: log.event_data.text as string | undefined,
          stage: log.event_data.stage as string | undefined,
          progress: log.event_data.progress as number | undefined,
          message: log.event_data.message as string | undefined,
          resultPreview: log.event_data.result_preview as string | undefined,
          success: log.event_data.success as boolean | undefined,
          errorMessage: log.event_data.error_message as string | undefined,
          companyName: log.event_data.company_name as string | undefined,
          companyIndex: log.event_data.company_index as number | undefined,
          totalCompanies: log.event_data.total_companies as number | undefined,
          score: log.event_data.score as number | undefined,
          status: log.event_data.status as string | undefined,
          reasoning: log.event_data.reasoning as string | undefined,
        }));
        setActivityLog(entries);
        const toolEntries = entries.filter((e) => e.type === 'tool_start');
        setToolCallCount(toolEntries.length);
        entryIdRef.current = entries.length;
      });
    }
  }, [runId, run?.status]);

  // ════════════════════════════════════════
  // Initial load + SSE connection
  // ════════════════════════════════════════

  useEffect(() => {
    if (!runId) return;
    startTimeRef.current = new Date();

    timerRef.current = setInterval(() => {
      setElapsedSeconds(Math.floor((new Date().getTime() - startTimeRef.current.getTime()) / 1000));
    }, 1000);

    getPipelineStatus(runId).then((res) => {
      setRun(res.data);
      if (res.data.signal_mode) setSignalMode(res.data.signal_mode as SignalMode);

      if (res.data.status === 'awaiting_review') {
        const cs = res.data.current_stage;
        if (cs === 'review_firmographic') {
          setActiveReviewGate('firmographic');
          setSseStage('review_firmographic');
          loadCompaniesForReview('firmographic_fit');
        } else if (cs === 'review_signals') {
          setActiveReviewGate('signal_review');
          setSseStage('review_signals');
          loadCompaniesForReview('signals');
        } else if (cs?.startsWith('review_')) {
          const sigType = cs.replace('review_', '');
          setCurrentSignalType(sigType);
          setSseStage(cs);
          const phase = res.data.signal_phase;
          if (phase === 'first_signal_done') {
            setActiveReviewGate('first_signal');
          } else {
            setActiveReviewGate('second_signal');
          }
          loadCompaniesForReview(sigType);
        } else {
          setActiveReviewGate('firmographic');
          setSseStage('review_firmographic');
          loadCompaniesForReview('firmographic_fit');
        }
        return;
      }

      if (res.data.status !== 'completed' && res.data.status !== 'failed' && res.data.status !== 'cancelled') {
        connectSSE(runId);
      }
    });

    return () => {
      eventSourceRef.current?.close();
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [runId, connectSSE, loadCompaniesForReview]);

  // ════════════════════════════════════════
  // Live companies polling (while running)
  // ════════════════════════════════════════

  useEffect(() => {
    if (!runId || run?.status !== 'running') return;
    const fetchCompanies = async () => {
      try {
        const res = await getCompaniesByStage(runId);
        setLiveCompanies(res.data as Company[]);
      } catch {
        // Silently ignore polling errors
      }
    };
    fetchCompanies();
    const pollInterval = setInterval(fetchCompanies, 6000);
    return () => clearInterval(pollInterval);
  }, [runId, run?.status]);

  // ════════════════════════════════════════
  // Action Handlers
  // ════════════════════════════════════════

  /** Gate 1: Promote firmographic companies with signal mode */
  const handlePromoteFirmographic = async () => {
    if (!runId || selectedCompanyIds.size === 0) return;
    setPromoting(true);
    try {
      const res = await promoteFirmographic(runId, Array.from(selectedCompanyIds), selectedSignalMode);
      setRun(res.data);
      setSignalMode(selectedSignalMode);
      setActiveReviewGate(null);
      setSseStage(selectedSignalMode === 'both' ? 'budget_signals' : (selectedSignalMode === 'budget_first' ? 'budget_signals' : 'urgency_signals'));
      setSseMessage('Resuming pipeline for signal research...');
      connectSSE(runId);
    } catch (err: any) {
      message.error(err?.response?.data?.detail || 'Failed to promote companies');
    } finally {
      setPromoting(false);
    }
  };

  /** Gate 2a: Promote after first signal review (serial mode) */
  const handlePromoteFirstSignal = async () => {
    if (!runId || selectedCompanyIds.size === 0) return;
    setPromoting(true);
    try {
      const res = await promoteFirstSignal(runId, Array.from(selectedCompanyIds));
      setRun(res.data);
      setActiveReviewGate(null);
      // Second signal type
      const secondType = signalMode === 'budget_first' ? 'urgency_signals' : 'budget_signals';
      setSseStage(secondType);
      setSseMessage(`Resuming pipeline for ${secondType.replace(/_/g, ' ')}...`);
      connectSSE(runId);
    } catch (err: any) {
      message.error(err?.response?.data?.detail || 'Failed to promote companies');
    } finally {
      setPromoting(false);
    }
  };

  /** Gate 2b/2: Promote after final signal review → contact discovery */
  const handlePromoteSignals = async () => {
    if (!runId || selectedCompanyIds.size === 0) return;
    setPromoting(true);
    try {
      const res = await promoteSignals(runId, Array.from(selectedCompanyIds));
      setRun(res.data);
      setActiveReviewGate(null);
      setSseStage('contact_discovery');
      setSseMessage('Resuming pipeline for contact discovery...');
      connectSSE(runId);
    } catch (err: any) {
      message.error(err?.response?.data?.detail || 'Failed to promote companies');
    } finally {
      setPromoting(false);
    }
  };

  const handleCancel = async () => {
    if (!runId) return;
    setCancelling(true);
    try {
      await cancelPipeline(runId);
      message.info('Cancellation requested -- pipeline will stop shortly');
    } catch (err: any) {
      message.error(err?.response?.data?.detail || 'Failed to cancel pipeline');
      setCancelling(false);
    }
  };

  // ════════════════════════════════════════
  // Selection Helpers
  // ════════════════════════════════════════

  const toggleCompanySelection = (companyId: string) => {
    setSelectedCompanyIds((prev) => {
      const next = new Set(prev);
      if (next.has(companyId)) {
        next.delete(companyId);
      } else {
        next.add(companyId);
      }
      return next;
    });
  };

  const selectAll = () => setSelectedCompanyIds(new Set(reviewCompanies.map((c) => c.id)));
  const deselectAll = () => setSelectedCompanyIds(new Set());
  const selectTopMatches = () => {
    const top = reviewCompanies
      .filter((c) =>
        c.qualification === 'verified_match' ||
        c.qualification === 'best_fit' ||
        (c.icp_match_score != null && c.icp_match_score >= 70) ||
        (c.budget_signal_score != null && c.budget_signal_score >= 60) ||
        (c.urgency_signal_score != null && c.urgency_signal_score >= 60)
      )
      .map((c) => c.id);
    setSelectedCompanyIds(new Set(top.length > 0 ? top : reviewCompanies.slice(0, Math.ceil(reviewCompanies.length / 2)).map((c) => c.id)));
  };

  // ════════════════════════════════════════
  // Stage History Backtracking
  // ════════════════════════════════════════

  const stageKeyToApiStage: Record<string, string> = {
    industry_discovery: 'industry_discovery',
    firmographic_fit: 'firmographic_fit',
    budget_signals: 'budget_signals',
    urgency_signals: 'urgency_signals',
    budget_urgency_signals: 'signals',
    contact_discovery: 'contact_discovery',
    final_scoring: 'final_scoring',
    review_firmographic: 'firmographic_fit',
    review_signals: 'signals',
    review_budget_signals: 'budget_signals',
    review_urgency_signals: 'urgency_signals',
  };

  const handleViewStageHistory = useCallback(async (stageKey: string) => {
    if (!runId) return;
    const apiStage = stageKeyToApiStage[stageKey] || stageKey;
    setViewingStageHistory(stageKey);
    setStageHistoryLoading(true);
    try {
      const res = await getCompaniesByStage(runId, apiStage);
      setStageHistoryCompanies(res.data as Company[]);
    } catch {
      message.error('Failed to load stage history');
      setStageHistoryCompanies([]);
    } finally {
      setStageHistoryLoading(false);
    }
  }, [runId]);

  const stageHistoryColumns = [
    {
      title: 'Company',
      dataIndex: 'name',
      width: 180,
      render: (name: string, record: Company) => (
        <div>
          <div style={{ fontWeight: 600, fontSize: 13 }}>{name}</div>
          {record.website && (
            <a href={record.website.startsWith('http') ? record.website : `https://${record.website}`} target="_blank" rel="noreferrer" style={{ fontSize: 11, color: 'var(--purple)' }}>
              {record.website}
            </a>
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
      title: 'Employees',
      dataIndex: 'employee_count',
      width: 90,
      render: (count: number | null) => count ? count.toLocaleString() : '-',
    },
    {
      title: 'Qualification',
      dataIndex: 'qualification',
      width: 100,
      render: (q: string | null) => {
        if (!q) return '-';
        const color = q === 'qualified' || q === 'verified_match' || q === 'best_fit' ? 'green'
          : q === 'disqualified' ? 'red' : 'blue';
        return <Tag color={color} style={{ fontSize: 11 }}>{q.replace(/_/g, ' ')}</Tag>;
      },
    },
    {
      title: 'Match Score',
      dataIndex: 'icp_match_score',
      width: 100,
      sorter: (a: Company, b: Company) => (a.icp_match_score || 0) - (b.icp_match_score || 0),
      defaultSortOrder: 'descend' as const,
      render: (score: number | null) => {
        if (score == null) return '-';
        const color = score >= 70 ? '#52c41a' : score >= 50 ? '#faad14' : '#ff4d4f';
        return <span style={{ fontWeight: 700, color }}>{Math.round(score)}/100</span>;
      },
    },
  ];

  // ════════════════════════════════════════
  // Live Progress Summary (from activity log)
  // ════════════════════════════════════════

  const progressSummary = useMemo(() => {
    const stageMap: Record<string, { passed: number; failed: number; total: number }> = {};
    for (const entry of activityLog) {
      if (entry.type === 'company_stage_result' && entry.stage) {
        if (!stageMap[entry.stage]) stageMap[entry.stage] = { passed: 0, failed: 0, total: 0 };
        stageMap[entry.stage].total++;
        if (entry.status === 'passed') stageMap[entry.stage].passed++;
        else stageMap[entry.stage].failed++;
      }
    }
    return Object.entries(stageMap);
  }, [activityLog]);

  // ════════════════════════════════════════
  // Stepper Computation
  // ════════════════════════════════════════

  const stages = getStepperStages(signalMode);
  const stepKeys = stages.map((s) => s.key);
  const mappedKey = mapStageToStepKey(sseStage, signalMode);
  const currentIndex = stepKeys.indexOf(mappedKey);
  const isCompleted = run?.status === 'completed' || sseStage === 'completed';
  const isFailed = run?.status === 'failed';
  const isCancelledFinal = run?.status === 'cancelled' || sseStage === 'cancelled';

  const getStepStatus = (index: number): 'wait' | 'process' | 'finish' | 'error' => {
    if (isCompleted) return 'finish';
    if (isFailed) return index <= currentIndex ? 'error' : 'wait';
    if (index < currentIndex) return 'finish';
    if (index === currentIndex) return 'process';
    return 'wait';
  };

  // ════════════════════════════════════════
  // Time Formatting
  // ════════════════════════════════════════

  const getElapsedTime = (entryTime: Date) => {
    const diffMs = entryTime.getTime() - startTimeRef.current.getTime();
    const secs = Math.floor(diffMs / 1000);
    if (secs < 60) return `${secs}s`;
    const mins = Math.floor(secs / 60);
    const remainSecs = secs % 60;
    return `${mins}m ${remainSecs}s`;
  };

  // ════════════════════════════════════════
  // Activity Log Rendering
  // ════════════════════════════════════════

  const renderActivityEntry = (entry: ActivityEntry) => {
    switch (entry.type) {
      case 'tool_start':
        return (
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <Tag
                color={toolColors[entry.toolName || ''] || 'default'}
                icon={toolIcons[entry.toolName || ''] || <ToolOutlined />}
              >
                {entry.displayName || entry.toolName}
              </Tag>
              <Text type="secondary" style={{ fontSize: 12 }}>
                <ClockCircleOutlined /> {getElapsedTime(entry.timestamp)}
              </Text>
            </div>
            {entry.context && (
              <Paragraph
                type="secondary"
                style={{ margin: '4px 0 0 0', fontSize: 13 }}
                ellipsis={{ rows: 2 }}
              >
                {entry.context}
              </Paragraph>
            )}
          </div>
        );

      case 'agent_reasoning': {
        const reasoningLabel = entry.text && entry.text.length > 0
          ? entry.text.substring(0, 60) + (entry.text.length > 60 ? '...' : '')
          : 'Analyzing...';
        return (
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <BulbOutlined style={{ color: '#faad14' }} />
              <Text strong style={{ fontSize: 13 }}>{reasoningLabel}</Text>
              <Text type="secondary" style={{ fontSize: 12 }}>
                <ClockCircleOutlined /> {getElapsedTime(entry.timestamp)}
              </Text>
            </div>
            <Paragraph
              style={{
                margin: 0,
                fontSize: 13,
                background: '#fafafa',
                padding: '8px 12px',
                borderRadius: 6,
                borderLeft: '3px solid #faad14',
              }}
              ellipsis={{ rows: 4, expandable: true, symbol: 'more' }}
            >
              {entry.text}
            </Paragraph>
          </div>
        );
      }

      case 'stage_update':
        return (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <RocketOutlined style={{ color: stageColors[entry.stage || ''] || '#1890ff' }} />
            <Text strong style={{ color: stageColors[entry.stage || ''] || '#1890ff' }}>
              {entry.message}
            </Text>
            <Text type="secondary" style={{ fontSize: 12 }}>
              <ClockCircleOutlined /> {getElapsedTime(entry.timestamp)}
            </Text>
          </div>
        );

      case 'tool_result':
        return (
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Tag color="success" style={{ fontSize: 11 }}>FOUND</Tag>
              <Text type="secondary" style={{ fontSize: 12 }}>
                {friendlyResultSummary(entry.toolName || '', entry.resultPreview || '')}
              </Text>
              <Text type="secondary" style={{ fontSize: 12 }}>
                <ClockCircleOutlined /> {getElapsedTime(entry.timestamp)}
              </Text>
            </div>
          </div>
        );

      case 'tool_error':
        return (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Tag color="orange" style={{ fontSize: 11 }}>RETRYING</Tag>
            <Text style={{ fontSize: 12, color: '#fa8c16' }}>
              {friendlyErrorMessage(entry.toolName || '', entry.errorMessage || '')}
            </Text>
            <Text type="secondary" style={{ fontSize: 12 }}>
              <ClockCircleOutlined /> {getElapsedTime(entry.timestamp)}
            </Text>
          </div>
        );

      case 'company_start':
        return (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <RocketOutlined style={{ color: '#722ed1' }} />
            <Text strong style={{ color: '#722ed1' }}>
              Company {entry.companyIndex}/{entry.totalCompanies}: {entry.companyName}
            </Text>
            <Text type="secondary" style={{ fontSize: 12 }}>
              <ClockCircleOutlined /> {getElapsedTime(entry.timestamp)}
            </Text>
          </div>
        );

      case 'company_stage_result':
        return (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <SafetyCertificateOutlined style={{ color: entry.status === 'passed' ? '#52c41a' : '#ff4d4f' }} />
            <Text style={{ fontSize: 12 }}>
              <Text strong>{entry.companyName}</Text>
              {' '}{entry.stage?.replace(/_/g, ' ')}:
              {entry.score != null && <Tag color={entry.status === 'passed' ? 'green' : 'red'} style={{ marginLeft: 4, fontSize: 11 }}>{Math.round(entry.score)}/100</Tag>}
              {entry.status === 'passed' ? ' Passed' : ' Failed'}
            </Text>
            <Text type="secondary" style={{ fontSize: 12 }}>
              <ClockCircleOutlined /> {getElapsedTime(entry.timestamp)}
            </Text>
          </div>
        );

      default:
        return null;
    }
  };

  const getTimelineDotColor = (entry: ActivityEntry) => {
    if (entry.type === 'company_start') return '#722ed1';
    if (entry.type === 'company_stage_result') return entry.status === 'passed' ? '#52c41a' : '#ff4d4f';
    if (entry.type === 'stage_update') return stageColors[entry.stage || ''] || '#1890ff';
    if (entry.type === 'tool_start') return toolColors[entry.toolName || ''] || '#1890ff';
    if (entry.type === 'tool_result') return '#d9d9d9';
    if (entry.type === 'tool_error') return '#fa8c16';
    return '#faad14';
  };

  // ════════════════════════════════════════
  // Log entry rendering for right panel
  // ════════════════════════════════════════

  const getLogTagInfo = (entry: ActivityEntry): { tagClass: string; tagText: string } => {
    if (entry.type === 'tool_start') {
      if (entry.toolName?.includes('company')) return { tagClass: 'discover', tagText: 'SEARCHING' };
      if (entry.toolName?.includes('people') || entry.toolName?.includes('contact') || entry.toolName?.includes('hunter') || entry.toolName?.includes('lusha'))
        return { tagClass: 'contact', tagText: 'CONTACTS' };
      if (entry.toolName?.includes('score')) return { tagClass: 'score', tagText: 'SCORING' };
      return { tagClass: 'icp', tagText: 'RESEARCH' };
    }
    if (entry.type === 'stage_update') {
      if (entry.stage === 'completed') return { tagClass: 'done', tagText: 'COMPLETE' };
      return { tagClass: 'icp', tagText: 'PROGRESS' };
    }
    if (entry.type === 'agent_reasoning') return { tagClass: 'icp', tagText: 'REASONING' };
    if (entry.type === 'tool_result') return { tagClass: 'done', tagText: 'FOUND' };
    if (entry.type === 'tool_error') return { tagClass: 'score', tagText: 'RETRY' };
    if (entry.type === 'company_start') return { tagClass: 'icp', tagText: 'COMPANY' };
    if (entry.type === 'company_stage_result') {
      return entry.status === 'passed'
        ? { tagClass: 'done', tagText: 'PASSED' }
        : { tagClass: 'warn', tagText: 'FAILED' };
    }
    return { tagClass: 'system', tagText: 'UPDATE' };
  };

  const getLogMessage = (entry: ActivityEntry): string => {
    if (entry.type === 'tool_start') {
      let msg = `${entry.displayName || entry.toolName}`;
      if (entry.context) {
        msg += ` -- ${entry.context.substring(0, 80)}${entry.context.length > 80 ? '...' : ''}`;
      }
      return msg;
    }
    if (entry.type === 'stage_update') return entry.message || '';
    if (entry.type === 'agent_reasoning')
      return (entry.text?.substring(0, 100) ?? '') + (entry.text && entry.text.length > 100 ? '...' : '');
    if (entry.type === 'tool_result')
      return friendlyResultSummary(entry.toolName || '', entry.resultPreview || '');
    if (entry.type === 'tool_error')
      return friendlyErrorMessage(entry.toolName || '', entry.errorMessage || '');
    if (entry.type === 'company_start')
      return `Processing company ${entry.companyIndex}/${entry.totalCompanies}: ${entry.companyName}`;
    if (entry.type === 'company_stage_result')
      return `${entry.companyName}: ${entry.stage?.replace(/_/g, ' ')} ${entry.status}${entry.score != null ? ` (${Math.round(entry.score)}/100)` : ''}`;
    return '';
  };

  // ════════════════════════════════════════════════════════════════
  // Stage History Drawer (shared across all views)
  // ════════════════════════════════════════════════════════════════

  const stageHistoryDrawer = (
    <Drawer
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <EyeOutlined style={{ color: 'var(--purple)' }} />
          <span>Stage History: {stages.find((s) => s.key === viewingStageHistory)?.title || viewingStageHistory?.replace(/_/g, ' ')}</span>
        </div>
      }
      placement="right"
      width={720}
      open={!!viewingStageHistory}
      onClose={() => setViewingStageHistory(null)}
    >
      <Table
        columns={stageHistoryColumns}
        dataSource={stageHistoryCompanies}
        rowKey="id"
        loading={stageHistoryLoading}
        pagination={false}
        scroll={{ x: 600 }}
        size="small"
      />
      {!stageHistoryLoading && stageHistoryCompanies.length === 0 && (
        <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--g400)' }}>
          No companies found at this stage.
        </div>
      )}
    </Drawer>
  );

  /** Build step items with clickable completed steps */
  const buildStepItems = (activeIndex: number, activeIcon?: React.ReactNode) =>
    stages.map((s, i) => {
      const isDone = i < activeIndex;
      const isActive = i === activeIndex;
      return {
        title: (
          <span
            style={isDone ? { cursor: 'pointer' } : undefined}
            onClick={isDone ? () => handleViewStageHistory(s.key) : undefined}
          >
            {s.title}
          </span>
        ),
        icon: isDone
          ? <CheckCircleOutlined style={{ color: '#52c41a', cursor: 'pointer' }} onClick={() => handleViewStageHistory(s.key)} />
          : isActive
            ? (activeIcon || s.icon)
            : s.icon,
        status: (isDone ? 'finish' : isActive ? 'process' : 'wait') as 'finish' | 'process' | 'wait',
        description: isDone ? (
          <span
            style={{ fontSize: 11, color: 'var(--purple)', cursor: 'pointer' }}
            onClick={() => handleViewStageHistory(s.key)}
          >
            View results
          </span>
        ) : undefined,
      };
    });

  // ════════════════════════════════════════════════════════════════
  // REVIEW UI - Firmographic Gate
  // ════════════════════════════════════════════════════════════════

  if (activeReviewGate === 'firmographic') {
    const getMatchScoreColor = (score: number | null) => {
      if (score == null) return '#999';
      return score >= 70 ? '#52c41a' : score >= 50 ? '#faad14' : '#ff4d4f';
    };

    const formatMatchScore = (score: number | null) => {
      if (score == null) return 'N/A';
      return `${Math.round(score)}/100`;
    };

    const firmographicColumns = [
      {
        title: () => (
          <Checkbox
            checked={selectedCompanyIds.size === reviewCompanies.length && reviewCompanies.length > 0}
            indeterminate={selectedCompanyIds.size > 0 && selectedCompanyIds.size < reviewCompanies.length}
            onChange={(e) => e.target.checked ? selectAll() : deselectAll()}
          />
        ),
        dataIndex: 'id',
        width: 50,
        render: (id: string) => (
          <Checkbox
            checked={selectedCompanyIds.has(id)}
            onChange={() => toggleCompanySelection(id)}
          />
        ),
      },
      {
        title: 'Company',
        dataIndex: 'name',
        width: 200,
        render: (name: string, record: Company) => (
          <div>
            <div style={{ fontWeight: 600, fontSize: 13 }}>{name}</div>
            {record.website && (
              <a href={record.website.startsWith('http') ? record.website : `https://${record.website}`} target="_blank" rel="noreferrer" style={{ fontSize: 11, color: 'var(--purple)' }}>
                {record.website}
              </a>
            )}
          </div>
        ),
      },
      {
        title: 'Industry',
        dataIndex: 'industry',
        width: 150,
        render: (ind: string | null) => ind || '-',
      },
      {
        title: 'Country',
        dataIndex: 'country',
        width: 120,
        render: (country: string | null) => country || '-',
      },
      {
        title: 'Employees',
        dataIndex: 'employee_count',
        width: 100,
        render: (count: number | null) => count ? count.toLocaleString() : '-',
      },
      {
        title: 'Revenue',
        dataIndex: 'revenue_estimate',
        width: 110,
        render: (rev: number | null) => {
          if (rev == null) return '-';
          if (rev >= 1_000_000_000) return `$${(rev / 1_000_000_000).toFixed(1)}B`;
          if (rev >= 1_000_000) return `$${(rev / 1_000_000).toFixed(0)}M`;
          return `$${rev.toLocaleString()}`;
        },
      },
      {
        title: () => (
          <Tooltip title="Calculated from 9 dimensions: Offering, Geography, Industry, Size, Tech Maturity, Infrastructure, Transformation Drivers, Leadership, Priority Areas. Each scored 0-2, weighted and normalized to 100.">
            <span style={{ cursor: 'help', borderBottom: '1px dashed var(--g400)' }}>Fit Score</span>
          </Tooltip>
        ),
        dataIndex: 'icp_match_score',
        width: 100,
        sorter: (a: Company, b: Company) => (a.icp_match_score || 0) - (b.icp_match_score || 0),
        defaultSortOrder: 'descend' as const,
        render: (score: number | null) => (
          <span style={{ fontWeight: 700, fontSize: 15, color: getMatchScoreColor(score) }}>
            {formatMatchScore(score)}
          </span>
        ),
      },
      {
        title: 'Reasoning',
        dataIndex: 'match_reasoning',
        width: 250,
        render: (reasoning: string | null, record: Company) => {
          // Fallback chain: match_reasoning -> stage_results reasoning -> dimension summary
          let text = reasoning;
          if (!text) {
            const firmoResult = record.stage_results?.find(sr => sr.stage === 'firmographic_fit');
            text = firmoResult?.reasoning || null;
          }
          if (!text && record.raw_data_json) {
            const evidence = (record.raw_data_json.dimension_evidence || record.raw_data_json) as Record<string, unknown>;
            const dims = Object.entries(DIMENSION_LABELS);
            const parts: string[] = [];
            dims.forEach(([key, label]) => {
              const dim = evidence[key] as Record<string, unknown> | undefined;
              if (!dim || typeof dim.score !== 'number') return;
              parts.push(`${label}: ${dim.score}/2`);
            });
            if (parts.length > 0) text = parts.join(', ');
          }
          return (
            <Paragraph
              style={{ margin: 0, fontSize: 12 }}
              ellipsis={{ rows: 2, expandable: true, symbol: 'more' }}
            >
              {text || '-'}
            </Paragraph>
          );
        },
      },
      {
        title: 'Status',
        dataIndex: 'qualification',
        width: 120,
        render: (_q: string | null, record: Company) => {
          const score = record.icp_match_score;
          // Derive status from the score so it's always in sync with the Fit Score column
          if (score != null) {
            if (score >= 70) return <Tag color="green">High Fit</Tag>;
            if (score >= 40) return <Tag color="gold">Medium Fit</Tag>;
            return (
              <Tooltip title={record.rejection_reason || record.match_reasoning || ''}>
                <Tag color="red">Low Fit</Tag>
              </Tooltip>
            );
          }
          // Fallback: no score available — use stage_results status
          const firmoResult = record.stage_results?.find(sr => sr.stage === 'firmographic_fit');
          if (firmoResult) {
            if (firmoResult.status === 'passed') return <Tag color="green">High Fit</Tag>;
            if (firmoResult.status === 'failed') {
              return (
                <Tooltip title={firmoResult.reasoning || record.rejection_reason || ''}>
                  <Tag color="red">Low Fit</Tag>
                </Tooltip>
              );
            }
            return <Tag color="blue">{firmoResult.status}</Tag>;
          }
          return <Tag>—</Tag>;
        },
      },
    ];

    return (
      <div style={{ padding: '28px 32px', maxWidth: 1500, margin: '0 auto', width: '100%' }}>
        <div style={{ marginBottom: 24 }}>
          <div className="section-label">Review Gate 1</div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h1 className="page-title">
              Review Firmographic Fit
              {run?.icp_name && <span style={{ fontWeight: 400, fontSize: 15, color: 'var(--g500)' }}> -- {run.icp_name}</span>}
            </h1>
            <Button size="small" onClick={() => navigate('/dashboard')} style={{ fontSize: 12 }}>
              Back to Dashboard
            </Button>
          </div>
        </div>

        {/* Steps indicator */}
        <Card bordered={false} style={{ marginBottom: 24 }}>
          <Steps
            current={stepKeys.indexOf('review_firmographic')}
            size="small"
            items={buildStepItems(stepKeys.indexOf('review_firmographic'), <EyeOutlined />)}
          />
        </Card>
        {stageHistoryDrawer}

        {/* Signal mode selector */}
        <Card
          bordered={false}
          style={{ marginBottom: 24, background: '#f7f7fa' }}
          title={
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <BulbOutlined style={{ color: 'var(--purple)' }} />
              <span>Signal Research Mode</span>
            </div>
          }
        >
          <Paragraph style={{ marginBottom: 12, fontSize: 13, color: 'var(--g600)' }}>
            Choose how to evaluate Budget and Urgency signals for selected companies:
          </Paragraph>
          <Radio.Group
            value={selectedSignalMode}
            onChange={(e: RadioChangeEvent) => setSelectedSignalMode(e.target.value as SignalMode)}
            style={{ marginBottom: 0 }}
          >
            <Space direction="vertical" size={12}>
              <Radio value="both">
                <span style={{ fontWeight: 600 }}>Both at Once</span>
                <div style={{ fontSize: 12, color: 'var(--g500)', marginLeft: 24 }}>
                  Run budget and urgency signal research together. Faster, one review gate.
                </div>
              </Radio>
              <Radio value="budget_first">
                <span style={{ fontWeight: 600 }}>Budget First</span>
                <div style={{ fontSize: 12, color: 'var(--g500)', marginLeft: 24 }}>
                  Evaluate budget signals first, review, then urgency. Two review gates for tighter control.
                </div>
              </Radio>
              <Radio value="urgency_first">
                <span style={{ fontWeight: 600 }}>Urgency First</span>
                <div style={{ fontSize: 12, color: 'var(--g500)', marginLeft: 24 }}>
                  Evaluate urgency signals first, review, then budget. Two review gates for tighter control.
                </div>
              </Radio>
            </Space>
          </Radio.Group>
        </Card>

        {/* Toolbar */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 16,
          padding: '12px 16px',
          background: '#f7f7fa',
          borderRadius: 8,
          border: '1px solid var(--g100, #f0f0f0)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Button size="small" onClick={selectAll}>Select All</Button>
            <Button size="small" onClick={deselectAll}>Deselect All</Button>
            <Button size="small" onClick={selectTopMatches}>Select Top Matches</Button>
            <Tag color="purple" style={{ fontSize: 13, padding: '2px 10px', margin: 0 }}>
              {selectedCompanyIds.size} of {reviewCompanies.length} selected
            </Tag>
          </div>
          <Button
            type="primary"
            size="large"
            disabled={selectedCompanyIds.size === 0}
            loading={promoting}
            onClick={handlePromoteFirmographic}
            icon={<RocketOutlined />}
          >
            Continue with {selectedCompanyIds.size} {selectedCompanyIds.size === 1 ? 'Company' : 'Companies'}
          </Button>
        </div>

        {/* Company review table */}
        <Card bordered={false} style={{ marginBottom: 24 }}>
          <Table
            columns={firmographicColumns}
            dataSource={reviewCompanies}
            rowKey="id"
            loading={reviewLoading}
            pagination={false}
            scroll={{ x: 1100 }}
            size="small"
            expandable={{
              expandedRowRender: (record: Company) => (
                <div style={{ padding: '8px 0' }}>
                  {record.rejection_reason && (
                    <div style={{
                      marginBottom: 12,
                      padding: '8px 12px',
                      background: '#fff1f0',
                      border: '1px solid #ffa39e',
                      borderRadius: 6,
                      fontSize: 12,
                      color: '#cf1322',
                      lineHeight: 1.6,
                    }}>
                      <Text strong style={{ fontSize: 11, color: '#cf1322' }}>Rejection Reason: </Text>
                      {record.rejection_reason}
                    </div>
                  )}
                  {record.match_reasoning && (
                    <div style={{ marginBottom: 12 }}>
                      <Text type="secondary" style={{ fontSize: 11 }}>Match Reasoning</Text>
                      <div style={{
                        background: '#fafafa',
                        padding: '8px 12px',
                        borderRadius: 6,
                        fontSize: 12,
                        lineHeight: 1.6,
                        borderLeft: '3px solid var(--purple)',
                      }}>
                        {record.match_reasoning}
                      </div>
                    </div>
                  )}
                  <DimensionTags rawData={record.raw_data_json} showCount />
                  {record.description && (
                    <div style={{ marginBottom: 12 }}>
                      <Text type="secondary" style={{ fontSize: 11 }}>Description</Text>
                      <div style={{ fontSize: 12, lineHeight: 1.6 }}>{record.description}</div>
                    </div>
                  )}
                  <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
                    {record.tech_stack_json && Array.isArray(record.tech_stack_json) && (record.tech_stack_json as string[]).length > 0 && (
                      <div>
                        <Text type="secondary" style={{ fontSize: 11 }}>Tech Stack</Text>
                        <div style={{ marginTop: 4 }}>
                          {(record.tech_stack_json as unknown as string[]).map((t, i) => (
                            <Tag key={i} color="blue" style={{ fontSize: 11, marginBottom: 3 }}>{String(t)}</Tag>
                          ))}
                        </div>
                      </div>
                    )}
                    {record.source && (
                      <div>
                        <Text type="secondary" style={{ fontSize: 11 }}>Source</Text>
                        <div><Tag style={{ fontSize: 11 }}>{record.source}</Tag></div>
                      </div>
                    )}
                  </div>
                </div>
              ),
            }}
          />
        </Card>

        {/* Activity log (collapsible) */}
        {mergedActivityLog.length > 0 && (
          <Collapse
            items={[{
              key: 'firmographic-log',
              label: (
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <span>Activity Log</span>
                  <Badge
                    count={`${toolCallCount} tool calls`}
                    style={{ backgroundColor: 'var(--purple-pale)', color: 'var(--purple) !important', fontWeight: 600 }}
                    showZero
                  />
                </div>
              ),
              children: (
                <div style={{ maxHeight: 400, overflowY: 'auto' }}>
                  <Timeline
                    items={mergedActivityLog.map((entry) => ({
                      key: entry.id,
                      color: getTimelineDotColor(entry),
                      children: renderActivityEntry(entry),
                    }))}
                  />
                </div>
              ),
            }]}
          />
        )}
      </div>
    );
  }

  // ════════════════════════════════════════════════════════════════
  // REVIEW UI - Signal Review Gates
  // ════════════════════════════════════════════════════════════════

  if (activeReviewGate === 'first_signal' || activeReviewGate === 'second_signal' || activeReviewGate === 'signal_review') {

    const isFirstSignal = activeReviewGate === 'first_signal';
    const isSecondSignal = activeReviewGate === 'second_signal';
    const isBothSignals = activeReviewGate === 'signal_review';

    const gateLabel = isFirstSignal
      ? `Review ${(currentSignalType || 'signal').replace(/_/g, ' ')}`
      : isSecondSignal
        ? `Review ${(currentSignalType || 'signal').replace(/_/g, ' ')}`
        : 'Review Signal Results';

    const gateNumber = isFirstSignal ? 2 : isSecondSignal ? 3 : 2;

    const handlePromoteFromSignalGate = () => {
      if (isFirstSignal) {
        handlePromoteFirstSignal();
      } else {
        // Both second_signal and signal_review promote to contact discovery
        handlePromoteSignals();
      }
    };

    const getSignalScoreColor = (score: number | null) => {
      if (score == null) return '#999';
      return score >= 70 ? '#52c41a' : score >= 40 ? '#faad14' : '#ff4d4f';
    };

    const signalColumns = [
      {
        title: () => (
          <Checkbox
            checked={selectedCompanyIds.size === reviewCompanies.length && reviewCompanies.length > 0}
            indeterminate={selectedCompanyIds.size > 0 && selectedCompanyIds.size < reviewCompanies.length}
            onChange={(e) => e.target.checked ? selectAll() : deselectAll()}
          />
        ),
        dataIndex: 'id',
        width: 50,
        render: (id: string) => (
          <Checkbox
            checked={selectedCompanyIds.has(id)}
            onChange={() => toggleCompanySelection(id)}
          />
        ),
      },
      {
        title: 'Company',
        dataIndex: 'name',
        width: 200,
        render: (name: string, record: Company) => (
          <div>
            <div style={{ fontWeight: 600, fontSize: 13 }}>{name}</div>
            {record.industry && (
              <Text type="secondary" style={{ fontSize: 11 }}>{record.industry}</Text>
            )}
          </div>
        ),
      },
    ];

    // Add budget signal column if applicable
    if (isBothSignals || currentSignalType === 'budget_signals') {
      signalColumns.push({
        title: 'Budget Score',
        dataIndex: 'budget_signal_score' as any,
        width: 120,
        sorter: ((a: Company, b: Company) => (a.budget_signal_score || 0) - (b.budget_signal_score || 0)) as any,
        defaultSortOrder: 'descend' as any,
        render: ((score: number | null) => (
          <span style={{ fontWeight: 700, fontSize: 15, color: getSignalScoreColor(score) }}>
            {score != null ? `${Math.round(score)}/100` : 'N/A'}
          </span>
        )) as any,
      } as any);
    }

    // Add urgency signal column if applicable
    if (isBothSignals || currentSignalType === 'urgency_signals') {
      signalColumns.push({
        title: 'Urgency Score',
        dataIndex: 'urgency_signal_score' as any,
        width: 120,
        sorter: ((a: Company, b: Company) => (a.urgency_signal_score || 0) - (b.urgency_signal_score || 0)) as any,
        defaultSortOrder: (isBothSignals ? undefined : 'descend') as any,
        render: ((score: number | null) => (
          <span style={{ fontWeight: 700, fontSize: 15, color: getSignalScoreColor(score) }}>
            {score != null ? `${Math.round(score)}/100` : 'N/A'}
          </span>
        )) as any,
      } as any);
    }

    // Key evidence column
    signalColumns.push({
      title: 'Key Evidence',
      dataIndex: 'stage_results' as any,
      width: 300,
      render: ((_: unknown, record: Company) => {
        const stageResults = record.stage_results || [];
        const relevantResults = stageResults.filter((sr) => {
          if (isBothSignals) return sr.stage === 'budget_signals' || sr.stage === 'urgency_signals';
          return sr.stage === currentSignalType;
        });
        if (relevantResults.length === 0) return <Text type="secondary" style={{ fontSize: 12 }}>-</Text>;
        return (
          <div>
            {relevantResults.map((sr, i) => (
              <div key={i} style={{ marginBottom: i < relevantResults.length - 1 ? 6 : 0 }}>
                {isBothSignals && (
                  <Tag
                    color={sr.stage === 'budget_signals' ? 'orange' : 'magenta'}
                    style={{ fontSize: 10, marginBottom: 2 }}
                  >
                    {sr.stage === 'budget_signals' ? 'Budget' : 'Urgency'}
                  </Tag>
                )}
                <Paragraph
                  style={{ margin: 0, fontSize: 12 }}
                  ellipsis={{ rows: 2, expandable: true, symbol: 'more' }}
                >
                  {sr.reasoning || '-'}
                </Paragraph>
                <EvidenceSignalSummary evidence={sr.evidence} maxSignals={2} />
              </div>
            ))}
          </div>
        );
      }) as any,
    } as any);

    // Determine current step index for the stepper
    let reviewStepKey = 'review_signals';
    if (isFirstSignal && currentSignalType) {
      reviewStepKey = `review_${currentSignalType}`;
    } else if (isSecondSignal && currentSignalType) {
      reviewStepKey = `review_${currentSignalType}`;
    }
    const reviewStepIndex = stepKeys.indexOf(reviewStepKey);

    return (
      <div style={{ padding: '28px 32px', maxWidth: 1500, margin: '0 auto', width: '100%' }}>
        <div style={{ marginBottom: 24 }}>
          <div className="section-label">Review Gate {gateNumber}</div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h1 className="page-title">
              {gateLabel}
              {run?.icp_name && <span style={{ fontWeight: 400, fontSize: 15, color: 'var(--g500)' }}> -- {run.icp_name}</span>}
            </h1>
            <Button size="small" onClick={() => navigate('/dashboard')} style={{ fontSize: 12 }}>
              Back to Dashboard
            </Button>
          </div>
        </div>

        {/* Steps indicator */}
        <Card bordered={false} style={{ marginBottom: 24 }}>
          <Steps
            current={reviewStepIndex >= 0 ? reviewStepIndex : 3}
            size="small"
            items={buildStepItems(reviewStepIndex >= 0 ? reviewStepIndex : 3, <AuditOutlined />)}
          />
        </Card>
        {stageHistoryDrawer}

        {/* Toolbar */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 16,
          padding: '12px 16px',
          background: '#f7f7fa',
          borderRadius: 8,
          border: '1px solid var(--g100, #f0f0f0)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Button size="small" onClick={selectAll}>Select All</Button>
            <Button size="small" onClick={deselectAll}>Deselect All</Button>
            <Button size="small" onClick={selectTopMatches}>Select Top Scores</Button>
            <Tag color="purple" style={{ fontSize: 13, padding: '2px 10px', margin: 0 }}>
              {selectedCompanyIds.size} of {reviewCompanies.length} selected
            </Tag>
          </div>
          <Button
            type="primary"
            size="large"
            disabled={selectedCompanyIds.size === 0}
            loading={promoting}
            onClick={handlePromoteFromSignalGate}
            icon={<RocketOutlined />}
          >
            {isFirstSignal
              ? `Continue to ${signalMode === 'budget_first' ? 'Urgency' : 'Budget'} Signals with ${selectedCompanyIds.size}`
              : `Continue to Contact Discovery with ${selectedCompanyIds.size}`}
          </Button>
        </div>

        {/* Signal review table */}
        <Card bordered={false} style={{ marginBottom: 24 }}>
          <Table
            columns={signalColumns}
            dataSource={reviewCompanies}
            rowKey="id"
            loading={reviewLoading}
            pagination={false}
            scroll={{ x: 950 }}
            size="small"
            expandable={{
              expandedRowRender: (record: Company) => {
                const stageResults = record.stage_results || [];
                const relevantResults = stageResults.filter((sr) => {
                  if (isBothSignals) return sr.stage === 'budget_signals' || sr.stage === 'urgency_signals';
                  return sr.stage === currentSignalType;
                });
                if (relevantResults.length === 0) {
                  return <Text type="secondary" style={{ fontSize: 12, padding: 8 }}>No evidence details available.</Text>;
                }
                return (
                  <div style={{ padding: '8px 0', display: 'flex', flexDirection: 'column', gap: 12 }}>
                    {relevantResults.map((sr, i) => (
                      <div key={i}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                          <Tag
                            color={sr.stage === 'budget_signals' ? 'green' : sr.stage === 'urgency_signals' ? 'orange' : 'blue'}
                            style={{ fontSize: 11 }}
                          >
                            {sr.stage === 'budget_signals' ? 'Budget Signal' : sr.stage === 'urgency_signals' ? 'Urgency Signal' : sr.stage.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                          </Tag>
                          {sr.score != null && (
                            <Text style={{ fontSize: 12, fontWeight: 600, color: getSignalScoreColor(sr.score) }}>
                              Score: {Math.round(sr.score)}/100
                            </Text>
                          )}
                        </div>
                        {sr.reasoning && (
                          <div style={{
                            background: '#fafafa', padding: '10px 14px',
                            borderRadius: 6, fontSize: 12, color: 'var(--g700)',
                            lineHeight: 1.7, marginBottom: 10,
                            borderLeft: `3px solid ${sr.stage === 'budget_signals' ? '#52c41a' : sr.stage === 'urgency_signals' ? '#fa8c16' : '#1677ff'}`,
                          }}>
                            <Text type="secondary" style={{ fontSize: 11, fontWeight: 600 }}>Reasoning: </Text>
                            {sr.reasoning}
                          </div>
                        )}
                        {sr.evidence != null && (
                          <div>
                            <Text type="secondary" style={{ fontSize: 11, fontWeight: 600, marginBottom: 6, display: 'block' }}>
                              Evidence
                            </Text>
                            <EvidenceDisplay evidence={sr.evidence} />
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                );
              },
            }}
          />
        </Card>

        {/* Activity log (collapsible) */}
        {mergedActivityLog.length > 0 && (
          <Collapse
            items={[{
              key: 'signal-log',
              label: (
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <span>Activity Log</span>
                  <Badge
                    count={`${toolCallCount} tool calls`}
                    style={{ backgroundColor: 'var(--purple-pale)', color: 'var(--purple) !important', fontWeight: 600 }}
                    showZero
                  />
                </div>
              ),
              children: (
                <div style={{ maxHeight: 400, overflowY: 'auto' }}>
                  <Timeline
                    items={mergedActivityLog.map((entry) => ({
                      key: entry.id,
                      color: getTimelineDotColor(entry),
                      children: renderActivityEntry(entry),
                    }))}
                  />
                </div>
              ),
            }]}
          />
        )}
      </div>
    );
  }

  // ════════════════════════════════════════════════════════════════
  // PROGRESS VIEW (running pipeline)
  // ════════════════════════════════════════════════════════════════

  if (!isCompleted && !isFailed && !isCancelledFinal) {
    const overallProgress = stages.length > 0 ? ((Math.max(0, currentIndex) / stages.length) * 100) : 0;
    const companiesFound = run?.companies_found || 0;
    const contactsFound = run?.contacts_found || 0;

    return (
      <div className="progress-overlay" style={{ gridTemplateColumns: `${leftPanelWidth}px 1fr` }}>
        {/* Left Panel - Step Pipeline */}
        <div className="prog-left">
          <div
            className="prog-left-resize-handle"
            onMouseDown={handleResizeStart}
          />
          <div className="prog-left-header">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <div className="prog-title">
                Generating Leads
                {run?.icp_name && <span style={{ fontWeight: 400, fontSize: 13, color: 'var(--g500)' }}> -- {run.icp_name}</span>}
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <Popconfirm
                  title="Stop this pipeline?"
                  description="The pipeline will be cancelled. Any results found so far will be preserved."
                  onConfirm={handleCancel}
                  okText="Stop"
                  cancelText="Keep Running"
                  okButtonProps={{ danger: true }}
                >
                  <Button
                    size="small"
                    danger
                    icon={<StopOutlined />}
                    loading={cancelling}
                    style={{ fontSize: 12 }}
                  >
                    Stop
                  </Button>
                </Popconfirm>
                <Button
                  size="small"
                  onClick={() => navigate('/dashboard')}
                  style={{ fontSize: 12 }}
                >
                  Back
                </Button>
              </div>
            </div>
            <div className="prog-subtitle">{sseMessage}</div>
            <div style={{
              fontSize: 12,
              color: 'var(--g600)',
              marginTop: 10,
              background: '#f0f9ff',
              border: '1px solid #bae0ff',
              borderRadius: 8,
              padding: '10px 14px',
              lineHeight: 1.6,
            }}>
              <div style={{ fontWeight: 600, marginBottom: 2 }}>
                Estimated duration: ~{Math.ceil((run?.estimated_duration_seconds || 300) / 60)} min
              </div>
              <div style={{ fontSize: 11, color: 'var(--g500)' }}>
                You can safely leave this page -- results are saved automatically.{' '}
                <span
                  style={{ color: 'var(--purple)', cursor: 'pointer', fontWeight: 500 }}
                  onClick={() => navigate('/dashboard')}
                >
                  Go to Dashboard
                </span>
              </div>
            </div>
            <div className="prog-overall-bar">
              <div className="prog-overall-fill" style={{ width: `${overallProgress}%` }} />
            </div>
          </div>

          <div className="prog-steps-list">
            {stages.map((stage, i) => {
              const status = i < currentIndex ? 'done' : i === currentIndex ? 'active' : 'pending';
              return (
                <div key={stage.key} className={`prog-step-item ${status}`}>
                  <div className="prog-step-num">
                    {status === 'done' ? '\u2713' : status === 'active' ? <div className="spinner" /> : i + 1}
                  </div>
                  <div className="prog-step-info">
                    <div className="prog-step-name">{stage.title}</div>
                    <div className="prog-step-desc">
                      {status === 'active' ? sseMessage : status === 'done' ? 'Completed' : 'Waiting...'}
                    </div>
                    {status === 'done' && (
                      <div className="prog-step-count">{'\u2713'} Complete</div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Live company progress indicator */}
          {currentCompany && (
            <div style={{
              margin: '0 16px 12px',
              padding: '10px 14px',
              background: '#f6f0ff',
              border: '1px solid #d3adf7',
              borderRadius: 8,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                <span style={{ fontWeight: 600, fontSize: 13, color: 'var(--purple)' }}>
                  {currentCompany.name}
                </span>
                <span style={{ fontSize: 12, color: 'var(--g500)' }}>
                  {currentCompany.index} of {currentCompany.total}
                </span>
              </div>
              <div style={{ background: '#e8d5f5', borderRadius: 3, height: 6, overflow: 'hidden' }}>
                <div style={{
                  width: `${Math.round((currentCompany.index / currentCompany.total) * 100)}%`,
                  height: '100%',
                  background: 'var(--purple, #722ed1)',
                  borderRadius: 3,
                  transition: 'width 0.3s ease',
                }} />
              </div>
            </div>
          )}

          <div className="prog-stat-bar">
            <div className="prog-stat">
              <div className="sv">{companiesFound}</div>
              <div className="sl">Companies</div>
            </div>
            <div className="prog-stat">
              <div className="sv">{contactsFound}</div>
              <div className="sl">Contacts</div>
            </div>
            <div className="prog-stat">
              <div className="sv">{toolCallCount}</div>
              <div className="sl">Tool Calls</div>
            </div>
            <div className="prog-stat">
              <div className="sv">
                {elapsedSeconds < 60 ? `${elapsedSeconds}s` : `${Math.floor(elapsedSeconds / 60)}m`}
              </div>
              <div className="sl">Elapsed</div>
            </div>
          </div>
        </div>

        {/* Right Panel - Tabbed (Activity Log + Companies) */}
        <div className="prog-right">
          <div className="prog-right-header" style={{ padding: 0, borderBottom: '1px solid var(--g200)' }}>
            <Tabs
              size="small"
              activeKey={rightTab}
              onChange={(k) => setRightTab(k as 'log' | 'companies')}
              style={{ padding: '0 16px' }}
              items={[
                { key: 'log', label: 'Activity Log' },
                { key: 'companies', label: `Companies (${liveCompanies.length})` },
              ]}
            />
          </div>

          {/* Live Progress Summary — shown in both tabs */}
          {progressSummary.length > 0 && (
            <div style={{
              padding: '10px 20px',
              borderBottom: '1px solid var(--g200)',
              background: '#fff',
              display: 'flex',
              flexWrap: 'wrap',
              gap: '6px 16px',
              fontSize: 12,
            }}>
              {progressSummary.map(([stage, counts]) => {
                const stageColor = stageColors[stage] || '#8c8c8c';
                return (
                  <div key={stage} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <div style={{ width: 8, height: 8, borderRadius: '50%', background: stageColor, flexShrink: 0 }} />
                    <span style={{ color: 'var(--g600)', fontWeight: 500 }}>
                      {stage.replace(/_/g, ' ')}:
                    </span>
                    <span style={{ color: '#52c41a', fontWeight: 600 }}>{counts.passed} passed</span>
                    {counts.failed > 0 && (
                      <span style={{ color: '#ff4d4f', fontWeight: 600 }}>{counts.failed} failed</span>
                    )}
                  </div>
                );
              })}
              {currentCompany && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--purple)', fontWeight: 600 }}>
                  <LoadingOutlined style={{ fontSize: 11 }} />
                  {currentCompany.name}
                </div>
              )}
            </div>
          )}

          {rightTab === 'log' && (
            <div className="prog-log-area" ref={logContainerRef}>
              {mergedActivityLog.map((entry) => {
                const timeStr = entry.timestamp.toLocaleTimeString('en-US', {
                  hour: '2-digit',
                  minute: '2-digit',
                  second: '2-digit',
                  hour12: false,
                });

                const { tagClass, tagText } = getLogTagInfo(entry);
                const logMsg = getLogMessage(entry);

                return (
                  <div key={entry.id} className="log-entry">
                    <div className="log-time">{timeStr}</div>
                    <div className={`log-tag ${tagClass}`}>{tagText}</div>
                    <div className="log-msg">{logMsg}</div>
                  </div>
                );
              })}
              {mergedActivityLog.length === 0 && (
                <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--g400)' }}>
                  Waiting for activity...
                </div>
              )}
            </div>
          )}

          {rightTab === 'companies' && (
            <div style={{ flex: 1, overflow: 'auto', padding: '12px 16px' }}>
              <LiveCompanyDashboard
                companies={liveCompanies}
                currentCompany={currentCompany}
                stageFilter={stageFilter}
                onStageFilterChange={setStageFilter}
              />
            </div>
          )}
        </div>
      </div>
    );
  }

  // ════════════════════════════════════════════════════════════════
  // COMPLETED / FAILED / CANCELLED VIEW
  // ════════════════════════════════════════════════════════════════

  return (
    <div style={{ padding: '28px 32px', maxWidth: 1400, margin: '0 auto', width: '100%' }}>
      <div style={{ marginBottom: 24 }}>
        <div className="section-label">Search Progress</div>
        <h1 className="page-title">
          {isCompleted ? 'Search Complete' : isFailed ? 'Search Failed' : isCancelledFinal ? 'Search Cancelled' : 'Search in Progress'}
        </h1>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
        {/* Stage Progress Stepper */}
        <Card title="Progress Details" bordered={false}>
          <Steps
            current={isCompleted ? stages.length : currentIndex}
            size="small"
            items={isCompleted
              ? buildStepItems(stages.length)
              : stages.map((s, i) => ({
                  title: s.title,
                  icon: getStepStatus(i) === 'process' ? <LoadingOutlined /> : s.icon,
                  status: getStepStatus(i),
                }))
            }
          />
          {stageHistoryDrawer}

          {isCompleted && (
            <Result
              status="success"
              title="Search Complete"
              subTitle={`Found ${run?.companies_found || 0} companies and ${run?.contacts_found || 0} contacts`}
              style={{ padding: '24px 0 0 0' }}
              extra={[
                <Button type="primary" key="leads" onClick={() => navigate(`/leads/${runId}`)}>
                  View Leads
                </Button>,
                <Button key="dashboard" onClick={() => navigate('/dashboard')}>
                  Dashboard
                </Button>,
              ]}
            />
          )}

          {isFailed && (
            <Result
              status="error"
              title="Search Failed"
              subTitle={run?.error_log?.substring(0, 200) || 'An error occurred during search execution'}
              style={{ padding: '24px 0 0 0' }}
              extra={<Button onClick={() => navigate('/dashboard')}>Dashboard</Button>}
            />
          )}

          {isCancelledFinal && (
            <Result
              status="warning"
              title="Search Cancelled"
              subTitle={`Pipeline was cancelled. ${run?.companies_found ? `${run.companies_found} companies were found before cancellation.` : 'No results were saved.'}`}
              style={{ padding: '24px 0 0 0' }}
              extra={[
                ...(run?.companies_found ? [
                  <Button type="primary" key="leads" onClick={() => navigate(`/leads/${runId}`)}>
                    View Partial Results
                  </Button>,
                ] : []),
                <Button key="dashboard" onClick={() => navigate('/dashboard')}>
                  Dashboard
                </Button>,
              ]}
            />
          )}
        </Card>

        {/* Activity Log */}
        <Card
          title={
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <span>Activity Log</span>
              <Badge
                count={`${toolCallCount} tool calls`}
                style={{ backgroundColor: 'var(--purple-pale)', color: 'var(--purple) !important', fontWeight: 600 }}
                showZero
              />
            </div>
          }
          bordered={false}
        >
          <div
            ref={logContainerRef}
            style={{
              maxHeight: 500,
              overflowY: 'auto',
              paddingRight: 8,
            }}
          >
            {mergedActivityLog.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
                <LoadingOutlined style={{ fontSize: 24, marginBottom: 12 }} />
                <div>Waiting for activity...</div>
              </div>
            ) : (
              <Timeline
                items={mergedActivityLog.map((entry) => ({
                  key: entry.id,
                  color: getTimelineDotColor(entry),
                  children: renderActivityEntry(entry),
                }))}
              />
            )}
          </div>
        </Card>
      </div>
    </div>
  );
};

export default PipelinePage;
