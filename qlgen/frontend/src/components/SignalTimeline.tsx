import React, { useEffect, useState, useRef, useCallback } from 'react';
import { Button, Spin, Tooltip, Progress, message } from 'antd';
import {
  ThunderboltOutlined, EyeInvisibleOutlined, ReloadOutlined,
  StarOutlined, StarFilled, ClockCircleOutlined as ClockIcon,
} from '@ant-design/icons';
import { Badge, EmptyState, SectionLabel, SourceBadge } from './ui';
import {
  getCompanySignals, dismissSignal, saveSignal, unsaveSignal, snoozeSignal,
  startDetectSignals, getSignalDetectionStreamUrl,
} from '../api/signalApi';
import {
  SignalEvent, SIGNAL_TYPE_LABELS, SIGNAL_PRIORITY_COLORS,
} from '../types';
import { getSignalFreshness, FRESHNESS_DESCRIPTIONS } from '../utils/signalFreshness';

interface SignalTimelineProps {
  companyKbId: string;
  companyName?: string;
  showDetectButton?: boolean;
}

const PRIORITY_DOT_CLS: Record<string, string> = {
  critical: 'bg-red-500',
  high: 'bg-orange-500',
  medium: 'bg-amber-400',
  low: 'bg-gray-300',
};

const SignalTimeline: React.FC<SignalTimelineProps> = ({
  companyKbId, companyName, showDetectButton = true,
}) => {
  const [signals, setSignals] = useState<SignalEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [detecting, setDetecting] = useState(false);
  const [detectionProgress, setDetectionProgress] = useState(0);
  const [detectionLabel, setDetectionLabel] = useState('');
  const [detectionSignals, setDetectionSignals] = useState(0);
  const esRef = useRef<EventSource | null>(null);

  const fetchSignals = useCallback(() => {
    setLoading(true);
    getCompanySignals(companyKbId, { limit: 50 })
      .then((res) => setSignals(res.data.signals || []))
      .catch(() => setSignals([]))
      .finally(() => setLoading(false));
  }, [companyKbId]);

  useEffect(() => { fetchSignals(); }, [fetchSignals]);

  // Clean up SSE on unmount
  useEffect(() => {
    return () => { esRef.current?.close(); };
  }, []);

  const handleDetect = async () => {
    try {
      const res = await startDetectSignals(companyKbId);
      const runId = res.data.run_id;

      // Connect to SSE stream
      esRef.current?.close();
      setDetecting(true);
      setDetectionProgress(0);
      setDetectionLabel('Starting...');
      setDetectionSignals(0);

      const url = getSignalDetectionStreamUrl(companyKbId, runId);
      const es = new EventSource(url);
      esRef.current = es;

      es.addEventListener('signal_progress', (e) => {
        const data = JSON.parse(e.data);
        setDetectionProgress(data.percent || 0);
        setDetectionLabel(data.label || '');
        setDetectionSignals(data.signals_found || 0);
      });

      es.addEventListener('signal_detection_completed', (e) => {
        const data = JSON.parse(e.data);
        setDetecting(false);
        setDetectionProgress(100);
        message.success(`${data.signals_detected} signals detected`);
        fetchSignals();
        es.close();
      });

      es.addEventListener('signal_detection_failed', (e) => {
        const data = JSON.parse(e.data);
        setDetecting(false);
        message.error(data.message || 'Signal detection failed');
        es.close();
      });

      es.addEventListener('timeout', () => {
        setDetecting(false);
        message.warning('Signal detection timed out');
        fetchSignals();
        es.close();
      });

      es.onerror = () => {
        if (es.readyState === EventSource.CLOSED && esRef.current === es) {
          setDetecting(false);
        }
      };
    } catch {
      message.error('Failed to start signal detection');
    }
  };

  const handleDismiss = async (signalId: string) => {
    try {
      await dismissSignal(signalId);
      setSignals((prev) => prev.filter((s) => s.id !== signalId));
    } catch {
      message.error('Failed to dismiss');
    }
  };

  const handleSave = async (signalId: string) => {
    try {
      await saveSignal(signalId);
      setSignals((prev) => prev.map((s) => s.id === signalId ? { ...s, is_saved: true } : s));
    } catch {
      message.error('Failed to save');
    }
  };

  const handleUnsave = async (signalId: string) => {
    try {
      await unsaveSignal(signalId);
      setSignals((prev) => prev.map((s) => s.id === signalId ? { ...s, is_saved: false } : s));
    } catch {
      message.error('Failed to unsave');
    }
  };

  const formatDate = (iso: string | null) => {
    if (!iso) return '';
    return new Date(iso).toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric',
    });
  };

  // Group signals by month (using evidence_date — when the event actually occurred)
  const grouped: Record<string, SignalEvent[]> = {};
  signals.forEach((s) => {
    const date = s.evidence_date || s.detected_at || s.created_at || '';
    const key = date ? new Date(date).toLocaleDateString('en-US', { month: 'long', year: 'numeric' }) : 'Unknown';
    if (!grouped[key]) grouped[key] = [];
    grouped[key].push(s);
  });

  if (loading) {
    return <div className="flex justify-center py-10"><Spin /></div>;
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-gray-900">Signal Timeline</h3>
          {companyName && (
            <span className="text-sm text-gray-400">{companyName}</span>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          {showDetectButton && (
            <Button
              size="small"
              icon={<ThunderboltOutlined />}
              loading={detecting}
              onClick={handleDetect}
              className="!rounded-md !text-xs"
            >
              Detect
            </Button>
          )}
          <Tooltip title="Refresh">
            <Button
              size="small"
              icon={<ReloadOutlined />}
              onClick={fetchSignals}
              className="!rounded-md"
            />
          </Tooltip>
        </div>
      </div>

      {/* Detection Progress */}
      {detecting && (
        <div className="flex items-center gap-3 px-4 py-3 bg-brand-bg rounded-lg border border-brand-light/20 mb-4">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <ThunderboltOutlined className="text-brand" />
              <span className="text-sm font-semibold text-brand">Detecting Signals...</span>
              {detectionLabel && (
                <span className="text-xs text-gray-500">{detectionLabel}</span>
              )}
            </div>
            <Progress
              percent={detectionProgress}
              strokeColor="#5C2D8F"
              size="small"
              className="!mb-0.5"
            />
            <span className="text-xs text-gray-500">{detectionSignals} signal{detectionSignals !== 1 ? 's' : ''} found so far</span>
          </div>
        </div>
      )}

      {signals.length === 0 ? (
        <EmptyState
          icon={<ThunderboltOutlined />}
          title="No signals detected yet"
          description="Run signal detection to find recent company activity."
          className="py-8"
        />
      ) : (
        <div className="relative pl-5">
          {/* Vertical timeline line */}
          <div className="absolute left-[5px] top-0 bottom-0 w-0.5 bg-gray-200" />

          {Object.entries(grouped).map(([month, monthSignals]) => (
            <div key={month} className="mb-5">
              {/* Month label */}
              <div className="relative -ml-5 pl-5 mb-2.5">
                <div className="absolute left-0.5 top-0.5 w-2.5 h-2.5 rounded-full bg-gray-200 z-10" />
                <SectionLabel className="!mb-0">{month}</SectionLabel>
              </div>

              {/* Signal items */}
              {monthSignals.map((signal) => {
                const dotCls = PRIORITY_DOT_CLS[signal.priority] || 'bg-gray-300';
                const freshness = getSignalFreshness(signal.evidence_date, signal.detected_at);
                return (
                  <div key={signal.id} className="relative mb-2.5 group">
                    {/* Dot on timeline */}
                    <div className={`absolute -left-[17px] top-3.5 w-2 h-2 rounded-full ${dotCls} z-10 ring-2 ring-white`} />

                    {/* Card */}
                    <div
                      className="bg-white border border-gray-200 rounded-lg p-3 hover:border-gray-300 transition-colors"
                      style={{ borderLeftWidth: 3, borderLeftColor: freshness.color }}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex-1 min-w-0">
                          {/* Badges + freshness */}
                          <div className="flex items-center gap-1.5 mb-1.5 flex-wrap">
                            <Badge variant="signal-type" signalType={signal.signal_type}>
                              {SIGNAL_TYPE_LABELS[signal.signal_type] || signal.signal_type}
                            </Badge>
                            <Badge variant="priority" priority={signal.priority}>
                              {signal.priority}
                            </Badge>
                            <Tooltip title={FRESHNESS_DESCRIPTIONS[freshness.tier]}>
                              <span
                                className="inline-flex items-center text-[10px] font-medium px-1.5 py-0.5 rounded-full ml-auto shrink-0"
                                style={{ color: freshness.color, background: freshness.bgColor }}
                              >
                                {freshness.label}
                              </span>
                            </Tooltip>
                          </div>

                          {/* Title */}
                          <p className="text-sm font-medium text-gray-900 leading-snug mb-1">
                            {signal.title}
                          </p>

                          {/* Summary */}
                          {signal.summary && (
                            <p className="text-xs text-gray-500 leading-relaxed line-clamp-2 mb-2">
                              {signal.summary}
                            </p>
                          )}

                          {/* Source meta */}
                          <div className="flex items-center gap-2 text-[11px] text-gray-400">
                            {signal.source_tool && (
                              <span className="font-mono bg-gray-100 px-1.5 py-0.5 rounded">
                                {signal.source_tool}
                              </span>
                            )}
                            <SourceBadge sourceUrl={signal.source_url} />
                            <span>{formatDate(signal.detected_at)}</span>
                          </div>
                        </div>

                        {/* Save/Unsave + Dismiss */}
                        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-all shrink-0">
                          <Tooltip title={signal.is_saved ? 'Unsave' : 'Save'}>
                            <button
                              onClick={() => signal.is_saved ? handleUnsave(signal.id) : handleSave(signal.id)}
                              className={`w-6 h-6 flex items-center justify-center rounded transition-colors ${
                                signal.is_saved ? 'text-amber-400' : 'text-gray-300 hover:text-gray-500 hover:bg-gray-100'
                              }`}
                            >
                              {signal.is_saved ? <StarFilled /> : <StarOutlined />}
                            </button>
                          </Tooltip>
                          <Tooltip title="Dismiss">
                            <button
                              onClick={() => handleDismiss(signal.id)}
                              className="w-6 h-6 flex items-center justify-center rounded text-gray-300 hover:text-gray-500 hover:bg-gray-100 transition-all"
                            >
                              <EyeInvisibleOutlined />
                            </button>
                          </Tooltip>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default SignalTimeline;
