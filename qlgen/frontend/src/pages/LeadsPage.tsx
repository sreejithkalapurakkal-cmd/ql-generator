import React, { useEffect, useState, useMemo } from 'react';
import { Card, Table, Tag, Button, Space, Tooltip, Descriptions, Select, Typography, Collapse } from 'antd';
import { DownloadOutlined, ProfileOutlined, ToolOutlined, BarChartOutlined } from '@ant-design/icons';
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

const CompanyInsightsPanel: React.FC<{ company: Company }> = ({ company }) => {
  const matchScore = company.icp_match_score;
  const matchColor = matchScore && matchScore >= 8 ? '#52c41a' : matchScore && matchScore >= 6 ? '#faad14' : '#ff4d4f';
  const techStack = company.tech_stack_json;
  const techItems: string[] = Array.isArray(techStack) ? techStack.map(String) : [];
  const revenue = company.revenue_estimate;
  const revenueStr = revenue ? (revenue >= 1_000_000_000 ? `$${(revenue / 1_000_000_000).toFixed(1)}B` : revenue >= 1_000_000 ? `$${(revenue / 1_000_000).toFixed(0)}M` : `$${revenue.toLocaleString()}`) : null;

  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 8, color: 'var(--g800)' }}>Company Insights</div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, marginBottom: 12 }}>
        {matchScore != null && (
          <div>
            <Text type="secondary" style={{ fontSize: 11 }}>Match Score</Text>
            <div style={{ fontWeight: 700, fontSize: 16, color: matchColor }}>{matchScore}/10</div>
          </div>
        )}
        {revenueStr && (
          <div>
            <Text type="secondary" style={{ fontSize: 11 }}>Revenue Est.</Text>
            <div style={{ fontWeight: 600, fontSize: 14 }}>{revenueStr}</div>
          </div>
        )}
        {company.employee_count != null && (
          <div>
            <Text type="secondary" style={{ fontSize: 11 }}>Employees</Text>
            <div style={{ fontWeight: 600, fontSize: 14 }}>{company.employee_count.toLocaleString()}</div>
          </div>
        )}
        {company.source && (
          <div>
            <Text type="secondary" style={{ fontSize: 11 }}>Source</Text>
            <div><Tag style={{ fontSize: 11 }}>{company.source}</Tag></div>
          </div>
        )}
      </div>
      {techItems.length > 0 && (
        <div style={{ marginBottom: 10 }}>
          <Text type="secondary" style={{ fontSize: 11 }}>Tech Stack: </Text>
          {techItems.map((t, i) => <Tag key={i} color="blue" style={{ fontSize: 11, marginBottom: 3 }}>{t}</Tag>)}
        </div>
      )}
      {company.match_reasoning && (
        <div style={{ background: 'var(--g50, #fafafa)', padding: '8px 12px', borderRadius: 6, fontSize: 12, color: 'var(--g700)', lineHeight: 1.6 }}>
          <Text type="secondary" style={{ fontSize: 11 }}>Overview: </Text>
          {company.match_reasoning}
        </div>
      )}
    </div>
  );
};

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

// Friendly source names and descriptions for sales audience
const SOURCE_FRIENDLY_NAMES: Record<string, string> = {
  apollo_company_search: 'B2B Company Database',
  apollo_people_search: 'Professional Contact Database',
  exa_search: 'Business Intelligence',
  tavily_search: 'Market Research',
  duckduckgo_search: 'Web Research',
  hunter_domain_search: 'Email Discovery',
  hunter_email_finder: 'Email Verification',
  lusha_person_search: 'Phone Number Lookup',
  scrape_webpage: 'Company Website Analysis',
};

const SOURCE_DESCRIPTIONS: Record<string, string> = {
  apollo_company_search: 'Company profiles, industry data, and firmographics',
  apollo_people_search: 'Contact names, job titles, and professional details',
  exa_search: 'News coverage, funding rounds, and company intelligence',
  tavily_search: 'Press releases, financial data, and market trends',
  duckduckgo_search: 'LinkedIn profiles, job postings, and public web data',
  hunter_domain_search: 'Email patterns and domain-level contact discovery',
  hunter_email_finder: 'Verified professional email addresses',
  lusha_person_search: 'Direct phone numbers and mobile contacts',
  scrape_webpage: 'About pages, team pages, and careers information',
};

const SOURCE_COLORS: Record<string, string> = {
  apollo_company_search: '#1677ff', apollo_people_search: '#1677ff',
  exa_search: '#722ed1', tavily_search: '#fa8c16', duckduckgo_search: '#52c41a',
  hunter_domain_search: '#13c2c2', hunter_email_finder: '#13c2c2',
  lusha_person_search: '#eb2f96', scrape_webpage: '#fa541c',
};

const STEP_FRIENDLY: Record<string, { label: string; desc: string }> = {
  company_discovery: { label: 'Finding Companies', desc: 'Identified companies matching your criteria' },
  contact_discovery: { label: 'Finding Contacts', desc: 'Located decision-makers at each company' },
  enrichment: { label: 'Verifying Details', desc: 'Confirmed emails, phones, and LinkedIn profiles' },
  scoring: { label: 'Qualifying Leads', desc: 'Scored each company on Budget, Authority, Need, and Timing' },
};

const RunSummaryPanel: React.FC<{ logs: PipelineLogEntry[]; companies: Company[] }> = ({ logs, companies }) => {
  const summary = useMemo(() => {
    const toolCalls = logs.filter(l => l.event_type === 'tool_start');

    // Source usage
    const toolCounts: Record<string, number> = {};
    toolCalls.forEach(l => {
      const name = l.event_data.tool_name as string;
      toolCounts[name] = (toolCounts[name] || 0) + 1;
    });
    const sourceBreakdown = Object.entries(toolCounts).sort(([, a], [, b]) => b - a);
    const maxCount = sourceBreakdown.length > 0 ? sourceBreakdown[0][1] : 1;

    // Steps
    const stageCounts: Record<string, number> = {};
    toolCalls.forEach(l => {
      const stage = l.event_data.stage as string;
      if (stage) stageCounts[stage] = (stageCounts[stage] || 0) + 1;
    });

    // Duration
    let durationStr = '—';
    if (logs.length >= 2) {
      const first = new Date(logs[0].created_at).getTime();
      const last = new Date(logs[logs.length - 1].created_at).getTime();
      const diffMs = last - first;
      const diffMin = Math.floor(diffMs / 60000);
      const diffSec = Math.floor((diffMs % 60000) / 1000);
      durationStr = diffMin > 0 ? `${diffMin}m ${diffSec}s` : `${diffSec}s`;
    }

    // Data completeness
    const companiesWithScores = companies.filter(c => c.bant_score && c.bant_score.total_score).length;
    const companiesWithContacts = companies.filter(c => c.contacts.length > 0).length;
    const allContacts = companies.flatMap(c => c.contacts);
    const contactsWithEmail = allContacts.filter(c => c.email).length;
    const contactsWithPhone = allContacts.filter(c => c.phone).length;
    const contactsWithLinkedin = allContacts.filter(c => c.linkedin_url).length;

    // Completed time
    let completedAt = '';
    if (logs.length > 0) {
      completedAt = new Date(logs[logs.length - 1].created_at).toLocaleString('en-US', {
        month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit',
      });
    }

    return {
      totalLookups: toolCalls.length,
      sourcesUsed: Object.keys(toolCounts).length,
      durationStr,
      completedAt,
      sourceBreakdown,
      maxCount,
      stageCounts,
      companiesWithScores,
      companiesWithContacts,
      contactsWithEmail,
      contactsWithPhone,
      contactsWithLinkedin,
      totalContacts: allContacts.length,
    };
  }, [logs, companies]);

  if (logs.length === 0) {
    return <div style={{ textAlign: 'center', padding: 20, color: 'var(--g400)' }}>No summary available.</div>;
  }

  const pctScored = companies.length > 0 ? Math.round((summary.companiesWithScores / companies.length) * 100) : 0;
  const pctWithContacts = companies.length > 0 ? Math.round((summary.companiesWithContacts / companies.length) * 100) : 0;
  const pctWithEmail = summary.totalContacts > 0 ? Math.round((summary.contactsWithEmail / summary.totalContacts) * 100) : 0;

  return (
    <div>
      {/* Overview metrics */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
        gap: 12, marginBottom: 20,
      }}>
        <div style={{ background: 'var(--g50, #fafafa)', borderRadius: 8, padding: '14px 16px', border: '1px solid var(--g100, #f0f0f0)' }}>
          <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--purple)', letterSpacing: '-0.5px' }}>{summary.durationStr}</div>
          <Text type="secondary" style={{ fontSize: 11 }}>Time Taken</Text>
        </div>
        <div style={{ background: 'var(--g50, #fafafa)', borderRadius: 8, padding: '14px 16px', border: '1px solid var(--g100, #f0f0f0)' }}>
          <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--purple)', letterSpacing: '-0.5px' }}>{summary.sourcesUsed}</div>
          <Text type="secondary" style={{ fontSize: 11 }}>Sources Searched</Text>
        </div>
        <div style={{ background: 'var(--g50, #fafafa)', borderRadius: 8, padding: '14px 16px', border: '1px solid var(--g100, #f0f0f0)' }}>
          <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--purple)', letterSpacing: '-0.5px' }}>{summary.totalLookups}</div>
          <Text type="secondary" style={{ fontSize: 11 }}>Lookups Performed</Text>
        </div>
        <div style={{ background: 'var(--g50, #fafafa)', borderRadius: 8, padding: '14px 16px', border: '1px solid var(--g100, #f0f0f0)' }}>
          <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--g800)', letterSpacing: '-0.5px' }}>{pctScored}%</div>
          <Text type="secondary" style={{ fontSize: 11 }}>Companies Qualified</Text>
        </div>
      </div>

      {summary.completedAt && (
        <div style={{ fontSize: 12, color: 'var(--g400)', marginBottom: 16 }}>
          Completed on {summary.completedAt}
        </div>
      )}

      <div style={{ display: 'flex', gap: 32, flexWrap: 'wrap' }}>
        {/* Where data came from */}
        <div style={{ flex: '1 1 300px' }}>
          <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 10, color: 'var(--g700)' }}>Where Your Data Came From</div>
          {summary.sourceBreakdown.map(([source, count]) => (
            <div key={source} style={{ marginBottom: 8 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 2 }}>
                <Text style={{ fontSize: 12, fontWeight: 600, color: 'var(--g700)' }}>
                  {SOURCE_FRIENDLY_NAMES[source] || source}
                </Text>
                <Text style={{ fontSize: 11, color: 'var(--g400)' }}>{count} {count === 1 ? 'lookup' : 'lookups'}</Text>
              </div>
              <div style={{ flex: 1, background: 'var(--g100, #f0f0f0)', borderRadius: 3, height: 6, overflow: 'hidden' }}>
                <div style={{
                  width: `${(count / summary.maxCount) * 100}%`,
                  height: '100%',
                  background: SOURCE_COLORS[source] || '#8c8c8c',
                  borderRadius: 3,
                }} />
              </div>
              <Text style={{ fontSize: 11, color: 'var(--g400)', lineHeight: 1.4 }}>
                {SOURCE_DESCRIPTIONS[source] || ''}
              </Text>
            </div>
          ))}
        </div>

        {/* Right column */}
        <div style={{ flex: '1 1 250px' }}>
          {/* What was done */}
          <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 10, color: 'var(--g700)' }}>What Was Done</div>
          {['company_discovery', 'contact_discovery', 'enrichment', 'scoring'].map(stage => {
            const info = STEP_FRIENDLY[stage];
            const count = summary.stageCounts[stage] || 0;
            return (
              <div key={stage} style={{ marginBottom: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Text style={{ fontSize: 12, fontWeight: 600, color: 'var(--g700)' }}>{info?.label || stage}</Text>
                  <Text style={{ fontSize: 11, color: 'var(--g400)' }}>{count} {count === 1 ? 'lookup' : 'lookups'}</Text>
                </div>
                <Text style={{ fontSize: 11, color: 'var(--g400)' }}>{info?.desc || ''}</Text>
              </div>
            );
          })}

          {/* Data completeness */}
          <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 8, marginTop: 16, color: 'var(--g700)' }}>Data Completeness</div>
          <div style={{ fontSize: 12, display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
                <Text type="secondary">Companies with contacts</Text>
                <Text style={{ fontWeight: 600 }}>{summary.companiesWithContacts}/{companies.length}</Text>
              </div>
              <div style={{ background: 'var(--g100, #f0f0f0)', borderRadius: 3, height: 4, overflow: 'hidden' }}>
                <div style={{ width: `${pctWithContacts}%`, height: '100%', background: 'var(--purple)', borderRadius: 3 }} />
              </div>
            </div>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
                <Text type="secondary">Contacts with email</Text>
                <Text style={{ fontWeight: 600 }}>{summary.contactsWithEmail}/{summary.totalContacts}</Text>
              </div>
              <div style={{ background: 'var(--g100, #f0f0f0)', borderRadius: 3, height: 4, overflow: 'hidden' }}>
                <div style={{ width: `${pctWithEmail}%`, height: '100%', background: '#13c2c2', borderRadius: 3 }} />
              </div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <Text type="secondary">Contacts with phone</Text>
              <Text style={{ fontWeight: 600 }}>{summary.contactsWithPhone}/{summary.totalContacts}</Text>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <Text type="secondary">Contacts with LinkedIn</Text>
              <Text style={{ fontWeight: 600 }}>{summary.contactsWithLinkedin}/{summary.totalContacts}</Text>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const LeadsPage: React.FC = () => {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [sortBy, setSortBy] = useState('bant_score');
  const [expandedRowKeys, setExpandedRowKeys] = useState<(string | number)[]>([]);
  const [pipelineRun, setPipelineRun] = useState<PipelineRun | null>(null);
  const [agentLogs, setAgentLogs] = useState<PipelineLogEntry[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);

  useEffect(() => {
    if (runId) {
      getPipelineStatus(runId).then(res => setPipelineRun(res.data));
      setLogsLoading(true);
      getPipelineLogs(runId)
        .then((res) => setAgentLogs(Array.isArray(res.data) ? res.data : []))
        .catch(() => setAgentLogs([]))
        .finally(() => setLogsLoading(false));
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
    source: string | null;
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
          source: contact.source || company.source,
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
        source: company.source,
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
    {
      title: 'Source',
      dataIndex: 'source',
      width: 120,
      render: (src: string | null) => src ? <Tag style={{ fontSize: 11 }}>{src}</Tag> : '-',
    },
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
          <h1 className="page-title">Search Results</h1>
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
                Search Criteria
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
            key: 'run-summary',
            label: (
              <span style={{ fontWeight: 600, fontSize: 14 }}>
                <BarChartOutlined style={{ marginRight: 8 }} />
                Search Summary
              </span>
            ),
            children: logsLoading
              ? <div style={{ textAlign: 'center', padding: 20, color: 'var(--g400)' }}>Loading summary...</div>
              : <RunSummaryPanel logs={agentLogs} companies={companies} />,
          }]}
        />
      )}

      {runId && (
        <div style={{ textAlign: 'right', marginBottom: 16 }}>
          <Button type="link" size="small" icon={<ToolOutlined />}
            onClick={() => navigate(`/pipeline/${runId}`)}>
            View detailed agent logs →
          </Button>
        </div>
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
            expandedRowRender: (record) => (
              <div>
                {record.company && <CompanyInsightsPanel company={record.company} />}
                {record.company?.bant_score ? (
                  <BANTDetailPanel score={record.company.bant_score} />
                ) : (
                  <Text type="secondary">No BANT scoring data available</Text>
                )}
              </div>
            ),
          }}
          size="small"
        />
      </Card>
    </div>
  );
};

export default LeadsPage;
