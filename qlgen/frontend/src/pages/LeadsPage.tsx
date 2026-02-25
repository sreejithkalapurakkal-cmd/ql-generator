import React, { useEffect, useState } from 'react';
import { Card, Table, Tag, Button, Space, Tooltip, Descriptions, Select, InputNumber, Row, Col, Statistic, Typography, Collapse } from 'antd';
import { DownloadOutlined, BarChartOutlined, TeamOutlined } from '@ant-design/icons';
import { useParams } from 'react-router-dom';
import { getLeadCompanies, getExportUrl } from '../api/leadsApi';
import { Company, Contact, BANTScore } from '../types';

const { Text } = Typography;

const BANTScoreDisplay: React.FC<{ score: BANTScore | null }> = ({ score }) => {
  if (!score || !score.total_score) return <Tag>N/A</Tag>;
  const total = score.total_score;
  const color = total >= 16 ? 'green' : total >= 12 ? 'gold' : total >= 9 ? 'blue' : 'red';
  const label = total >= 16 ? 'HOT' : total >= 12 ? 'WARM' : total >= 9 ? 'COOL' : 'COLD';

  return (
    <Tooltip title={`B:${score.budget_score} A:${score.authority_score} N:${score.need_score} T:${score.timing_score}`}>
      <Tag color={color} style={{ fontWeight: 'bold', fontSize: 13 }}>
        {total}/20 {label}
      </Tag>
    </Tooltip>
  );
};

const BANTDetailPanel: React.FC<{ score: BANTScore }> = ({ score }) => (
  <Descriptions bordered size="small" column={2}>
    <Descriptions.Item label={`Budget (${score.budget_score}/5)`}>{score.budget_reason || '-'}</Descriptions.Item>
    <Descriptions.Item label={`Authority (${score.authority_score}/5)`}>{score.authority_reason || '-'}</Descriptions.Item>
    <Descriptions.Item label={`Need (${score.need_score}/5)`}>{score.need_reason || '-'}</Descriptions.Item>
    <Descriptions.Item label={`Timing (${score.timing_score}/5)`}>{score.timing_reason || '-'}</Descriptions.Item>
    <Descriptions.Item label="Summary" span={2}>{score.overall_summary || '-'}</Descriptions.Item>
  </Descriptions>
);

const LeadsPage: React.FC = () => {
  const { runId } = useParams<{ runId: string }>();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [sortBy, setSortBy] = useState('bant_score');

  useEffect(() => {
    if (!runId) return;
    setLoading(true);
    getLeadCompanies(runId, { sort_by: sortBy })
      .then((res) => setCompanies(res.data))
      .finally(() => setLoading(false));
  }, [runId, sortBy]);

  // Flatten companies+contacts into rows for the main table
  const flatRows: any[] = [];
  let serial = 1;
  companies.forEach((company) => {
    if (company.contacts.length > 0) {
      company.contacts.forEach((contact) => {
        flatRows.push({
          key: `${company.id}-${contact.id}`,
          serial: serial++,
          company_name: company.name,
          website: company.website,
          city: [company.city, company.state_region, company.country].filter(Boolean).join(', '),
          contact_name: contact.full_name,
          designation: contact.designation,
          linkedin: contact.linkedin_url,
          email: contact.email,
          phone: contact.phone,
          bant_score: company.bant_score,
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
        city: [company.city, company.state_region, company.country].filter(Boolean).join(', '),
        contact_name: '-',
        designation: '-',
        linkedin: null,
        email: null,
        phone: null,
        bant_score: company.bant_score,
        company,
        contact: null,
      });
    }
  });

  const totalContacts = companies.reduce((s, c) => s + c.contacts.length, 0);
  const avgBant = companies.length > 0
    ? (companies.reduce((s, c) => s + (c.bant_score?.total_score || 0), 0) / companies.length).toFixed(1)
    : '0';
  const hotLeads = companies.filter((c) => (c.bant_score?.total_score || 0) >= 16).length;
  const warmLeads = companies.filter((c) => {
    const t = c.bant_score?.total_score || 0;
    return t >= 12 && t < 16;
  }).length;

  const columns = [
    { title: '#', dataIndex: 'serial', width: 50 },
    { title: 'Company Name', dataIndex: 'company_name', width: 180 },
    {
      title: 'Website',
      dataIndex: 'website',
      width: 150,
      render: (url: string | null) => url ? <a href={url.startsWith('http') ? url : `https://${url}`} target="_blank" rel="noreferrer">{url}</a> : '-',
    },
    { title: 'Geo/City', dataIndex: 'city', width: 150 },
    { title: 'Contact Name', dataIndex: 'contact_name', width: 150 },
    { title: 'Designation', dataIndex: 'designation', width: 180 },
    {
      title: 'LinkedIn',
      dataIndex: 'linkedin',
      width: 80,
      render: (url: string | null) => url ? <a href={url} target="_blank" rel="noreferrer">Profile</a> : '-',
    },
    { title: 'Email', dataIndex: 'email', width: 200, render: (e: string | null) => e || '-' },
    { title: 'Phone', dataIndex: 'phone', width: 140, render: (p: string | null) => p || '-' },
    {
      title: 'BANT Score',
      dataIndex: 'bant_score',
      width: 130,
      render: (score: BANTScore | null) => <BANTScoreDisplay score={score} />,
    },
  ];

  return (
    <div>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card><Statistic title="Companies" value={companies.length} prefix={<TeamOutlined />} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="Contacts" value={totalContacts} prefix={<TeamOutlined />} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="Avg BANT Score" value={avgBant} prefix={<BarChartOutlined />} suffix="/20" /></Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="Hot / Warm"
              value={hotLeads}
              suffix={`/ ${warmLeads}`}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
      </Row>

      <Card
        title="Qualified Leads"
        extra={
          <Space>
            <Select value={sortBy} onChange={setSortBy} style={{ width: 160 }}>
              <Select.Option value="bant_score">Sort by BANT Score</Select.Option>
              <Select.Option value="company_name">Sort by Company</Select.Option>
            </Select>
            <Button icon={<DownloadOutlined />} onClick={() => window.open(getExportUrl(runId!, 'xlsx'))}>
              Export XLSX
            </Button>
            <Button icon={<DownloadOutlined />} onClick={() => window.open(getExportUrl(runId!, 'csv'))}>
              Export CSV
            </Button>
          </Space>
        }
      >
        <Table
          columns={columns}
          dataSource={flatRows}
          loading={loading}
          pagination={{ pageSize: 50, showSizeChanger: true }}
          scroll={{ x: 1400 }}
          expandable={{
            expandedRowRender: (record) =>
              record.company?.bant_score ? (
                <BANTDetailPanel score={record.company.bant_score} />
              ) : (
                <Text type="secondary">No BANT scoring data available</Text>
              ),
          }}
          size="small"
        />
      </Card>
    </div>
  );
};

export default LeadsPage;
