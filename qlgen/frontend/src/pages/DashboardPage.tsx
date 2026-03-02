import React, { useEffect, useState } from 'react';
import { Card, Row, Col, Button, Tag, Empty, Space, Modal, Table } from 'antd';
import { PlusOutlined, CloseOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { listICPs } from '../api/icpApi';
import { listPipelineRuns, getPipelineStatsByICP, ICPStat } from '../api/pipelineApi';
import { PipelineRun } from '../types';

const WELCOME_DISMISSED_KEY = 'qlgen_welcome_dismissed';

const HOW_IT_WORKS = [
  { step: '1', title: 'Define ICP', desc: 'Configure your ideal customer profile across 8 dimensions — industry, size, tech stack, and more.' },
  { step: '2', title: 'Run Pipeline', desc: 'Our AI agent searches 9 data sources autonomously to discover and qualify leads.' },
  { step: '3', title: 'Review Leads', desc: 'Get BANT-scored companies with verified decision-maker contacts.' },
  { step: '4', title: 'Export & Act', desc: 'Download qualified leads as Excel or CSV and start outreach.' },
];

type TileKey = 'total_leads' | 'pipeline_runs' | 'companies' | 'contacts';

const TILE_LABELS: Record<TileKey, string> = {
  total_leads: 'Total Leads',
  pipeline_runs: 'Pipeline Runs',
  companies: 'Companies Found',
  contacts: 'Contacts Found',
};

const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const [runs, setRuns] = useState<PipelineRun[]>([]);
  const [welcomeDismissed, setWelcomeDismissed] = useState(
    () => localStorage.getItem(WELCOME_DISMISSED_KEY) === 'true'
  );

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

  const dismissWelcome = () => {
    localStorage.setItem(WELCOME_DISMISSED_KEY, 'true');
    setWelcomeDismissed(true);
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

  const statsColumns = [
    { title: 'ICP Name', dataIndex: 'icp_name', key: 'icp_name', render: (v: string) => <span style={{ fontWeight: 600 }}>{v}</span> },
    { title: 'Runs', dataIndex: 'run_count', key: 'run_count', width: 80 },
    { title: 'Companies', dataIndex: 'total_companies', key: 'total_companies', width: 110 },
    { title: 'Contacts', dataIndex: 'total_contacts', key: 'total_contacts', width: 100 },
    {
      title: 'Total Leads', key: 'total_leads', width: 110,
      render: (_: unknown, record: ICPStat) => record.total_companies + record.total_contacts,
    },
  ];

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
    <div>
      <div style={{ marginBottom: 24 }}>
        <div className="section-label">Overview</div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h1 className="page-title">Dashboard</h1>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/icp/new')}>
            New Run
          </Button>
        </div>
      </div>

      {/* Welcome Banner */}
      {!welcomeDismissed && (
        <div style={{
          background: 'linear-gradient(135deg, var(--purple-pale) 0%, #fff 100%)',
          border: '1px solid var(--g200)',
          borderRadius: 'var(--radius)',
          padding: '24px 28px',
          marginBottom: 24,
          position: 'relative',
        }}>
          <Button
            type="text"
            size="small"
            icon={<CloseOutlined />}
            onClick={dismissWelcome}
            style={{ position: 'absolute', top: 12, right: 12, color: 'var(--g400)' }}
          />
          <h2 style={{ fontSize: 17, fontWeight: 700, color: 'var(--g900)', margin: '0 0 4px' }}>
            Welcome to qlGen
          </h2>
          <p style={{ fontSize: 13, color: 'var(--g600)', margin: '0 0 20px', lineHeight: 1.6, maxWidth: 620 }}>
            AI-powered qualified lead generation. Define your Ideal Customer Profile, and our AI agent
            autonomously discovers companies, finds decision-maker contacts, enriches their data, and
            scores each lead using the BANT framework.
          </p>
          <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
            {HOW_IT_WORKS.map((item) => (
              <div key={item.step} style={{ flex: '1 1 140px', minWidth: 140 }}>
                <div style={{
                  width: 28, height: 28, borderRadius: '50%',
                  background: 'var(--purple)', color: '#fff',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 13, fontWeight: 700, marginBottom: 8,
                }}>
                  {item.step}
                </div>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--g800)' }}>{item.title}</div>
                <div style={{ fontSize: 12, color: 'var(--g500)', marginTop: 2, lineHeight: 1.5 }}>{item.desc}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={12} sm={12} md={6}>
          <div className="metric-tile metric-tile-clickable" onClick={() => openStatsModal('total_leads')}>
            <div className="metric-icon">🎯</div>
            <div className="label">Total Leads</div>
            <div className="value">{totalCompanies + totalContacts}</div>
          </div>
        </Col>
        <Col xs={12} sm={12} md={6}>
          <div className="metric-tile metric-tile-clickable" onClick={() => openStatsModal('pipeline_runs')}>
            <div className="metric-icon">📈</div>
            <div className="label">Pipeline Runs</div>
            <div className="value">{runsList.length}</div>
          </div>
        </Col>
        <Col xs={12} sm={12} md={6}>
          <div className="metric-tile metric-tile-clickable" onClick={() => openStatsModal('companies')}>
            <div className="metric-icon">🏢</div>
            <div className="label">Companies Found</div>
            <div className="value">{totalCompanies}</div>
          </div>
        </Col>
        <Col xs={12} sm={12} md={6}>
          <div className="metric-tile metric-tile-clickable" onClick={() => openStatsModal('contacts')}>
            <div className="metric-icon">👥</div>
            <div className="label">Contacts Found</div>
            <div className="value">{totalContacts}</div>
          </div>
        </Col>
      </Row>

      <div style={{ marginBottom: 16 }}>
        <div className="section-label">Recent Activity</div>
        <h2 style={{ fontSize: 16, fontWeight: 700, color: 'var(--g800)', margin: 0 }}>Recent Runs</h2>
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
                onMouseEnter={(e) => {
                  if (run.status === 'failed') {
                    e.currentTarget.style.transform = 'none';
                    e.currentTarget.style.boxShadow = 'var(--shadow)';
                  }
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: 8 }}>
                  <div className="fw-600" style={{ fontSize: 15, color: 'var(--g900)', letterSpacing: '-0.2px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 200 }}>
                    {run.icp_name || `Run #${run.id.substring(0, 8)}`}
                  </div>
                  <Tag color={statusColor[run.status] || 'default'}>{run.status.toUpperCase()}</Tag>
                </div>
                <div className="text-muted" style={{ fontSize: 12, marginBottom: 12 }}>
                  {run.started_at ? new Date(run.started_at).toLocaleDateString() : 'Not started'}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div className="text-muted" style={{ fontSize: 12 }}>
                    {run.companies_found} companies, {run.contacts_found} contacts
                  </div>
                  {run.status === 'completed' && (
                    <span style={{ fontSize: 12, color: 'var(--purple)', fontWeight: 500 }}>View →</span>
                  )}
                  {run.status === 'running' && (
                    <span style={{ fontSize: 12, color: 'var(--orange)', fontWeight: 500 }}>Progress →</span>
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
            Get Started with Your First Run
          </h3>
          <p style={{ color: 'var(--g500)', marginBottom: 24, maxWidth: 460, margin: '0 auto 24px', fontSize: 13, lineHeight: 1.6 }}>
            Create an Ideal Customer Profile to define your target market, then our AI agent will
            autonomously find and qualify leads matching your criteria.
          </p>
          <Space size="middle" direction="vertical" style={{ width: '100%' }}>
            <Space size="middle">
              <Button type="primary" size="large" icon={<PlusOutlined />} onClick={() => navigate('/icp/new')}>
                Create Your First ICP
              </Button>
            </Space>
            <div style={{ fontSize: 13, color: 'var(--g400)', marginTop: 4 }}>
              or{' '}
              <span
                style={{ color: 'var(--purple)', cursor: 'pointer', fontWeight: 500 }}
                onClick={() => navigate('/icp?import=true')}
              >
                import ICPs from an Excel spreadsheet
              </span>
            </div>
          </Space>
        </Card>
      )}

      {/* Stats Breakdown Modal */}
      <Modal
        title={`${TILE_LABELS[statsModalTile]} — Breakdown by ICP`}
        open={statsModalOpen}
        onCancel={() => setStatsModalOpen(false)}
        footer={null}
        width={800}
      >
        <Table
          columns={statsColumns}
          dataSource={icpStats}
          rowKey="icp_id"
          loading={statsLoading}
          expandable={{ expandedRowRender }}
          pagination={false}
          size="middle"
          locale={{ emptyText: 'No pipeline runs found' }}
        />
      </Modal>
    </div>
  );
};

export default DashboardPage;
