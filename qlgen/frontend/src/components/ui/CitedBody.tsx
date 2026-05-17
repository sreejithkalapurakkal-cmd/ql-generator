import React from 'react';
import type { BriefSectionSource } from '../../types';

interface CitedBodyProps {
  text: string;
  sources?: BriefSectionSource[];
  highlightIdx: number | null;
  onCite: (idx: number) => void;
}

/**
 * Renders paragraph text with inline [N] citation badges.
 * Citations are clickable and highlight the corresponding source chip.
 */
const CitedBody: React.FC<CitedBodyProps> = ({ text, sources, highlightIdx, onCite }) => {
  const parts = text.split(/(\[\d+\])/);

  return (
    <>
      {parts.map((part, i) => {
        const m = part.match(/^\[(\d+)\]$/);
        if (m && sources) {
          const idx = parseInt(m[1]) - 1;
          const src = sources[idx];
          return (
            <button
              key={i}
              onClick={() => onCite(idx)}
              title={src?.label}
              className={`inline-flex items-center justify-center w-[18px] h-[18px] text-[10px] font-bold rounded-full mx-0.5 align-super leading-none shrink-0 transition-colors ${
                highlightIdx === idx
                  ? 'bg-purple-600 text-white'
                  : 'bg-purple-100 text-purple-700 hover:bg-purple-200'
              }`}
            >
              {m[1]}
            </button>
          );
        }
        return <span key={i}>{part}</span>;
      })}
    </>
  );
};

export default CitedBody;
