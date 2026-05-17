import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Button, Card, Table, Tag, Tooltip, Progress, Spin, message, Space, Typography,
} from 'antd';
import {
  LoadingOutlined, CheckCircleOutlined, BulbOutlined, ApiOutlined,
  ThunderboltOutlined, CloseCircleOutlined, ArrowLeftOutlined,
} from '@ant-design/icons';
import { useParams, useNavigate } from 'react-router-dom';
import {
  getBatchStatus, getIngestBatchLogs, getIngestStreamUrl, addSelectedCompanies,
} from '../api/ingestApi';
import type {
  IngestBatchStatus, IngestBatchLogEntry, IngestActivityEntry, ScoredCompany,
} from '../types';

const { Paragraph, Text } = Typography;

const TOOL_COLORS: Record<string, string> = {
  apollo_company_search: '#5C2D8F',
  research_company: '#1890ff',
};

const TOOL_DISPLAY_NAMES: Record<string, string> = {
  apollo_company_search: 'Apollo',
  research_company: 'Web Research',
};

const IngestEvaluationPage: React.FC = () => {
  const { batchId } = useParams<{ batchId: string }>();
  const navigate = useNavigate();

  const [batch, setBatch] = useState<IngestBatchStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [activityLog, setActivityLog] = useState<IngestActivityEntry[]>([]);
  const [scoredCompanies, setScoredCompanies] = useState<ScoredCompany[]>([]);
  const [selectedKbIds, setSelectedKbIds] = useState<string[]>([]);
  const [addingSelected, setAddingSelected] = useState(false);
  const [evaluationDone, setEvaluationDone] = useState(false);
  const [currentCompany, setCurrentCompany] = useState<string>('');
  const [progressPercent, setProgressPercent] = useState(0);

  const eventSourceRef = useRef<EventSource | null>(null);
  const activityRef = useRef<HTMLDivElement>(null);
  const activityIdRef = useRef(0);
  const seenEventsRef = useRef<Set<string>>(new Set());
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const lastLogSeqRef = useRef(-1);

  // Auto-scroll activity feed
  useEffect(() => {
    if (activityRef.current) {
      activityRef.current.scrollTop = activityRef.current.scrollHeight;
    }
  }, [activityLog]);

  const addActivityEntry = useCallback((
    type: IngestActivityEntry['type'],
    data: Record<string, unknown>,
  ) => {
    const fp = `${type}|${data.company_name || ''}|${data.tool_name || ''}|${data.company_index || ''}|${String(data.score ?? '')}`;
    if (seenEventsRef.current.has(fp)) return; // skip duplicate
    seenEventsRef.current.add(fp);

    activityIdRef.current += 1;
    const entry: IngestActivityEntry = {
      id: activityIdRef.current,
      type,
      timestamp: new Date(),
      company_name: data.company_name as string,
      tool_name: data.tool_name as string,
      display_name: data.display_name as string,
      context: data.context as string,
      text: data.text as string,
      score: data.score as number,
      justification: data.justification as string,
      result_preview: data.result_preview as string,
      success: data.success as boolean,
      company_index: data.company_index as number,
      total: data.total as number,
      fields_found: data.fields_found as string[],
    };
    setActivityLog((prev) => [...prev, entry]);
  }, []);

  /** Replay DB logs into activity feed and return metadata */
  const replayDbLogs = useCallback((logs: IngestBatchLogEntry[]) => {
    let hasCompletion = false;
    let scored: ScoredCompany[] = [];
    const entries: IngestActivityEntry[] = [];
    let maxSeq = -1;

    const activityTypes = ['company_start', 'tool_start', 'tool_result', 'agent_reasoning', 'company_result'];

    for (const log of logs) {
      const rawEventData = log.event_data as Record<string, unknown>;
      const data = (rawEventData?.data || rawEventData) as Record<string, unknown>;
      const eventType = log.event_type;

      if (log.sequence_number > maxSeq) maxSeq = log.sequence_number;

      if (activityTypes.includes(eventType)) {
        const fp = `${eventType}|${data.company_name || ''}|${data.tool_name || ''}|${data.company_index || ''}|${String(data.score ?? '')}`;
        seenEventsRef.current.add(fp);

        activityIdRef.current += 1;
        entries.push({
          id: activityIdRef.current,
          type: eventType as IngestActivityEntry['type'],
          timestamp: log.created_at ? new Date(log.created_at) : new Date(),
          company_name: data.company_name as string,
          tool_name: data.tool_name as string,
          display_name: data.display_name as string,
          context: data.context as string,
          text: data.text as string,
          score: data.score as number,
          justification: data.justification as string,
          result_preview: data.result_preview as string,
          success: data.success as boolean,
          company_index: data.company_index as number,
          total: data.total as number,
          fields_found: data.fields_found as string[],
        });
      }

      // Update progress from company_start events
      if (eventType === 'company_start') {
        setCurrentCompany((data.company_name as string) || '');
        setProgressPercent(Math.round((data.percent as number) || 0));
      }

      if (eventType === 'firmographic_completed') {
        hasCompletion = true;
        scored = (data.scored_companies as ScoredCompany[]) || [];
      }
    }

    return { entries, hasCompletion, scored, maxSeq };
  }, []);

  /** Start polling DB logs for new events (fallback for reconnection) */
  const startLogPolling = useCallback((id: string) => {
    if (pollIntervalRef.current) return; // already polling

    pollIntervalRef.current = setInterval(async () => {
      try {
        const logsRes = await getIngestBatchLogs(id);
        const logs: IngestBatchLogEntry[] = logsRes.data || [];

        // Only process logs we haven't seen yet
        const newLogs = logs.filter((l) => l.sequence_number > lastLogSeqRef.current);
        if (newLogs.length === 0) return;

        for (const log of newLogs) {
          const rawEventData = log.event_data as Record<string, unknown>;
          const data = (rawEventData?.data || rawEventData) as Record<string, unknown>;
          const eventType = log.event_type;

          if (log.sequence_number > lastLogSeqRef.current) {
            lastLogSeqRef.current = log.sequence_number;
          }

          const activityTypes = ['company_start', 'tool_start', 'tool_result', 'agent_reasoning', 'company_result'];
          if (activityTypes.includes(eventType)) {
            addActivityEntry(eventType as IngestActivityEntry['type'], data);
          }

          if (eventType === 'company_start') {
            setCurrentCompany((data.company_name as string) || '');
            setProgressPercent(Math.round((data.percent as number) || 0));
          }

          if (eventType === 'firmographic_completed') {
            const scored = (data.scored_companies as ScoredCompany[]) || [];
            setScoredCompanies(scored);
            setSelectedKbIds(scored.filter((c) => c.score >= 40).map((c) => c.company_kb_id));
            setEvaluationDone(true);
            setProgressPercent(100);
            // Stop polling
            if (pollIntervalRef.current) {
              clearInterval(pollIntervalRef.current);
              pollIntervalRef.current = null;
            }
          }
        }
      } catch {
        // Polling error — ignore, will retry
      }
    }, 3000);
  }, [addActivityEntry]);

  const connectSSE = useCallback((id: string) => {
    const url = getIngestStreamUrl(id);
    const es = new EventSource(url);
    eventSourceRef.current = es;

    es.addEventListener('ingest_progress', () => {
      // Import phase — no progress update, this page is for evaluation
    });

    es.addEventListener('ingest_completed', () => {
      // Import done, evaluation will start
    });

    es.addEventListener('company_start', (e) => {
      const data = JSON.parse(e.data);
      setCurrentCompany(data.company_name || '');
      setProgressPercent(Math.round(data.percent || 0));
      addActivityEntry('company_start', data);
    });

    es.addEventListener('tool_start', (e) => {
      const data = JSON.parse(e.data);
      addActivityEntry('tool_start', data);
    });

    es.addEventListener('tool_result', (e) => {
      const data = JSON.parse(e.data);
      addActivityEntry('tool_result', data);
    });

    es.addEventListener('agent_reasoning', (e) => {
      const data = JSON.parse(e.data);
      addActivityEntry('agent_reasoning', data);
    });

    es.addEventListener('company_result', (e) => {
      const data = JSON.parse(e.data);
      addActivityEntry('company_result', data);
    });

    es.addEventListener('firmographic_completed', (e) => {
      const data = JSON.parse(e.data);
      const scored: ScoredCompany[] = data.scored_companies || [];
      setScoredCompanies(scored);
      setSelectedKbIds(scored.filter((c) => c.score >= 40).map((c) => c.company_kb_id));
      setEvaluationDone(true);
      setProgressPercent(100);
      es.close();
      // Stop polling if active
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
    });

    es.addEventListener('ingest_failed', (e) => {
      const data = JSON.parse(e.data);
      message.error(data.message || 'Processing failed');
      es.close();
    });

    es.addEventListener('timeout', () => {
      message.warning('Stream timed out');
      es.close();
    });

    es.onerror = () => {
      es.close();
      // SSE failed — ensure polling is active as fallback
      if (id && !pollIntervalRef.current) {
        startLogPolling(id);
      }
    };
  }, [addActivityEntry, startLogPolling]);

  // On mount: fetch batch status, replay logs if any, connect SSE if still running
  useEffect(() => {
    if (!batchId) return;

    const init = async () => {
      try {
        const res = await getBatchStatus(batchId);
        const b = res.data;
        setBatch(b);

        if (!b.has_filter) {
          navigate('/ingest');
          return;
        }

        // Replay existing logs from DB
        let hasCompletionEvent = false;
        let hasDbLogs = false;
        try {
          const logsRes = await getIngestBatchLogs(batchId);
          const logs: IngestBatchLogEntry[] = logsRes.data || [];
          if (logs.length > 0) {
            hasDbLogs = true;
            const result = replayDbLogs(logs);
            hasCompletionEvent = result.hasCompletion;
            lastLogSeqRef.current = result.maxSeq;
            setActivityLog(result.entries);

            if (result.scored.length > 0) {
              setScoredCompanies(result.scored);
              setSelectedKbIds(result.scored.filter((c) => c.score >= 40).map((c) => c.company_kb_id));
              setEvaluationDone(true);
              setProgressPercent(100);
            }
          }
        } catch {
          // No logs yet — that's fine
        }

        // If evaluation is NOT complete, reconnect for live updates
        if (!hasCompletionEvent && b.evaluation_status !== 'completed' && b.status !== 'failed') {
          // Always connect SSE for real-time events
          connectSSE(batchId);
          // Also start DB log polling as a fallback (picks up events
          // that were persisted before SSE connected, and continues
          // working even if SSE fails)
          if (hasDbLogs) {
            startLogPolling(batchId);
          }
        }
      } catch {
        message.error('Failed to load batch');
        navigate('/ingest');
      } finally {
        setLoading(false);
      }
    };

    init();
    return () => {
      eventSourceRef.current?.close();
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
    };
  }, [batchId, navigate, connectSSE, replayDbLogs, startLogPolling]);

  const handleAddSelected = async () => {
    if (!batchId || !batch?.target_tracking_list_id || selectedKbIds.length === 0) return;
    setAddingSelected(true);
    try {
      const res = await addSelectedCompanies(batchId, selectedKbIds, batch.target_tracking_list_id);
      message.success(`Added ${res.data.added} companies to tracking list`);
      navigate(`/tracking/${batch.target_tracking_list_id}`);
    } catch {
      message.error('Failed to add companies');
    } finally {
      setAddingSelected(false);
    }
  };

  const formatRevenue = (v: number | null) => {
    if (!v) return '-';
    if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
    if (v >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
    if (v >= 1e3) return `$${(v / 1e3).toFixed(0)}K`;
    return `$${v}`;
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: 80 }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div style={{ padding: '32px 40px', maxWidth: 1100, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
        <Button
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate('/ingest')}
          size="small"
          type="text"
        />
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: '#1a1a2e', margin: 0 }}>
            Firmographic Evaluation
          </h1>
          <p style={{ color: '#888', fontSize: 13, margin: 0 }}>
            {batch?.name || 'Batch'} — {batch?.total_rows || 0} companies
          </p>
        </div>
        {!evaluationDone && (
          <Tag color="processing" style={{ marginLeft: 'auto' }}>
            <LoadingOutlined spin style={{ marginRight: 4 }} />
            Evaluating...
          </Tag>
        )}
        {evaluationDone && (
          <Tag color="success" style={{ marginLeft: 'auto' }}>
            <CheckCircleOutlined style={{ marginRight: 4 }} />
            Complete
          </Tag>
        )}
      </div>

      {/* Progress bar */}
      {!evaluationDone && (
        <Card style={{ borderRadius: 12, marginBottom: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                <span style={{ fontSize: 13, fontWeight: 500, color: '#333' }}>
                  {currentCompany ? `Evaluating: ${currentCompany}` : 'Starting evaluation...'}
                </span>
                <span style={{ fontSize: 12, color: '#888' }}>{progressPercent}%</span>
              </div>
              <Progress
                percent={progressPercent}
                strokeColor={{ '0%': '#5C2D8F', '100%': '#1E9B6B' }}
                showInfo={false}
                size="small"
              />
            </div>
          </div>
        </Card>
      )}

      {/* Activity Feed */}
      <Card
        title={
          <span style={{ fontSize: 14, fontWeight: 600 }}>
            <ThunderboltOutlined style={{ marginRight: 8, color: '#5C2D8F' }} />
            Activity Feed
          </span>
        }
        style={{ borderRadius: 12, marginBottom: 20 }}
        styles={{ body: { padding: 0 } }}
      >
        <div
          ref={activityRef}
          style={{
            maxHeight: evaluationDone ? 300 : 450,
            overflowY: 'auto',
            padding: '12px 20px',
          }}
        >
          {activityLog.length === 0 && (
            <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>
              {loading ? 'Loading events...' : 'Waiting for events...'}
            </div>
          )}
          {activityLog.map((entry) => (
            <div
              key={entry.id}
              style={{
                padding: '8px 0',
                borderBottom: '1px solid #f5f5f5',
                display: 'flex',
                alignItems: 'flex-start',
                gap: 10,
              }}
            >
              {/* Icon */}
              <div style={{ width: 24, textAlign: 'center', paddingTop: 2, flexShrink: 0 }}>
                {entry.type === 'company_start' && (
                  <span style={{ fontSize: 14, color: '#5C2D8F' }}>
                    {entry.company_index || ''}
                  </span>
                )}
                {entry.type === 'tool_start' && (
                  <ApiOutlined style={{ color: TOOL_COLORS[entry.tool_name || ''] || '#999' }} />
                )}
                {entry.type === 'tool_result' && (
                  entry.success
                    ? <CheckCircleOutlined style={{ color: '#52c41a' }} />
                    : <CloseCircleOutlined style={{ color: '#faad14' }} />
                )}
                {entry.type === 'agent_reasoning' && (
                  <BulbOutlined style={{ color: '#faad14' }} />
                )}
                {entry.type === 'company_result' && (
                  <Tag
                    color={
                      (entry.score || 0) >= 70 ? 'green'
                        : (entry.score || 0) >= 40 ? 'orange'
                          : 'red'
                    }
                    style={{ margin: 0, fontSize: 11, lineHeight: '20px', padding: '0 6px' }}
                  >
                    {entry.score}
                  </Tag>
                )}
              </div>

              {/* Content */}
              <div style={{ flex: 1, minWidth: 0 }}>
                {entry.type === 'company_start' && (
                  <div>
                    <Text strong style={{ fontSize: 13 }}>{entry.company_name}</Text>
                    <Text type="secondary" style={{ fontSize: 11, marginLeft: 8 }}>
                      ({entry.company_index} of {entry.total})
                    </Text>
                  </div>
                )}
                {entry.type === 'tool_start' && (
                  <div>
                    <Tag
                      color={TOOL_COLORS[entry.tool_name || ''] || 'default'}
                      style={{ fontSize: 11 }}
                    >
                      {TOOL_DISPLAY_NAMES[entry.tool_name || ''] || entry.display_name || entry.tool_name}
                    </Tag>
                    {entry.context && (
                      <Text type="secondary" style={{ fontSize: 12 }}>{entry.context}</Text>
                    )}
                  </div>
                )}
                {entry.type === 'tool_result' && (
                  <Paragraph
                    type={entry.success ? 'success' : 'warning'}
                    style={{ fontSize: 12, margin: 0 }}
                    ellipsis={{ rows: 2, expandable: true, symbol: 'more' }}
                  >
                    {entry.result_preview}
                  </Paragraph>
                )}
                {entry.type === 'agent_reasoning' && (
                  <Paragraph
                    style={{ fontSize: 12, margin: 0, color: '#666' }}
                    ellipsis={{ rows: 3, expandable: true, symbol: 'more' }}
                  >
                    {entry.text}
                  </Paragraph>
                )}
                {entry.type === 'company_result' && (
                  <div>
                    <Text strong style={{ fontSize: 13 }}>{entry.company_name}</Text>
                    {entry.justification && (
                      <Paragraph
                        type="secondary"
                        style={{ fontSize: 12, margin: '2px 0 0' }}
                        ellipsis={{ rows: 2, expandable: true, symbol: 'more' }}
                      >
                        {entry.justification}
                      </Paragraph>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Selection table (after evaluation completes) */}
      {evaluationDone && scoredCompanies.length > 0 && (
        <Card style={{ borderRadius: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <div>
              <h2 style={{ fontSize: 16, fontWeight: 700, color: '#1a1a2e', marginBottom: 4 }}>
                Select Companies to Add
              </h2>
              <p style={{ color: '#666', fontSize: 13, margin: 0 }}>
                {scoredCompanies.length} evaluated.
                {' '}{scoredCompanies.filter((c) => c.score >= 70).length} strong,
                {' '}{scoredCompanies.filter((c) => c.score >= 40 && c.score < 70).length} moderate,
                {' '}{scoredCompanies.filter((c) => c.score < 40).length} weak.
              </p>
            </div>
            <Space>
              <Button size="small" onClick={() => setSelectedKbIds(scoredCompanies.map((c) => c.company_kb_id))}>
                Select All
              </Button>
              <Button size="small" onClick={() => setSelectedKbIds([])}>
                Deselect All
              </Button>
            </Space>
          </div>

          <Table
            dataSource={[...scoredCompanies].sort((a, b) => b.score - a.score)}
            rowKey="company_kb_id"
            rowSelection={{
              selectedRowKeys: selectedKbIds,
              onChange: (keys) => setSelectedKbIds(keys as string[]),
            }}
            columns={[
              {
                title: 'Company',
                dataIndex: 'company_name',
                width: 160,
                render: (name: string) => <span style={{ fontWeight: 500 }}>{name || '-'}</span>,
              },
              {
                title: 'Domain',
                dataIndex: 'domain',
                width: 120,
                render: (d: string | null) => (
                  <span style={{ fontSize: 12, color: '#666', fontFamily: 'monospace' }}>{d || '-'}</span>
                ),
              },
              { title: 'Industry', dataIndex: 'industry', width: 110, render: (v: string | null) => v || '-' },
              { title: 'Country', dataIndex: 'country', width: 90, render: (v: string | null) => v || '-' },
              {
                title: 'Employees',
                dataIndex: 'employee_count',
                width: 90,
                render: (v: number | null) => v?.toLocaleString() || '-',
              },
              {
                title: 'Revenue',
                dataIndex: 'revenue_estimate',
                width: 100,
                render: (v: number | null) => formatRevenue(v),
              },
              {
                title: 'Score',
                dataIndex: 'score',
                width: 80,
                sorter: (a: ScoredCompany, b: ScoredCompany) => a.score - b.score,
                defaultSortOrder: 'descend' as const,
                render: (score: number, record: ScoredCompany) => (
                  <Tooltip
                    title={
                      record.score_breakdown ? (
                        <div style={{ fontSize: 11 }}>
                          <div>Industry: {record.score_breakdown.industry?.score ?? '?'}/30
                            {record.score_breakdown.industry?.reasoning && (
                              <span style={{ opacity: 0.8 }}> — {record.score_breakdown.industry.reasoning}</span>
                            )}
                          </div>
                          <div>Geography: {record.score_breakdown.geography?.score ?? '?'}/20
                            {record.score_breakdown.geography?.reasoning && (
                              <span style={{ opacity: 0.8 }}> — {record.score_breakdown.geography.reasoning}</span>
                            )}
                          </div>
                          <div>Employees: {record.score_breakdown.employees?.score ?? '?'}/25
                            {record.score_breakdown.employees?.reasoning && (
                              <span style={{ opacity: 0.8 }}> — {record.score_breakdown.employees.reasoning}</span>
                            )}
                          </div>
                          <div>Revenue: {record.score_breakdown.revenue?.score ?? '?'}/25
                            {record.score_breakdown.revenue?.reasoning && (
                              <span style={{ opacity: 0.8 }}> — {record.score_breakdown.revenue.reasoning}</span>
                            )}
                          </div>
                        </div>
                      ) : undefined
                    }
                  >
                    <Tag
                      color={score >= 70 ? 'green' : score >= 40 ? 'orange' : 'red'}
                      style={{ fontWeight: 600, cursor: 'help' }}
                    >
                      {score}
                    </Tag>
                  </Tooltip>
                ),
              },
              {
                title: 'Justification',
                dataIndex: 'justification',
                width: 280,
                render: (text: string) => (
                  <span style={{ fontSize: 12, color: '#555', whiteSpace: 'pre-wrap', lineHeight: 1.5 }}>
                    {text || '-'}
                  </span>
                ),
              },
            ]}
            pagination={{ pageSize: 20, showSizeChanger: false }}
            size="small"
            scroll={{ x: 950 }}
          />

          <div style={{ marginTop: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ color: '#666', fontSize: 13 }}>
              {selectedKbIds.length} of {scoredCompanies.length} selected
            </span>
            <Button
              type="primary"
              loading={addingSelected}
              disabled={selectedKbIds.length === 0}
              onClick={handleAddSelected}
              style={{ borderRadius: 8 }}
            >
              Add {selectedKbIds.length} Selected to Tracking List
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
};

export default IngestEvaluationPage;
