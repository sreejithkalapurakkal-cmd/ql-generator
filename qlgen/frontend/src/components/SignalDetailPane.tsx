import React, { useState } from 'react';
import { Tooltip, Popover } from 'antd';
import {
  CloseOutlined, EyeInvisibleOutlined, LinkOutlined,
  ClockCircleOutlined, ThunderboltOutlined, StarOutlined, StarFilled,
  MailOutlined, LinkedinOutlined, FileTextOutlined,
  QuestionCircleOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { Badge, SectionLabel, SourceBadge } from './ui';
import { useDraftDrawer } from '../context/DraftDrawerContext';
import { SIGNAL_TYPE_LABELS } from '../types';
import { getSignalFreshness, FRESHNESS_DESCRIPTIONS } from '../utils/signalFreshness';

interface Signal {
  id: string;
  company_kb_id?: string;
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
  is_saved?: boolean;
}

interface SignalDetailPaneProps {
  signal: Signal;
  onClose: () => void;
  onDismiss?: (id: string) => void;
  onSave?: (id: string) => void;
  onUnsave?: (id: string) => void;
  onSnooze?: (id: string, hours: number) => void;
}

function formatDate(iso: string | null) {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

const SNOOZE_OPTIONS = [
  { label: '1 hour', hours: 1 },
  { label: '4 hours', hours: 4 },
  { label: '1 day', hours: 24 },
  { label: '3 days', hours: 72 },
  { label: '1 week', hours: 168 },
];

const CONFIDENCE_EXPLAINER: Record<string, { label: string; desc: string; color: string }> = {
  critical: { label: 'Critical', desc: 'Extremely strong signal — multiple corroborating sources confirm this event.', color: '#f5222d' },
  high: { label: 'High', desc: 'Strong signal — reliable source confirms this event with clear evidence.', color: '#fa541c' },
  medium: { label: 'Medium', desc: 'Moderate signal — some evidence found but may need verification.', color: '#faad14' },
  low: { label: 'Low', desc: 'Weak signal — limited evidence; treat as a lead for further research.', color: '#8c8c8c' },
};

const SignalDetailPane: React.FC<SignalDetailPaneProps> = ({
  signal, onClose, onDismiss, onSave, onUnsave, onSnooze,
}) => {
  const navigate = useNavigate();
  const { openDraftDrawer } = useDraftDrawer();
  const [snoozeOpen, setSnoozeOpen] = useState(false);
  const isSaved = signal.is_saved ?? false;

  const confidenceInfo = CONFIDENCE_EXPLAINER[signal.priority] || CONFIDENCE_EXPLAINER.medium;

  const snoozeContent = (
    <div className="space-y-1 min-w-[140px]">
      <p className="text-xs font-semibold text-gray-500 mb-2">Snooze for...</p>
      {SNOOZE_OPTIONS.map((opt) => (
        <button
          key={opt.hours}
          onClick={() => {
            onSnooze?.(signal.id, opt.hours);
            setSnoozeOpen(false);
          }}
          className="block w-full text-left text-sm px-2.5 py-1.5 rounded-md hover:bg-gray-100 text-gray-700 transition-colors"
        >
          {opt.label}
        </button>
      ))}
    </div>
  );

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
              {isSaved && (
                <span className="inline-flex items-center gap-0.5 text-[10px] font-medium text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded-full">
                  <StarFilled className="text-[9px]" /> Saved
                </span>
              )}
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
            <Badge variant="count">Strength: {Math.round(signal.strength * 100) / 100}%</Badge>
          )}
          <Popover
            content={
              <div className="max-w-[260px]">
                <p className="text-sm font-semibold mb-1" style={{ color: confidenceInfo.color }}>{confidenceInfo.label}</p>
                <p className="text-xs text-gray-600 leading-relaxed">{confidenceInfo.desc}</p>
              </div>
            }
            title="Confidence Level"
            trigger="click"
          >
            <button className="inline-flex items-center gap-0.5 text-[10px] text-gray-400 hover:text-brand transition-colors cursor-pointer">
              <QuestionCircleOutlined className="text-[10px]" /> What does this mean?
            </button>
          </Popover>
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

        {/* Research brief link */}
        {signal.company_kb_id && (
          <div>
            <SectionLabel>Research</SectionLabel>
            <button
              onClick={() => navigate(`/accounts/${signal.company_kb_id}/brief`)}
              className="flex items-center gap-2 w-full text-left px-3 py-2.5 bg-brand-bg border border-brand-light/20 rounded-lg text-sm text-brand font-medium hover:bg-brand-pale transition-colors"
            >
              <FileTextOutlined className="text-sm" />
              View research brief
            </button>
          </div>
        )}

        {/* Actions */}
        <div>
          <SectionLabel>Actions</SectionLabel>
          <div className="flex flex-wrap gap-2">
            {/* Save / Unsave */}
            {(onSave || onUnsave) && (
              <button
                onClick={() => isSaved ? onUnsave?.(signal.id) : onSave?.(signal.id)}
                className={`flex items-center gap-1.5 h-8 px-3 text-xs font-medium rounded-md border transition-colors ${
                  isSaved
                    ? 'border-amber-200 bg-amber-50 text-amber-700 hover:bg-amber-100'
                    : 'border-gray-200 bg-white text-gray-600 hover:bg-gray-50'
                }`}
              >
                {isSaved ? <StarFilled className="text-amber-500" /> : <StarOutlined />}
                {isSaved ? 'Saved' : 'Save'}
              </button>
            )}

            {/* Snooze */}
            {onSnooze && (
              <Popover
                content={snoozeContent}
                trigger="click"
                open={snoozeOpen}
                onOpenChange={setSnoozeOpen}
                placement="bottomLeft"
              >
                <button className="flex items-center gap-1.5 h-8 px-3 text-xs font-medium rounded-md border border-gray-200 bg-white text-gray-600 hover:bg-gray-50 transition-colors">
                  <ClockCircleOutlined /> Snooze
                </button>
              </Popover>
            )}

            {/* Dismiss */}
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

        {/* Outreach actions */}
        {signal.company_kb_id && (
          <div>
            <SectionLabel>Draft outreach</SectionLabel>
            <div className="flex flex-col gap-2">
              <button
                onClick={() => openDraftDrawer({
                  companyKbId: signal.company_kb_id!,
                  companyName: signal.company_name || undefined,
                  domain: signal.domain || undefined,
                  signalId: signal.id,
                  signalTitle: signal.title,
                  signalType: signal.signal_type,
                  format: 'email',
                })}
                className="flex items-center gap-2 w-full text-left h-9 px-3 text-xs font-medium rounded-md border border-brand-light/30 bg-brand-bg text-brand hover:bg-brand-pale transition-colors"
              >
                <MailOutlined className="text-sm" /> Draft email outreach
              </button>
              <button
                onClick={() => openDraftDrawer({
                  companyKbId: signal.company_kb_id!,
                  companyName: signal.company_name || undefined,
                  domain: signal.domain || undefined,
                  signalId: signal.id,
                  signalTitle: signal.title,
                  signalType: signal.signal_type,
                  format: 'linkedin',
                })}
                className="flex items-center gap-2 w-full text-left h-9 px-3 text-xs font-medium rounded-md border border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100 transition-colors"
              >
                <LinkedinOutlined className="text-sm" /> Draft LinkedIn message
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default SignalDetailPane;
