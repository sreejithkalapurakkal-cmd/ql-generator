import React from 'react';

type BadgeVariant = 'signal-type' | 'priority' | 'confidence' | 'status' | 'count' | 'default';

interface BadgeProps {
  variant?: BadgeVariant;
  signalType?: string;
  priority?: string;
  status?: string;
  confidence?: 'high' | 'medium' | 'low';
  closable?: boolean;
  onClose?: () => void;
  children?: React.ReactNode;
  className?: string;
  dot?: boolean;
  dotColor?: string;
}

const SIGNAL_TYPE_CLASSES: Record<string, string> = {
  funding: 'bg-green-50 text-green-700',
  hiring_surge: 'bg-sky-50 text-sky-700',
  executive_change: 'bg-purple-50 text-purple-700',
  tech_adoption: 'bg-indigo-50 text-indigo-700',
  partnership: 'bg-blue-50 text-blue-700',
  product_launch: 'bg-orange-50 text-orange-700',
  expansion: 'bg-teal-50 text-teal-700',
  award: 'bg-amber-50 text-amber-700',
  earnings: 'bg-blue-50 text-blue-700',
  sec_filing: 'bg-indigo-50 text-indigo-700',
  press_release: 'bg-gray-100 text-gray-600',
  web_change: 'bg-gray-100 text-gray-600',
  acquisition: 'bg-rose-50 text-rose-700',
  regulation: 'bg-red-50 text-red-700',
  market_shift: 'bg-violet-50 text-violet-700',
};

const PRIORITY_CLASSES: Record<string, string> = {
  critical: 'bg-red-50 text-red-700',
  high: 'bg-orange-50 text-orange-700',
  medium: 'bg-amber-50 text-amber-700',
  low: 'bg-gray-100 text-gray-500',
};

const PRIORITY_DOT: Record<string, string> = {
  critical: 'bg-red-500',
  high: 'bg-orange-500',
  medium: 'bg-amber-500',
  low: 'bg-gray-400',
};

const CONFIDENCE_CLASSES: Record<string, { bg: string; text: string; dot: string; label: string }> = {
  high: { bg: 'bg-emerald-50', text: 'text-emerald-700', dot: 'bg-emerald-500', label: 'High' },
  medium: { bg: 'bg-amber-50', text: 'text-amber-700', dot: 'bg-amber-500', label: 'Medium' },
  low: { bg: 'bg-gray-100', text: 'text-gray-500', dot: 'bg-gray-400', label: 'Low' },
};

const STATUS_DOT: Record<string, string> = {
  not_started: 'bg-gray-400',
  researching: 'bg-blue-500',
  drafted: 'bg-indigo-500',
  sent: 'bg-purple-500',
  replied: 'bg-amber-500',
  meeting_booked: 'bg-teal-500',
  won: 'bg-emerald-500',
  lost: 'bg-red-500',
};

const Badge: React.FC<BadgeProps> = ({
  variant = 'default',
  signalType,
  priority,
  status,
  confidence,
  closable,
  onClose,
  children,
  className = '',
  dot,
  dotColor,
}) => {
  const base = 'inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium';

  if (variant === 'confidence' && confidence) {
    const c = CONFIDENCE_CLASSES[confidence];
    return (
      <span className={`${base} ${c.bg} ${c.text} ${className}`}>
        <span className={`w-1.5 h-1.5 rounded-full ${c.dot}`} />
        {children || c.label}
      </span>
    );
  }

  if (variant === 'signal-type' && signalType) {
    const cls = SIGNAL_TYPE_CLASSES[signalType] || 'bg-gray-100 text-gray-600';
    return <span className={`${base} ${cls} ${className}`}>{children}</span>;
  }

  if (variant === 'priority' && priority) {
    const cls = PRIORITY_CLASSES[priority] || 'bg-gray-100 text-gray-500';
    const dotCls = PRIORITY_DOT[priority] || 'bg-gray-400';
    return (
      <span className={`${base} ${cls} ${className}`}>
        <span className={`w-1.5 h-1.5 rounded-full ${dotCls}`} />
        {children}
      </span>
    );
  }

  if (variant === 'status' && status) {
    const dotCls = STATUS_DOT[status] || 'bg-gray-400';
    return (
      <span className={`${base} bg-gray-100 text-gray-600 ${className}`}>
        <span className={`w-2 h-2 rounded-full ${dotCls}`} />
        {children}
      </span>
    );
  }

  if (variant === 'count') {
    return (
      <span className={`${base} bg-gray-100 text-gray-600 ${className}`}>
        {children}
      </span>
    );
  }

  // default
  let colorCls = 'bg-gray-100 text-gray-600';
  if (dot || dotColor) {
    return (
      <span className={`${base} ${colorCls} ${className}`}>
        {(dot || dotColor) && (
          <span className={`w-1.5 h-1.5 rounded-full ${dotColor || 'bg-gray-400'}`} />
        )}
        {children}
        {closable && (
          <button
            onClick={(e) => { e.stopPropagation(); onClose?.(); }}
            className="ml-0.5 text-current opacity-60 hover:opacity-100"
          >
            &times;
          </button>
        )}
      </span>
    );
  }

  return (
    <span className={`${base} ${colorCls} ${className}`}>
      {children}
      {closable && (
        <button
          onClick={(e) => { e.stopPropagation(); onClose?.(); }}
          className="ml-0.5 text-current opacity-60 hover:opacity-100"
        >
          &times;
        </button>
      )}
    </span>
  );
};

export default Badge;
