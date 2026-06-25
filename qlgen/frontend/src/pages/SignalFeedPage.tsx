import React, { useEffect, useState, useMemo } from 'react';
import { Select, Spin, Tooltip, Popover, message, Input, DatePicker } from 'antd';
import {
  ReloadOutlined, EyeInvisibleOutlined, ThunderboltOutlined,
  ClockCircleOutlined, StarOutlined, StarFilled, WarningOutlined,
  SearchOutlined, CheckSquareOutlined, CloseCircleOutlined,
  FileTextOutlined, CheckOutlined, LinkOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { PillTabs, Badge, Banner, EmptyState, SourceBadge } from '../components/ui';
import SignalDetailPane from '../components/SignalDetailPane';
import {
  useSignalFeed, useSaveSignal, useUnsaveSignal, useDismissSignal,
  useSnoozeSignal, useBulkDismiss, useBulkSave, useBulkSnooze,
  useCorrelations,
} from '../hooks/useSignalQueries';
import { SIGNAL_TYPE_LABELS, type SignalFeedTab } from '../types';
import { getSignalFreshness, FRESHNESS_DESCRIPTIONS } from '../utils/signalFreshness';
import type { Dayjs } from 'dayjs';

const { RangePicker } = DatePicker;

const PRIORITY_DOT_CLS: Record<string, string> = {
  critical: 'bg-red-500',
  high: 'bg-orange-500',
  medium: 'bg-amber-400',
  low: 'bg-gray-300',
};

const TAB_KEYS: { key: SignalFeedTab; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'today', label: 'Today' },
  { key: 'week', label: 'This Week' },
  { key: 'saved', label: 'Saved' },
];

const SNOOZE_OPTIONS = [
  { label: '1 hour', hours: 1 },
  { label: '4 hours', hours: 4 },
  { label: '1 day', hours: 24 },
  { label: '3 days', hours: 72 },
  { label: '1 week', hours: 168 },
];

const STALE_THRESHOLD_DAYS = 30;

const SignalFeedPage: React.FC = () => {
  const navigate = useNavigate();
  const [typeFilter, setTypeFilter] = useState<string | undefined>(undefined);
  const [priorityFilter, setPriorityFilter] = useState<string | undefined>(undefined);
  const [activeTab, setActiveTab] = useState<SignalFeedTab>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [dateRange, setDateRange] = useState<[Dayjs | null, Dayjs | null] | null>(null);
  const [offset, setOffset] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [lastRefreshed, setLastRefreshed] = useState<Date>(new Date());
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const limit = 50;

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchQuery), 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const feedParams = useMemo(() => ({
    tab: activeTab,
    signal_type: typeFilter,
    priority: priorityFilter,
    search: debouncedSearch || undefined,
    date_from: dateRange?.[0]?.toISOString() || undefined,
    date_to: dateRange?.[1]?.toISOString() || undefined,
    limit,
    offset,
  }), [activeTab, typeFilter, priorityFilter, debouncedSearch, dateRange, offset]);

  const { data: feedData, isLoading: loading, isRefetching: refreshing, refetch, dataUpdatedAt } = useSignalFeed(feedParams);
  const signals = feedData?.signals || [];
  const total = feedData?.total || 0;
  const snoozedReturnedCount = feedData?.snoozed_returned_count || 0;

  // Correlations
  const { data: correlationData } = useCorrelations();
  const correlations = correlationData?.correlations || [];

  // Track last refresh time from React Query's dataUpdatedAt
  useEffect(() => {
    if (dataUpdatedAt) setLastRefreshed(new Date(dataUpdatedAt));
  }, [dataUpdatedAt]);

  // Reset offset when filters change
  useEffect(() => { setOffset(0); }, [typeFilter, priorityFilter, activeTab, debouncedSearch, dateRange]);

  // Clear selection when feed data changes
  useEffect(() => { setSelectedIds(new Set()); }, [feedData]);

  // Mutation hooks
  const saveMutation = useSaveSignal();
  const unsaveMutation = useUnsaveSignal();
  const dismissMutation = useDismissSignal();
  const snoozeMutation = useSnoozeSignal();
  const bulkDismissMutation = useBulkDismiss();
  const bulkSaveMutation = useBulkSave();
  const bulkSnoozeMutation = useBulkSnooze();

  const handleDismiss = async (signalId: string) => {
    try {
      await dismissMutation.mutateAsync(signalId);
      if (selectedId === signalId) setSelectedId(null);
      message.success('Signal dismissed');
    } catch {
      message.error('Failed to dismiss');
    }
  };

  const handleSave = async (signalId: string) => {
    try {
      await saveMutation.mutateAsync(signalId);
      message.success('Signal saved');
    } catch {
      message.error('Failed to save');
    }
  };

  const handleUnsave = async (signalId: string) => {
    try {
      await unsaveMutation.mutateAsync(signalId);
      message.success('Signal unsaved');
    } catch {
      message.error('Failed to unsave');
    }
  };

  const handleSnooze = async (signalId: string, hours: number) => {
    try {
      await snoozeMutation.mutateAsync({ signalId, hours });
      if (selectedId === signalId) setSelectedId(null);
      const label = SNOOZE_OPTIONS.find((o) => o.hours === hours)?.label || `${hours}h`;
      message.success(`Signal snoozed for ${label}`);
    } catch {
      message.error('Failed to snooze');
    }
  };

  // Bulk actions
  const handleBulkDismiss = async () => {
    const ids = [...selectedIds];
    try {
      await bulkDismissMutation.mutateAsync(ids);
      setSelectedIds(new Set());
      if (selectedId && ids.includes(selectedId)) setSelectedId(null);
      message.success(`${ids.length} signal${ids.length > 1 ? 's' : ''} dismissed`);
    } catch {
      message.error('Failed to dismiss signals');
    }
  };

  const handleBulkSave = async () => {
    const ids = [...selectedIds];
    try {
      await bulkSaveMutation.mutateAsync(ids);
      setSelectedIds(new Set());
      message.success(`${ids.length} signal${ids.length > 1 ? 's' : ''} saved`);
    } catch {
      message.error('Failed to save signals');
    }
  };

  const handleBulkSnooze = async (hours: number) => {
    const ids = [...selectedIds];
    try {
      await bulkSnoozeMutation.mutateAsync({ signalIds: ids, hours });
      setSelectedIds(new Set());
      if (selectedId && ids.includes(selectedId)) setSelectedId(null);
      const label = SNOOZE_OPTIONS.find((o) => o.hours === hours)?.label || `${hours}h`;
      message.success(`${ids.length} signal${ids.length > 1 ? 's' : ''} snoozed for ${label}`);
    } catch {
      message.error('Failed to snooze signals');
    }
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === signals.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(signals.map(s => s.id)));
    }
  };

  const toggleSelect = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const signalTypeOptions = Object.entries(SIGNAL_TYPE_LABELS).map(([k, v]) => ({
    value: k, label: v,
  }));

  const selectedSignal = signals.find((s) => s.id === selectedId) || null;

  const hasActiveFilters = !!(debouncedSearch || dateRange || typeFilter || priorityFilter);

  // Time since last refresh
  const [timeSinceRefresh, setTimeSinceRefresh] = useState('just now');
  useEffect(() => {
    const update = () => {
      const diff = Math.floor((Date.now() - lastRefreshed.getTime()) / 1000);
      if (diff < 5) setTimeSinceRefresh('just now');
      else if (diff < 60) setTimeSinceRefresh(`${diff}s ago`);
      else setTimeSinceRefresh(`${Math.floor(diff / 60)}m ago`);
    };
    update();
    const interval = setInterval(update, 5000);
    return () => clearInterval(interval);
  }, [lastRefreshed]);

  return (
    <div className="px-10 py-8 max-w-[1400px] mx-auto">
      {/* Secondary nav */}
      <PillTabs
        tabs={[
          { key: 'lists', label: 'My Lists' },
          { key: 'feed', label: 'Signal Feed' },
          { key: 'rules', label: 'Signal Rules' },
        ]}
        activeKey="feed"
        onChange={(v) => {
          if (v === 'lists') navigate('/tracking');
          if (v === 'rules') navigate('/signals/rules');
        }}
        className="mb-6"
      />

      {/* Header with live indicator */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-xl font-bold text-gray-900">Signal Feed</h1>
            <span className="inline-flex items-center gap-1.5 text-xs text-gray-400">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500" />
              </span>
              Live
              <span className="text-gray-300">·</span>
              refreshed {timeSinceRefresh}
            </span>
          </div>
          <p className="text-sm text-gray-500">
            Recent signals across all your tracked companies
          </p>
        </div>
        <Tooltip title="Refresh">
          <button
            onClick={() => refetch()}
            className={`w-8 h-8 flex items-center justify-center rounded-md text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors ${refreshing ? 'animate-spin' : ''}`}
          >
            <ReloadOutlined />
          </button>
        </Tooltip>
      </div>

      {/* Snooze return banner */}
      {snoozedReturnedCount > 0 && (
        <div className="flex items-center gap-2 px-4 py-2.5 mb-4 bg-amber-50 border border-amber-200 rounded-lg text-sm">
          <ClockCircleOutlined className="text-amber-500" />
          <span className="text-amber-800 font-medium">
            {snoozedReturnedCount} snoozed signal{snoozedReturnedCount !== 1 ? 's' : ''} returned
          </span>
          <span className="text-amber-600 text-xs">— previously snoozed signals have reappeared in your feed</span>
        </div>
      )}

      {/* Correlation insights */}
      {correlations.length > 0 && (
        <div className="mb-4 space-y-2">
          <div className="flex items-center gap-1.5 mb-1">
            <LinkOutlined className="text-brand text-xs" />
            <span className="text-xs font-semibold text-gray-600 uppercase tracking-wide">Signal Correlations</span>
          </div>
          {correlations.slice(0, 3).map((corr) => (
            <div
              key={corr.id}
              className="flex items-start gap-3 px-4 py-3 bg-gradient-to-r from-purple-50 to-blue-50 border border-purple-200/50 rounded-lg"
            >
              <div className="w-8 h-8 rounded-lg bg-brand/10 flex items-center justify-center shrink-0 mt-0.5">
                <ThunderboltOutlined className="text-brand text-sm" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-semibold text-brand">{corr.company_name}</span>
                  {corr.domain && <span className="text-[10px] text-gray-400">{corr.domain}</span>}
                  {corr.confidence != null && (
                    <Badge variant="count" className="text-[10px]">
                      {Math.round(corr.confidence * 100)}% confidence
                    </Badge>
                  )}
                </div>
                <p className="text-sm text-gray-700 leading-snug">{corr.narrative}</p>
                {corr.narrative_detail && (
                  <p className="text-xs text-gray-500 mt-1">{corr.narrative_detail}</p>
                )}
                <span className="text-[10px] text-gray-400 mt-1 inline-block">
                  {corr.created_at ? new Date(corr.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : ''}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Tab filters */}
      <div className="flex items-center gap-1.5 mb-4">
        {TAB_KEYS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`h-8 px-3.5 text-xs font-semibold rounded-full transition-colors ${
              activeTab === tab.key
                ? 'bg-brand text-white'
                : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Filter bar */}
      <div className="bg-white border border-gray-200 rounded-lg px-4 py-3 mb-4">
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-xs text-gray-400 flex items-center gap-1">
            <ThunderboltOutlined /> Filter:
          </span>
          <Input
            placeholder="Search signals..."
            prefix={<SearchOutlined className="text-gray-400" />}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            allowClear
            size="small"
            style={{ width: 200 }}
          />
          <Select
            placeholder="All signal types"
            value={typeFilter}
            onChange={setTypeFilter}
            allowClear
            size="small"
            style={{ width: 180 }}
            options={signalTypeOptions}
          />
          <Select
            placeholder="All priorities"
            value={priorityFilter}
            onChange={setPriorityFilter}
            allowClear
            size="small"
            style={{ width: 140 }}
            options={[
              { value: 'critical', label: 'Critical' },
              { value: 'high', label: 'High' },
              { value: 'medium', label: 'Medium' },
              { value: 'low', label: 'Low' },
            ]}
          />
          <RangePicker
            size="small"
            style={{ width: 240 }}
            onChange={(dates) => setDateRange(dates as [Dayjs | null, Dayjs | null] | null)}
            value={dateRange}
            allowClear
            placeholder={['From date', 'To date']}
          />
          {hasActiveFilters && (
            <button
              onClick={() => {
                setSearchQuery('');
                setTypeFilter(undefined);
                setPriorityFilter(undefined);
                setDateRange(null);
              }}
              className="text-xs text-gray-400 hover:text-gray-600 flex items-center gap-1 transition-colors"
            >
              <CloseCircleOutlined className="text-[10px]" /> Clear all
            </button>
          )}
          {total > 0 && (
            <span className="ml-auto text-xs text-gray-400">
              {total} signal{total !== 1 ? 's' : ''}
            </span>
          )}
        </div>
      </div>

      {/* EU coverage notice */}
      <Banner
        type="info"
        dismissible
        storageKey="eu-coverage-notice"
        message="Some EU-based accounts may have limited contact data due to GDPR compliance requirements."
        className="mb-4"
      />

      {/* Bulk action bar */}
      {selectedIds.size > 0 && (
        <div className="flex items-center gap-3 px-4 py-2.5 mb-4 bg-brand-bg border border-brand-light/30 rounded-lg animate-fadeIn">
          <span className="text-xs font-semibold text-brand">
            {selectedIds.size} selected
          </span>
          <div className="h-4 w-px bg-gray-200" />
          <button
            onClick={handleBulkSave}
            className="flex items-center gap-1 text-xs font-medium text-gray-600 hover:text-brand transition-colors"
          >
            <StarOutlined className="text-[11px]" /> Save
          </button>
          <Popover
            content={
              <div className="space-y-1 min-w-[130px]">
                <p className="text-xs font-semibold text-gray-500 mb-2">Snooze for...</p>
                {SNOOZE_OPTIONS.map((opt) => (
                  <button
                    key={opt.hours}
                    onClick={() => handleBulkSnooze(opt.hours)}
                    className="block w-full text-left text-sm px-2.5 py-1.5 rounded-md hover:bg-gray-100 text-gray-700 transition-colors"
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            }
            trigger="click"
            placement="bottomLeft"
          >
            <button className="flex items-center gap-1 text-xs font-medium text-gray-600 hover:text-brand transition-colors">
              <ClockCircleOutlined className="text-[11px]" /> Snooze
            </button>
          </Popover>
          <button
            onClick={handleBulkDismiss}
            className="flex items-center gap-1 text-xs font-medium text-gray-600 hover:text-red-500 transition-colors"
          >
            <EyeInvisibleOutlined className="text-[11px]" /> Dismiss
          </button>
          <button
            onClick={() => setSelectedIds(new Set())}
            className="ml-auto text-xs text-gray-400 hover:text-gray-600 transition-colors"
          >
            Clear selection
          </button>
        </div>
      )}

      {/* Master-detail layout */}
      <div className={`flex transition-all ${selectedSignal ? 'gap-5' : 'gap-0'}`}>
        {/* Signal list (left) */}
        <div className="flex-1 min-w-0">
          {loading ? (
            <div className="flex justify-center py-20"><Spin size="large" /></div>
          ) : signals.length === 0 ? (
            <div className="bg-white border border-gray-200 rounded-lg">
              <EmptyState
                icon={<ThunderboltOutlined />}
                title={activeTab === 'saved' ? 'No saved signals' : debouncedSearch ? 'No matching signals' : 'No signals yet'}
                description={
                  activeTab === 'saved'
                    ? 'Save signals by clicking the star icon to bookmark them for later.'
                    : debouncedSearch
                      ? `No signals found matching "${debouncedSearch}". Try different keywords.`
                      : 'Signals will appear here when you detect them for tracked companies.'
                }
                className="py-16"
              />
            </div>
          ) : (
            <>
              <div className="bg-white border border-gray-200 rounded-lg overflow-hidden" role="feed">
                {/* Select all header */}
                <div className="flex items-center gap-2 px-4 py-2 border-b border-gray-100 bg-gray-50/50">
                  <button
                    onClick={toggleSelectAll}
                    className={`w-4 h-4 rounded border flex items-center justify-center transition-colors ${
                      selectedIds.size === signals.length && signals.length > 0
                        ? 'bg-brand border-brand text-white'
                        : selectedIds.size > 0
                          ? 'bg-brand/20 border-brand/50 text-brand'
                          : 'border-gray-300 hover:border-gray-400'
                    }`}
                  >
                    {selectedIds.size > 0 && (
                      selectedIds.size === signals.length
                        ? <CheckOutlined className="text-[8px]" />
                        : <span className="block w-1.5 h-0.5 bg-brand rounded" />
                    )}
                  </button>
                  <span className="text-[11px] text-gray-400">
                    {selectedIds.size > 0
                      ? `${selectedIds.size} of ${signals.length} selected`
                      : 'Select all'}
                  </span>
                </div>

                {signals.map((signal) => {
                  const dotCls = PRIORITY_DOT_CLS[signal.priority] || 'bg-gray-300';
                  const isSelected = signal.id === selectedId;
                  const isChecked = selectedIds.has(signal.id);
                  const freshness = getSignalFreshness(signal.evidence_date, signal.detected_at || signal.created_at);
                  const isStale = freshness.days >= STALE_THRESHOLD_DAYS;
                  const isSaved = signal.is_saved ?? false;
                  const hasNotes = !!signal.notes;

                  return (
                    <div
                      key={signal.id}
                      onClick={() => setSelectedId(isSelected ? null : signal.id)}
                      className={`group relative flex gap-3.5 px-4 py-3.5 border-b border-gray-100 cursor-pointer transition-colors ${
                        isSelected
                          ? 'bg-brand-pale'
                          : isChecked
                            ? 'bg-blue-50/50'
                            : 'hover:bg-gray-50'
                      }`}
                      style={{
                        borderLeft: isSelected
                          ? '3px solid var(--purple, #5C2D8F)'
                          : `3px solid ${freshness.color}`,
                      }}
                    >
                      {/* Checkbox */}
                      <div className="flex flex-col items-center pt-1.5 shrink-0">
                        <button
                          onClick={(e) => { e.stopPropagation(); toggleSelect(signal.id); }}
                          className={`w-4 h-4 rounded border flex items-center justify-center transition-colors ${
                            isChecked
                              ? 'bg-brand border-brand text-white'
                              : 'border-gray-300 group-hover:border-gray-400'
                          }`}
                        >
                          {isChecked && <CheckOutlined className="text-[8px]" />}
                        </button>
                        <div className={`w-2 h-2 rounded-full mt-1.5 ${dotCls}`} />
                      </div>

                      {/* Content */}
                      <div className="flex-1 min-w-0">
                        {/* Badges + freshness */}
                        <div className="flex items-center gap-1.5 mb-1.5 flex-wrap">
                          <Badge variant="signal-type" signalType={signal.signal_type} className="text-[10px]">
                            {SIGNAL_TYPE_LABELS[signal.signal_type] || signal.signal_type}
                          </Badge>
                          <Badge variant="priority" priority={signal.priority} className="text-[10px]">
                            {signal.priority}
                          </Badge>
                          <Tooltip title={FRESHNESS_DESCRIPTIONS[freshness.tier]}>
                            <span
                              className="inline-flex items-center text-[10px] font-medium px-1.5 py-0.5 rounded-full"
                              style={{ color: freshness.color, background: freshness.bgColor }}
                            >
                              {freshness.label}
                            </span>
                          </Tooltip>
                          {isSaved && (
                            <StarFilled className="text-amber-400 text-[11px]" />
                          )}
                          {signal.is_acted_on && (
                            <Tooltip title="Outreach drafted for this signal">
                              <span className="inline-flex items-center gap-0.5 text-[10px] font-medium text-green-600 bg-green-50 px-1.5 py-0.5 rounded-full">
                                <CheckSquareOutlined className="text-[9px]" /> Acted
                              </span>
                            </Tooltip>
                          )}
                          {hasNotes && (
                            <Tooltip title="Has notes">
                              <span className="inline-flex items-center text-[10px] font-medium text-blue-500 bg-blue-50 px-1.5 py-0.5 rounded-full">
                                <FileTextOutlined className="text-[9px] mr-0.5" /> Note
                              </span>
                            </Tooltip>
                          )}
                          {isStale && (
                            <Tooltip title="This signal is over 30 days old and may be outdated">
                              <span className="inline-flex items-center gap-0.5 text-[10px] font-medium text-orange-500 bg-orange-50 px-1.5 py-0.5 rounded-full">
                                <WarningOutlined className="text-[9px]" /> Stale
                              </span>
                            </Tooltip>
                          )}
                        </div>

                        {/* Company */}
                        <div className="flex items-baseline gap-1.5 mb-1">
                          <span className={`text-xs font-semibold shrink-0 ${isSelected ? 'text-brand-dark' : 'text-brand'}`}>
                            {signal.company_name || 'Unknown'}
                          </span>
                          {signal.domain && (
                            <span className="text-xs text-gray-400">
                              {signal.domain}
                            </span>
                          )}
                        </div>

                        {/* Title */}
                        <p className="text-sm font-medium text-gray-900 leading-snug mb-1 truncate">
                          {signal.title}
                        </p>

                        {/* Summary preview */}
                        {signal.summary && (
                          <p className="text-xs text-gray-500 leading-relaxed mb-2 line-clamp-2">
                            {signal.summary}
                          </p>
                        )}

                        {/* Meta */}
                        <div className="flex items-center gap-3 text-[11px] text-gray-400">
                          {signal.source_tool && (
                            <span className="font-mono bg-gray-100 px-1.5 py-0.5 rounded">
                              {signal.source_tool}
                            </span>
                          )}
                          <span onClick={(e) => e.stopPropagation()}>
                            <SourceBadge sourceUrl={signal.source_url} />
                          </span>
                          <span className="flex items-center gap-1">
                            <ClockCircleOutlined className="text-[10px]" />
                            {new Date(signal.detected_at || signal.created_at || '').toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                          </span>
                        </div>
                      </div>

                      {/* Quick actions */}
                      <div className={`flex flex-col items-end gap-1 shrink-0 transition-opacity ${
                        isSelected ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'
                      }`}>
                        {/* Save/Unsave */}
                        <Tooltip title={isSaved ? 'Unsave' : 'Save'}>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              isSaved ? handleUnsave(signal.id) : handleSave(signal.id);
                            }}
                            className={`w-6 h-6 flex items-center justify-center rounded transition-colors ${
                              isSaved
                                ? 'text-amber-400 hover:text-amber-500'
                                : 'text-gray-400 hover:bg-gray-200 hover:text-gray-600'
                            }`}
                          >
                            {isSaved ? <StarFilled className="text-xs" /> : <StarOutlined className="text-xs" />}
                          </button>
                        </Tooltip>

                        {/* Snooze */}
                        <Popover
                          content={
                            <div className="space-y-1 min-w-[130px]">
                              <p className="text-xs font-semibold text-gray-500 mb-2">Snooze for...</p>
                              {SNOOZE_OPTIONS.map((opt) => (
                                <button
                                  key={opt.hours}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleSnooze(signal.id, opt.hours);
                                  }}
                                  className="block w-full text-left text-sm px-2.5 py-1.5 rounded-md hover:bg-gray-100 text-gray-700 transition-colors"
                                >
                                  {opt.label}
                                </button>
                              ))}
                            </div>
                          }
                          trigger="click"
                          placement="bottomRight"
                        >
                          <Tooltip title="Snooze">
                            <button
                              onClick={(e) => e.stopPropagation()}
                              className="w-6 h-6 flex items-center justify-center rounded text-gray-400 hover:bg-gray-200 hover:text-gray-600 transition-colors"
                            >
                              <ClockCircleOutlined className="text-xs" />
                            </button>
                          </Tooltip>
                        </Popover>

                        {/* Dismiss */}
                        <Tooltip title="Dismiss">
                          <button
                            onClick={(e) => { e.stopPropagation(); handleDismiss(signal.id); }}
                            className="w-6 h-6 flex items-center justify-center rounded text-gray-400 hover:bg-gray-200 hover:text-gray-600 transition-colors"
                          >
                            <EyeInvisibleOutlined className="text-xs" />
                          </button>
                        </Tooltip>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Pagination */}
              {total > limit && (
                <div className="flex items-center justify-center gap-3 mt-4">
                  <button
                    disabled={offset === 0}
                    onClick={() => setOffset(Math.max(0, offset - limit))}
                    className="h-8 px-3 text-xs font-medium rounded-md border border-gray-200 bg-white text-gray-600 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  >
                    Previous
                  </button>
                  <span className="text-xs text-gray-400">
                    {offset + 1}&ndash;{Math.min(offset + limit, total)} of {total}
                  </span>
                  <button
                    disabled={offset + limit >= total}
                    onClick={() => setOffset(offset + limit)}
                    className="h-8 px-3 text-xs font-medium rounded-md border border-gray-200 bg-white text-gray-600 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  >
                    Next
                  </button>
                </div>
              )}
            </>
          )}
        </div>

        {/* Detail pane (right) */}
        {selectedSignal && (
          <div
            className="w-[420px] shrink-0 bg-white border border-gray-200 rounded-lg overflow-hidden"
            style={{
              height: 'calc(100vh - 120px)',
              position: 'sticky',
              top: '80px',
              animation: 'slide-in-right 0.2s ease-out',
            }}
          >
            <SignalDetailPane
              signal={selectedSignal}
              onClose={() => setSelectedId(null)}
              onDismiss={handleDismiss}
              onSave={handleSave}
              onUnsave={handleUnsave}
              onSnooze={handleSnooze}
            />
          </div>
        )}
      </div>
    </div>
  );
};

export default SignalFeedPage;
