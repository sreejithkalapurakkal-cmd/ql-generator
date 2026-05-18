import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, Tabs, Table, Tag, Button, Space, Spin, Empty, Avatar, Tooltip, message, Timeline } from 'antd';
import {
  ArrowLeftOutlined, MailOutlined, FileTextOutlined, ThunderboltOutlined,
  UserOutlined, GlobalOutlined, TeamOutlined, LinkOutlined, ExperimentOutlined,
  ClockCircleOutlined, CheckCircleOutlined, EditOutlined,
} from '@ant-design/icons';
import { Badge, KpiStrip } from '../components/ui';
import { useDraftDrawer } from '../context/DraftDrawerContext';
import client from '../api/client';
import type {
  AccountProfile, SignalEvent, OutreachDraft, BriefRevision,
  SIGNAL_TYPE_LABELS, SIGNAL_PRIORITY_COLORS,
} from '../types';

// ─── Constants ──────────────────────────────────────────────────────────────

const SIGNAL_TYPE_LABEL_MAP: Record<string, string> = {
  funding: 'Funding',
  hiring_surge: 'Hiring Surge',
  executive_change: 'Executive Change',
  champion_job_change: 'Champion Job Change',
  tech_adoption: 'Tech Adoption',
  product_launch: 'Product Launch',
  earnings_report: 'Earnings Report',
  press_mention: 'Press Mention',
  partnership: 'Partnership',
  expansion: 'Expansion',
  competitor_adoption: 'Competitor Adoption',
  competitor_churn: 'Competitor Churn',
  budget_signal: 'Budget Signal',
  urgency_signal: 'Urgency Signal',
  custom_signal: 'Custom Signal',
};

const PRIORITY_DOT_CLS: Record<string, string> = {
  critical: 'bg-red-500',
  high: 'bg-orange-500',
  medium: 'bg-amber-400',
  low: 'bg-gray-300',
};

const ICP_FIT_CONFIG: Record<string, { bg: string; text: string; label: string }> = {
  strong: { bg: 'bg-emerald-50', text: 'text-emerald-700', label: 'Strong Fit' },
  moderate: { bg: 'bg-amber-50', text: 'text-amber-700', label: 'Moderate Fit' },
  weak: { bg: 'bg-gray-100', text: 'text-gray-500', label: 'Weak Fit' },
};

const STATUS_CONFIG: Record<string, { color: string; label: string }> = {
  monitored: { color: '#52c41a', label: 'Monitored' },
  paused: { color: '#faad14', label: 'Paused' },
  archived: { color: '#8c8c8c', label: 'Archived' },
};

const DRAFT_STATUS_LABELS: Record<string, string> = {
  in_progress: 'In Progress',
  sent: 'Sent',
  discarded: 'Discarded',
};

const DRAFT_STATUS_COLORS: Record<string, string> = {
  in_progress: 'blue',
  sent: 'green',
  discarded: 'default',
};

// ─── Helpers ────────────────────────────────────────────────────────────────

function initials(name: string | null | undefined): string {
  if (!name) return '?';
  return name.split(/[\s.]+/).slice(0, 2).map(w => w[0]?.toUpperCase() || '').join('');
}

function formatNumber(num: number | null | undefined): string {
  if (num == null) return '--';
  if (num >= 1_000_000) return `${(num / 1_000_000).toFixed(1)}M`;
  if (num >= 1_000) return `${(num / 1_000).toFixed(0)}K`;
  return num.toString();
}

function timeAgo(dateStr: string | null | undefined): string {
  if (!dateStr) return 'Unknown';
  const now = new Date();
  const date = new Date(dateStr);
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHrs = Math.floor(diffMins / 60);
  if (diffHrs < 24) return `${diffHrs}h ago`;
  const diffDays = Math.floor(diffHrs / 24);
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

// ─── Interfaces ─────────────────────────────────────────────────────────────

interface ContactRecord {
  full_name: string | null;
  first_name?: string | null;
  last_name?: string | null;
  designation: string | null;
  email: string | null;
  phone: string | null;
  linkedin_url: string | null;
  city: string | null;
  source: string | null;
  confidence: number | null;
}

// ─── Component ──────────────────────────────────────────────────────────────

const AccountProfilePage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { openDraftDrawer } = useDraftDrawer();

  // ── State ───────────────────────────────────────────────────────────────
  const [account, setAccount] = useState<AccountProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');

  // Signals tab
  const [signals, setSignals] = useState<SignalEvent[]>([]);
  const [signalsLoading, setSignalsLoading] = useState(false);
  const [signalsFetched, setSignalsFetched] = useState(false);

  // Drafts tab
  const [drafts, setDrafts] = useState<OutreachDraft[]>([]);
  const [draftsLoading, setDraftsLoading] = useState(false);
  const [draftsFetched, setDraftsFetched] = useState(false);

  // Brief tab
  const [brief, setBrief] = useState<BriefRevision | null>(null);
  const [briefLoading, setBriefLoading] = useState(false);
  const [briefFetched, setBriefFetched] = useState(false);
  const [generatingBrief, setGeneratingBrief] = useState(false);

  // ── Data Fetching ───────────────────────────────────────────────────────

  const fetchAccount = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
      const res = await client.get<AccountProfile>(`/accounts/${id}`);
      setAccount(res.data);
    } catch (err) {
      message.error('Failed to load account details');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [id]);

  const fetchSignals = useCallback(async () => {
    if (!id || signalsFetched) return;
    setSignalsLoading(true);
    try {
      const res = await client.get<{ company_kb_id: string; count: number; signals: SignalEvent[] }>(
        `/signals/company/${id}`,
        { params: { limit: 100 } },
      );
      setSignals(res.data.signals || []);
      setSignalsFetched(true);
    } catch {
      setSignals([]);
    } finally {
      setSignalsLoading(false);
    }
  }, [id, signalsFetched]);

  const fetchDrafts = useCallback(async () => {
    if (!id || draftsFetched) return;
    setDraftsLoading(true);
    try {
      const res = await client.get<{ company_kb_id: string; drafts: OutreachDraft[] }>(
        `/briefs/drafts/${id}`,
      );
      setDrafts(res.data.drafts || []);
      setDraftsFetched(true);
    } catch {
      setDrafts([]);
    } finally {
      setDraftsLoading(false);
    }
  }, [id, draftsFetched]);

  const fetchBrief = useCallback(async () => {
    if (!id || briefFetched) return;
    setBriefLoading(true);
    try {
      const res = await client.get<{ company_kb_id: string; brief: BriefRevision | null }>(
        `/briefs/${id}`,
      );
      setBrief(res.data.brief || null);
      setBriefFetched(true);
    } catch {
      setBrief(null);
    } finally {
      setBriefLoading(false);
    }
  }, [id, briefFetched]);

  const handleGenerateBrief = async () => {
    if (!id) return;
    setGeneratingBrief(true);
    try {
      const res = await client.post<{ company_kb_id: string; brief: BriefRevision | null }>(
        `/briefs/${id}/generate`,
        {},
      );
      setBrief(res.data.brief || null);
      message.success('Research brief generated');
    } catch {
      message.error('Failed to generate brief');
    } finally {
      setGeneratingBrief(false);
    }
  };

  const handleMarkActedOn = async (signalId: string) => {
    try {
      await client.post(`/signals/${signalId}/acted-on`);
      message.success('Signal marked as acted on');
      // Refresh signals
      setSignalsFetched(false);
    } catch {
      message.error('Failed to update signal');
    }
  };

  // ── Effects ─────────────────────────────────────────────────────────────

  useEffect(() => {
    fetchAccount();
  }, [fetchAccount]);

  // Lazy-load tab data
  useEffect(() => {
    if (activeTab === 'signals') fetchSignals();
    if (activeTab === 'drafts') fetchDrafts();
    if (activeTab === 'brief') fetchBrief();
  }, [activeTab, fetchSignals, fetchDrafts, fetchBrief]);

  // Also pre-fetch signals for the overview tab's preview
  useEffect(() => {
    if (account && !signalsFetched) {
      fetchSignals();
    }
  }, [account, signalsFetched, fetchSignals]);

  // ── Loading State ───────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex justify-center items-center py-32">
        <Spin size="large" />
      </div>
    );
  }

  if (!account) {
    return (
      <div className="px-10 py-8 max-w-[1200px] mx-auto">
        <Button
          type="text"
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate('/accounts')}
          className="mb-4 text-gray-500 hover:text-gray-700"
        >
          Accounts
        </Button>
        <Empty description="Account not found" />
      </div>
    );
  }

  // ── Derived Values ────────────────────────────────────────────────────

  const contacts: ContactRecord[] = (account.best_known_contacts || []).map((c: Record<string, unknown>) => ({
    full_name: (c.full_name as string) || null,
    first_name: (c.first_name as string) || null,
    last_name: (c.last_name as string) || null,
    designation: (c.designation as string) || null,
    email: (c.email as string) || null,
    phone: (c.phone as string) || null,
    linkedin_url: (c.linkedin_url as string) || null,
    city: (c.city as string) || null,
    source: (c.source as string) || null,
    confidence: (c.confidence as number) || null,
  }));

  const statusCfg = STATUS_CONFIG[account.status] || STATUS_CONFIG.monitored;
  const fitCfg = ICP_FIT_CONFIG[account.icp_fit] || ICP_FIT_CONFIG.moderate;

  // ── Render: Header Card ───────────────────────────────────────────────

  const renderHeader = () => (
    <div className="bg-white border border-gray-200 rounded-lg p-6 mb-4">
      <div className="flex items-start gap-5">
        {/* Avatar */}
        <Avatar
          size={64}
          className="shrink-0 bg-brand-pale text-brand text-xl font-bold"
          style={{ backgroundColor: '#f0e6ff', color: '#5C2D8F' }}
        >
          {initials(account.name)}
        </Avatar>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-1">
            <h1 className="text-2xl font-bold text-gray-900 truncate">{account.name}</h1>
            <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold ${fitCfg.bg} ${fitCfg.text}`}>
              {fitCfg.label}
            </span>
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: statusCfg.color }} />
              {statusCfg.label}
            </span>
          </div>

          <div className="flex items-center gap-4 text-sm text-gray-500 mb-3">
            {account.domain && (
              <a
                href={`https://${account.domain}`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-brand hover:text-brand/80 transition-colors"
              >
                <GlobalOutlined className="text-xs" />
                {account.domain}
              </a>
            )}
            {account.industry && (
              <span className="flex items-center gap-1">
                <span className="text-gray-300">|</span>
                {account.industry}
              </span>
            )}
            {account.employee_count && (
              <span className="flex items-center gap-1">
                <TeamOutlined className="text-xs" />
                {formatNumber(account.employee_count)} employees
              </span>
            )}
            {account.country && (
              <span className="flex items-center gap-1">
                <span className="text-gray-300">|</span>
                {[account.city, account.region, account.country].filter(Boolean).join(', ')}
              </span>
            )}
          </div>

          {/* Tags */}
          {account.tags && account.tags.length > 0 && (
            <div className="flex items-center gap-1.5 flex-wrap">
              {account.tags.map((tag) => (
                <Tag key={tag} className="m-0 text-xs" style={{ borderRadius: 12 }}>
                  {tag}
                </Tag>
              ))}
            </div>
          )}
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2 shrink-0">
          <Button
            icon={<MailOutlined />}
            onClick={() =>
              openDraftDrawer({
                companyKbId: id!,
                companyName: account.name,
                domain: account.domain,
              })
            }
          >
            Draft Email
          </Button>
          <Button
            icon={<FileTextOutlined />}
            onClick={() => navigate(`/accounts/${id}/brief`)}
          >
            Generate Brief
          </Button>
          <Button
            icon={<ExperimentOutlined />}
            onClick={async () => {
              try {
                await client.post(`/briefs/research/${id}`);
                message.success('Research started');
                fetchAccount();
              } catch {
                message.error('Research failed');
              }
            }}
          >
            Research
          </Button>
        </div>
      </div>
    </div>
  );

  // ── Render: Overview Tab ──────────────────────────────────────────────

  const renderOverview = () => {
    const briefStatus = account.has_brief ? 'Ready' : 'None';
    const briefStatusColor = account.has_brief ? '#1E9B6B' : '#8c8c8c';

    return (
      <div>
        {/* KPI Cards */}
        <KpiStrip
          items={[
            { label: 'Signals', value: account.signal_count, color: '#fa541c' },
            { label: 'Open Drafts', value: account.open_draft_count, color: '#5C2D8F' },
            { label: 'Brief Status', value: briefStatus, color: briefStatusColor },
            { label: 'Contacts', value: contacts.length },
          ]}
          className="mb-6"
        />

        {/* Recent Signals Preview */}
        <div className="bg-white border border-gray-200 rounded-lg p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
              <ThunderboltOutlined className="text-orange-500" />
              Recent Signals
            </h3>
            {signals.length > 3 && (
              <button
                onClick={() => setActiveTab('signals')}
                className="text-xs text-brand hover:text-brand/80 font-medium transition-colors"
              >
                View all {signals.length} signals
              </button>
            )}
          </div>

          {signalsLoading ? (
            <div className="flex justify-center py-6"><Spin /></div>
          ) : signals.length === 0 ? (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description="No signals detected yet"
              className="py-4"
            />
          ) : (
            <div className="space-y-3">
              {signals.slice(0, 3).map((signal) => (
                <div
                  key={signal.id}
                  className="flex items-start gap-3 p-3 rounded-lg border border-gray-100 hover:border-gray-200 transition-colors cursor-pointer"
                  onClick={() => setActiveTab('signals')}
                >
                  <span className={`w-2.5 h-2.5 rounded-full mt-1.5 shrink-0 ${PRIORITY_DOT_CLS[signal.priority] || 'bg-gray-300'}`} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">{signal.title}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <Badge variant="signal-type" signalType={signal.signal_type}>
                        {SIGNAL_TYPE_LABEL_MAP[signal.signal_type] || signal.signal_type}
                      </Badge>
                      <span className="text-xs text-gray-400">
                        {timeAgo(signal.evidence_date || signal.detected_at)}
                      </span>
                    </div>
                  </div>
                  <Badge variant="priority" priority={signal.priority}>
                    {signal.priority}
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  };

  // ── Render: Signals Tab ───────────────────────────────────────────────

  const renderSignals = () => {
    if (signalsLoading) {
      return <div className="flex justify-center py-16"><Spin size="large" /></div>;
    }

    if (signals.length === 0) {
      return (
        <div className="bg-white border border-gray-200 rounded-lg py-16">
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="No signals detected for this account"
          >
            <Button
              type="primary"
              icon={<ThunderboltOutlined />}
              onClick={async () => {
                try {
                  await client.post(`/signals/detect/${id}/start`);
                  message.success('Signal detection started');
                  setSignalsFetched(false);
                } catch {
                  message.error('Failed to start detection');
                }
              }}
            >
              Detect Signals
            </Button>
          </Empty>
        </div>
      );
    }

    return (
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-sm font-semibold text-gray-900">
            {signals.length} signal{signals.length !== 1 ? 's' : ''} detected
          </h3>
          <Button
            size="small"
            icon={<ThunderboltOutlined />}
            onClick={async () => {
              try {
                await client.post(`/signals/detect/${id}/start`);
                message.success('Signal detection started');
                setSignalsFetched(false);
              } catch {
                message.error('Failed to start detection');
              }
            }}
          >
            Re-detect
          </Button>
        </div>

        <Timeline
          items={signals.map((signal) => ({
            key: signal.id,
            dot: (
              <span
                className={`inline-block w-3 h-3 rounded-full ${PRIORITY_DOT_CLS[signal.priority] || 'bg-gray-300'}`}
              />
            ),
            children: (
              <div className="pb-2">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-gray-900 mb-1">{signal.title}</p>
                    {signal.summary && (
                      <p className="text-xs text-gray-500 mb-2 line-clamp-2">{signal.summary}</p>
                    )}
                    <div className="flex items-center gap-2 flex-wrap">
                      <Badge variant="signal-type" signalType={signal.signal_type}>
                        {SIGNAL_TYPE_LABEL_MAP[signal.signal_type] || signal.signal_type}
                      </Badge>
                      <Badge variant="priority" priority={signal.priority}>
                        {signal.priority}
                      </Badge>
                      {signal.strength > 0 && (
                        <span className="text-xs text-gray-400">
                          Strength: {Math.round(signal.strength * 100)}%
                        </span>
                      )}
                      <span className="text-xs text-gray-400 flex items-center gap-1">
                        <ClockCircleOutlined className="text-[10px]" />
                        {timeAgo(signal.evidence_date || signal.detected_at)}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    {signal.source_url && (
                      <Tooltip title="View source">
                        <Button
                          type="text"
                          size="small"
                          icon={<LinkOutlined />}
                          onClick={(e) => {
                            e.stopPropagation();
                            window.open(signal.source_url!, '_blank');
                          }}
                        />
                      </Tooltip>
                    )}
                    <Tooltip title="Draft outreach from signal">
                      <Button
                        type="text"
                        size="small"
                        icon={<MailOutlined />}
                        onClick={(e) => {
                          e.stopPropagation();
                          openDraftDrawer({
                            companyKbId: id!,
                            companyName: account.name,
                            domain: account.domain,
                            signalId: signal.id,
                            signalTitle: signal.title,
                            signalType: signal.signal_type,
                          });
                        }}
                      />
                    </Tooltip>
                    <Tooltip title="Mark as acted on">
                      <Button
                        type="text"
                        size="small"
                        icon={<CheckCircleOutlined />}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleMarkActedOn(signal.id);
                        }}
                      />
                    </Tooltip>
                  </div>
                </div>
              </div>
            ),
          }))}
        />
      </div>
    );
  };

  // ── Render: Research Brief Tab ────────────────────────────────────────

  const renderBrief = () => {
    if (briefLoading) {
      return <div className="flex justify-center py-16"><Spin size="large" /></div>;
    }

    if (!brief) {
      return (
        <div className="bg-white border border-gray-200 rounded-lg py-16">
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="No research brief generated yet"
          >
            <Space>
              <Button
                type="primary"
                icon={<FileTextOutlined />}
                loading={generatingBrief}
                onClick={handleGenerateBrief}
              >
                Generate Brief
              </Button>
              <Button
                icon={<FileTextOutlined />}
                onClick={() => navigate(`/accounts/${id}/brief`)}
              >
                Open Brief Page
              </Button>
            </Space>
          </Empty>
        </div>
      );
    }

    return (
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <div className="flex items-center justify-between mb-5">
          <div>
            <h3 className="text-sm font-semibold text-gray-900 mb-1">
              Research Brief v{brief.version}
            </h3>
            <p className="text-xs text-gray-400">
              {brief.word_count ? `${brief.word_count} words` : ''}
              {brief.created_at ? ` \u00b7 Generated ${timeAgo(brief.created_at)}` : ''}
              {brief.generated_by ? ` \u00b7 by ${brief.generated_by}` : ''}
            </p>
          </div>
          <Space>
            <Button
              size="small"
              icon={<FileTextOutlined />}
              onClick={() => navigate(`/accounts/${id}/brief`)}
            >
              Full Brief
            </Button>
            <Button
              size="small"
              loading={generatingBrief}
              onClick={handleGenerateBrief}
            >
              Regenerate
            </Button>
          </Space>
        </div>

        {brief.trigger_signal_headline && (
          <div className="bg-orange-50 border border-orange-100 rounded-lg px-4 py-2.5 mb-4 text-xs text-orange-700">
            <ThunderboltOutlined className="mr-1.5" />
            Triggered by: {brief.trigger_signal_headline}
          </div>
        )}

        {/* Section summaries */}
        <div className="space-y-3">
          {brief.sections.map((section) => (
            <div
              key={section.id}
              className="border border-gray-100 rounded-lg p-4 hover:border-gray-200 transition-colors"
            >
              <div className="flex items-center gap-2 mb-2">
                <span className="text-sm">{getSectionIcon(section.id)}</span>
                <h4 className="text-sm font-semibold text-gray-900">{section.heading}</h4>
                {section.confidence != null && (
                  <Badge
                    variant="confidence"
                    confidence={section.confidence >= 0.7 ? 'high' : section.confidence >= 0.4 ? 'medium' : 'low'}
                  />
                )}
                {section.insufficient && (
                  <Tag color="warning" className="m-0 text-xs">Insufficient data</Tag>
                )}
              </div>
              <p className="text-xs text-gray-600 line-clamp-3">
                {section.body}
              </p>
              {section.bullets && section.bullets.length > 0 && (
                <ul className="mt-2 space-y-0.5">
                  {section.bullets.slice(0, 3).map((b, i) => (
                    <li key={i} className="text-xs text-gray-500 flex items-start gap-1.5">
                      <span className="text-gray-300 mt-0.5">&#x2022;</span>
                      <span className="line-clamp-1">{b}</span>
                    </li>
                  ))}
                  {section.bullets.length > 3 && (
                    <li className="text-xs text-gray-400 ml-3">
                      +{section.bullets.length - 3} more
                    </li>
                  )}
                </ul>
              )}
            </div>
          ))}
        </div>
      </div>
    );
  };

  // ── Render: Drafts Tab ────────────────────────────────────────────────

  const renderDrafts = () => {
    if (draftsLoading) {
      return <div className="flex justify-center py-16"><Spin size="large" /></div>;
    }

    if (drafts.length === 0) {
      return (
        <div className="bg-white border border-gray-200 rounded-lg py-16">
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="No outreach drafts yet"
          >
            <Button
              type="primary"
              icon={<MailOutlined />}
              onClick={() =>
                openDraftDrawer({
                  companyKbId: id!,
                  companyName: account.name,
                  domain: account.domain,
                })
              }
            >
              Create Draft
            </Button>
          </Empty>
        </div>
      );
    }

    const columns = [
      {
        title: 'Subject / Recipient',
        key: 'subject',
        render: (_: unknown, record: OutreachDraft) => (
          <div>
            <p className="text-sm font-medium text-gray-900 truncate">
              {record.subject || 'No subject'}
            </p>
            {record.contact_name && (
              <p className="text-xs text-gray-400 mt-0.5">
                To: {record.contact_name}
                {record.contact_title ? ` (${record.contact_title})` : ''}
              </p>
            )}
          </div>
        ),
      },
      {
        title: 'Format',
        dataIndex: 'format',
        key: 'format',
        width: 100,
        render: (format: string) => (
          <Tag className="m-0 capitalize">{format}</Tag>
        ),
      },
      {
        title: 'Tone',
        dataIndex: 'tone',
        key: 'tone',
        width: 110,
        render: (tone: string) => (
          <span className="text-xs text-gray-600 capitalize">{tone}</span>
        ),
      },
      {
        title: 'Status',
        dataIndex: 'status',
        key: 'status',
        width: 120,
        render: (status: string) => (
          <Tag color={DRAFT_STATUS_COLORS[status] || 'default'} className="m-0">
            {DRAFT_STATUS_LABELS[status] || status}
          </Tag>
        ),
      },
      {
        title: 'Created',
        dataIndex: 'created_at',
        key: 'created_at',
        width: 120,
        render: (dt: string | null) => (
          <span className="text-xs text-gray-400">{timeAgo(dt)}</span>
        ),
      },
      {
        title: '',
        key: 'actions',
        width: 80,
        render: (_: unknown, record: OutreachDraft) => (
          <Space size="small">
            <Tooltip title="Edit draft">
              <Button
                type="text"
                size="small"
                icon={<EditOutlined />}
                onClick={() =>
                  openDraftDrawer({
                    companyKbId: id!,
                    companyName: account.name,
                    domain: account.domain,
                    signalId: record.signal_id || undefined,
                    contactName: record.contact_name || undefined,
                    contactTitle: record.contact_title || undefined,
                    format: record.format,
                    tone: record.tone,
                  })
                }
              />
            </Tooltip>
          </Space>
        ),
      },
    ];

    return (
      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100">
          <span className="text-sm font-semibold text-gray-900">
            {drafts.length} draft{drafts.length !== 1 ? 's' : ''}
          </span>
          <Button
            size="small"
            type="primary"
            icon={<MailOutlined />}
            onClick={() =>
              openDraftDrawer({
                companyKbId: id!,
                companyName: account.name,
                domain: account.domain,
              })
            }
          >
            New Draft
          </Button>
        </div>
        <Table
          dataSource={drafts}
          columns={columns}
          rowKey="id"
          pagination={false}
          size="small"
          className="[&_.ant-table-thead_th]:bg-gray-50 [&_.ant-table-thead_th]:text-xs [&_.ant-table-thead_th]:font-semibold [&_.ant-table-thead_th]:text-gray-400 [&_.ant-table-thead_th]:uppercase"
        />
      </div>
    );
  };

  // ── Render: Contacts Tab ──────────────────────────────────────────────

  const renderContacts = () => {
    if (contacts.length === 0) {
      return (
        <div className="bg-white border border-gray-200 rounded-lg py-16">
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="No contacts found for this account"
          >
            <Button
              icon={<ExperimentOutlined />}
              onClick={async () => {
                try {
                  await client.post(`/briefs/research/${id}`);
                  message.success('Research started - contacts will be enriched');
                  fetchAccount();
                } catch {
                  message.error('Research failed');
                }
              }}
            >
              Research Contacts
            </Button>
          </Empty>
        </div>
      );
    }

    const columns = [
      {
        title: 'Name',
        key: 'name',
        render: (_: unknown, record: ContactRecord) => (
          <div className="flex items-center gap-2.5">
            <Avatar size={28} icon={<UserOutlined />} className="shrink-0 bg-gray-200" />
            <div>
              <p className="text-sm font-medium text-gray-900">
                {record.full_name || [record.first_name, record.last_name].filter(Boolean).join(' ') || 'Unknown'}
              </p>
            </div>
          </div>
        ),
      },
      {
        title: 'Title',
        dataIndex: 'designation',
        key: 'designation',
        render: (val: string | null) => (
          <span className="text-xs text-gray-600">{val || '--'}</span>
        ),
      },
      {
        title: 'Email',
        dataIndex: 'email',
        key: 'email',
        render: (email: string | null) =>
          email ? (
            <a href={`mailto:${email}`} className="text-xs text-brand hover:underline">
              {email}
            </a>
          ) : (
            <span className="text-xs text-gray-300">--</span>
          ),
      },
      {
        title: 'LinkedIn',
        dataIndex: 'linkedin_url',
        key: 'linkedin',
        width: 80,
        render: (url: string | null) =>
          url ? (
            <a href={url} target="_blank" rel="noopener noreferrer" className="text-brand hover:text-brand/80">
              <LinkOutlined />
            </a>
          ) : (
            <span className="text-xs text-gray-300">--</span>
          ),
      },
      {
        title: 'Confidence',
        dataIndex: 'confidence',
        key: 'confidence',
        width: 100,
        render: (val: number | null) => {
          if (val == null) return <span className="text-xs text-gray-300">--</span>;
          const tier = val >= 0.7 ? 'high' : val >= 0.4 ? 'medium' : 'low';
          return <Badge variant="confidence" confidence={tier} />;
        },
      },
      {
        title: '',
        key: 'actions',
        width: 50,
        render: (_: unknown, record: ContactRecord) => (
          <Tooltip title="Draft outreach">
            <Button
              type="text"
              size="small"
              icon={<MailOutlined />}
              onClick={() =>
                openDraftDrawer({
                  companyKbId: id!,
                  companyName: account.name,
                  domain: account.domain,
                  contactName: record.full_name || undefined,
                  contactTitle: record.designation || undefined,
                })
              }
            />
          </Tooltip>
        ),
      },
    ];

    return (
      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100">
          <span className="text-sm font-semibold text-gray-900">
            {contacts.length} contact{contacts.length !== 1 ? 's' : ''}
          </span>
        </div>
        <Table
          dataSource={contacts}
          columns={columns}
          rowKey={(record) => record.email || record.full_name || Math.random().toString()}
          pagination={false}
          size="small"
          className="[&_.ant-table-thead_th]:bg-gray-50 [&_.ant-table-thead_th]:text-xs [&_.ant-table-thead_th]:font-semibold [&_.ant-table-thead_th]:text-gray-400 [&_.ant-table-thead_th]:uppercase"
        />
      </div>
    );
  };

  // ── Render: Tabs ──────────────────────────────────────────────────────

  const tabItems = [
    {
      key: 'overview',
      label: (
        <span className="flex items-center gap-1.5">
          <ThunderboltOutlined />
          Overview
        </span>
      ),
      children: renderOverview(),
    },
    {
      key: 'signals',
      label: (
        <span className="flex items-center gap-1.5">
          <ThunderboltOutlined />
          Signals
          {account.signal_count > 0 && (
            <span className="inline-flex items-center justify-center min-w-[18px] h-[18px] rounded-full bg-orange-100 text-orange-600 text-[10px] font-bold px-1">
              {account.signal_count}
            </span>
          )}
        </span>
      ),
      children: renderSignals(),
    },
    {
      key: 'brief',
      label: (
        <span className="flex items-center gap-1.5">
          <FileTextOutlined />
          Research Brief
          {account.has_brief && (
            <CheckCircleOutlined className="text-green-500 text-xs" />
          )}
        </span>
      ),
      children: renderBrief(),
    },
    {
      key: 'drafts',
      label: (
        <span className="flex items-center gap-1.5">
          <MailOutlined />
          Drafts
          {account.open_draft_count > 0 && (
            <span className="inline-flex items-center justify-center min-w-[18px] h-[18px] rounded-full bg-brand/10 text-brand text-[10px] font-bold px-1">
              {account.open_draft_count}
            </span>
          )}
        </span>
      ),
      children: renderDrafts(),
    },
    {
      key: 'contacts',
      label: (
        <span className="flex items-center gap-1.5">
          <UserOutlined />
          Contacts
          {contacts.length > 0 && (
            <span className="text-xs text-gray-400">({contacts.length})</span>
          )}
        </span>
      ),
      children: renderContacts(),
    },
  ];

  // ── Main Render ───────────────────────────────────────────────────────

  return (
    <div className="px-10 py-8 max-w-[1200px] mx-auto">
      {/* Back Button */}
      <Button
        type="text"
        icon={<ArrowLeftOutlined />}
        onClick={() => navigate('/accounts')}
        className="mb-4 text-gray-500 hover:text-gray-700 -ml-2"
      >
        Accounts
      </Button>

      {/* Header Card */}
      {renderHeader()}

      {/* Tabs */}
      <Card
        className="[&_.ant-card-body]:p-0"
        styles={{ body: { padding: 0 } }}
      >
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={tabItems}
          className="[&_.ant-tabs-nav]:px-5 [&_.ant-tabs-nav]:mb-0 [&_.ant-tabs-content-holder]:p-5"
        />
      </Card>
    </div>
  );
};

// ─── Section Icon Helper ─────────────────────────────────────────────────

const SECTION_ICON_MAP: Record<string, string> = {
  'overview': '\uD83C\uDFE2',
  'org': '\uD83D\uDC65',
  'signals': '\u26A1',
  'competitive': '\uD83C\uDFAF',
  'tech': '\u2699\uFE0F',
  'budget': '\uD83D\uDCB0',
  'why-now': '\u23F1\uFE0F',
  'angle': '\uD83D\uDCAC',
};

function getSectionIcon(sectionId: string): string {
  return SECTION_ICON_MAP[sectionId] || '\uD83D\uDCC4';
}

export default AccountProfilePage;
