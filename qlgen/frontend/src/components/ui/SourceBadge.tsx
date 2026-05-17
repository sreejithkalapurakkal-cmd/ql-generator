import React from 'react';
import { LinkOutlined, WarningOutlined } from '@ant-design/icons';

interface SourceBadgeProps {
  sourceUrl: string | null | undefined;
  className?: string;
}

const extractDomain = (url: string): string => {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url.length > 30 ? url.slice(0, 30) + '...' : url;
  }
};

const SourceBadge: React.FC<SourceBadgeProps> = ({ sourceUrl, className = '' }) => {
  if (sourceUrl) {
    return (
      <a
        href={sourceUrl}
        target="_blank"
        rel="noopener noreferrer"
        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-blue-50 text-blue-700 hover:bg-blue-100 transition-colors ${className}`}
      >
        <LinkOutlined className="text-[10px]" />
        {extractDomain(sourceUrl)}
      </a>
    );
  }

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-50 text-amber-600 ${className}`}>
      <WarningOutlined className="text-[10px]" />
      No source
    </span>
  );
};

export default SourceBadge;
