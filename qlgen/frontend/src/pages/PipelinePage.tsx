import React, { useEffect, useState, useRef, useCallback, useMemo } from 'react';
import { Card, Steps, Result, Button, Typography, Tag, Timeline, Badge, Table, Checkbox, message, Collapse, Tooltip, Popconfirm } from 'antd';
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
} from '@ant-design/icons';
import { useParams, useNavigate } from 'react-router-dom';
import { getPipelineStatus, getPipelineLogs, promoteCompanies, cancelPipeline } from '../api/pipelineApi';
import { getLeadCompanies } from '../api/leadsApi';
import { PipelineRun, Company } from '../types';

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
import { API_BASE } from '../api/client';

const { Text, Paragraph } = Typography;

const stageOrder = ['company_discovery', 'contact_discovery', 'enrichment', 'scoring', 'completed'];

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
  company_discovery: '#1890ff',
  contact_discovery: '#52c41a',
  enrichment: '#722ed1',
  scoring: '#fa8c16',
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
    return 'Data source rate limit reached — switching to alternative source';
  if (lower.includes('404') || lower.includes('not found'))
    return 'No data found at this source — trying another approach';
  if (lower.includes('timeout') || lower.includes('timed out'))
    return 'Source took too long to respond — moving on';
  if (lower.includes('unauthorized') || lower.includes('401') || lower.includes('403'))
    return 'Access issue with data source — using backup source';
  return 'Data source temporarily unavailable — trying alternative';
};

interface ActivityEntry {
  id: number;
  type: 'tool_start' | 'agent_reasoning' | 'stage_update' | 'tool_result' | 'tool_error' | 'company_start';
  timestamp: Date;
  // tool_start fields
  toolName?: string;
  displayName?: string;
  context?: string;
  toolCallNumber?: number;
  // agent_reasoning fields
  text?: string;
  // stage_update fields
  stage?: string;
  progress?: number;
  message?: string;
  // tool_result fields
  resultPreview?: string;
  success?: boolean;
  // tool_error fields
  errorMessage?: string;
  // company_start fields
  companyName?: string;
  companyIndex?: number;
  totalCompanies?: number;
}

const PipelinePage: React.FC = () => {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
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

  // Review mode state
  const [isAwaitingReview, setIsAwaitingReview] = useState(false);
  const [discoveredCompanies, setDiscoveredCompanies] = useState<Company[]>([]);
  const [selectedCompanyIds, setSelectedCompanyIds] = useState<Set<string>>(new Set());
  const [promoting, setPromoting] = useState(false);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [cancelling, setCancelling] = useState(false);

  const addEntry = useCallback((entry: Omit<ActivityEntry, 'id' | 'timestamp'>) => {
    const newEntry: ActivityEntry = {
      ...entry,
      id: ++entryIdRef.current,
      timestamp: new Date(),
    };
    setActivityLog((prev) => [...prev, newEntry]);
  }, []);

  // Merge consecutive agent_reasoning entries into single entries
  const mergedActivityLog = useMemo(() => {
    const result: ActivityEntry[] = [];
    for (const entry of activityLog) {
      if (
        entry.type === 'agent_reasoning' &&
        result.length > 0 &&
        result[result.length - 1].type === 'agent_reasoning'
      ) {
        // Merge into previous reasoning entry
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

  // Load discovered companies for review
  const loadDiscoveredCompanies = useCallback(async () => {
    if (!runId) return;
    setReviewLoading(true);
    try {
      const res = await getLeadCompanies(runId, { sort_by: 'qualification' });
      setDiscoveredCompanies(res.data);
      // Pre-select all by default
      setSelectedCompanyIds(new Set(res.data.map((c) => c.id)));
    } catch {
      message.error('Failed to load discovered companies');
    } finally {
      setReviewLoading(false);
    }
  }, [runId]);

  // SSE connection setup - extracted for reuse
  const connectSSE = useCallback((targetRunId: string) => {
    const es = new EventSource(`${API_BASE}/pipeline/${targetRunId}/stream`);
    eventSourceRef.current = es;

    es.addEventListener('stage_update', (event) => {
      const data = JSON.parse(event.data);
      setSseStage(data.stage);
      setSseMessage(data.message || 'Agent is working...');
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
      addEntry({
        type: 'company_start',
        companyName: data.company_name,
        companyIndex: data.company_index,
        totalCompanies: data.total_companies,
        progress: data.progress,
      });
    });

    es.addEventListener('awaiting_review', (event) => {
      const data = JSON.parse(event.data);
      setSseStage('review');
      setSseMessage(`Discovery complete: ${data.companies_found} companies found. Review and select companies to continue.`);
      setIsAwaitingReview(true);
      loadDiscoveredCompanies();
      getPipelineStatus(targetRunId).then((res) => setRun(res.data));
      es.close();
    });

    es.addEventListener('completed', (event) => {
      const data = JSON.parse(event.data);
      setSseStage('completed');
      setSseMessage(`Completed: ${data.companies_found} companies, ${data.contacts_found} contacts`);
      setIsAwaitingReview(false);
      addEntry({
        type: 'stage_update',
        stage: 'completed',
        progress: 100,
        message: `Search complete — found ${data.companies_found} companies and ${data.contacts_found} contacts`,
      });
      getPipelineStatus(targetRunId).then((res) => setRun(res.data));
      es.close();
    });

    es.addEventListener('cancelled', (event) => {
      const data = JSON.parse(event.data);
      setSseStage('cancelled');
      setSseMessage(`Cancelled: ${data.companies_found} companies found before cancellation`);
      setCancelling(false);
      addEntry({
        type: 'stage_update',
        stage: 'cancelled',
        message: `Pipeline cancelled — ${data.companies_found} companies found before cancellation`,
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
            setIsAwaitingReview(true);
            loadDiscoveredCompanies();
            clearInterval(interval);
          }
        });
      }, 5000);
    };

    return es;
  }, [addEntry, loadDiscoveredCompanies]);

  // Load persisted logs for completed/failed/awaiting_review runs
  useEffect(() => {
    if (!runId || !run) return;
    if (run.status === 'completed' || run.status === 'failed' || run.status === 'awaiting_review' || run.status === 'cancelled') {
      getPipelineLogs(runId).then((res) => {
        const entries: ActivityEntry[] = res.data.map((log, i) => ({
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
        }));
        setActivityLog(entries);
        const toolEntries = entries.filter(e => e.type === 'tool_start');
        setToolCallCount(toolEntries.length);
        entryIdRef.current = entries.length;
      });
    }
  }, [runId, run?.status]);

  // Initial load + SSE connection
  useEffect(() => {
    if (!runId) return;
    startTimeRef.current = new Date();

    timerRef.current = setInterval(() => {
      setElapsedSeconds(Math.floor((new Date().getTime() - startTimeRef.current.getTime()) / 1000));
    }, 1000);

    getPipelineStatus(runId).then((res) => {
      setRun(res.data);
      // If awaiting_review on initial load, show review UI directly
      if (res.data.status === 'awaiting_review') {
        setIsAwaitingReview(true);
        setSseStage('review');
        loadDiscoveredCompanies();
        return;
      }
      // If still running or pending, connect SSE
      if (res.data.status !== 'completed' && res.data.status !== 'failed' && res.data.status !== 'cancelled') {
        connectSSE(runId);
      }
    });

    return () => {
      eventSourceRef.current?.close();
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [runId, connectSSE, loadDiscoveredCompanies]);

  // Handle promote
  const handlePromote = async () => {
    if (!runId || selectedCompanyIds.size === 0) return;
    setPromoting(true);
    try {
      const res = await promoteCompanies(runId, Array.from(selectedCompanyIds));
      setRun(res.data);
      setIsAwaitingReview(false);
      setSseStage('contact_discovery');
      setSseMessage('Resuming pipeline for promoted companies...');
      // Reconnect SSE for Phase 2+
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
      message.info('Cancellation requested — pipeline will stop shortly');
    } catch (err: any) {
      message.error(err?.response?.data?.detail || 'Failed to cancel pipeline');
      setCancelling(false);
    }
  };

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

  const selectAll = () => setSelectedCompanyIds(new Set(discoveredCompanies.map((c) => c.id)));
  const deselectAll = () => setSelectedCompanyIds(new Set());
  const selectTopMatches = () => {
    const top = discoveredCompanies
      .filter((c) => c.qualification === 'verified_match' || c.qualification === 'best_fit' || (c.icp_match_score != null && c.icp_match_score >= 70))
      .map((c) => c.id);
    setSelectedCompanyIds(new Set(top.length > 0 ? top : discoveredCompanies.slice(0, Math.ceil(discoveredCompanies.length / 2)).map((c) => c.id)));
  };

  const multiStepStages = [
    { key: 'company_discovery', title: 'Discovery', icon: <SearchOutlined /> },
    { key: 'review', title: 'Review & Select', icon: <EyeOutlined /> },
    { key: 'contact_discovery', title: 'Contact Discovery', icon: <TeamOutlined /> },
    { key: 'scoring', title: 'BANT Scoring', icon: <BarChartOutlined /> },
  ];

  const singleRunStages = [
    { key: 'company_discovery', title: 'Company Discovery', icon: <SearchOutlined /> },
    { key: 'contact_discovery', title: 'Contact Discovery', icon: <TeamOutlined /> },
    { key: 'enrichment', title: 'Enrichment', icon: <DatabaseOutlined /> },
    { key: 'scoring', title: 'BANT Scoring', icon: <BarChartOutlined /> },
  ];

  const isMultiStep = run?.pipeline_mode === 'multi_step';
  const stages = isMultiStep ? multiStepStages : singleRunStages;
  const activeStageOrder = isMultiStep
    ? ['company_discovery', 'review', 'contact_discovery', 'scoring', 'completed']
    : stageOrder;

  const currentIndex = activeStageOrder.indexOf(sseStage);
  const isCompleted = run?.status === 'completed' || sseStage === 'completed';
  const isFailed = run?.status === 'failed';
  const isCancelledFinal = run?.status === 'cancelled' || sseStage === 'cancelled';

  const getStepStatus = (index: number) => {
    if (isCompleted) return 'finish';
    if (isFailed) return index <= currentIndex ? 'error' : 'wait';
    if (index < currentIndex) return 'finish';
    if (index === currentIndex) return 'process';
    return 'wait';
  };

  const getElapsedTime = (entryTime: Date) => {
    const diffMs = entryTime.getTime() - startTimeRef.current.getTime();
    const secs = Math.floor(diffMs / 1000);
    if (secs < 60) return `${secs}s`;
    const mins = Math.floor(secs / 60);
    const remainSecs = secs % 60;
    return `${mins}m ${remainSecs}s`;
  };

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
              <Tag color="success" style={{ fontSize: 11 }}>
                FOUND
              </Tag>
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
            <Tag color="orange" style={{ fontSize: 11 }}>
              RETRYING
            </Tag>
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

      default:
        return null;
    }
  };

  const getTimelineDotColor = (entry: ActivityEntry) => {
    if (entry.type === 'company_start') return '#722ed1';
    if (entry.type === 'stage_update') return stageColors[entry.stage || ''] || '#1890ff';
    if (entry.type === 'tool_start') return toolColors[entry.toolName || ''] || '#1890ff';
    if (entry.type === 'tool_result') return '#d9d9d9';
    if (entry.type === 'tool_error') return '#fa8c16';
    return '#faad14';
  };

  // ════════════════════════════════════════
  // REVIEW UI - shown when awaiting_review
  // ════════════════════════════════════════
  if (isAwaitingReview) {
    const getMatchScoreColor = (score: number | null) => {
      if (score == null) return '#999';
      if (score > 10) return score >= 70 ? '#52c41a' : score >= 50 ? '#faad14' : '#ff4d4f';
      return score >= 8 ? '#52c41a' : score >= 6 ? '#faad14' : '#ff4d4f';
    };

    const formatMatchScore = (score: number | null) => {
      if (score == null) return 'N/A';
      return score > 10 ? `${Math.round(score)}%` : `${score}/10`;
    };

    const reviewColumns = [
      {
        title: () => (
          <Checkbox
            checked={selectedCompanyIds.size === discoveredCompanies.length && discoveredCompanies.length > 0}
            indeterminate={selectedCompanyIds.size > 0 && selectedCompanyIds.size < discoveredCompanies.length}
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
        title: 'Match Score',
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
        title: 'Category',
        dataIndex: 'qualification',
        width: 130,
        render: (q: string | null) => {
          if (q === 'verified_match') return <Tag color="green">Verified Match</Tag>;
          if (q === 'potential_match') return <Tag color="blue">Potential Match</Tag>;
          if (q === 'weak_match') return <Tag color="gold">Weak Match</Tag>;
          if (q === 'best_fit') return <Tag color="green">Best Fit</Tag>;
          if (q === 'good_fit') return <Tag color="blue">Good Fit</Tag>;
          if (q === 'possible_fit') return <Tag color="gold">Possible Fit</Tag>;
          return <Tag>{q || 'N/A'}</Tag>;
        },
      },
      {
        title: 'Industry',
        dataIndex: 'industry',
        width: 150,
        render: (ind: string | null) => ind || '-',
      },
      {
        title: 'Location',
        width: 150,
        render: (_: unknown, record: Company) =>
          [record.city, record.state_region, record.country].filter(Boolean).join(', ') || '-',
      },
      {
        title: 'Employees',
        dataIndex: 'employee_count',
        width: 100,
        render: (count: number | null) => count ? count.toLocaleString() : '-',
      },
    ];

    const multiStepStageIndex = ['company_discovery', 'review', 'contact_discovery', 'scoring'];

    return (
      <div style={{ padding: '28px 32px', maxWidth: 1400, margin: '0 auto', width: '100%' }}>
        <div style={{ marginBottom: 24 }}>
          <div className="section-label">Review Mode</div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h1 className="page-title">
              Review Discovered Companies
              {run?.icp_name && <span style={{ fontWeight: 400, fontSize: 15, color: 'var(--g500)' }}> — {run.icp_name}</span>}
              {run?.match_strictness === 'strict' && <Tag color="red" style={{ marginLeft: 8, fontSize: 12 }}>Strict Mode</Tag>}
              {run?.match_strictness === 'relaxed' && <Tag color="blue" style={{ marginLeft: 8, fontSize: 12 }}>Relaxed Mode</Tag>}
            </h1>
            <Button size="small" onClick={() => navigate('/dashboard')} style={{ fontSize: 12 }}>
              ← Back
            </Button>
          </div>
        </div>

        {/* Steps indicator */}
        <Card bordered={false} style={{ marginBottom: 24 }}>
          <Steps
            current={1}
            items={multiStepStages.map((s, i) => ({
              title: s.title,
              icon: i === 1 ? <EyeOutlined /> : i === 0 ? <CheckCircleOutlined style={{ color: '#52c41a' }} /> : s.icon,
              status: i === 0 ? 'finish' : i === 1 ? 'process' : 'wait',
            }))}
          />
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
              {selectedCompanyIds.size} of {discoveredCompanies.length} selected
            </Tag>
          </div>
          <Button
            type="primary"
            size="large"
            disabled={selectedCompanyIds.size === 0}
            loading={promoting}
            onClick={handlePromote}
            icon={<RocketOutlined />}
          >
            Continue with {selectedCompanyIds.size} {selectedCompanyIds.size === 1 ? 'Company' : 'Companies'}
          </Button>
        </div>

        {/* Company review table */}
        <Card bordered={false} style={{ marginBottom: 24 }}>
          <Table
            columns={reviewColumns}
            dataSource={discoveredCompanies}
            rowKey="id"
            loading={reviewLoading}
            pagination={false}
            scroll={{ x: 880 }}
            size="small"
            expandable={{
              expandedRowRender: (record: Company) => (
                <div style={{ padding: '8px 0' }}>
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
                    {record.revenue_estimate != null && (
                      <div>
                        <Text type="secondary" style={{ fontSize: 11 }}>Revenue Est.</Text>
                        <div style={{ fontWeight: 600, fontSize: 13 }}>
                          {record.revenue_estimate >= 1_000_000_000
                            ? `$${(record.revenue_estimate / 1_000_000_000).toFixed(1)}B`
                            : record.revenue_estimate >= 1_000_000
                              ? `$${(record.revenue_estimate / 1_000_000).toFixed(0)}M`
                              : `$${record.revenue_estimate.toLocaleString()}`}
                        </div>
                      </div>
                    )}
                  </div>
                  <DimensionTags rawData={record.raw_data_json} showCount={run?.match_strictness === 'relaxed'} />
                </div>
              ),
            }}
          />
        </Card>

        {/* Phase 1 activity log (collapsible) */}
        {mergedActivityLog.length > 0 && (
          <Collapse
            items={[{
              key: 'phase1-log',
              label: (
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <span>Phase 1 Activity Log</span>
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

  // ════════════════════════════════════════
  // PROGRESS VIEW (running pipeline)
  // ════════════════════════════════════════
  if (!isCompleted && !isFailed && !isCancelledFinal) {
    const overallProgress = (currentIndex / stages.length) * 100;
    const companiesFound = run?.companies_found || 0;
    const contactsFound = run?.contacts_found || 0;

    return (
      <div className="progress-overlay">
        {/* Left Panel - Step Pipeline */}
        <div className="prog-left">
          <div className="prog-left-header">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <div className="prog-title">
                Generating Leads
                {run?.icp_name && <span style={{ fontWeight: 400, fontSize: 13, color: 'var(--g500)' }}> — {run.icp_name}</span>}
                {run?.match_strictness === 'strict' && <Tag color="red" style={{ marginLeft: 8, fontSize: 11, verticalAlign: 'middle' }}>Strict</Tag>}
                {run?.match_strictness === 'relaxed' && <Tag color="blue" style={{ marginLeft: 8, fontSize: 11, verticalAlign: 'middle' }}>Relaxed</Tag>}
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
                    Stop Pipeline
                  </Button>
                </Popconfirm>
                <Button
                  size="small"
                  onClick={() => navigate('/dashboard')}
                  style={{ fontSize: 12 }}
                >
                  ← Back
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
                You can safely leave this page — results are saved automatically.{' '}
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
                    {status === 'done' ? '✓' : status === 'active' ? <div className="spinner" /> : i + 1}
                  </div>
                  <div className="prog-step-info">
                    <div className="prog-step-name">{stage.title}</div>
                    <div className="prog-step-desc">
                      {status === 'active' ? sseMessage : status === 'done' ? 'Completed' : 'Waiting...'}
                    </div>
                    {status === 'done' && (
                      <div className="prog-step-count">✓ Complete</div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

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

        {/* Right Panel - Live Log */}
        <div className="prog-right">
          <div className="prog-right-header">
            <span className="log-title">AI Agent Reasoning</span>
          </div>

          <div className="prog-log-area" ref={logContainerRef}>
            {mergedActivityLog.map((entry) => {
              const timeStr = entry.timestamp.toLocaleTimeString('en-US', {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                hour12: false
              });

              let tagClass = 'system';
              let tagText = 'UPDATE';

              if (entry.type === 'tool_start') {
                if (entry.toolName?.includes('company')) {
                  tagClass = 'discover';
                  tagText = 'SEARCHING';
                } else if (entry.toolName?.includes('people') || entry.toolName?.includes('contact') || entry.toolName?.includes('hunter') || entry.toolName?.includes('lusha')) {
                  tagClass = 'contact';
                  tagText = 'CONTACTS';
                } else if (entry.toolName?.includes('score')) {
                  tagClass = 'score';
                  tagText = 'SCORING';
                } else {
                  tagClass = 'icp';
                  tagText = 'RESEARCH';
                }
              } else if (entry.type === 'stage_update') {
                if (entry.stage === 'completed') {
                  tagClass = 'done';
                  tagText = 'COMPLETE';
                } else {
                  tagClass = 'icp';
                  tagText = 'PROGRESS';
                }
              } else if (entry.type === 'agent_reasoning') {
                tagClass = 'icp';
                tagText = 'REASONING';
              } else if (entry.type === 'tool_result') {
                tagClass = 'done';
                tagText = 'FOUND';
              } else if (entry.type === 'tool_error') {
                tagClass = 'score';
                tagText = 'RETRY';
              } else if (entry.type === 'company_start') {
                tagClass = 'icp';
                tagText = 'COMPANY';
              }

              let message = '';
              if (entry.type === 'tool_start') {
                message = `${entry.displayName || entry.toolName}`;
                if (entry.context) {
                  message += ` — ${entry.context.substring(0, 80)}${entry.context.length > 80 ? '...' : ''}`;
                }
              } else if (entry.type === 'stage_update') {
                message = entry.message || '';
              } else if (entry.type === 'agent_reasoning') {
                message = entry.text?.substring(0, 100) + (entry.text && entry.text.length > 100 ? '...' : '') || '';
              } else if (entry.type === 'tool_result') {
                message = friendlyResultSummary(entry.toolName || '', entry.resultPreview || '');
              } else if (entry.type === 'tool_error') {
                message = friendlyErrorMessage(entry.toolName || '', entry.errorMessage || '');
              } else if (entry.type === 'company_start') {
                message = `Processing company ${entry.companyIndex}/${entry.totalCompanies}: ${entry.companyName}`;
              }

              return (
                <div key={entry.id} className="log-entry">
                  <div className="log-time">{timeStr}</div>
                  <div className={`log-tag ${tagClass}`}>{tagText}</div>
                  <div className="log-msg">{message}</div>
                </div>
              );
            })}
            {mergedActivityLog.length === 0 && (
              <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--g400)' }}>
                Waiting for activity...
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  // ════════════════════════════════════════
  // COMPLETED / FAILED VIEW
  // ════════════════════════════════════════
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
            items={stages.map((s, i) => ({
              title: s.title,
              icon: getStepStatus(i) === 'process' ? <LoadingOutlined /> : s.icon,
              status: getStepStatus(i) as 'wait' | 'process' | 'finish' | 'error',
            }))}
          />

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
