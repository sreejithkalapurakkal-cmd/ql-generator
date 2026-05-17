import React from 'react';
import type { BriefSectionSource } from '../../types';

interface SourceCitationChipProps {
  source: BriefSectionSource;
  index: number;
  isHighlighted?: boolean;
  chipRef?: (el: HTMLSpanElement | null) => void;
}

/**
 * Clickable source citation chip shown below brief sections.
 * Renders source label + source class (monospace) with optional external link.
 */
const SourceCitationChip: React.FC<SourceCitationChipProps> = ({
  source,
  index,
  isHighlighted = false,
  chipRef,
}) => {
  const chip = (
    <span
      ref={chipRef}
      className={`inline-flex items-center gap-1 text-[10px] border px-2 py-0.5 rounded-full transition-all duration-300 ${
        isHighlighted
          ? 'bg-purple-50 border-purple-300 text-purple-700 ring-2 ring-purple-200 ring-offset-1'
          : source.url
          ? 'bg-gray-50 border-gray-100 text-gray-400 hover:border-purple-200 hover:text-purple-600 hover:bg-purple-50 cursor-pointer'
          : 'bg-gray-50 border-gray-100 text-gray-400'
      }`}
    >
      <svg className="w-2.5 h-2.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
      </svg>
      {source.label}
      <span className="text-gray-300">·</span>
      <span className="font-mono">{source.source_class}</span>
    </span>
  );

  if (source.url) {
    return (
      <a
        href={source.url}
        target="_blank"
        rel="noopener noreferrer"
        onClick={(e) => e.stopPropagation()}
      >
        {chip}
      </a>
    );
  }

  return chip;
};

export default SourceCitationChip;
