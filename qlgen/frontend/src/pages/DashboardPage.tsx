import React, { useEffect, useState } from 'react';
import { Card, Row, Col, Button, Tag, Empty } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { listICPs } from '../api/icpApi';
import { listPipelineRuns } from '../api/pipelineApi';
import { PipelineRun } from '../types';

const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const [runs, setRuns] = useState<PipelineRun[]>([]);

  useEffect(() => {
    Promise.all([listICPs(), listPipelineRuns()])
      .then(([, runRes]) => {
        setRuns(runRes.data);
      });
  }, []);

  const completedRuns = runs.filter((r) => r.status === 'completed');
  const totalCompanies = completedRuns.reduce((s, r) => s + r.companies_found, 0);
  const totalContacts = completedRuns.reduce((s, r) => s + r.contacts_found, 0);

  const statusColor: Record<string, string> = {
    pending: 'default',
    running: 'processing',
    completed: 'success',
    failed: 'error',
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

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <div className="metric-tile">
            <div className="metric-icon">🎯</div>
            <div className="label">Total Leads</div>
            <div className="value">{totalCompanies + totalContacts}</div>
          </div>
        </Col>
        <Col span={6}>
          <div className="metric-tile">
            <div className="metric-icon">📈</div>
            <div className="label">Pipeline Runs</div>
            <div className="value">{runs.length}</div>
          </div>
        </Col>
        <Col span={6}>
          <div className="metric-tile">
            <div className="metric-icon">🏢</div>
            <div className="label">Companies Found</div>
            <div className="value">{totalCompanies}</div>
          </div>
        </Col>
        <Col span={6}>
          <div className="metric-tile">
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

      {runs.length > 0 ? (
        <Row gutter={16}>
          {runs.slice(0, 6).map((run) => (
            <Col span={8} key={run.id} style={{ marginBottom: 16 }}>
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
                  <div className="fw-600" style={{ fontSize: 15, color: 'var(--g900)', letterSpacing: '-0.2px' }}>
                    Run #{run.id}
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
        <Card>
          <Empty description="No pipeline runs yet. Create an ICP configuration to get started.">
            <Button type="primary" onClick={() => navigate('/icp/new')}>
              Create ICP Configuration
            </Button>
          </Empty>
        </Card>
      )}
    </div>
  );
};

export default DashboardPage;
