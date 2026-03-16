import React, { useEffect, useState, useMemo, useRef } from 'react';
import { Card, Row, Col, Button, Tag, Space, Modal, Table, Popconfirm, message, Input, Progress } from 'antd';
import { PlusOutlined, DeleteOutlined, SearchOutlined, LoadingOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { listICPs } from '../api/icpApi';
import { listPipelineRuns, getPipelineStatsByICP, ICPStat, deletePipelineRun, getPipelineStatus } from '../api/pipelineApi';
import { PipelineRun } from '../types';

type TileKey = 'total_leads' | 'pipeline_runs' | 'companies' | 'contacts';

const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const [runs, setRuns] = useState<PipelineRun[]>([]);

  // Search + filter + infinite scroll state
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [displayCount, setDisplayCount] = useState(12);
  const sentinelRef = useRef<HTMLDivElement>(null);

  // Stats modal
  const [statsModalOpen, setStatsModalOpen] = useState(false);
  const [statsModalTile, setStatsModalTile] = useState<TileKey>('total_leads');
  const [icpStats, setIcpStats] = useState<ICPStat[]>([]);
  const [statsLoading, setStatsLoading] = useState(false);

  const refreshRuns = () => {
    Promise.all([listICPs(), listPipelineRuns()])
      .then(([, runRes]) => {
        setRuns(Array.isArray(runRes.data) ? runRes.data : []);
      })
      .catch(() => setRuns([]));
  };

  useEffect(() => {
    refreshRuns();
  }, []);

  const runsList = Array.isArray(runs) ? runs : [];

  // Poll for progress on running pipelines
  const hasRunning = runsList.some((r) => r.status === 'running');
  useEffect(() => {
    if (!hasRunning) return;
    const interval = setInterval(() => {
      const runningRuns = runsList.filter((r) => r.status === 'running');
      runningRuns.forEach((r) => {
        getPipelineStatus(r.id).then((res) => {
          setRuns((prev) =>
            prev.map((existing) => (existing.id === r.id ? res.data : existing))
          );
          // If status changed from running, do a full refresh
          if (res.data.status !== 'running') {
            refreshRuns();
          }
        }).catch(() => { });
      });
    }, 10000);
    return () => clearInterval(interval);
  }, [hasRunning, runsList]);

  const handleDeleteRun = async (runId: string) => {
    try {
      await deletePipelineRun(runId);
      message.success('Search result deleted');
      refreshRuns();
    } catch {
      message.error('Failed to delete search result');
    }
  };
  const completedRuns = runsList.filter((r) => r.status === 'completed');
  const totalCompanies = completedRuns.reduce((s, r) => s + r.companies_found, 0);
  const totalContacts = completedRuns.reduce((s, r) => s + r.contacts_found, 0);

  const filteredRuns = useMemo(() => {
    let result = runsList;
    if (statusFilter !== 'all') {
      result = result.filter((r) => r.status === statusFilter);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (r) =>
          r.icp_name?.toLowerCase().includes(q) ||
          r.icp_description?.toLowerCase().includes(q)
      );
    }
    return result;
  }, [runsList, statusFilter, searchQuery]);

  // Reset display count when filters change
  useEffect(() => { setDisplayCount(12); }, [searchQuery, statusFilter]);

  // IntersectionObserver for infinite scroll
  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          setDisplayCount((prev) => prev + 12);
        }
      },
      { threshold: 0.1 }
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [filteredRuns.length]);

  const statusColor: Record<string, string> = {
    pending: 'default',
    running: 'processing',
    completed: 'success',
    failed: 'error',
    awaiting_review: 'warning',
    cancelled: 'default',
  };

  const openStatsModal = async (tile: TileKey) => {
    setStatsModalTile(tile);
    setStatsModalOpen(true);
    setStatsLoading(true);
    try {
      const res = await getPipelineStatsByICP();
      setIcpStats(Array.isArray(res.data) ? res.data : []);
    } catch {
      setIcpStats([]);
    } finally {
      setStatsLoading(false);
    }
  };

  const MODAL_TITLES: Record<TileKey, string> = {
    total_leads: 'Total Leads - By Search Criteria',
    pipeline_runs: 'Searches - Overview',
    companies: 'Companies Found - By Search Criteria',
    contacts: 'Contacts Found - By Search Criteria',
  };

  const getModalColumns = (tile: TileKey) => {
    if (tile === 'pipeline_runs') {
      return [
        {
          title: 'Search Criteria', key: 'icp_name', width: 180,
          render: (_: unknown, r: PipelineRun) => <span style={{ fontWeight: 600 }}>{r.icp_name || 'Unknown'}</span>,
        },
        {
          title: 'Status', dataIndex: 'status', key: 'status', width: 100,
          render: (s: string) => <Tag color={statusColor[s] || 'default'}>{s.toUpperCase()}</Tag>,
        },
        { title: 'Leads', dataIndex: 'contacts_found', key: 'contacts_found', width: 100 },
        { title: 'Companies', dataIndex: 'companies_found', key: 'companies_found', width: 100 },
        {
          title: 'Started', dataIndex: 'started_at', key: 'started_at',
          render: (d: string | null) => d ? new Date(d).toLocaleString() : '—',
        },
        {
          title: '', key: 'action', width: 80,
          render: (_: unknown, r: PipelineRun) => r.status === 'completed' ? (
            <a onClick={() => { setStatsModalOpen(false); navigate(`/leads/${r.id}`); }}
              style={{ color: 'var(--purple)', cursor: 'pointer', fontSize: 12 }}>View →</a>
          ) : r.status === 'awaiting_review' ? (
            <a onClick={() => { setStatsModalOpen(false); navigate(`/pipeline/${r.id}`); }}
              style={{ color: 'var(--orange)', cursor: 'pointer', fontSize: 12 }}>Review →</a>
          ) : null,
        },
      ];
    }
    if (tile === 'companies') {
      return [
        { title: 'Search Criteria', dataIndex: 'icp_name', key: 'icp_name', render: (v: string) => <span style={{ fontWeight: 600 }}>{v}</span> },
        {
          title: 'Companies', dataIndex: 'total_companies', key: 'total_companies', width: 120,
          render: (v: number) => <span style={{ fontWeight: 700, fontSize: 15, color: 'var(--purple)' }}>{v}</span>,
        },
        { title: 'Contacts', dataIndex: 'total_contacts', key: 'total_contacts', width: 100 },
        { title: 'Runs', dataIndex: 'run_count', key: 'run_count', width: 80 },
      ];
    }
    if (tile === 'contacts') {
      return [
        { title: 'Search Criteria', dataIndex: 'icp_name', key: 'icp_name', render: (v: string) => <span style={{ fontWeight: 600 }}>{v}</span> },
        {
          title: 'Leads', dataIndex: 'total_contacts', key: 'total_contacts', width: 120,
          render: (v: number) => <span style={{ fontWeight: 700, fontSize: 15, color: 'var(--purple)' }}>{v}</span>,
        },
        { title: 'Companies', dataIndex: 'total_companies', key: 'total_companies', width: 100 },
        { title: 'Searches', dataIndex: 'run_count', key: 'run_count', width: 80 },
      ];
    }
    // total_leads (default)
    return [
      { title: 'Search Criteria', dataIndex: 'icp_name', key: 'icp_name', render: (v: string) => <span style={{ fontWeight: 600 }}>{v}</span> },
      {
        title: 'Total Leads', key: 'total_leads', width: 120,
        render: (_: unknown, record: ICPStat) => <span style={{ fontWeight: 700, fontSize: 15, color: 'var(--purple)' }}>{record.total_companies + record.total_contacts}</span>,
      },
      { title: 'Companies', dataIndex: 'total_companies', key: 'total_companies', width: 110 },
      { title: 'Contacts', dataIndex: 'total_contacts', key: 'total_contacts', width: 100 },
      { title: 'Runs', dataIndex: 'run_count', key: 'run_count', width: 80 },
    ];
  };

  const expandedRowRender = (stat: ICPStat) => {
    const runColumns = [
      {
        title: 'Run', dataIndex: 'id', key: 'id', width: 120,
        render: (id: string) => (
          <a onClick={() => { setStatsModalOpen(false); navigate(`/leads/${id}`); }}
            style={{ color: 'var(--purple)', cursor: 'pointer' }}>
            {id.substring(0, 8)}...
          </a>
        ),
      },
      {
        title: 'Status', dataIndex: 'status', key: 'status', width: 100,
        render: (s: string) => <Tag color={statusColor[s] || 'default'}>{s.toUpperCase()}</Tag>,
      },
      { title: 'Companies', dataIndex: 'companies_found', key: 'companies_found', width: 100 },
      { title: 'Contacts', dataIndex: 'contacts_found', key: 'contacts_found', width: 100 },
      {
        title: 'Started', dataIndex: 'started_at', key: 'started_at',
        render: (d: string | null) => d ? new Date(d).toLocaleString() : '—',
      },
    ];
    return <Table columns={runColumns} dataSource={Array.isArray(stat.runs) ? stat.runs : []} rowKey="id" pagination={false} size="small" />;
  };

  return (
    <div style={{ padding: '28px 32px', maxWidth: 1400, margin: '0 auto', width: '100%' }}>
      <div style={{ marginBottom: 24 }}>
        <div className="section-label">Overview</div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h1 className="page-title">Dashboard</h1>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/icp/new')}>
            New Search
          </Button>
        </div>
      </div>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={12} sm={12} md={8}>
          <div className="metric-tile metric-tile-clickable" onClick={() => openStatsModal('pipeline_runs')}>
            <div className="metric-icon">📈</div>
            <div className="label">Total Searches</div>
            <div className="value">{runsList.length}</div>
          </div>
        </Col>
        <Col xs={12} sm={12} md={8}>
          <div className="metric-tile metric-tile-clickable" onClick={() => openStatsModal('contacts')}>
            <div className="metric-icon">👥</div>
            <div className="label">Qualified Leads</div>
            <div className="value">{totalContacts}</div>
          </div>
        </Col>
        <Col xs={12} sm={12} md={8}>
          <div className="metric-tile metric-tile-clickable" onClick={() => openStatsModal('companies')}>
            <div className="metric-icon">🏢</div>
            <div className="label">Companies Found</div>
            <div className="value">{totalCompanies}</div>
          </div>
        </Col>
      </Row>

      <div style={{ marginBottom: 16 }}>
        <div className="section-label">Recent Activity</div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
          <h2 style={{ fontSize: 16, fontWeight: 700, color: 'var(--g800)', margin: 0 }}>Recent Searches</h2>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
            <Input
              prefix={<SearchOutlined style={{ color: 'var(--g400)' }} />}
              placeholder="Search by name or description..."
              allowClear
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ maxWidth: 320, width: 280 }}
            />
            <div style={{ display: 'flex', gap: 6 }}>
              {(['all', 'completed', 'running', 'cancelled', 'failed'] as const).map((status) => (
                <div
                  key={status}
                  onClick={() => setStatusFilter(status)}
                  style={{
                    padding: '4px 12px',
                    borderRadius: 6,
                    fontSize: 12,
                    fontWeight: 600,
                    cursor: 'pointer',
                    background: statusFilter === status ? 'var(--purple-pale, #f0e6ff)' : 'var(--g100, #f5f5f5)',
                    color: statusFilter === status ? 'var(--purple)' : 'var(--g500)',
                    transition: 'all 0.2s',
                  }}
                >
                  {status === 'all' ? 'All' : status.charAt(0).toUpperCase() + status.slice(1)}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {runsList.length > 0 ? (
        filteredRuns.length === 0 ? (
          <Card style={{ textAlign: 'center', padding: '40px 0' }}>
            <div style={{ fontSize: 40, marginBottom: 16 }}>🔍</div>
            <h3 style={{ fontSize: 18, fontWeight: 700, marginBottom: 8, color: 'var(--g900)' }}>
              No Matches Found
            </h3>
            <p style={{ color: 'var(--g500)', fontSize: 13 }}>
              No searches match your current filters. Try a different search term or status filter.
            </p>
          </Card>
        ) : (
          <>
            <Row gutter={[16, 16]}>
              {filteredRuns.slice(0, displayCount).map((run) => (
                <Col xs={24} sm={12} md={8} key={run.id}>
                  <div
                    className="run-card"
                    style={run.status === 'failed' ? { cursor: 'default' } : {}}
                    onClick={() => {
                      if (run.status === 'completed') navigate(`/leads/${run.id}`);
                      else if (run.status === 'running' || run.status === 'awaiting_review') navigate(`/pipeline/${run.id}`);
                      else if (run.status === 'cancelled') {
                        if (run.companies_found > 0) navigate(`/leads/${run.id}`);
                        else navigate(`/pipeline/${run.id}`);
                      }
                    }}
                  >
                    {/* Header: name + status badge */}
                    <div className="rc-header">
                      <div className="rc-title">{run.icp_name || `Run #${run.id.substring(0, 8)}`}</div>
                      <Tag color={statusColor[run.status] || 'default'} style={{ fontSize: 11, height: 22 }}>
                        {run.status.toUpperCase()}
                      </Tag>
                    </div>

                    {/* Date + offering snippet */}
                    <div className="rc-meta">
                      <span className="rc-date">
                        🗓 {run.started_at ? new Date(run.started_at).toLocaleString() : 'Not started'}
                      </span>
                      {run.icp_description && (
                        <span className="rc-offering" title={run.icp_description}>
                          {run.icp_description}
                        </span>
                      )}
                    </div>

                    {/* Emphasized stats row */}
                    <div className="rc-stats">
                      <div className="rc-stat">
                        <div className="rc-stat-val">{run.companies_found}</div>
                        <div className="rc-stat-lbl">Companies</div>
                      </div>
                      <div className="rc-stat-div"></div>
                      <div className="rc-stat">
                        <div className="rc-stat-val">{run.contacts_found}</div>
                        <div className="rc-stat-lbl">Contacts</div>
                      </div>
                    </div>

                    {/* Mini pipeline funnel for completed/review/cancelled runs */}
                    {['completed', 'awaiting_review', 'cancelled'].includes(run.status) &&
                      run.stage_details?.total_discovered != null && (
                        <div style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 6,
                          padding: '0 12px 10px',
                          fontSize: 11,
                          color: 'var(--g500)',
                          fontWeight: 500,
                        }}>
                          <span style={{ fontWeight: 700, color: 'var(--g700)' }}>
                            {run.stage_details.total_discovered}
                          </span>
                          discovered
                          <span style={{ color: 'var(--g300)' }}>&rsaquo;</span>
                          <span style={{ fontWeight: 700, color: 'var(--g700)' }}>
                            {run.stage_details.pre_filter_passed ?? '?'}
                          </span>
                          filtered
                          <span style={{ color: 'var(--g300)' }}>&rsaquo;</span>
                          <span style={{ fontWeight: 700, color: 'var(--purple)' }}>
                            {run.stage_details.promoted_count ?? '?'}
                          </span>
                          promoted
                        </div>
                      )}

                    {/* Progress indicator for running pipelines */}
                    {run.status === 'running' && run.stage_details?.current_company_index != null && (
                      <div style={{ padding: '0 12px 8px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                          <span style={{ fontSize: 11, color: 'var(--g500)' }}>
                            <LoadingOutlined style={{ marginRight: 4 }} />
                            {run.stage_details.current_company_name || 'Processing...'}
                          </span>
                          <span style={{ fontSize: 11, color: 'var(--g400)' }}>
                            {run.stage_details.current_company_index}/{run.stage_details.total_companies_in_stage}
                          </span>
                        </div>
                        <Progress
                          percent={Math.round(((run.stage_details.current_company_index || 0) / (run.stage_details.total_companies_in_stage || 1)) * 100)}
                          size="small"
                          showInfo={false}
                          strokeColor="var(--purple, #722ed1)"
                        />
                      </div>
                    )}

                    {/* ICP details */}
                    {run.icp_config && (
                      <div className="rc-icp-block">
                        {run.icp_config.firmographic_details?.geography?.countries && run.icp_config.firmographic_details.geography.countries.length > 0 && (
                          <div className="rc-icp-row">
                            <span className="rc-icp-key">📍 Regions</span>
                            <span className="rc-icp-val">
                              {run.icp_config.firmographic_details.geography.countries.slice(0, 3).join(', ')}
                            </span>
                          </div>
                        )}
                        {run.icp_config.firmographic_details?.industry_types && run.icp_config.firmographic_details.industry_types.length > 0 && (
                          <div className="rc-icp-row">
                            <span className="rc-icp-key">🏭 Industries</span>
                            <span className="rc-icp-val">
                              {run.icp_config.firmographic_details.industry_types.map((i: { vertical: string }) => i.vertical).slice(0, 3).join(', ')}
                            </span>
                          </div>
                        )}
                        {(run.icp_config as any).personas && (run.icp_config as any).personas.length > 0 && (
                          <div className="rc-icp-row">
                            <span className="rc-icp-key">👤 Roles</span>
                            <span className="rc-icp-val">
                              {(run.icp_config as any).personas.map((p: any) => p.job_title).slice(0, 3).join(', ')}
                            </span>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Footer actions */}
                    <div className="rc-footer">
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <Button
                          size="small"
                          className="rc-edit-btn"
                          onClick={(e) => {
                            e.stopPropagation();
                            navigate(`/icp/${run.icp_config_id}/edit`);
                          }}
                        >
                          ✏ Edit Search
                        </Button>
                        {(run.status === 'completed' || run.status === 'failed' || run.status === 'cancelled') && (
                          <Popconfirm
                            title="Delete this search result?"
                            description="This will permanently remove all companies, contacts, and scores from this run."
                            onConfirm={(e) => {
                              e?.stopPropagation();
                              handleDeleteRun(run.id);
                            }}
                            onCancel={(e) => e?.stopPropagation()}
                            okText="Delete"
                            cancelText="Cancel"
                            okButtonProps={{ danger: true }}
                          >
                            <Button
                              size="small"
                              danger
                              icon={<DeleteOutlined />}
                              onClick={(e) => e.stopPropagation()}
                            />
                          </Popconfirm>
                        )}
                      </div>
                      {run.status === 'completed' && (
                        <span className="rc-view-link">View Results →</span>
                      )}
                      {run.status === 'running' && (
                        <span className="rc-view-link" style={{ color: 'var(--orange)' }}>View Progress →</span>
                      )}
                      {run.status === 'awaiting_review' && (
                        <span className="rc-view-link" style={{ color: 'var(--orange)' }}>Review Companies →</span>
                      )}
                      {run.status === 'cancelled' && (
                        <span className="rc-view-link" style={{ color: 'var(--g500)' }}>
                          {run.companies_found > 0 ? 'View Partial Results →' : 'Cancelled'}
                        </span>
                      )}
                    </div>
                  </div>
                </Col>
              ))}
            </Row>
            <div ref={sentinelRef} style={{ height: 1 }} />
            {displayCount < filteredRuns.length ? (
              <div style={{ textAlign: 'center', padding: '16px 0', color: 'var(--g400)', fontSize: 13 }}>
                Loading more...
              </div>
            ) : filteredRuns.length > 12 ? (
              <div style={{ textAlign: 'center', padding: '16px 0', color: 'var(--g400)', fontSize: 12 }}>
                Showing all {filteredRuns.length} items
              </div>
            ) : null}
          </>
        )
      ) : (
        <Card style={{ textAlign: 'center', padding: '20px 0' }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>🚀</div>
          <h3 style={{ fontSize: 18, fontWeight: 700, marginBottom: 8, color: 'var(--g900)' }}>
            Get Started with Your First Search
          </h3>
          <p style={{ color: 'var(--g500)', marginBottom: 24, maxWidth: 460, margin: '0 auto 24px', fontSize: 13, lineHeight: 1.6 }}>
            Define your search criteria to set your target market, then our AI agent will
            autonomously find and qualify leads matching your criteria.
          </p>
          <Space size="middle" direction="vertical" style={{ width: '100%' }}>
            <Space size="middle">
              <Button type="primary" size="large" icon={<PlusOutlined />} onClick={() => navigate('/icp/new')}>
                Create Your First Search
              </Button>
            </Space>
          </Space>
        </Card>
      )}

      {/* Stats Breakdown Modal */}
      <Modal
        title={MODAL_TITLES[statsModalTile]}
        open={statsModalOpen}
        onCancel={() => setStatsModalOpen(false)}
        footer={null}
        width={800}
      >
        {statsModalTile === 'pipeline_runs' ? (
          <>
            <div style={{ display: 'flex', gap: 16, marginBottom: 16 }}>
              <Tag color="success">{completedRuns.length} Completed</Tag>
              <Tag color="processing">{runsList.filter(r => r.status === 'running').length} Running</Tag>
              <Tag color="error">{runsList.filter(r => r.status === 'failed').length} Failed</Tag>
              <Tag>{runsList.filter(r => r.status === 'cancelled').length} Cancelled</Tag>
              <Tag>{runsList.filter(r => r.status === 'pending').length} Pending</Tag>
            </div>
            <Table
              columns={getModalColumns('pipeline_runs') as any}
              dataSource={runsList}
              rowKey="id"
              pagination={false}
              size="middle"
              locale={{ emptyText: 'No searches found' }}
            />
          </>
        ) : (
          <Table
            columns={getModalColumns(statsModalTile) as any}
            dataSource={icpStats}
            rowKey="icp_id"
            loading={statsLoading}
            expandable={{ expandedRowRender }}
            pagination={false}
            size="middle"
            locale={{ emptyText: 'No searches found' }}
          />
        )}
      </Modal>
    </div>
  );
};

export default DashboardPage;
