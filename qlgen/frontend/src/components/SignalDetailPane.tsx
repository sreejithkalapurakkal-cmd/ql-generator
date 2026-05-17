import React from 'react';
import { Tooltip } from 'antd';
import {
  CloseOutlined, EyeInvisibleOutlined, LinkOutlined,
  ClockCircleOutlined, ThunderboltOutlined,
} from '@ant-design/icons';
import { Badge, SectionLabel, SourceBadge } from './ui';
import { SIGNAL_TYPE_LABELS } from '../types';
import { getSignalFreshness, FRESHNESS_DESCRIPTIONS } from '../utils/signalFreshness';

interface Signal {
  id: string;
  signal_type: string;
  priority: string;
  title: string;
  summary: string | null;
  source_url: string | null;
  source_tool: string | null;
  detected_at: string | null;
  evidence_date: string | null;
  created_at: string | null;
  company_name: string | null;
  domain: string | null;
  strength?: number;
}

interface SignalDetailPaneProps {
  signal: Signal;
  onClose: () => void;
  onDismiss?: (id: string) => void;
}

function formatDate(iso: string | null) {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

const SignalDetailPane: React.FC<SignalDetailPaneProps> = ({
  signal, onClose, onDismiss,
}) => {
  return (
    <div className="flex flex-col h-full">
      {/* Pinned header */}
      <div className="shrink-0 px-5 pt-4 pb-3 border-b border-gray-100 bg-white">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-gray-900 truncate">
              {signal.company_name || 'Unknown Company'}
            </p>
            {signal.domain && (
              <a
                href={`https://${signal.domain}`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-0.5 text-xs text-gray-400 hover:text-brand transition-colors mt-0.5"
              >
                {signal.domain}
                <LinkOutlined className="text-[10px]" />
              </a>
            )}
          </div>
          <button
            onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded-md text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors shrink-0"
          >
            <CloseOutlined className="text-sm" />
          </button>
        </div>

        {/* Agent attribution + freshness */}
        {(() => {
          const freshness = getSignalFreshness(signal.evidence_date, signal.detected_at || signal.created_at);
          return (
            <div className="flex items-center gap-1.5 mt-2">
              <span className="inline-flex items-center gap-1 text-[10px] font-semibold bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded-full">
                <ThunderboltOutlined className="text-[9px]" />Signal Agent
              </span>
              <Tooltip title={FRESHNESS_DESCRIPTIONS[freshness.tier]}>
                <span
                  className="inline-flex items-center text-[10px] font-medium px-1.5 py-0.5 rounded-full"
                  style={{ color: freshness.color, background: freshness.bgColor }}
                >
                  {freshness.label}
                </span>
              </Tooltip>
            </div>
          );
        })()}
      </div>

      {/* Scrollable body */}
      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
        {/* Badges */}
        <div className="flex items-center gap-1.5 flex-wrap">
          <Badge variant="signal-type" signalType={signal.signal_type}>
            {SIGNAL_TYPE_LABELS[signal.signal_type] || signal.signal_type}
          </Badge>
          <Badge variant="priority" priority={signal.priority}>
            {signal.priority}
          </Badge>
          {signal.strength != null && signal.strength > 0 && (
            <Badge variant="count">Strength: {Math.round(signal.strength * 100)}%</Badge>
          )}
        </div>

        {/* Time */}
        <div className="flex items-center gap-1.5 text-xs text-gray-400">
          <ClockCircleOutlined className="text-[11px]" />
          {formatDate(signal.detected_at || signal.created_at)}
        </div>

        {/* Title */}
        <div>
          <SectionLabel>Signal headline</SectionLabel>
          <p className="text-base font-semibold text-gray-900 leading-snug">{signal.title}</p>
        </div>

        {/* Summary / Why this matters */}
        {signal.summary && (
          <div>
            <SectionLabel>Why this matters</SectionLabel>
            <p className="text-sm text-gray-700 leading-relaxed bg-gray-50 border border-gray-100 rounded-lg px-3 py-2.5">
              {signal.summary}
            </p>
          </div>
        )}

        {/* Source */}
        {(signal.source_tool || signal.source_url) && (
          <div>
            <SectionLabel>Source</SectionLabel>
            <div className="flex items-center gap-2 p-3 bg-gray-50 rounded-lg border border-gray-100">
              {signal.source_tool && (
                <span className="text-xs font-mono bg-white border border-gray-200 px-1.5 py-0.5 rounded-md text-gray-500">
                  {signal.source_tool}
                </span>
              )}
              <SourceBadge sourceUrl={signal.source_url} />
            </div>
          </div>
        )}

        {/* Evidence date */}
        {signal.evidence_date && (
          <div>
            <SectionLabel>Evidence date</SectionLabel>
            <p className="text-sm text-gray-600">{signal.evidence_date}</p>
          </div>
        )}

        {/* Actions */}
        <div>
          <SectionLabel>Actions</SectionLabel>
          <div className="flex flex-wrap gap-2">
            {onDismiss && (
              <button
                onClick={() => onDismiss(signal.id)}
                className="flex items-center gap-1.5 h-8 px-3 text-xs font-medium rounded-md border border-gray-200 bg-white text-gray-600 hover:bg-gray-50 transition-colors"
              >
                <EyeInvisibleOutlined /> Dismiss
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default SignalDetailPane;
