import React, { useEffect, useState, useCallback, useRef } from 'react';
import { Select, Spin, Tooltip, Popover, message } from 'antd';
import {
  ReloadOutlined, EyeInvisibleOutlined, ThunderboltOutlined,
  ClockCircleOutlined, StarOutlined, StarFilled, WarningOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { PillTabs, Badge, EmptyState, SourceBadge } from '../components/ui';
import SignalDetailPane from '../components/SignalDetailPane';
import {
  getSignalFeed, dismissSignal, saveSignal, unsaveSignal, snoozeSignal,
  type SignalFeedResponse,
} from '../api/signalApi';
import { SIGNAL_TYPE_LABELS, type SignalFeedTab } from '../types';
import { getSignalFreshness, FRESHNESS_DESCRIPTIONS } from '../utils/signalFreshness';

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
const AUTO_REFRESH_INTERVAL = 30_000; // 30s

const SignalFeedPage: React.FC = () => {
  const navigate = useNavigate();
  const [signals, setSignals] = useState<SignalFeedResponse['signals']>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [typeFilter, setTypeFilter] = useState<string | undefined>(undefined);
  const [priorityFilter, setPriorityFilter] = useState<string | undefined>(undefined);
  const [activeTab, setActiveTab] = useState<SignalFeedTab>('all');
  const [offset, setOffset] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [snoozedReturnedCount, setSnoozedReturnedCount] = useState(0);
  const [lastRefreshed, setLastRefreshed] = useState<Date>(new Date());
  const [refreshing, setRefreshing] = useState(false);
  const limit = 50;
  const autoRefreshRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchFeed = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    else setRefreshing(true);
    try {
      const res = await getSignalFeed({
        signal_type: typeFilter,
        priority: priorityFilter,
        tab: activeTab,
        limit,
        offset,
      });
      setSignals(res.data.signals || []);
      setTotal(res.data.total || 0);
      setSnoozedReturnedCount(res.data.snoozed_returned_count || 0);
      setLastRefreshed(new Date());
    } catch {
      if (!silent) setSignals([]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [typeFilter, priorityFilter, activeTab, offset]);

  useEffect(() => { fetchFeed(); }, [fetchFeed]);

  // Auto-refresh
  useEffect(() => {
    autoRefreshRef.current = setInterval(() => fetchFeed(true), AUTO_REFRESH_INTERVAL);
    return () => { if (autoRefreshRef.current) clearInterval(autoRefreshRef.current); };
  }, [fetchFeed]);

  // Reset offset when filters change
  useEffect(() => { setOffset(0); }, [typeFilter, priorityFilter, activeTab]);

  const handleDismiss = async (signalId: string) => {
    try {
      await dismissSignal(signalId);
      setSignals((prev) => prev.filter((s) => s.id !== signalId));
      setTotal((prev) => Math.max(0, prev - 1));
      if (selectedId === signalId) setSelectedId(null);
      message.success('Signal dismissed');
    } catch {
      message.error('Failed to dismiss');
    }
  };

  const handleSave = async (signalId: string) => {
    try {
      await saveSignal(signalId);
      setSignals((prev) => prev.map((s) => s.id === signalId ? { ...s, is_saved: true } : s));
      message.success('Signal saved');
    } catch {
      message.error('Failed to save');
    }
  };

  const handleUnsave = async (signalId: string) => {
    try {
      await unsaveSignal(signalId);
      setSignals((prev) => prev.map((s) => s.id === signalId ? { ...s, is_saved: false } : s));
      if (activeTab === 'saved') {
        setSignals((prev) => prev.filter((s) => s.id !== signalId));
        setTotal((prev) => Math.max(0, prev - 1));
      }
      message.success('Signal unsaved');
    } catch {
      message.error('Failed to unsave');
    }
  };

  const handleSnooze = async (signalId: string, hours: number) => {
    try {
      await snoozeSignal(signalId, hours);
      setSignals((prev) => prev.filter((s) => s.id !== signalId));
      setTotal((prev) => Math.max(0, prev - 1));
      if (selectedId === signalId) setSelectedId(null);
      const label = SNOOZE_OPTIONS.find((o) => o.hours === hours)?.label || `${hours}h`;
      message.success(`Signal snoozed for ${label}`);
    } catch {
      message.error('Failed to snooze');
    }
  };

  const signalTypeOptions = Object.entries(SIGNAL_TYPE_LABELS).map(([k, v]) => ({
    value: k, label: v,
  }));

  const selectedSignal = signals.find((s) => s.id === selectedId) || null;

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
            onClick={() => fetchFeed()}
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
          {total > 0 && (
            <span className="ml-auto text-xs text-gray-400">
              {total} signal{total !== 1 ? 's' : ''}
            </span>
          )}
        </div>
      </div>

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
                title={activeTab === 'saved' ? 'No saved signals' : 'No signals yet'}
                description={
                  activeTab === 'saved'
                    ? 'Save signals by clicking the star icon to bookmark them for later.'
                    : 'Signals will appear here when you detect them for tracked companies.'
                }
                className="py-16"
              />
            </div>
          ) : (
            <>
              <div className="bg-white border border-gray-200 rounded-lg overflow-hidden" role="feed">
                {signals.map((signal) => {
                  const dotCls = PRIORITY_DOT_CLS[signal.priority] || 'bg-gray-300';
                  const isSelected = signal.id === selectedId;
                  const freshness = getSignalFreshness(signal.evidence_date, signal.detected_at || signal.created_at);
                  const isStale = freshness.days >= STALE_THRESHOLD_DAYS;
                  const isSaved = signal.is_saved ?? false;

                  return (
                    <div
                      key={signal.id}
                      onClick={() => setSelectedId(isSelected ? null : signal.id)}
                      className={`group relative flex gap-3.5 px-4 py-3.5 border-b border-gray-100 cursor-pointer transition-colors ${
                        isSelected
                          ? 'bg-brand-pale'
                          : 'hover:bg-gray-50'
                      }`}
                      style={{
                        borderLeft: isSelected
                          ? '3px solid var(--purple, #5C2D8F)'
                          : `3px solid ${freshness.color}`,
                      }}
                    >
                      {/* Confidence/priority dot */}
                      <div className="flex flex-col items-center pt-1.5 shrink-0">
                        <div className={`w-2 h-2 rounded-full ${dotCls}`} />
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
