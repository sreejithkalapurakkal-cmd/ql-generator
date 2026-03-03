import React, { useEffect, useState } from 'react';
import { Card, Row, Col, Button, Tag, Space, Modal, Table } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { listICPs } from '../api/icpApi';
import { listPipelineRuns, getPipelineStatsByICP, ICPStat } from '../api/pipelineApi';
import { PipelineRun } from '../types';

type TileKey = 'total_leads' | 'pipeline_runs' | 'companies' | 'contacts';

const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const [runs, setRuns] = useState<PipelineRun[]>([]);

  // Stats modal
  const [statsModalOpen, setStatsModalOpen] = useState(false);
  const [statsModalTile, setStatsModalTile] = useState<TileKey>('total_leads');
  const [icpStats, setIcpStats] = useState<ICPStat[]>([]);
  const [statsLoading, setStatsLoading] = useState(false);

  useEffect(() => {
    Promise.all([listICPs(), listPipelineRuns()])
      .then(([, runRes]) => {
        setRuns(Array.isArray(runRes.data) ? runRes.data : []);
      })
      .catch(() => setRuns([]));
  }, []);

  const runsList = Array.isArray(runs) ? runs : [];
  const completedRuns = runsList.filter((r) => r.status === 'completed');
  const totalCompanies = completedRuns.reduce((s, r) => s + r.companies_found, 0);
  const totalContacts = completedRuns.reduce((s, r) => s + r.contacts_found, 0);

  const statusColor: Record<string, string> = {
    pending: 'default',
    running: 'processing',
    completed: 'success',
    failed: 'error',
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
        {
          title: 'Avg / Run', key: 'avg', width: 100,
          render: (_: unknown, record: ICPStat) => record.run_count > 0 ? (record.total_companies / record.run_count).toFixed(1) : '—',
        },
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
        {
          title: 'Avg / Run', key: 'avg', width: 100,
          render: (_: unknown, record: ICPStat) => record.run_count > 0 ? (record.total_contacts / record.run_count).toFixed(1) : '—',
        },
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
        <h2 style={{ fontSize: 16, fontWeight: 700, color: 'var(--g800)', margin: 0 }}>Recent Searches</h2>
      </div>

      {runsList.length > 0 ? (
        <Row gutter={[16, 16]}>
          {runsList.slice(0, 6).map((run) => (
            <Col xs={24} sm={12} md={8} key={run.id}>
              <div
                className="run-card"
                style={run.status === 'failed' ? { cursor: 'default' } : {}}
                onClick={() => {
                  if (run.status === 'completed') navigate(`/leads/${run.id}`);
                  else if (run.status === 'running') navigate(`/pipeline/${run.id}`);
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
                    🗓 {run.started_at ? new Date(run.started_at).toLocaleDateString() : 'Not started'}
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

                {/* ICP details */}
                {run.icp_config && (
                  <div className="rc-icp-block">
                    {run.icp_config.regions?.countries && run.icp_config.regions.countries.length > 0 && (
                      <div className="rc-icp-row">
                        <span className="rc-icp-key">📍 Regions</span>
                        <span className="rc-icp-val">
                          {run.icp_config.regions.countries.slice(0, 3).join(', ')}
                        </span>
                      </div>
                    )}
                    {run.icp_config.industry_types && run.icp_config.industry_types.length > 0 && (
                      <div className="rc-icp-row">
                        <span className="rc-icp-key">🏭 Industries</span>
                        <span className="rc-icp-val">
                          {run.icp_config.industry_types.map(i => i.vertical).slice(0, 3).join(', ')}
                        </span>
                      </div>
                    )}
                    {run.icp_config.personas && run.icp_config.personas.length > 0 && (
                      <div className="rc-icp-row">
                        <span className="rc-icp-key">👤 Roles</span>
                        <span className="rc-icp-val">
                          {run.icp_config.personas.map(p => p.job_title).slice(0, 3).join(', ')}
                        </span>
                      </div>
                    )}
                  </div>
                )}

                {/* Footer actions */}
                <div className="rc-footer">
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
                  {run.status === 'completed' && (
                    <span className="rc-view-link">View Results →</span>
                  )}
                  {run.status === 'running' && (
                    <span className="rc-view-link" style={{ color: 'var(--orange)' }}>View Progress →</span>
                  )}
                </div>
              </div>
            </Col>
          ))}
        </Row>
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
              <Tag>{runsList.filter(r => r.status === 'pending').length} Pending</Tag>
            </div>
            <Table
              columns={getModalColumns('pipeline_runs')}
              dataSource={runsList}
              rowKey="id"
              pagination={false}
              size="middle"
              locale={{ emptyText: 'No searches found' }}
            />
          </>
        ) : (
          <Table
            columns={getModalColumns(statsModalTile)}
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
