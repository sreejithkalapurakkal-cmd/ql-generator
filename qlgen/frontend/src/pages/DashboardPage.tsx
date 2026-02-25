import React, { useEffect, useState } from 'react';
import { Card, Row, Col, Button, Table, Tag, Statistic, Empty } from 'antd';
import {
  PlusOutlined,
  RocketOutlined,
  TeamOutlined,
  BarChartOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { listICPs } from '../api/icpApi';
import { listPipelineRuns } from '../api/pipelineApi';
import { ICPConfig, PipelineRun } from '../types';

const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const [icps, setIcps] = useState<ICPConfig[]>([]);
  const [runs, setRuns] = useState<PipelineRun[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([listICPs(), listPipelineRuns()])
      .then(([icpRes, runRes]) => {
        setIcps(icpRes.data);
        setRuns(runRes.data);
      })
      .finally(() => setLoading(false));
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

  const runColumns = [
    {
      title: 'Status',
      dataIndex: 'status',
      render: (s: string) => <Tag color={statusColor[s] || 'default'}>{s.toUpperCase()}</Tag>,
    },
    { title: 'Companies', dataIndex: 'companies_found' },
    { title: 'Contacts', dataIndex: 'contacts_found' },
    {
      title: 'Started',
      dataIndex: 'started_at',
      render: (d: string | null) => (d ? new Date(d).toLocaleString() : '-'),
    },
    {
      title: 'Actions',
      render: (_: unknown, record: PipelineRun) => (
        <span>
          {record.status === 'running' && (
            <Button size="small" onClick={() => navigate(`/pipeline/${record.id}`)}>
              View Progress
            </Button>
          )}
          {record.status === 'completed' && (
            <Button size="small" type="primary" onClick={() => navigate(`/leads/${record.id}`)}>
              View Leads
            </Button>
          )}
        </span>
      ),
    },
  ];

  return (
    <div>
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic title="ICP Configurations" value={icps.length} prefix={<BarChartOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="Pipeline Runs" value={runs.length} prefix={<RocketOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="Companies Found" value={totalCompanies} prefix={<TeamOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="Contacts Found" value={totalContacts} prefix={<TeamOutlined />} />
          </Card>
        </Col>
      </Row>

      <Card
        title="Recent Pipeline Runs"
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/icp/new')}>
            New ICP & Pipeline
          </Button>
        }
      >
        {runs.length > 0 ? (
          <Table columns={runColumns} dataSource={runs} rowKey="id" loading={loading} pagination={{ pageSize: 10 }} />
        ) : (
          <Empty description="No pipeline runs yet. Create an ICP configuration to get started.">
            <Button type="primary" onClick={() => navigate('/icp/new')}>
              Create ICP Configuration
            </Button>
          </Empty>
        )}
      </Card>
    </div>
  );
};

export default DashboardPage;
