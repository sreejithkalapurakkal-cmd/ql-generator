import React, { useEffect, useState, useCallback } from 'react';
import { Spin, Tooltip } from 'antd';
import {
  ThunderboltOutlined, SearchOutlined, LinkOutlined,
  CheckCircleFilled, ExclamationCircleFilled, FileTextOutlined,
} from '@ant-design/icons';
import { EmptyState, SectionLabel } from './ui';
import {
  getActivityFeed, type ActivityEvent, type VerbosityLevel,
} from '../api/activityApi';

interface ActivityFeedProps {
  companyKbId: string;
  maxItems?: number;
}

const EVENT_ICONS: Record<string, React.ReactNode> = {
  research_start: <SearchOutlined className="text-brand" />,
  tool_call: <SearchOutlined className="text-gray-400" />,
  signal_detected: <ThunderboltOutlined className="text-orange-500" />,
  section_generated: <FileTextOutlined className="text-blue-500" />,
  correlation_found: <LinkOutlined className="text-red-500" />,
  verification_complete: <CheckCircleFilled className="text-green-500" />,
  contact_found: <CheckCircleFilled className="text-brand" />,
  brief_ready: <FileTextOutlined className="text-green-500" />,
  research_complete: <CheckCircleFilled className="text-green-600" />,
  error: <ExclamationCircleFilled className="text-red-500" />,
};

const CATEGORY_COLORS: Record<string, string> = {
  research: '#5C2D8F',
  signal: '#fa541c',
  synthesis: '#1890ff',
  contact: '#52c41a',
  outreach: '#722ed1',
  correlation: '#f5222d',
};

const VERBOSITY_OPTIONS: { key: VerbosityLevel; label: string; desc: string }[] = [
  { key: 'summary', label: 'Summary', desc: 'Key milestones only' },
  { key: 'detailed', label: 'Detailed', desc: 'All activity with context' },
  { key: 'technical', label: 'Technical', desc: 'Full tool call traces' },
];

const ActivityFeed: React.FC<ActivityFeedProps> = ({ companyKbId, maxItems = 50 }) => {
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [verbosity, setVerbosity] = useState<VerbosityLevel>('summary');

  const fetchEvents = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getActivityFeed(companyKbId, {
        verbosity,
        limit: maxItems,
      });
      setEvents(res.data.events || []);
      setTotal(res.data.total || 0);
    } catch {
      setEvents([]);
    } finally {
      setLoading(false);
    }
  }, [companyKbId, verbosity, maxItems]);

  useEffect(() => { fetchEvents(); }, [fetchEvents]);

  const formatTime = (iso: string | null) => {
    if (!iso) return '';
    const d = new Date(iso);
    const now = Date.now();
    const diff = now - d.getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  return (
    <div>
      {/* Verbosity toggle */}
      <div className="flex items-center justify-between mb-4">
        <SectionLabel>Activity Timeline</SectionLabel>
        <div className="flex items-center gap-1">
          {VERBOSITY_OPTIONS.map((opt) => (
            <Tooltip key={opt.key} title={opt.desc}>
              <button
                onClick={() => setVerbosity(opt.key)}
                className={`h-7 px-2.5 text-[11px] font-semibold rounded-md transition-colors ${
                  verbosity === opt.key
                    ? 'bg-brand text-white'
                    : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                }`}
              >
                {opt.label}
              </button>
            </Tooltip>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-8"><Spin /></div>
      ) : events.length === 0 ? (
        <EmptyState
          icon={<SearchOutlined />}
          title="No activity yet"
          description="Activity events will appear here as research and signal detection runs."
          className="py-8"
        />
      ) : (
        <div className="relative pl-5">
          {/* Vertical timeline line */}
          <div className="absolute left-[5px] top-0 bottom-0 w-0.5 bg-gray-200" />

          {events.map((event) => {
            const icon = EVENT_ICONS[event.event_type] || <SearchOutlined className="text-gray-400" />;
            const catColor = CATEGORY_COLORS[event.event_category || ''] || '#8c8c8c';

            return (
              <div key={event.id} className="relative mb-3 group">
                {/* Dot on timeline */}
                <div className="absolute -left-[17px] top-2 z-10">
                  <div
                    className={`w-3 h-3 rounded-full ring-2 ring-white flex items-center justify-center text-[8px] ${
                      event.milestone ? 'bg-brand' : 'bg-gray-200'
                    }`}
                  />
                </div>

                {/* Event card */}
                <div className={`bg-white border rounded-lg px-3 py-2.5 transition-colors ${
                  event.milestone ? 'border-brand-light/30 bg-brand-bg/30' : 'border-gray-100'
                }`}>
                  <div className="flex items-start gap-2">
                    <span className="mt-0.5 shrink-0">{icon}</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5 mb-0.5">
                        {event.event_category && (
                          <span
                            className="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded"
                            style={{ color: catColor, background: `${catColor}15` }}
                          >
                            {event.event_category}
                          </span>
                        )}
                        <span className="text-[10px] text-gray-400 ml-auto shrink-0">
                          {formatTime(event.created_at)}
                        </span>
                      </div>
                      <p className="text-xs text-gray-800 leading-snug">
                        {event.narrative}
                      </p>

                      {/* Detailed view */}
                      {verbosity !== 'summary' && event.narrative_detail && (
                        <p className="text-[11px] text-gray-500 mt-1 leading-relaxed">
                          {event.narrative_detail}
                        </p>
                      )}

                      {/* Technical view */}
                      {verbosity === 'technical' && event.technical_detail && (
                        <pre className="text-[10px] text-gray-400 mt-1.5 bg-gray-50 rounded p-2 overflow-x-auto font-mono leading-tight">
                          {JSON.stringify(event.technical_detail, null, 2)}
                        </pre>
                      )}

                      {/* Confidence */}
                      {event.confidence != null && event.confidence > 0 && (
                        <div className="flex items-center gap-1 mt-1">
                          <div className="h-1 w-16 bg-gray-100 rounded-full overflow-hidden">
                            <div
                              className="h-full rounded-full bg-brand"
                              style={{ width: `${Math.round(event.confidence * 100)}%` }}
                            />
                          </div>
                          <span className="text-[10px] text-gray-400">{Math.round(event.confidence * 100)}%</span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}

          {total > events.length && (
            <div className="text-center text-xs text-gray-400 mt-2">
              Showing {events.length} of {total} events
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ActivityFeed;
