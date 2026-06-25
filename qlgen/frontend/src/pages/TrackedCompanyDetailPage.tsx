import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { Button, Select, Spin, message, Tooltip, Input } from 'antd';
import {
  ArrowLeftOutlined, ReloadOutlined, GlobalOutlined, LinkedinOutlined,
  SearchOutlined, FileTextOutlined,
} from '@ant-design/icons';
import { PillTabs, Badge, KpiStrip, SectionLabel, SourceBadge } from '../components/ui';
import {
  getListMembers, updateMember,
} from '../api/trackingApi';
import {
  researchCompany, getLatestBrief, generateStructuredBrief,
  getCompanyDrafts, generateDraft, updateDraft,
  getBriefExportUrl, getSignalReportExportUrl,
  startBriefGeneration, getBriefGenerationStreamUrl,
  startCompanyResearch, getResearchStreamUrl,
} from '../api/briefApi';
import { API_BASE } from '../api/client';
import SignalTimeline from '../components/SignalTimeline';
import CompanyBriefModal from '../components/CompanyBriefModal';
import OutreachDraftModal from '../components/OutreachDraftModal';
import ContactsPanel from '../components/ContactsPanel';
import { useDraftDrawer } from '../context/DraftDrawerContext';
import ActivityFeed from '../components/ActivityFeed';
import { useSSEStream } from '../hooks/useSSEStream';
import {
  TrackingListMember,
  OUTREACH_STATUSES, OUTREACH_STATUS_LABELS, OUTREACH_STATUS_COLORS,
  SIGNAL_PRIORITY_COLORS, SIGNAL_TYPE_LABELS,
  BriefRevision, BriefSection, OutreachDraft, BRIEF_SECTION_ICONS,
} from '../types';
import { getSignalFreshness, FRESHNESS_DESCRIPTIONS } from '../utils/signalFreshness';

type TabKey = 'overview' | 'signals' | 'brief' | 'drafts' | 'contacts' | 'notes';

const getHeatColor = (score: number) => {
  if (score >= 75) return '#f5222d';
  if (score >= 50) return '#fa541c';
  if (score >= 25) return '#faad14';
  return '#8c8c8c';
};

const TrackedCompanyDetailPage: React.FC = () => {
  const { listId, membershipId } = useParams<{ listId: string; membershipId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const { openDraftDrawer } = useDraftDrawer();

  const [member, setMember] = useState<TrackingListMember | null>(
    (location.state as { member?: TrackingListMember })?.member || null,
  );
  const [loading, setLoading] = useState(!member);
  const [activeTab, setActiveTab] = useState<TabKey>('overview');
  const [notes, setNotes] = useState('');
  const [savingNotes, setSavingNotes] = useState(false);
  const [researching, setResearching] = useState(false);
  const [researchThought, setResearchThought] = useState('');
  const [brief, setBrief] = useState<BriefRevision | null>(null);
  const [briefLoading, setBriefLoading] = useState(false);
  const [briefGenerating, setBriefGenerating] = useState(false);
  const [briefThought, setBriefThought] = useState('');
  const [drafts, setDrafts] = useState<OutreachDraft[]>([]);
  const [draftsLoading, setDraftsLoading] = useState(false);

  // SSE stream for company research
  const researchStream = useSSEStream({
    terminalEvents: ['research_complete', 'research_failed'],
    onEvent: (eventType, data) => {
      if (eventType === 'agent_thought') setResearchThought(data.message as string || '');
    },
    onComplete: async (eventType, data) => {
      if (eventType === 'research_complete') {
        const fields = (data.fields_updated as string[]) || [];
        if (fields.length > 0) {
          await fetchMember();
          message.success(`Updated ${fields.length} field${fields.length > 1 ? 's' : ''}: ${fields.join(', ')}`);
        } else {
          message.info('No new information found for this company');
        }
      } else {
        message.error((data.message as string) || 'Company research failed');
      }
      setResearching(false);
      setResearchThought('');
    },
    onError: () => { setResearching(false); setResearchThought(''); },
  });

  // SSE stream for brief generation
  const briefGenStream = useSSEStream({
    terminalEvents: ['brief_ready', 'brief_failed'],
    onEvent: (eventType, data) => {
      if (eventType === 'agent_thought') setBriefThought(data.message as string || '');
    },
    onComplete: async (eventType) => {
      if (eventType === 'brief_ready' && member) {
        const res = await getLatestBrief(member.company_kb_id);
        setBrief(res.data.brief || null);
        message.success('Brief generated');
      } else {
        message.error('Failed to generate brief');
      }
      setBriefGenerating(false);
      setBriefThought('');
    },
    onError: () => { setBriefGenerating(false); setBriefThought(''); },
  });

  const handleResearch = async () => {
    if (!member) return;
    setResearching(true);
    setResearchThought('');
    try {
      const res = await startCompanyResearch(member.company_kb_id);
      const streamUrl = getResearchStreamUrl(member.company_kb_id, res.data.run_id);
      researchStream.connect(streamUrl);
    } catch {
      message.error('Failed to start company research');
      setResearching(false);
    }
  };

  // Check if the company is missing key details
  const isMissingDetails = member && (
    !member.domain || !member.industry || !member.country || !member.employee_count
  );

  const fetchMember = useCallback(async () => {
    if (!listId || !membershipId) return;
    setLoading(true);
    try {
      const res = await getListMembers(listId, { limit: 200, offset: 0 });
      const found = (res.data.members || []).find(
        (m) => m.membership_id === membershipId,
      );
      if (found) {
        setMember(found);
        setNotes(found.notes || '');
      } else {
        message.error('Company not found in this list');
        navigate(`/tracking/${listId}`);
      }
    } catch {
      message.error('Failed to load company details');
    } finally {
      setLoading(false);
    }
  }, [listId, membershipId, navigate]);

  useEffect(() => {
    if (!member) fetchMember();
    else setNotes(member.notes || '');
  }, [member, fetchMember]);

  // Fetch brief when tab switches
  useEffect(() => {
    if (activeTab !== 'brief' || !member) return;
    setBriefLoading(true);
    getLatestBrief(member.company_kb_id)
      .then(res => setBrief(res.data.brief || null))
      .catch(() => {})
      .finally(() => setBriefLoading(false));
  }, [activeTab, member]);

  // Fetch drafts when tab switches
  useEffect(() => {
    if (activeTab !== 'drafts' || !member) return;
    setDraftsLoading(true);
    getCompanyDrafts(member.company_kb_id)
      .then(res => setDrafts(res.data.drafts || []))
      .catch(() => {})
      .finally(() => setDraftsLoading(false));
  }, [activeTab, member]);

  const handleGenerateBrief = async () => {
    if (!member || briefGenerating) return;
    setBriefGenerating(true);
    setBriefThought('');
    try {
      const res = await startBriefGeneration(member.company_kb_id);
      const streamUrl = getBriefGenerationStreamUrl(member.company_kb_id, res.data.run_id);
      briefGenStream.connect(streamUrl);
    } catch {
      message.error('Failed to start brief generation');
      setBriefGenerating(false);
    }
  };

  const handleDraftStatusChange = async (draftId: string, newStatus: string) => {
    try {
      await updateDraft(draftId, { status: newStatus });
      setDrafts(prev => prev.map(d => d.id === draftId ? { ...d, status: newStatus as OutreachDraft['status'] } : d));
    } catch {
      message.error('Failed to update draft');
    }
  };

  const handleStatusChange = async (newStatus: string) => {
    if (!listId || !membershipId || !member) return;
    try {
      await updateMember(listId, membershipId, { outreach_status: newStatus });
      setMember({ ...member, outreach_status: newStatus });
    } catch {
      message.error('Failed to update status');
    }
  };

  const handleSaveNotes = async () => {
    if (!listId || !membershipId) return;
    setSavingNotes(true);
    try {
      await updateMember(listId, membershipId, { notes });
      message.success('Notes saved');
    } catch {
      message.error('Failed to save notes');
    } finally {
      setSavingNotes(false);
    }
  };

  if (loading || !member) {
    return <div className="flex justify-center py-32"><Spin size="large" /></div>;
  }

  const heatScore = member.signal_heat_score || 0;

  const formatRevenue = (v: number | null) => {
    if (!v) return '-';
    if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
    if (v >= 1e6) return `$${(v / 1e6).toFixed(0)}M`;
    return `$${v.toLocaleString()}`;
  };

  return (
    <div className="px-10 py-6 max-w-[1200px] mx-auto">
      {/* Header card */}
      <div className="bg-white border border-gray-200 rounded-lg px-6 py-5 mb-5">
        <div className="flex items-start gap-4">
          {/* Back */}
          <button
            onClick={() => navigate(`/tracking/${listId}`)}
            className="mt-1 w-8 h-8 flex items-center justify-center rounded-md text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors shrink-0"
          >
            <ArrowLeftOutlined />
          </button>

          {/* Company avatar */}
          <div className="w-12 h-12 rounded-xl bg-brand-pale flex items-center justify-center text-lg font-bold text-brand shrink-0">
            {(member.company_name || 'U')[0].toUpperCase()}
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="text-xl font-bold text-gray-900">
                {member.company_name || 'Unknown Company'}
              </h1>
              {/* Heat score circle */}
              <div
                className="w-12 h-12 rounded-full flex items-center justify-center text-sm font-bold ring-2 ring-offset-2"
                style={{
                  background: `${getHeatColor(heatScore)}15`,
                  color: getHeatColor(heatScore),
                  // @ts-expect-error CSS custom property for ring color
                  '--tw-ring-color': `${getHeatColor(heatScore)}40`,
                }}
              >
                {Math.round(heatScore)}
              </div>
            </div>

            <div className="flex items-center gap-3 mt-1.5 text-sm text-gray-500 flex-wrap">
              {member.domain && <span>{member.domain}</span>}
              {member.industry && (
                <Badge>{member.industry}</Badge>
              )}
              {member.country && (
                <Badge>{member.country}</Badge>
              )}
              {member.employee_count && (
                <span>{member.employee_count.toLocaleString()} employees</span>
              )}
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2 shrink-0">
            <Select
              value={member.outreach_status}
              onChange={handleStatusChange}
              style={{ width: 170 }}
              options={OUTREACH_STATUSES.map((s) => ({
                value: s,
                label: (
                  <span className="flex items-center gap-1.5">
                    <span
                      className="w-2 h-2 rounded-full inline-block"
                      style={{ background: OUTREACH_STATUS_COLORS[s] }}
                    />
                    {OUTREACH_STATUS_LABELS[s]}
                  </span>
                ),
              }))}
            />
            {member.domain && (
              <Tooltip title="Visit website">
                <a href={`https://${member.domain}`} target="_blank" rel="noopener noreferrer">
                  <Button icon={<GlobalOutlined />} className="!rounded-md" />
                </a>
              </Tooltip>
            )}
            {member.domain && (
              <Tooltip title="LinkedIn">
                <a
                  href={`https://linkedin.com/company/${member.domain.replace(/\.\w+$/, '')}`}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <Button icon={<LinkedinOutlined />} className="!rounded-md" />
                </a>
              </Tooltip>
            )}
            <Tooltip title="Full Research Brief">
              <Button
                icon={<SearchOutlined />}
                onClick={() => navigate(`/tracking/${listId}/company/${membershipId}/brief`)}
                className="!rounded-md"
              >
                Brief
              </Button>
            </Tooltip>
            <CompanyBriefModal
              companyKbId={member.company_kb_id}
              companyName={member.company_name || undefined}
            />
            <Tooltip title="Open Draft Drawer">
              <Button
                icon={<FileTextOutlined />}
                onClick={() => openDraftDrawer({
                  companyKbId: member.company_kb_id,
                  companyName: member.company_name || undefined,
                  domain: member.domain || undefined,
                  contactName: member.best_known_contacts?.[0]?.full_name || undefined,
                  contactTitle: member.best_known_contacts?.[0]?.designation || undefined,
                })}
                className="!rounded-md"
              >
                Draft
              </Button>
            </Tooltip>
            <OutreachDraftModal
              companyKbId={member.company_kb_id}
              companyName={member.company_name || undefined}
              contactName={member.best_known_contacts?.[0]?.full_name}
            />
            <Tooltip title="Refresh">
              <Button
                icon={<ReloadOutlined />}
                onClick={fetchMember}
                className="!rounded-md"
              />
            </Tooltip>
          </div>
        </div>
      </div>

      {/* Tab Navigation */}
      <PillTabs
        variant="underline"
        tabs={[
          { key: 'overview', label: 'Overview' },
          { key: 'signals', label: 'Signals' },
          { key: 'brief', label: 'Research brief' },
          { key: 'drafts', label: 'Drafts' },
          { key: 'contacts', label: 'Contacts' },
          { key: 'notes', label: 'Notes & History' },
        ]}
        activeKey={activeTab}
        onChange={(v) => setActiveTab(v as TabKey)}
        className="mb-5"
      />

      {/* Overview Tab */}
      {activeTab === 'overview' && (
        <div className="space-y-5">
          {/* Research CTA when details are missing */}
          {isMissingDetails && (
            <div className="bg-white border border-amber-200 rounded-lg px-5 py-4 flex items-center justify-between">
              <div>
                <p className="text-sm font-semibold text-gray-800 flex items-center gap-1.5">
                  <SearchOutlined className="text-amber-500" />
                  Missing company details
                </p>
                <p className="text-xs text-gray-500 mt-0.5">
                  {[
                    !member.domain && 'domain',
                    !member.industry && 'industry',
                    !member.country && 'country',
                    !member.employee_count && 'employee count',
                    !member.revenue_estimate && 'revenue',
                  ].filter(Boolean).join(', ')} not available. Research can fill these in automatically.
                </p>
              </div>
              <Button
                type="primary"
                icon={<SearchOutlined />}
                onClick={handleResearch}
                loading={researching}
                className="!rounded-md"
              >
                {researching ? 'Researching...' : 'Research Company'}
              </Button>
              {researching && (
                <div className="w-full mt-2">
                  {researchThought && (
                    <p className="text-xs text-purple-500 italic animate-pulse mb-1">{researchThought}</p>
                  )}
                  {researchStream.progress > 0 && (
                    <div className="h-1 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-purple-500 rounded-full transition-all duration-500 ease-out"
                        style={{ width: `${researchStream.progress}%` }}
                      />
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* KPI Strip */}
          <KpiStrip items={[
            { label: 'Heat Score', value: Math.round(heatScore), color: getHeatColor(heatScore) },
            { label: 'Contacts', value: member.best_known_contacts?.length || 0, color: '#1890ff' },
            { label: 'Score', value: member.best_final_score != null ? Math.round(member.best_final_score) : '-', color: '#1E9B6B' },
            {
              label: 'Latest Signal',
              value: member.latest_signal
                ? (SIGNAL_TYPE_LABELS[member.latest_signal.signal_type] || member.latest_signal.signal_type)
                : 'None',
              color: '#5C2D8F',
            },
          ]} />

          <div className="grid grid-cols-2 gap-5">
            {/* Company Details */}
            <div className="bg-white border border-gray-200 rounded-lg p-5">
              <div className="flex items-center justify-between mb-4">
                <SectionLabel className="!mb-0">Company Details</SectionLabel>
                {!isMissingDetails && (
                  <Tooltip title="Research to update company info">
                    <Button
                      size="small"
                      icon={<SearchOutlined />}
                      onClick={handleResearch}
                      loading={researching}
                      className="!rounded-md !text-xs"
                    >
                      Research
                    </Button>
                  </Tooltip>
                )}
              </div>
              <div className="grid grid-cols-[100px_1fr] gap-x-4 gap-y-2.5 text-sm">
                {[
                  ['Domain', member.domain],
                  ['Industry', member.industry],
                  ['Country', member.country],
                  ['City', member.city],
                  ['Employees', member.employee_count?.toLocaleString()],
                  ['Revenue', formatRevenue(member.revenue_estimate)],
                  ['Score', member.best_final_score != null ? Math.round(member.best_final_score) : null],
                  ['Added', member.added_at ? new Date(member.added_at).toLocaleDateString() : null],
                  ['Source', member.added_from],
                ].map(([label, value]) => (
                  <React.Fragment key={label as string}>
                    <span className="text-xs text-gray-400">{label}</span>
                    <span className="text-gray-700">{value || '-'}</span>
                  </React.Fragment>
                ))}
              </div>
            </div>

            {/* Latest Signal */}
            <div className="bg-white border border-gray-200 rounded-lg p-5">
              <SectionLabel className="!mb-4">Latest Signal</SectionLabel>
              {member.latest_signal ? (() => {
                const sigFreshness = getSignalFreshness(member.latest_signal.evidence_date, member.latest_signal.detected_at);
                return (
                  <div
                    className="rounded-lg p-3"
                    style={{ borderLeft: `3px solid ${sigFreshness.color}`, background: '#fafafa' }}
                  >
                    <div className="flex items-center gap-1.5 mb-1.5">
                      <Badge variant="signal-type" signalType={member.latest_signal.signal_type} className="text-[10px]">
                        {member.latest_signal.signal_type.replace(/_/g, ' ')}
                      </Badge>
                      <Badge variant="priority" priority={member.latest_signal.priority} className="text-[10px]">
                        {member.latest_signal.priority}
                      </Badge>
                      <Tooltip title={FRESHNESS_DESCRIPTIONS[sigFreshness.tier]}>
                        <span
                          className="inline-flex items-center text-[10px] font-medium px-1.5 py-0.5 rounded-full"
                          style={{ color: sigFreshness.color, background: sigFreshness.bgColor }}
                        >
                          {sigFreshness.label}
                        </span>
                      </Tooltip>
                    </div>
                    <p className="text-sm font-medium text-gray-900 leading-snug mb-1.5">
                      {member.latest_signal.title}
                    </p>
                    <div className="flex items-center gap-2 flex-wrap">
                      <SourceBadge sourceUrl={member.latest_signal.source_url} />
                      {member.latest_signal.detected_at && (
                        <span className="text-[11px] text-gray-400">
                          {new Date(member.latest_signal.detected_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })() : (
                <p className="text-sm text-gray-400 py-4 text-center">No signals detected yet</p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Signals Tab */}
      {activeTab === 'signals' && (
        <div className="bg-white border border-gray-200 rounded-lg p-6">
          <SignalTimeline
            companyKbId={member.company_kb_id}
            companyName={member.company_name || undefined}
            showDetectButton
          />
        </div>
      )}

      {/* Research Brief Tab */}
      {activeTab === 'brief' && (
        <div>
          {briefLoading ? (
            <div className="flex justify-center py-16"><Spin /></div>
          ) : brief ? (
            <div className="space-y-4">
              {/* Brief header */}
              <div className="bg-white border border-purple-200 rounded-lg overflow-hidden">
                <div className="px-5 py-3 border-b border-gray-100 bg-purple-50 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <FileTextOutlined className="text-purple-600" />
                    <span className="text-sm font-semibold text-purple-800">
                      {member.company_name} — Research Brief
                    </span>
                    <span className="text-xs bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded-full font-mono">
                      v{brief.version}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={handleGenerateBrief}
                      disabled={briefGenerating}
                      className="flex items-center gap-1 h-7 px-2.5 text-xs text-gray-500 hover:text-gray-700 border border-gray-200 rounded-md hover:border-gray-300 bg-white transition-colors disabled:opacity-50"
                    >
                      <ReloadOutlined className={briefGenerating ? 'animate-spin' : ''} />
                      {briefGenerating ? 'Regenerating...' : 'Regenerate'}
                    </button>
                    {briefGenerating && (
                      <div className="flex items-center gap-2">
                        {briefThought && (
                          <span className="text-xs text-purple-500 italic animate-pulse max-w-[200px] truncate">{briefThought}</span>
                        )}
                        {briefGenStream.progress > 0 && (
                          <span className="text-[10px] text-gray-400">{briefGenStream.progress}%</span>
                        )}
                      </div>
                    )}
                    <Tooltip title="Export brief as printable HTML (save as PDF from browser)">
                      <a
                        href={`${API_BASE}${getBriefExportUrl(member.company_kb_id)}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-1 h-7 px-2.5 text-xs text-gray-500 hover:text-gray-700 border border-gray-200 rounded-md hover:border-gray-300 bg-white transition-colors no-underline"
                      >
                        Export PDF
                      </a>
                    </Tooltip>
                    <Tooltip title="Download signal report as XLSX">
                      <a
                        href={`${API_BASE}${getSignalReportExportUrl(member.company_kb_id)}`}
                        className="flex items-center gap-1 h-7 px-2.5 text-xs text-gray-500 hover:text-gray-700 border border-gray-200 rounded-md hover:border-gray-300 bg-white transition-colors no-underline"
                      >
                        Signal Report
                      </a>
                    </Tooltip>
                    <Button
                      size="small"
                      onClick={() => navigate(`/tracking/${listId}/company/${membershipId}/brief`)}
                      className="!rounded-md"
                    >
                      Open full brief
                    </Button>
                  </div>
                </div>

                {/* Brief sections preview */}
                <div className="px-5 py-4 space-y-4">
                  {brief.sections.slice(0, 5).map((section: BriefSection) => (
                    <div key={section.id}>
                      <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1.5">
                        {BRIEF_SECTION_ICONS[section.id] || '•'} {section.heading}
                      </p>
                      {section.insufficient ? (
                        <p className="text-xs text-gray-300 italic">Insufficient data</p>
                      ) : (
                        <p className="text-sm text-gray-700 leading-relaxed line-clamp-3">
                          {section.body.replace(/\[\d+\]/g, '')}
                        </p>
                      )}
                    </div>
                  ))}
                  {brief.sections.length > 5 && (
                    <p className="text-xs text-gray-400">
                      +{brief.sections.length - 5} more sections —{' '}
                      <button
                        onClick={() => navigate(`/tracking/${listId}/company/${membershipId}/brief`)}
                        className="text-purple-600 hover:text-purple-700 underline underline-offset-2"
                      >
                        View full brief
                      </button>
                    </p>
                  )}
                </div>
              </div>

              {/* Brief meta */}
              <div className="flex items-center justify-between text-xs text-gray-400">
                <span>
                  ✦ Generated{' '}
                  {brief.created_at ? new Date(brief.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : ''}
                  {brief.trigger_signal_headline && ` · Triggered by: ${brief.trigger_signal_headline}`}
                </span>
                <span>{brief.word_count?.toLocaleString() || 0} words · {brief.sections.length} sections</span>
              </div>
            </div>
          ) : (
            <div className="bg-white border border-gray-200 rounded-lg">
              <div className="flex flex-col items-center py-14 px-8 gap-5">
                <div className="w-14 h-14 rounded-2xl bg-purple-50 border border-purple-100 flex items-center justify-center">
                  <FileTextOutlined className="text-xl text-purple-500" />
                </div>
                <div className="text-center max-w-sm">
                  <p className="text-sm font-semibold text-gray-800 mb-1.5">No research brief yet</p>
                  <p className="text-xs text-gray-400 leading-relaxed">
                    Generate a brief to get a structured view of this account — signals, org structure,
                    competitive context, and a recommended outreach angle.
                  </p>
                </div>
                <Button
                  type="primary"
                  onClick={handleGenerateBrief}
                  loading={briefGenerating}
                  className="!rounded-md"
                >
                  ✦ Generate brief
                </Button>
                {briefGenerating && briefThought && (
                  <p className="text-xs text-purple-500 italic animate-pulse">{briefThought}</p>
                )}
                {briefGenerating && briefGenStream.progress > 0 && (
                  <div className="w-48">
                    <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-purple-500 rounded-full transition-all duration-500 ease-out"
                        style={{ width: `${briefGenStream.progress}%` }}
                      />
                    </div>
                  </div>
                )}
                {!briefGenerating && (
                  <p className="text-[11px] text-gray-300">
                    Briefs are also auto-generated when high-confidence signals fire.
                  </p>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Drafts Tab */}
      {activeTab === 'drafts' && (
        <div>
          {draftsLoading ? (
            <div className="flex justify-center py-16"><Spin /></div>
          ) : drafts.length > 0 ? (
            <div className="space-y-3">
              {drafts.map(d => (
                <div key={d.id} className="bg-white border border-gray-200 rounded-lg p-4">
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2">
                      {d.format === 'email' ? (
                        <span className="text-purple-500">✉</span>
                      ) : (
                        <span className="text-blue-500">in</span>
                      )}
                      <span className="text-sm font-semibold text-gray-800">
                        {d.subject || `${d.format === 'email' ? 'Email' : 'LinkedIn'} to ${d.contact_name || 'contact'}`}
                      </span>
                    </div>
                    <Badge
                      variant="status"
                      status={d.status === 'in_progress' ? 'drafted' : d.status === 'sent' ? 'sent' : 'lost'}
                    >
                      {d.status === 'in_progress' ? 'In progress' : d.status === 'sent' ? 'Sent' : 'Discarded'}
                    </Badge>
                  </div>
                  {d.contact_name && (
                    <p className="text-xs text-gray-500 mb-2">To: {d.contact_name}{d.contact_title ? ` · ${d.contact_title}` : ''}</p>
                  )}
                  <p className="text-xs bg-gray-50 border border-gray-100 rounded px-2.5 py-1.5 text-gray-500 line-clamp-2">
                    {d.body.slice(0, 200)}
                  </p>
                  <div className="flex items-center justify-between mt-2">
                    <p className="text-xs text-gray-400">
                      {d.created_at ? new Date(d.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : ''}
                    </p>
                    {d.status === 'in_progress' && (
                      <div className="flex items-center gap-1.5">
                        <button
                          onClick={() => handleDraftStatusChange(d.id, 'sent')}
                          className="text-xs text-emerald-600 hover:text-emerald-700 underline underline-offset-2"
                        >
                          Mark sent
                        </button>
                        <button
                          onClick={() => handleDraftStatusChange(d.id, 'discarded')}
                          className="text-xs text-gray-400 hover:text-red-500 underline underline-offset-2"
                        >
                          Discard
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="bg-white border border-gray-200 rounded-lg py-16 text-center">
              <span className="text-3xl opacity-30 block mb-3">✉</span>
              <p className="text-sm text-gray-400">No drafts for this account yet.</p>
              <p className="text-xs text-gray-300 mt-1">Generate a draft from a signal or from the outreach button above.</p>
            </div>
          )}
        </div>
      )}

      {/* Contacts Tab */}
      {activeTab === 'contacts' && (
        <div className="bg-white border border-gray-200 rounded-lg p-6">
          <ContactsPanel
            listId={listId!}
            membershipId={membershipId!}
            companyName={member.company_name || undefined}
            enrichmentStatus={member.enrichment_status || 'not_started'}
          />
        </div>
      )}

      {/* Notes & History Tab */}
      {activeTab === 'notes' && (<>
        <div className="grid grid-cols-2 gap-5">
          {/* Notes */}
          <div className="bg-white border border-gray-200 rounded-lg p-5">
            <SectionLabel className="!mb-3">Notes</SectionLabel>
            <Input.TextArea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Add notes about this company..."
              rows={8}
              className="!mb-3"
            />
            <Button
              type="primary"
              onClick={handleSaveNotes}
              loading={savingNotes}
              className="!rounded-md"
            >
              Save Notes
            </Button>
          </div>

          {/* Outreach History */}
          <div className="bg-white border border-gray-200 rounded-lg p-5">
            <SectionLabel className="!mb-3">Outreach History</SectionLabel>
            {member.outreach_history && (member.outreach_history as Array<{ status: string; previous_status?: string; timestamp: string }>).length > 0 ? (
              <div className="relative pl-5">
                {/* Timeline line */}
                <div className="absolute left-[5px] top-1 bottom-1 w-0.5 bg-gray-200" />

                {(member.outreach_history as Array<{ status: string; previous_status?: string; timestamp: string }>).map((entry, i) => {
                  const statusColor = OUTREACH_STATUS_COLORS[entry.status] || '#8c8c8c';
                  const entryDate = new Date(entry.timestamp);
                  const daysAgo = Math.floor((Date.now() - entryDate.getTime()) / 86400000);
                  const relativeTime = daysAgo === 0 ? 'Today' : daysAgo === 1 ? 'Yesterday' : `${daysAgo}d ago`;

                  return (
                    <div key={i} className="relative mb-3 last:mb-0">
                      {/* Dot */}
                      <div
                        className="absolute -left-[17px] top-2.5 w-2.5 h-2.5 rounded-full ring-2 ring-white z-10"
                        style={{ background: statusColor }}
                      />
                      <div className="bg-gray-50 rounded-lg px-3 py-2.5">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-1.5 text-xs">
                            {entry.previous_status && (
                              <>
                                <Badge variant="status" status={entry.previous_status}>
                                  {OUTREACH_STATUS_LABELS[entry.previous_status] || entry.previous_status}
                                </Badge>
                                <span className="text-gray-300">&rarr;</span>
                              </>
                            )}
                            <Badge variant="status" status={entry.status}>
                              {OUTREACH_STATUS_LABELS[entry.status] || entry.status}
                            </Badge>
                          </div>
                          <div className="flex items-center gap-2 text-xs text-gray-400">
                            <span>{relativeTime}</span>
                            <span className="text-gray-300">&middot;</span>
                            <span>{entryDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-sm text-gray-400 text-center py-6">No outreach history yet</p>
            )}
          </div>
        </div>

        {/* Activity Timeline */}
        <div className="mt-5 bg-white border border-gray-200 rounded-lg p-5">
          <ActivityFeed companyKbId={member.company_kb_id} maxItems={30} />
        </div>
      </>)}
    </div>
  );
};

export default TrackedCompanyDetailPage;
