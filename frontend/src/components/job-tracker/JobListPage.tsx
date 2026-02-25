import { Box, Typography, Button } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import AddIcon from '@mui/icons-material/Add';
import JobCard from './JobCard';
import LoadingSpinner from '../shared/LoadingSpinner';
import EmptyState from '../shared/EmptyState';
import { useJobList } from '../../hooks/useJobList';
import { useJobStatus } from '../../hooks/useJobStatus';
import { useAppState } from '../../context/AppContext';

export default function JobListPage() {
  const { jobs, loading } = useJobList();
  const { state } = useAppState();
  const navigate = useNavigate();

  // Subscribe to SSE for the most recent active job
  const activeJob = jobs.find((j) =>
    ['PENDING', 'SEARCHING', 'ENRICHING', 'SCORING'].includes(j.status)
  );
  useJobStatus(activeJob?.id ?? null);

  const handleJobClick = (jobId: string) => {
    const job = jobs.find((j) => j.id === jobId);
    if (job?.status === 'COMPLETED') {
      navigate(`/results?jobId=${jobId}`);
    }
  };

  if (loading && jobs.length === 0) {
    return <LoadingSpinner message="Loading jobs..." />;
  }

  return (
    <Box maxWidth={800} mx="auto">
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4">Jobs</Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => navigate('/')}
        >
          New Search
        </Button>
      </Box>

      {jobs.length === 0 ? (
        <EmptyState
          title="No jobs yet"
          description="Start a new lead search to see your jobs here."
        />
      ) : (
        jobs.map((job) => (
          <JobCard
            key={job.id}
            job={job}
            progress={state.jobProgress[job.id]}
            onClick={handleJobClick}
          />
        ))
      )}
    </Box>
  );
}
