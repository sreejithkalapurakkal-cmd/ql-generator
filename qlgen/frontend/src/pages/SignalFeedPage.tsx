import React, { useEffect, useState, useCallback } from 'react';
import { Select, Spin, Tooltip, message } from 'antd';
import {
  ReloadOutlined, EyeInvisibleOutlined, ThunderboltOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { PillTabs, Badge, EmptyState, SourceBadge } from '../components/ui';
import SignalDetailPane from '../components/SignalDetailPane';
import { getSignalFeed, dismissSignal, type SignalFeedResponse } from '../api/signalApi';
import { SIGNAL_TYPE_LABELS } from '../types';
import { getSignalFreshness, FRESHNESS_DESCRIPTIONS } from '../utils/signalFreshness';

const PRIORITY_DOT_CLS: Record<string, string> = {
  critical: 'bg-red-500',
  high: 'bg-orange-500',
  medium: 'bg-amber-400',
  low: 'bg-gray-300',
};

const SignalFeedPage: React.FC = () => {
  const navigate = useNavigate();
  const [signals, setSignals] = useState<SignalFeedResponse['signals']>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [typeFilter, setTypeFilter] = useState<string | undefined>(undefined);
  const [priorityFilter, setPriorityFilter] = useState<string | undefined>(undefined);
  const [offset, setOffset] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const limit = 50;

  const fetchFeed = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getSignalFeed({
        signal_type: typeFilter,
        priority: priorityFilter,
        limit,
        offset,
      });
      setSignals(res.data.signals || []);
      setTotal(res.data.total || 0);
    } catch {
      setSignals([]);
    } finally {
      setLoading(false);
    }
  }, [typeFilter, priorityFilter, offset]);

  useEffect(() => { fetchFeed(); }, [fetchFeed]);

  const handleDismiss = async (signalId: string) => {
    try {
      await dismissSignal(signalId);
      setSignals((prev) => prev.filter((s) => s.id !== signalId));
      if (selectedId === signalId) setSelectedId(null);
      message.success('Signal dismissed');
    } catch {
      message.error('Failed to dismiss');
    }
  };

  const signalTypeOptions = Object.entries(SIGNAL_TYPE_LABELS).map(([k, v]) => ({
    value: k, label: v,
  }));

  const selectedSignal = signals.find((s) => s.id === selectedId) || null;

  return (
    <div className="px-10 py-8 max-w-[1400px] mx-auto">
      {/* Secondary nav */}
      <PillTabs
        tabs={[
          { key: 'lists', label: 'My Lists' },
          { key: 'feed', label: 'Signal Feed' },
        ]}
        activeKey="feed"
        onChange={(v) => { if (v === 'lists') navigate('/tracking'); }}
        className="mb-6"
      />

      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Signal Feed</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Recent signals across all your tracked companies
          </p>
        </div>
        <Tooltip title="Refresh">
          <button
            onClick={fetchFeed}
            className="w-8 h-8 flex items-center justify-center rounded-md text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors"
          >
            <ReloadOutlined />
          </button>
        </Tooltip>
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
                title="No signals yet"
                description="Signals will appear here when you detect them for tracked companies."
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
            />
          </div>
        )}
      </div>
    </div>
  );
};

export default SignalFeedPage;
