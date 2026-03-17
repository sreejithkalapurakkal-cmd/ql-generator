import React from 'react';
import type { RecommendationItem } from '../types';

const ICON_MAP: Record<string, string> = {
  'fire': '\u{1F525}',
  'bar-chart': '\u{1F4CA}',
  'search': '\u{1F50D}',
  'contacts': '\u{1F464}',
  'database': '\u{1F4BE}',
  'trophy': '\u{1F3C6}',
  'pie-chart': '\u{1F4C8}',
  'global': '\u{1F30D}',
  'experiment': '\u{1F9EA}',
  'bulb': '\u{1F4A1}',
  'swap': '\u{1F504}',
  'plus-circle': '\u{2795}',
  'question-circle': '\u{2753}',
};

interface Props {
  recommendations: RecommendationItem[];
  onSelect: (prompt: string) => void;
}

const CoPilotRecommendations: React.FC<Props> = ({ recommendations, onSelect }) => {
  if (recommendations.length === 0) return null;

  return (
    <div className="copilot-recs">
      <div className="copilot-recs-label">Suggestions</div>
      <div className="copilot-recs-grid">
        {recommendations.map((rec, i) => (
          <button
            key={i}
            className="copilot-rec-card"
            onClick={() => onSelect(rec.prompt)}
          >
            <span className="copilot-rec-icon">{ICON_MAP[rec.icon] || '\u{2728}'}</span>
            <span className="copilot-rec-text">{rec.text}</span>
          </button>
        ))}
      </div>
    </div>
  );
};

export default CoPilotRecommendations;
