import React, { useEffect, useState, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Button, Table, Select, Input, Spin, message, Tooltip, Progress,
} from 'antd';
import {
  ArrowLeftOutlined, ReloadOutlined, UnorderedListOutlined, AppstoreOutlined,
  UploadOutlined, SettingOutlined, TeamOutlined, ThunderboltOutlined,
  UserOutlined, CloseCircleOutlined, SearchOutlined, FilterOutlined,
  LoadingOutlined, CheckCircleOutlined, ExperimentOutlined,
} from '@ant-design/icons';
import { PillTabs, Badge, EmptyState, SourceBadge, KpiStrip } from '../components/ui';
import {
  getTrackingList, getListMembers, updateMember, getOutreachSummary,
  detectSignalsForList, enrichList, getLatestSignalDetection,
  cancelSignalDetection, getSignalDetectionStreamUrl,
  getSignalDetectionLogs,
  enrichListAsync, getLatestEnrichment, getEnrichmentStreamUrl,
  cancelEnrichment, getEnrichmentLogs,
  type MembersResponse,
} from '../api/trackingApi';
import { listBatches, dismissBatch, type IngestBatchSummary } from '../api/ingestApi';
import SignalHintsDrawer from '../components/SignalHintsDrawer';
import KanbanBoard from '../components/KanbanBoard';
import {
  TrackingList, TrackingListMember, SignalHints,
  OUTREACH_STATUSES, OUTREACH_STATUS_LABELS, OUTREACH_STATUS_COLORS,
  SIGNAL_TYPE_LABELS,
} from '../types';
import { getSignalFreshness, FRESHNESS_DESCRIPTIONS } from '../utils/signalFreshness';

type ViewMode = 'table' | 'kanban';

const TrackingListDetailPage: React.FC = () => {
  const { listId } = useParams<{ listId: string }>();
  const navigate = useNavigate();

  const [list, setList] = useState<TrackingList | null>(null);
  const [members, setMembers] = useState<TrackingListMember[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState<ViewMode>('table');
  const [outreachSummary, setOutreachSummary] = useState<Record<string, number>>({});
  const [sortBy, setSortBy] = useState('signal_heat_score');
  const [sortOrder, setSortOrder] = useState('desc');
  const [page, setPage] = useState(1);
  const pageSize = 50;
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [industryFilter, setIndustryFilter] = useState<string | undefined>(undefined);
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  const [detectingSignals, setDetectingSignals] = useState(false);
  const [enrichingContacts, setEnrichingContacts] = useState(false);
  const [hintsDrawerOpen, setHintsDrawerOpen] = useState(false);
  const [detectionRunId, setDetectionRunId] = useState<string | null>(null);
  const [detectionProgress, setDetectionProgress] = useState(0);
  const [detectionCompany, setDetectionCompany] = useState<string>('');
  const [detectionSignals, setDetectionSignals] = useState(0);
  const detectionEsRef = useRef<EventSource | null>(null);
  const [detectionActivityLog, setDetectionActivityLog] = useState<{ id: number; type: string; text: string; ts: number }[]>([]);
  const [detectionActivityOpen, setDetectionActivityOpen] = useState(false);
  const detectionLogIdRef = useRef(0);

  // Async enrichment state
  const [enrichmentRunId, setEnrichmentRunId] = useState<string | null>(null);
  const [enrichmentProgress, setEnrichmentProgress] = useState(0);
  const [enrichmentCompany, setEnrichmentCompany] = useState('');
  const [enrichmentContactsFound, setEnrichmentContactsFound] = useState(0);
  const [enrichmentActivityLog, setEnrichmentActivityLog] = useState<{ id: number; type: string; text: string; ts: number }[]>([]);
  const [enrichmentActivityOpen, setEnrichmentActivityOpen] = useState(false);
  const enrichmentEsRef = useRef<EventSource | null>(null);
  const enrichmentLogIdRef = useRef(0);

  const [activeBatches, setActiveBatches] = useState<IngestBatchSummary[]>([]);

  const fetchList = useCallback(async () => {
    if (!listId) return;
    try {
      const res = await getTrackingList(listId);
      setList(res.data);
    } catch {
      message.error('Failed to load tracking list');
    }
  }, [listId]);

  const fetchMembers = useCallback(async () => {
    if (!listId) return;
    setLoading(true);
    try {
      const res = await getListMembers(listId, {
        sort_by: sortBy, sort_order: sortOrder,
        limit: pageSize, offset: (page - 1) * pageSize,
        search: debouncedSearch || undefined,
        industry_filter: industryFilter,
        outreach_status: statusFilter,
      });
      setMembers(res.data.members || []);
      setTotal(res.data.total || 0);
    } catch {
      setMembers([]);
    } finally {
      setLoading(false);
    }
  }, [listId, sortBy, sortOrder, page, debouncedSearch, industryFilter, statusFilter]);

  const fetchOutreachSummary = useCallback(async () => {
    if (!listId) return;
    try {
      const res = await getOutreachSummary(listId);
      setOutreachSummary(res.data.summary || {});
    } catch { /* ignore */ }
  }, [listId]);

  useEffect(() => { fetchList(); }, [fetchList]);

  // Fetch active ingest batches targeting this list
  useEffect(() => {
    if (!listId) return;
    listBatches(listId, true, 5).then((res) => {
      const active = res.data.filter(
        (b) => b.has_filter && b.evaluation_status !== 'completed' && b.evaluation_status !== 'not_applicable',
      );
      const recent = res.data.filter(
        (b) => b.has_filter && b.evaluation_status === 'completed',
      );
      setActiveBatches([...active, ...recent.slice(0, 2)]);
    }).catch(() => { /* ignore */ });
  }, [listId]);
  useEffect(() => { fetchMembers(); }, [fetchMembers]);
  useEffect(() => { fetchOutreachSummary(); }, [fetchOutreachSummary]);

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchQuery), 400);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Reset to page 1 when filters change
  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, industryFilter, statusFilter]);

  // Helper to add a detection activity entry
  const addDetectionActivity = useCallback((type: string, text: string) => {
    setDetectionActivityLog((prev) => {
      const id = ++detectionLogIdRef.current;
      const next = [...prev, { id, type, text, ts: Date.now() }];
      return next.length > 200 ? next.slice(-200) : next;
    });
  }, []);

  // SSE for signal detection progress
  const connectDetectionSSE = useCallback((runId: string, skipReset?: boolean) => {
    if (!listId) return;
    detectionEsRef.current?.close();
    setDetectingSignals(true);
    setDetectionRunId(runId);
    if (!skipReset) {
      setDetectionProgress(0);
      setDetectionCompany('');
      setDetectionSignals(0);
      setDetectionActivityLog([]);
      detectionLogIdRef.current = 0;
    }

    const url = getSignalDetectionStreamUrl(listId, runId);
    const es = new EventSource(url);
    detectionEsRef.current = es;

    es.addEventListener('signal_progress', (e) => {
      const data = JSON.parse(e.data);
      setDetectionProgress(data.percent || 0);
      setDetectionCompany(data.company_name || '');
      addDetectionActivity('progress', `Scanning ${data.company_name || 'company'}...`);
    });
    es.addEventListener('tool_start', (e) => {
      const data = JSON.parse(e.data);
      addDetectionActivity('tool_start', data.label || `Running ${data.tool}...`);
    });
    es.addEventListener('tool_result', (e) => {
      const data = JSON.parse(e.data);
      const count = data.results_count || 0;
      const saved = data.signals_saved || 0;
      const label = data.label || data.tool;
      const summary = saved > 0
        ? `${label}: ${count} results, ${saved} signal${saved > 1 ? 's' : ''} saved`
        : `${label}: ${count} result${count !== 1 ? 's' : ''}`;
      addDetectionActivity('tool_result', summary);
    });
    es.addEventListener('signal_found', (e) => {
      const data = JSON.parse(e.data);
      addDetectionActivity('signal_found', `${data.priority?.toUpperCase() || ''} ${data.signal_type}: ${data.title || 'Signal detected'}`);
    });
    es.addEventListener('company_complete', (e) => {
      const data = JSON.parse(e.data);
      setDetectionProgress(data.percent || 0);
      setDetectionSignals((prev) => prev + (data.signals_found || 0));
      addDetectionActivity('complete', `${data.company_name}: ${data.signals_found} signal${data.signals_found !== 1 ? 's' : ''} found`);
    });
    es.addEventListener('signal_detection_completed', (e) => {
      const data = JSON.parse(e.data);
      setDetectingSignals(false);
      setDetectionRunId(null);
      setDetectionProgress(100);
      message.success(`Signal scan complete: ${data.signals_detected} signals detected across ${data.companies_scanned} companies`);
      fetchMembers();
      es.close();
    });
    es.addEventListener('signal_detection_failed', (e) => {
      const data = JSON.parse(e.data);
      setDetectingSignals(false);
      setDetectionRunId(null);
      message.error(data.message || 'Signal detection failed');
      es.close();
    });
    es.addEventListener('signal_detection_cancelled', () => {
      setDetectingSignals(false);
      setDetectionRunId(null);
      message.info('Signal detection cancelled');
      fetchMembers();
      es.close();
    });
    es.onerror = () => {
      if (es.readyState === EventSource.CLOSED && detectionEsRef.current === es) {
        setDetectingSignals(false);
        setDetectionRunId(null);
      }
    };
  }, [listId, fetchMembers, addDetectionActivity]);

  // Return-to-page recovery for signal detection
  useEffect(() => {
    if (!listId) return;
    getLatestSignalDetection(listId).then(async (res) => {
      const run = res.data.run;
      if (run && run.status === 'running') {
        // Replay persisted logs first
        try {
          const logsRes = await getSignalDetectionLogs(listId, run.run_id);
          const logs = logsRes.data;
          const entries: { id: number; type: string; text: string; ts: number }[] = [];
          for (const log of logs) {
            const d = log.event_data as Record<string, string | number>;
            let text = '';
            if (log.event_type === 'signal_progress') text = `Scanning ${d.company_name || 'company'}...`;
            else if (log.event_type === 'tool_start') text = (d.label as string) || `Running ${d.tool}...`;
            else if (log.event_type === 'tool_result') {
              const saved = (d.signals_saved as number) || 0;
              const count = (d.results_count as number) || 0;
              text = saved > 0 ? `${d.label}: ${count} results, ${saved} signal${saved > 1 ? 's' : ''} saved` : `${d.label}: ${count} result${count !== 1 ? 's' : ''}`;
            } else if (log.event_type === 'signal_found') text = `${(d.priority as string)?.toUpperCase() || ''} ${d.signal_type}: ${d.title || 'Signal detected'}`;
            else if (log.event_type === 'company_complete') text = `${d.company_name}: ${d.signals_found} signal${(d.signals_found as number) !== 1 ? 's' : ''} found`;
            else continue;
            entries.push({ id: ++detectionLogIdRef.current, type: log.event_type, text, ts: Date.now() });
          }
          setDetectionActivityLog(entries);
        } catch { /* proceed without replay */ }

        connectDetectionSSE(run.run_id, true);
        setDetectionProgress(
          run.total_companies > 0 ? Math.round((run.processed_companies / run.total_companies) * 100) : 0,
        );
        setDetectionSignals(run.signals_detected);
      }
    }).catch(() => {});
  }, [listId, connectDetectionSSE]);

  // Helper to add an enrichment activity entry
  const addEnrichmentActivity = useCallback((type: string, text: string) => {
    setEnrichmentActivityLog((prev) => {
      const id = ++enrichmentLogIdRef.current;
      const next = [...prev, { id, type, text, ts: Date.now() }];
      return next.length > 200 ? next.slice(-200) : next;
    });
  }, []);

  // SSE for async enrichment progress
  const connectEnrichmentSSE = useCallback((runId: string, skipReset?: boolean) => {
    if (!listId) return;
    enrichmentEsRef.current?.close();
    setEnrichingContacts(true);
    setEnrichmentRunId(runId);
    if (!skipReset) {
      setEnrichmentProgress(0);
      setEnrichmentCompany('');
      setEnrichmentContactsFound(0);
      setEnrichmentActivityLog([]);
      enrichmentLogIdRef.current = 0;
    }

    const url = getEnrichmentStreamUrl(listId, runId);
    const es = new EventSource(url);
    enrichmentEsRef.current = es;

    es.addEventListener('enrichment_progress', (e) => {
      const data = JSON.parse(e.data);
      setEnrichmentProgress(data.percent || 0);
      setEnrichmentCompany(data.company_name || '');
      addEnrichmentActivity('progress', `Enriching ${data.company_name || 'company'}...`);
    });
    es.addEventListener('tool_start', (e) => {
      const data = JSON.parse(e.data);
      addEnrichmentActivity('tool_start', data.label || `Running ${data.tool}...`);
    });
    es.addEventListener('tool_result', (e) => {
      const data = JSON.parse(e.data);
      addEnrichmentActivity('tool_result', `${data.label || data.tool}: ${data.contacts_found || 0} contacts found`);
    });
    es.addEventListener('company_complete', (e) => {
      const data = JSON.parse(e.data);
      setEnrichmentProgress(data.percent || 0);
      setEnrichmentContactsFound((prev) => prev + (data.contacts_for_company || 0));
      addEnrichmentActivity('complete', `${data.company_name}: ${data.contacts_for_company || 0} contacts enriched`);
    });
    es.addEventListener('enrichment_completed', (e) => {
      const data = JSON.parse(e.data);
      setEnrichingContacts(false);
      setEnrichmentRunId(null);
      setEnrichmentProgress(100);
      message.success(`Enrichment complete: ${data.total_contacts} contacts found across ${data.companies_enriched} companies`);
      fetchMembers();
      es.close();
    });
    es.addEventListener('enrichment_failed', (e) => {
      const data = JSON.parse(e.data);
      setEnrichingContacts(false);
      setEnrichmentRunId(null);
      message.error(data.message || 'Enrichment failed');
      es.close();
    });
    es.addEventListener('enrichment_cancelled', () => {
      setEnrichingContacts(false);
      setEnrichmentRunId(null);
      message.info('Enrichment cancelled');
      fetchMembers();
      es.close();
    });
    es.onerror = () => {
      if (es.readyState === EventSource.CLOSED && enrichmentEsRef.current === es) {
        setEnrichingContacts(false);
        setEnrichmentRunId(null);
      }
    };
  }, [listId, fetchMembers, addEnrichmentActivity]);

  // Return-to-page recovery for enrichment
  useEffect(() => {
    if (!listId) return;
    getLatestEnrichment(listId).then(async (res) => {
      const run = res.data.run;
      if (run && run.status === 'running') {
        try {
          const logsRes = await getEnrichmentLogs(listId, run.run_id);
          const entries: { id: number; type: string; text: string; ts: number }[] = [];
          for (const log of logsRes.data) {
            const d = log.event_data as Record<string, string | number>;
            let text = '';
            if (log.event_type === 'enrichment_progress') text = `Enriching ${d.company_name || 'company'}...`;
            else if (log.event_type === 'tool_start') text = (d.label as string) || `Running ${d.tool}...`;
            else if (log.event_type === 'tool_result') text = `${d.label || d.tool}: ${d.contacts_found || 0} contacts found`;
            else if (log.event_type === 'company_complete') text = `${d.company_name}: ${d.contacts_for_company || 0} contacts enriched`;
            else continue;
            entries.push({ id: ++enrichmentLogIdRef.current, type: log.event_type, text, ts: Date.now() });
          }
          setEnrichmentActivityLog(entries);
        } catch { /* proceed without replay */ }

        connectEnrichmentSSE(run.run_id, true);
        setEnrichmentProgress(
          run.total_companies > 0 ? Math.round((run.processed_companies / run.total_companies) * 100) : 0,
        );
        setEnrichmentContactsFound(run.contacts_found);
      }
    }).catch(() => {});
  }, [listId, connectEnrichmentSSE]);

  useEffect(() => {
    return () => { detectionEsRef.current?.close(); };
  }, []);

  const handleStatusChange = async (membershipId: string, newStatus: string) => {
    if (!listId) return;
    try {
      await updateMember(listId, membershipId, { outreach_status: newStatus });
      fetchMembers();
      fetchOutreachSummary();
    } catch {
      message.error('Failed to update status');
    }
  };

  const getHeatColor = (score: number) => {
    if (score >= 75) return '#f5222d';
    if (score >= 50) return '#fa541c';
    if (score >= 25) return '#faad14';
    return '#8c8c8c';
  };

  const getScoreColor = (score: number | null | undefined): string => {
    if (score == null) return '#d9d9d9';
    if (score >= 70) return '#52c41a';
    if (score >= 40) return '#faad14';
    return '#ff4d4f';
  };

  const formatRevenue = (v: number | null) => {
    if (!v) return '-';
    if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
    if (v >= 1e6) return `$${(v / 1e6).toFixed(0)}M`;
    return `$${v.toLocaleString()}`;
  };

  const uniqueIndustries = [...new Set(members.map((m) => m.industry).filter(Boolean))] as string[];
  const activeFilterCount = [industryFilter, statusFilter].filter(Boolean).length;

  // Table columns
  const columns = [
    {
      title: 'Company',
      key: 'company',
      width: 240,
      render: (_: unknown, record: TrackingListMember) => (
        <div>
          <p className="text-sm font-semibold text-gray-900">{record.company_name || 'Unknown'}</p>
          <p className="text-xs text-gray-400">{record.domain}</p>
        </div>
      ),
    },
    {
      title: 'Signal Heat',
      dataIndex: 'signal_heat_score',
      key: 'signal_heat_score',
      width: 110,
      sorter: true,
      render: (score: number) => (
        <div
          className="w-9 h-9 rounded-full flex items-center justify-center text-xs font-bold"
          style={{
            background: `${getHeatColor(score)}15`,
            color: getHeatColor(score),
          }}
        >
          {Math.round(score)}
        </div>
      ),
    },
    {
      title: 'Latest Signal',
      key: 'latest_signal',
      width: 220,
      render: (_: unknown, record: TrackingListMember) => {
        if (!record.latest_signal) return <span className="text-gray-300 text-xs">No signals</span>;
        const s = record.latest_signal;
        const freshness = getSignalFreshness(s.evidence_date, s.detected_at);
        return (
          <div>
            <div className="flex items-center gap-1.5 flex-wrap">
              <Badge variant="signal-type" signalType={s.signal_type} className="text-[10px]">
                {SIGNAL_TYPE_LABELS[s.signal_type] || s.signal_type}
              </Badge>
              <Tooltip title={FRESHNESS_DESCRIPTIONS[freshness.tier]}>
                <span
                  className="inline-flex items-center text-[10px] font-medium px-1.5 py-0.5 rounded-full"
                  style={{ color: freshness.color, background: freshness.bgColor }}
                >
                  {freshness.label}
                </span>
              </Tooltip>
            </div>
            <p className="text-xs text-gray-600 mt-1 leading-snug line-clamp-2">
              {s.title}
            </p>
          </div>
        );
      },
    },
    {
      title: 'Industry',
      dataIndex: 'industry',
      key: 'industry',
      width: 140,
      render: (v: string | null) => <span className="text-sm text-gray-600">{v || '-'}</span>,
    },
    {
      title: 'Revenue',
      key: 'revenue',
      width: 100,
      render: (_: unknown, r: TrackingListMember) => (
        <span className="text-sm text-gray-600">{formatRevenue(r.revenue_estimate)}</span>
      ),
    },
    {
      title: 'Size',
      key: 'size',
      width: 100,
      render: (_: unknown, r: TrackingListMember) => (
        <span className="text-sm text-gray-600">
          {r.employee_count ? `${r.employee_count.toLocaleString()} emp` : '-'}
        </span>
      ),
    },
    {
      title: 'Contacts',
      key: 'contacts',
      width: 90,
      render: (_: unknown, r: TrackingListMember) => {
        const count = r.best_known_contacts?.length || 0;
        return (
          <Tooltip title={count > 0 ? `${count} contacts found` : 'Not enriched'}>
            <span className={`flex items-center gap-1 text-xs ${count > 0 ? 'text-blue-600' : 'text-gray-300'}`}>
              <UserOutlined /> {count > 0 ? count : '-'}
            </span>
          </Tooltip>
        );
      },
    },
    {
      title: 'Score',
      dataIndex: 'best_final_score',
      key: 'best_final_score',
      width: 80,
      render: (v: number | null) => v != null ? (
        <span className="text-sm font-bold" style={{ color: getScoreColor(v) }}>{Math.round(v)}</span>
      ) : <span className="text-gray-300">-</span>,
    },
    {
      title: 'Outreach',
      dataIndex: 'outreach_status',
      key: 'outreach_status',
      width: 160,
      render: (status: string, record: TrackingListMember) => (
        <Select
          value={status}
          size="small"
          style={{ width: '100%' }}
          onChange={(val) => handleStatusChange(record.membership_id, val)}
          onClick={(e) => e.stopPropagation()}
          options={OUTREACH_STATUSES.map((s) => ({
            value: s,
            label: (
              <span className="flex items-center gap-1.5">
                <span
                  className="w-2 h-2 rounded-full inline-block"
                  style={{ background: OUTREACH_STATUS_COLORS[s] }}
                />
                {OUTREACH_STATUS_LABELS[s]}
              </span>
            ),
          }))}
        />
      ),
    },
    {
      title: 'Added',
      dataIndex: 'added_at',
      key: 'added_at',
      width: 100,
      render: (v: string | null) => (
        <span className="text-xs text-gray-400">
          {v ? new Date(v).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : '-'}
        </span>
      ),
    },
  ];

  if (!listId) return null;

  const hintsCount = (list?.signal_hints?.budget_signals?.length || 0) +
    (list?.signal_hints?.urgency_signals?.length || 0) +
    (list?.signal_hints?.custom_hints?.length || 0);

  return (
    <div className="px-10 py-6 max-w-[1600px] mx-auto">
      {/* Active / recent ingest batches */}
      {activeBatches.length > 0 && (
        <div className="mb-4 flex flex-col gap-2">
          {activeBatches.map((b) => {
            const isActive = b.evaluation_status !== 'completed';
            return (
              <div
                key={b.batch_id}
                className={`flex items-center justify-between px-4 py-2.5 rounded-lg border cursor-pointer transition-colors ${
                  isActive
                    ? 'bg-purple-50 border-purple-200 hover:bg-purple-100'
                    : 'bg-gray-50 border-gray-200 hover:bg-gray-100'
                }`}
                onClick={() => navigate(`/ingest/${b.batch_id}`)}
              >
                <div className="flex items-center gap-3">
                  {isActive ? (
                    <LoadingOutlined spin className="text-purple-600" />
                  ) : (
                    <CheckCircleOutlined className="text-green-600" />
                  )}
                  <div>
                    <span className="text-sm font-medium text-gray-800">
                      {b.name || 'Import'}
                    </span>
                    <span className="text-xs text-gray-500 ml-2">
                      {b.total_rows} companies
                      {b.enriched_count ? ` · ${b.enriched_count} evaluated` : ''}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                    isActive
                      ? 'bg-purple-100 text-purple-700'
                      : 'bg-green-100 text-green-700'
                  }`}>
                    {isActive ? 'Evaluating...' : 'View Results'}
                  </span>
                  {!isActive && (
                    <button
                      title="Dismiss"
                      onClick={(e) => {
                        e.stopPropagation();
                        dismissBatch(b.batch_id).then(() => {
                          setActiveBatches((prev) => prev.filter((x) => x.batch_id !== b.batch_id));
                        }).catch(() => message.error('Failed to dismiss'));
                      }}
                      className="w-5 h-5 flex items-center justify-center rounded text-gray-400 hover:text-gray-600 hover:bg-gray-200 transition-colors"
                    >
                      <CloseCircleOutlined style={{ fontSize: 12 }} />
                    </button>
                  )}
                  {isActive && <ExperimentOutlined className="text-gray-400 text-xs" />}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/tracking')}
            className="w-8 h-8 flex items-center justify-center rounded-md text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors"
          >
            <ArrowLeftOutlined />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold text-gray-900">
                {list?.name || 'Loading...'}
              </h1>
              {list && (
                <Badge variant="count">{list.company_count} companies</Badge>
              )}
            </div>
            {list?.description && (
              <p className="text-sm text-gray-500 mt-0.5">{list.description}</p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Tooltip title="Configure budget/urgency signals and target roles">
            <Button
              icon={<SettingOutlined />}
              onClick={() => setHintsDrawerOpen(true)}
              className="!rounded-md"
            >
              Signal Hints
              {hintsCount > 0 && (
                <span className="ml-1.5 text-[10px] font-semibold bg-brand text-white px-1.5 py-0.5 rounded-full leading-none">
                  {hintsCount}
                </span>
              )}
            </Button>
          </Tooltip>
          <Button
            icon={<UploadOutlined />}
            onClick={() => navigate(`/ingest?targetListId=${listId}`)}
            className="!rounded-md"
          >
            Import
          </Button>
          {selectedRowKeys.length > 0 && (
            <Tooltip title={`Detect signals for ${selectedRowKeys.length} selected companies`}>
              <Button
                icon={<ThunderboltOutlined />}
                type="primary"
                ghost
                loading={detectingSignals}
                disabled={detectingSignals}
                onClick={async () => {
                  const selectedKbIds = members
                    .filter((m) => selectedRowKeys.includes(m.membership_id))
                    .map((m) => m.company_kb_id);
                  try {
                    const res = await detectSignalsForList(listId!, selectedKbIds);
                    connectDetectionSSE(res.data.run_id);
                    setSelectedRowKeys([]);
                  } catch {
                    message.error('Failed to start signal detection');
                  }
                }}
                className="!rounded-md"
              >
                Detect Signals for {selectedRowKeys.length}
              </Button>
            </Tooltip>
          )}
          <Tooltip title="Scan all tracked companies for new signals (funding, hiring, exec changes, tech adoption, partnerships, etc.)">
            <Button
              icon={<ThunderboltOutlined />}
              loading={detectingSignals}
              disabled={detectingSignals}
              onClick={async () => {
                if (!members.length) { message.info('No companies to scan'); return; }
                try {
                  const res = await detectSignalsForList(listId!);
                  connectDetectionSSE(res.data.run_id);
                } catch {
                  message.error('Failed to start signal detection');
                }
              }}
              className="!rounded-md"
            >
              Detect All
            </Button>
          </Tooltip>
          <Tooltip title="Find decision-maker contacts using Apollo and web research. Configure target roles in Signal Hints.">
            <Button
              icon={<TeamOutlined />}
              loading={enrichingContacts}
              disabled={enrichingContacts}
              onClick={async () => {
                if (!members.length) { message.info('No companies to enrich'); return; }
                try {
                  const targetRoles = list?.signal_hints?.target_roles;
                  const res = await enrichListAsync(listId!, {
                    target_roles: targetRoles?.length ? targetRoles : undefined,
                    max_companies: 20,
                  });
                  connectEnrichmentSSE(res.data.run_id);
                } catch {
                  message.error('Failed to start contact enrichment');
                }
              }}
              className="!rounded-md"
            >
              Enrich Contacts
            </Button>
          </Tooltip>
          <PillTabs
            tabs={[
              { key: 'table', icon: <UnorderedListOutlined /> },
              { key: 'kanban', icon: <AppstoreOutlined /> },
            ]}
            activeKey={viewMode}
            onChange={(v) => setViewMode(v as ViewMode)}
          />
          <Tooltip title="Refresh">
            <button
              onClick={() => { fetchMembers(); fetchOutreachSummary(); }}
              className="w-8 h-8 flex items-center justify-center rounded-md text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors"
            >
              <ReloadOutlined />
            </button>
          </Tooltip>
        </div>
      </div>

      {/* Signal Hints Summary Bar */}
      {list && hintsCount > 0 && (
        <div className="flex flex-wrap gap-1.5 items-center px-3.5 py-2 bg-brand-pale rounded-lg border border-brand-light/20 mb-4">
          <span className="text-xs font-semibold text-brand mr-1">Signal Hints:</span>
          {list.signal_hints?.budget_signals?.map((s) => (
            <Badge key={`b-${s}`} className="bg-green-50 text-green-700 text-[11px]">$ {s}</Badge>
          ))}
          {list.signal_hints?.urgency_signals?.map((s) => (
            <Badge key={`u-${s}`} className="bg-orange-50 text-orange-700 text-[11px]">! {s}</Badge>
          ))}
          {list.signal_hints?.custom_hints?.map((s) => (
            <Badge key={`c-${s}`} className="bg-blue-50 text-blue-700 text-[11px]">{s}</Badge>
          ))}
          {(list.signal_hints?.target_roles?.length || 0) > 0 && (
            <Badge className="bg-purple-50 text-purple-700 text-[11px]">
              {list.signal_hints!.target_roles!.length} target roles
            </Badge>
          )}
        </div>
      )}

      {/* KPI Summary Strip */}
      {!loading && members.length > 0 && (
        <KpiStrip
          items={[
            { label: 'Total Companies', value: total, color: '#5C2D8F' },
            {
              label: 'Avg Heat Score',
              value: members.length > 0
                ? Math.round(members.reduce((sum, m) => sum + m.signal_heat_score, 0) / members.length)
                : 0,
              color: '#fa541c',
            },
            { label: 'With Signals', value: members.filter((m) => m.latest_signal).length, color: '#1E9B6B' },
            { label: 'Enriched', value: members.filter((m) => m.enrichment_status === 'enriched').length, color: '#1890ff' },
          ]}
          className="mb-4"
        />
      )}

      {/* Search & Filter Bar */}
      {!loading && members.length > 0 && (
        <div className="flex items-center gap-3 mb-4 flex-wrap">
          <FilterOutlined className="text-gray-400 text-xs" />
          <Input
            placeholder="Search company..."
            prefix={<SearchOutlined className="text-gray-400" />}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            allowClear
            style={{ width: 220 }}
            className="!rounded-md"
          />
          <Select
            placeholder="Industry"
            value={industryFilter}
            onChange={setIndustryFilter}
            allowClear
            showSearch
            style={{ width: 180 }}
            options={uniqueIndustries.map((i) => ({ label: i, value: i }))}
          />
          <Select
            placeholder="Outreach status"
            value={statusFilter}
            onChange={setStatusFilter}
            allowClear
            style={{ width: 160 }}
            options={OUTREACH_STATUSES.map((s) => ({
              value: s,
              label: OUTREACH_STATUS_LABELS[s],
            }))}
          />
          {activeFilterCount > 0 && (
            <button
              onClick={() => { setIndustryFilter(undefined); setStatusFilter(undefined); setSearchQuery(''); }}
              className="text-xs text-brand hover:text-brand-dark transition-colors"
            >
              Clear filters ({activeFilterCount})
            </button>
          )}
        </div>
      )}

      {/* Signal Detection Progress */}
      {detectingSignals && detectionRunId && (
        <div className="px-4 py-3.5 bg-brand-bg rounded-xl border border-brand-light/20 mb-4">
          <div className="flex items-center gap-4">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1.5">
                <ThunderboltOutlined className="text-brand" />
                <span className="text-sm font-semibold text-brand">Detecting Signals...</span>
                {detectionCompany && (
                  <span className="text-xs text-gray-500">Scanning: {detectionCompany}</span>
                )}
              </div>
              <Progress
                percent={detectionProgress}
                strokeColor="#5C2D8F"
                size="small"
                className="!mb-1"
              />
              <div className="flex items-center gap-3">
                <span className="text-xs text-gray-500">{detectionSignals} signals found so far</span>
                <button
                  onClick={() => setDetectionActivityOpen((v) => !v)}
                  className="text-xs text-brand hover:text-brand-dark transition-colors"
                >
                  {detectionActivityOpen ? 'Hide' : 'Show'} activity ({detectionActivityLog.length})
                </button>
              </div>
            </div>
            <Tooltip title="Cancel signal detection">
              <button
                onClick={() => { if (detectionRunId && listId) cancelSignalDetection(listId, detectionRunId); }}
                className="w-7 h-7 flex items-center justify-center rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
              >
                <CloseCircleOutlined />
              </button>
            </Tooltip>
          </div>
          {detectionActivityOpen && detectionActivityLog.length > 0 && (
            <div className="mt-2 max-h-48 overflow-y-auto border-t border-brand-light/20 pt-2 space-y-0.5">
              {detectionActivityLog.slice(-50).map((entry) => (
                <div key={entry.id} className="text-xs flex items-start gap-1.5">
                  <span className={`inline-block w-1.5 h-1.5 rounded-full mt-1 flex-shrink-0 ${
                    entry.type === 'signal_found' ? 'bg-green-500'
                    : entry.type === 'tool_start' ? 'bg-blue-400'
                    : entry.type === 'tool_result' ? 'bg-blue-300'
                    : entry.type === 'complete' ? 'bg-purple-500'
                    : 'bg-gray-300'
                  }`} />
                  <span className="text-gray-600">{entry.text}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Enrichment Progress */}
      {enrichingContacts && enrichmentRunId && (
        <div className="px-4 py-3.5 bg-green-50 rounded-xl border border-green-200 mb-4">
          <div className="flex items-center gap-4">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1.5">
                <TeamOutlined className="text-green-700" />
                <span className="text-sm font-semibold text-green-700">Enriching Contacts...</span>
                {enrichmentCompany && (
                  <span className="text-xs text-gray-500">Processing: {enrichmentCompany}</span>
                )}
              </div>
              <Progress
                percent={enrichmentProgress}
                strokeColor="#15803d"
                size="small"
                className="!mb-1"
              />
              <div className="flex items-center gap-3">
                <span className="text-xs text-gray-500">{enrichmentContactsFound} contacts found so far</span>
                <button
                  onClick={() => setEnrichmentActivityOpen((v) => !v)}
                  className="text-xs text-green-700 hover:text-green-800 transition-colors"
                >
                  {enrichmentActivityOpen ? 'Hide' : 'Show'} activity ({enrichmentActivityLog.length})
                </button>
              </div>
            </div>
            <Tooltip title="Cancel enrichment">
              <button
                onClick={() => { if (enrichmentRunId && listId) cancelEnrichment(listId, enrichmentRunId); }}
                className="w-7 h-7 flex items-center justify-center rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
              >
                <CloseCircleOutlined />
              </button>
            </Tooltip>
          </div>
          {enrichmentActivityOpen && enrichmentActivityLog.length > 0 && (
            <div className="mt-2 max-h-48 overflow-y-auto border-t border-green-200 pt-2 space-y-0.5">
              {enrichmentActivityLog.slice(-50).map((entry) => (
                <div key={entry.id} className="text-xs flex items-start gap-1.5">
                  <span className={`inline-block w-1.5 h-1.5 rounded-full mt-1 flex-shrink-0 ${
                    entry.type === 'tool_start' ? 'bg-blue-400'
                    : entry.type === 'tool_result' ? 'bg-blue-300'
                    : entry.type === 'complete' ? 'bg-green-500'
                    : 'bg-gray-300'
                  }`} />
                  <span className="text-gray-600">{entry.text}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Content */}
      {loading ? (
        <div className="flex justify-center py-20"><Spin size="large" /></div>
      ) : members.length === 0 ? (
        <div className="bg-white border border-gray-200 rounded-lg">
          <EmptyState
            icon={<UploadOutlined />}
            title="No companies in this list yet"
            description="Add companies from pipeline results, knowledge base, or upload a list."
            className="py-20"
          />
        </div>
      ) : viewMode === 'table' ? (
        <div className="ql-table">
          <Table
            dataSource={members}
            columns={columns}
            rowKey="membership_id"
            rowSelection={{
              selectedRowKeys,
              onChange: (keys) => setSelectedRowKeys(keys),
            }}
            pagination={{
              current: page, pageSize, total,
              onChange: (p) => setPage(p),
              showTotal: (t) => `${t} companies`,
              showSizeChanger: false,
            }}
            size="middle"
            onRow={(record) => ({
              onClick: (e) => {
                const target = e.target as HTMLElement;
                if (target.closest('.ant-checkbox-wrapper') || target.closest('.ant-select')) return;
                navigate(`/tracking/${listId}/company/${record.membership_id}`, { state: { member: record } });
              },
              style: { cursor: 'pointer' },
            })}
            onChange={(_pagination, _filters, sorter: any) => {
              if (sorter.columnKey) {
                setSortBy(sorter.columnKey);
                setSortOrder(sorter.order === 'ascend' ? 'asc' : 'desc');
              }
            }}
          />
        </div>
      ) : (
        <KanbanBoard
          members={members}
          outreachSummary={outreachSummary}
          onStatusChange={async (membershipId, newStatus) => {
            await handleStatusChange(membershipId, newStatus);
          }}
          onCardClick={(m) => navigate(`/tracking/${listId}/company/${m.membership_id}`, { state: { member: m } })}
        />
      )}

      {/* Signal Hints Drawer */}
      {list && (
        <SignalHintsDrawer
          open={hintsDrawerOpen}
          onClose={() => setHintsDrawerOpen(false)}
          listId={listId!}
          hints={list.signal_hints || {}}
          onSaved={(newHints) => {
            setList({ ...list, signal_hints: newHints });
          }}
        />
      )}
    </div>
  );
};

export default TrackingListDetailPage;
