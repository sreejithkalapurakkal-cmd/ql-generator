import React, { useEffect, useState } from 'react';
import { Card, Table, Tag, Button, Space, Tooltip, Descriptions, Select, Typography, Collapse } from 'antd';
import { DownloadOutlined, ProfileOutlined, CodeOutlined, ToolOutlined, BulbOutlined, RocketOutlined } from '@ant-design/icons';
import { useParams, useNavigate } from 'react-router-dom';
import { getLeadCompanies, getExportUrl } from '../api/leadsApi';
import { getPipelineStatus, getPipelineLogs } from '../api/pipelineApi';
import { Company, BANTScore, BANTSourceCitation, PipelineRun, PipelineLogEntry } from '../types';

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

const SourceLinks: React.FC<{ sources?: BANTSourceCitation[] | null }> = ({ sources }) => {
  if (!sources || sources.length === 0) return null;
  return (
    <div style={{ marginTop: 6 }}>
      {sources.map((s, i) => (
        <Tag key={i} style={{ marginBottom: 3, fontSize: 11 }}>
          <a href={s.url} target="_blank" rel="noreferrer" style={{ color: 'var(--purple)' }}>
            {s.title || new URL(s.url).hostname}
          </a>
          {s.tool && <span style={{ color: 'var(--g400)', marginLeft: 4 }}>({s.tool})</span>}
        </Tag>
      ))}
    </div>
  );
};

const BANTDetailPanel: React.FC<{ score: BANTScore }> = ({ score }) => (
  <Descriptions bordered size="small" column={2}>
    <Descriptions.Item label={`Budget (${score.budget_score}/5)`}>
      {score.budget_reason || '-'}
      <SourceLinks sources={score.budget_sources} />
    </Descriptions.Item>
    <Descriptions.Item label={`Authority (${score.authority_score}/5)`}>
      {score.authority_reason || '-'}
      <SourceLinks sources={score.authority_sources} />
    </Descriptions.Item>
    <Descriptions.Item label={`Need (${score.need_score}/5)`}>
      {score.need_reason || '-'}
      <SourceLinks sources={score.need_sources} />
    </Descriptions.Item>
    <Descriptions.Item label={`Timing (${score.timing_score}/5)`}>
      {score.timing_reason || '-'}
      <SourceLinks sources={score.timing_sources} />
    </Descriptions.Item>
    <Descriptions.Item label="Summary" span={2}>{score.overall_summary || '-'}</Descriptions.Item>
  </Descriptions>
);

const ICPConfigPanel: React.FC<{ config: Record<string, unknown> }> = ({ config }) => {
  const cfg = config as any;
  return (
    <Descriptions bordered size="small" column={2}>
      <Descriptions.Item label="Target Offerings" span={2}>
        {cfg?.target_offering?.join(', ') || '-'}
      </Descriptions.Item>
      <Descriptions.Item label="Countries">
        {cfg?.regions?.countries?.join(', ') || '-'}
      </Descriptions.Item>
      <Descriptions.Item label="Priority Areas">
        {cfg?.regions?.priority_areas?.join(', ') || '-'}
      </Descriptions.Item>
      <Descriptions.Item label="Industries" span={2}>
        {cfg?.industry_types?.map((i: any) =>
          `${i.vertical}${i.sub_vertical ? ` / ${i.sub_vertical}` : ''}`
        ).join(', ') || '-'}
      </Descriptions.Item>
      <Descriptions.Item label="Employees">
        {cfg?.company_size?.employees_min?.toLocaleString()}–{cfg?.company_size?.employees_max?.toLocaleString()}
      </Descriptions.Item>
      <Descriptions.Item label="Revenue">
        {cfg?.company_size?.revenue_currency} {cfg?.company_size?.revenue_min?.toLocaleString()}–{cfg?.company_size?.revenue_max?.toLocaleString()}
      </Descriptions.Item>
      <Descriptions.Item label="Tech Signals (Positive)">
        {cfg?.technology_maturity?.signals?.join(', ') || '-'}
      </Descriptions.Item>
      <Descriptions.Item label="Tech Signals (Negative)">
        {cfg?.technology_maturity?.negative_signals?.join(', ') || '-'}
      </Descriptions.Item>
      <Descriptions.Item label="Infrastructure" span={2}>
        {cfg?.infrastructure_readiness?.indicators?.join(', ') || '-'}
      </Descriptions.Item>
      <Descriptions.Item label="Growth Triggers">
        {cfg?.digital_transformation_drivers?.growth_triggers?.join(', ') || '-'}
      </Descriptions.Item>
      <Descriptions.Item label="Operational Pains">
        {cfg?.digital_transformation_drivers?.operational_pains?.join(', ') || '-'}
      </Descriptions.Item>
      <Descriptions.Item label="Competitive Pressures">
        {cfg?.digital_transformation_drivers?.competitive_pressures?.join(', ') || '-'}
      </Descriptions.Item>
      <Descriptions.Item label="Strategic Initiatives">
        {cfg?.digital_transformation_drivers?.strategic_initiatives?.join(', ') || '-'}
      </Descriptions.Item>
      <Descriptions.Item label="Target Roles">
        {cfg?.leadership_traits?.target_roles?.join(', ') || '-'}
      </Descriptions.Item>
      <Descriptions.Item label="Behavioral Traits">
        {cfg?.leadership_traits?.behavioral_traits?.join(', ') || '-'}
      </Descriptions.Item>
    </Descriptions>
  );
};

const toolTagColors: Record<string, string> = {
  apollo_company_search: 'blue', apollo_people_search: 'blue',
  exa_search: 'purple', tavily_search: 'orange', duckduckgo_search: 'green',
  hunter_domain_search: 'cyan', hunter_email_finder: 'cyan',
  lusha_person_search: 'magenta', scrape_webpage: 'volcano',
};

const AgentLogPanel: React.FC<{ runId: string }> = ({ runId }) => {
  const navigate = useNavigate();
  const [logs, setLogs] = useState<PipelineLogEntry[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (loaded) return;
    setLoading(true);
    getPipelineLogs(runId)
      .then((res) => {
        setLogs(Array.isArray(res.data) ? res.data : []);
        setLoaded(true);
      })
      .catch(() => setLogs([]))
      .finally(() => setLoading(false));
  }, [runId, loaded]);

  const toolCalls = logs.filter((l) => l.event_type === 'tool_start');
  const stages = logs.filter((l) => l.event_type === 'stage_update');

  return (
    <div>
      {loading && <div style={{ textAlign: 'center', padding: 20, color: 'var(--g400)' }}>Loading agent logs...</div>}
      {loaded && (
        <>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <Text type="secondary" style={{ fontSize: 12 }}>
              {toolCalls.length} tool calls across {stages.length} stage transitions
            </Text>
            <Button size="small" onClick={() => navigate(`/pipeline/${runId}`)}>
              View Full Log
            </Button>
          </div>
          <div style={{ maxHeight: 400, overflowY: 'auto' }}>
            {logs.map((log) => {
              const d = log.event_data;
              const time = log.created_at ? new Date(log.created_at).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }) : '';
              if (log.event_type === 'tool_start') {
                return (
                  <div key={log.id} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', padding: '4px 0', borderBottom: '1px solid var(--g100)' }}>
                    <Text type="secondary" style={{ fontSize: 11, whiteSpace: 'nowrap', minWidth: 60 }}>{time}</Text>
                    <Tag color={toolTagColors[d.tool_name as string] || 'default'} style={{ fontSize: 11 }}>
                      {(d.display_name as string) || (d.tool_name as string)}
                    </Tag>
                    {d.context && <Text type="secondary" style={{ fontSize: 12 }}>{(d.context as string).substring(0, 100)}</Text>}
                  </div>
                );
              }
              if (log.event_type === 'agent_reasoning') {
                return (
                  <div key={log.id} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', padding: '4px 0', borderBottom: '1px solid var(--g100)' }}>
                    <Text type="secondary" style={{ fontSize: 11, whiteSpace: 'nowrap', minWidth: 60 }}>{time}</Text>
                    <BulbOutlined style={{ color: '#faad14', fontSize: 12, marginTop: 2 }} />
                    <Text style={{ fontSize: 12, fontStyle: 'italic', color: 'var(--g600)' }}>
                      {(d.text as string)?.substring(0, 150)}{(d.text as string)?.length > 150 ? '...' : ''}
                    </Text>
                  </div>
                );
              }
              if (log.event_type === 'stage_update') {
                return (
                  <div key={log.id} style={{ display: 'flex', gap: 8, alignItems: 'center', padding: '6px 0', borderBottom: '1px solid var(--g100)' }}>
                    <Text type="secondary" style={{ fontSize: 11, whiteSpace: 'nowrap', minWidth: 60 }}>{time}</Text>
                    <RocketOutlined style={{ color: 'var(--purple)', fontSize: 12 }} />
                    <Text strong style={{ fontSize: 12, color: 'var(--purple)' }}>{d.message as string}</Text>
                  </div>
                );
              }
              if (log.event_type === 'tool_result') {
                return (
                  <div key={log.id} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', padding: '4px 0', borderBottom: '1px solid var(--g100)' }}>
                    <Text type="secondary" style={{ fontSize: 11, whiteSpace: 'nowrap', minWidth: 60 }}>{time}</Text>
                    <Tag color="default" style={{ fontSize: 10 }}>RESULT</Tag>
                    <Text type="secondary" style={{ fontSize: 11 }}>
                      {(d.tool_name as string)}: {(d.result_preview as string)?.substring(0, 80)}...
                    </Text>
                  </div>
                );
              }
              return null;
            })}
            {logs.length === 0 && <div style={{ textAlign: 'center', padding: 20, color: 'var(--g400)' }}>No agent logs available for this run.</div>}
          </div>
        </>
      )}
    </div>
  );
};

const LeadsPage: React.FC = () => {
  const { runId } = useParams<{ runId: string }>();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [sortBy, setSortBy] = useState('bant_score');
  const [expandedRowKeys, setExpandedRowKeys] = useState<(string | number)[]>([]);
  const [pipelineRun, setPipelineRun] = useState<PipelineRun | null>(null);

  useEffect(() => {
    if (runId) {
      getPipelineStatus(runId).then(res => setPipelineRun(res.data));
    }
  }, [runId]);

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
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <h1 className="page-title">Run Results</h1>
          {pipelineRun?.icp_name && (
            <Tag color="purple" style={{ fontSize: 13, padding: '2px 12px' }}>{pipelineRun.icp_name}</Tag>
          )}
        </div>
      </div>

      {pipelineRun?.icp_config && (
        <Collapse
          style={{ marginBottom: 16 }}
          items={[{
            key: 'icp-config',
            label: (
              <span style={{ fontWeight: 600, fontSize: 14 }}>
                <ProfileOutlined style={{ marginRight: 8 }} />
                Search Criteria (ICP Configuration)
              </span>
            ),
            children: <ICPConfigPanel config={pipelineRun.icp_config} />,
          }]}
        />
      )}

      {runId && (
        <Collapse
          style={{ marginBottom: 16 }}
          items={[{
            key: 'agent-logs',
            label: (
              <span style={{ fontWeight: 600, fontSize: 14 }}>
                <CodeOutlined style={{ marginRight: 8 }} />
                Agent Activity Log
              </span>
            ),
            children: <AgentLogPanel runId={runId} />,
          }]}
        />
      )}

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
