import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { Button, Select, Spin, message, Tooltip, Input } from 'antd';
import {
  ArrowLeftOutlined, ReloadOutlined, GlobalOutlined, LinkedinOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import { PillTabs, Badge, KpiStrip, SectionLabel, SourceBadge } from '../components/ui';
import {
  getListMembers, updateMember,
} from '../api/trackingApi';
import { researchCompany } from '../api/briefApi';
import SignalTimeline from '../components/SignalTimeline';
import CompanyBriefModal from '../components/CompanyBriefModal';
import OutreachDraftModal from '../components/OutreachDraftModal';
import ContactsPanel from '../components/ContactsPanel';
import {
  TrackingListMember,
  OUTREACH_STATUSES, OUTREACH_STATUS_LABELS, OUTREACH_STATUS_COLORS,
  SIGNAL_PRIORITY_COLORS, SIGNAL_TYPE_LABELS,
} from '../types';
import { getSignalFreshness, FRESHNESS_DESCRIPTIONS } from '../utils/signalFreshness';

type TabKey = 'overview' | 'signals' | 'contacts' | 'notes';

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

  const [member, setMember] = useState<TrackingListMember | null>(
    (location.state as { member?: TrackingListMember })?.member || null,
  );
  const [loading, setLoading] = useState(!member);
  const [activeTab, setActiveTab] = useState<TabKey>('overview');
  const [notes, setNotes] = useState('');
  const [savingNotes, setSavingNotes] = useState(false);
  const [researching, setResearching] = useState(false);

  const handleResearch = async () => {
    if (!member) return;
    setResearching(true);
    try {
      const res = await researchCompany(member.company_kb_id);
      const fields = res.data.fields_updated || [];
      if (fields.length > 0) {
        // Refetch member to get updated data
        await fetchMember();
        message.success(`Updated ${fields.length} field${fields.length > 1 ? 's' : ''}: ${fields.join(', ')}`);
      } else {
        message.info('No new information found for this company');
      }
    } catch {
      message.error('Company research failed');
    } finally {
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
            <CompanyBriefModal
              companyKbId={member.company_kb_id}
              companyName={member.company_name || undefined}
            />
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
      {activeTab === 'notes' && (
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
      )}
    </div>
  );
};

export default TrackedCompanyDetailPage;
