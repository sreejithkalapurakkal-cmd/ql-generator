import { Card, CardContent, CardActionArea, Typography, Box } from '@mui/material';
import JobStatusBadge from './JobStatusBadge';
import JobProgressBar from './JobProgressBar';
import { formatDate } from '../../lib/formatters';
import type { Job, JobProgress } from '../../types/job';

interface Props {
  job: Job;
  progress?: JobProgress;
  onClick: (jobId: string) => void;
}

export default function JobCard({ job, progress, onClick }: Props) {
  const isActive = ['SEARCHING', 'ENRICHING', 'SCORING', 'PENDING'].includes(job.status);

  return (
    <Card variant="outlined" sx={{ mb: 2 }}>
      <CardActionArea onClick={() => onClick(job.id)}>
        <CardContent>
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
            <Typography variant="subtitle1" fontWeight={600}>
              Job #{job.jobNumber || job.id.slice(0, 8)}
            </Typography>
            <JobStatusBadge status={job.status} />
          </Box>

          <Typography variant="body2" color="text.secondary">
            Created: {formatDate(job.createdAt)}
          </Typography>

          {job.status === 'COMPLETED' && (
            <Typography variant="body2" color="success.main" sx={{ mt: 0.5 }}>
              {job.leadCount} leads found
            </Typography>
          )}

          {job.status === 'FAILED' && job.errorMessage && (
            <Typography variant="body2" color="error" sx={{ mt: 0.5 }}>
              {job.errorMessage}
            </Typography>
          )}

          {isActive && progress && (
            <Box sx={{ mt: 2 }}>
              <JobProgressBar progress={progress} />
            </Box>
          )}
        </CardContent>
      </CardActionArea>
    </Card>
  );
}
