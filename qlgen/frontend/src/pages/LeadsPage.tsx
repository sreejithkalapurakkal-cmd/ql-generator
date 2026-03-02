import React, { useEffect, useState } from 'react';
import { Card, Table, Tag, Button, Space, Tooltip, Descriptions, Select, Typography } from 'antd';
import { DownloadOutlined } from '@ant-design/icons';
import { useParams } from 'react-router-dom';
import { getLeadCompanies, getExportUrl } from '../api/leadsApi';
import { Company, BANTScore } from '../types';

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
  const [expandedRowKeys, setExpandedRowKeys] = useState<(string | number)[]>([]);

  useEffect(() => {
    if (!runId) return;
    setLoading(true);
    getLeadCompanies(runId, { sort_by: sortBy })
      .then((res) => {
        setCompanies(res.data);
        // Auto-expand first row after data loads
        if (res.data.length > 0) {
          const firstCompany = res.data[0];
          if (firstCompany.contacts.length > 0) {
            setExpandedRowKeys([`${firstCompany.id}-${firstCompany.contacts[0].id}`]);
          } else {
            setExpandedRowKeys([firstCompany.id]);
          }
        }
      })
      .finally(() => setLoading(false));
  }, [runId, sortBy]);

  // Flatten companies+contacts into rows for the main table
  const flatRows: Array<{
    key: string | number;
    serial: number;
    company_name: string;
    website: string | null;
    city: string;
    contact_name: string;
    designation: string | null;
    linkedin: string | null;
    email: string | null;
    phone: string | null;
    bant_score: BANTScore | null;
    company: Company;
    contact: any;
  }> = [];
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
          contact_name: contact.full_name || "",
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
      <div style={{ marginBottom: 24 }}>
        <div className="section-label">Lead Generation</div>
        <h1 className="page-title">Run Results</h1>
      </div>

      <div className="summary-bar">
        <div className="summary-item">
          <div className="val">{companies.length}</div>
          <div className="lbl">Companies</div>
        </div>
        <div className="summary-item">
          <div className="val">{totalContacts}</div>
          <div className="lbl">Contacts</div>
        </div>
        <div className="summary-item">
          <div className="val">{avgBant}</div>
          <div className="lbl">Avg BANT Score</div>
        </div>
        <div className="summary-item">
          <div className="val" style={{ fontSize: 15, fontWeight: 600 }}>
            {hotLeads} / {warmLeads}
          </div>
          <div className="lbl">Hot / Warm</div>
        </div>
      </div>

      <Card
        title="Qualified Leads"
        extra={
          <Space>
            <Select value={sortBy} onChange={setSortBy} style={{ width: 160 }}>
              <Select.Option value="bant_score">Sort by BANT Score</Select.Option>
              <Select.Option value="company_name">Sort by Company</Select.Option>
            </Select>
            <Button type="primary" icon={<DownloadOutlined />} onClick={() => window.open(getExportUrl(runId!, 'xlsx'))}>
              Export Excel
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
            expandedRowKeys,
            onExpandedRowsChange: (keys) => setExpandedRowKeys(keys as (string | number)[]),
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
