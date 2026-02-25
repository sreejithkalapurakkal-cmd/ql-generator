import { Box, Typography, LinearProgress } from '@mui/material';
import type { BANTScore } from '../../types/lead';
import { formatScore } from '../../lib/formatters';

interface Props {
  score: BANTScore;
}

const dimensions = [
  { key: 'budget' as const, label: 'Budget', color: '#1976d2' },
  { key: 'authority' as const, label: 'Authority', color: '#9c27b0' },
  { key: 'need' as const, label: 'Need', color: '#2e7d32' },
  { key: 'timeline' as const, label: 'Timeline', color: '#ed6c02' },
];

export default function BANTScoreCard({ score }: Props) {
  return (
    <Box>
      <Typography variant="subtitle2" gutterBottom>
        BANT Score: {formatScore(score.total)}/10
      </Typography>
      {dimensions.map(({ key, label, color }) => (
        <Box key={key} display="flex" alignItems="center" gap={1} mb={0.5}>
          <Typography variant="caption" sx={{ minWidth: 65, color }}>
            {label}
          </Typography>
          <LinearProgress
            variant="determinate"
            value={(score[key] / 10) * 100}
            sx={{
              flex: 1,
              height: 6,
              borderRadius: 3,
              '& .MuiLinearProgress-bar': { backgroundColor: color },
              backgroundColor: `${color}20`,
            }}
          />
          <Typography variant="caption" sx={{ minWidth: 30, textAlign: 'right' }}>
            {formatScore(score[key])}
          </Typography>
        </Box>
      ))}
    </Box>
  );
}
