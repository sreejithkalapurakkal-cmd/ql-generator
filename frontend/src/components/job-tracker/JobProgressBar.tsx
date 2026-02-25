import { Box, LinearProgress, Typography } from '@mui/material';
import type { JobProgress } from '../../types/job';

interface Props {
  progress: JobProgress | undefined;
}

const stageOrder = ['SEARCHING', 'ENRICHING', 'SCORING', 'COMPLETED'];

export default function JobProgressBar({ progress }: Props) {
  if (!progress) return null;

  const percentage = progress.progress;
  const currentStageIndex = stageOrder.indexOf(progress.stage);

  return (
    <Box sx={{ width: '100%' }}>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={0.5}>
        <Typography variant="caption" color="text.secondary">
          {progress.message}
        </Typography>
        <Typography variant="caption" fontWeight={600}>
          {percentage}%
        </Typography>
      </Box>
      <LinearProgress
        variant="determinate"
        value={percentage}
        sx={{ height: 8, borderRadius: 4 }}
      />
      <Box display="flex" justifyContent="space-between" mt={1}>
        {stageOrder.map((stage, i) => (
          <Typography
            key={stage}
            variant="caption"
            sx={{
              fontWeight: i <= currentStageIndex ? 600 : 400,
              color: i <= currentStageIndex ? 'primary.main' : 'text.disabled',
            }}
          >
            {stage.charAt(0) + stage.slice(1).toLowerCase()}
          </Typography>
        ))}
      </Box>
    </Box>
  );
}
