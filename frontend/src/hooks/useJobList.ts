import { useEffect, useState } from 'react';
import { jobService } from '../services/jobService';
import { useAppState } from '../context/AppContext';

export function useJobList() {
  const { state, dispatch } = useAppState();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchJobs = async () => {
    setLoading(true);
    setError(null);
    try {
      const jobs = await jobService.getJobs();
      dispatch({ type: 'SET_JOBS', payload: jobs });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to fetch jobs';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { jobs: state.jobs, loading, error, refetch: fetchJobs };
}
