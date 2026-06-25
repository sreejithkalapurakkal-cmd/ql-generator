import React, { useState, useEffect } from 'react';
import { CloseOutlined } from '@ant-design/icons';

type BannerType = 'info' | 'warning' | 'error' | 'success';

interface BannerProps {
  type: BannerType;
  message: string;
  dismissible?: boolean;
  onDismiss?: () => void;
  storageKey?: string;
  icon?: React.ReactNode;
  className?: string;
}

const TYPE_CLASSES: Record<BannerType, { bg: string; border: string; text: string; icon: string }> = {
  info: {
    bg: 'bg-blue-50',
    border: 'border-blue-200',
    text: 'text-blue-800',
    icon: 'text-blue-500',
  },
  warning: {
    bg: 'bg-amber-50',
    border: 'border-amber-200',
    text: 'text-amber-800',
    icon: 'text-amber-500',
  },
  error: {
    bg: 'bg-red-50',
    border: 'border-red-200',
    text: 'text-red-800',
    icon: 'text-red-500',
  },
  success: {
    bg: 'bg-green-50',
    border: 'border-green-200',
    text: 'text-green-800',
    icon: 'text-green-500',
  },
};

const Banner: React.FC<BannerProps> = ({
  type,
  message,
  dismissible = true,
  onDismiss,
  storageKey,
  icon,
  className = '',
}) => {
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (storageKey) {
      const stored = localStorage.getItem(`banner-dismissed-${storageKey}`);
      if (stored === 'true') setDismissed(true);
    }
  }, [storageKey]);

  if (dismissed) return null;

  const cls = TYPE_CLASSES[type];

  const handleDismiss = () => {
    setDismissed(true);
    if (storageKey) {
      localStorage.setItem(`banner-dismissed-${storageKey}`, 'true');
    }
    onDismiss?.();
  };

  return (
    <div
      className={`flex items-center gap-2 px-4 py-2.5 rounded-lg border text-sm ${cls.bg} ${cls.border} ${className}`}
    >
      {icon && <span className={`${cls.icon} shrink-0`}>{icon}</span>}
      <span className={`${cls.text} flex-1 font-medium`}>{message}</span>
      {dismissible && (
        <button
          onClick={handleDismiss}
          className={`${cls.icon} shrink-0 hover:opacity-70 transition-opacity`}
          aria-label="Dismiss"
        >
          <CloseOutlined className="text-xs" />
        </button>
      )}
    </div>
  );
};

export default Banner;
