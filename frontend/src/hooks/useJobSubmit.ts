import { useState } from 'react';
import { jobService } from '../services/jobService';
import { useAppState } from '../context/AppContext';
import type { ICPFormData } from '../types/icp';
import type { Job } from '../types/job';

export function useJobSubmit() {
  const { dispatch } = useAppState();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submitJob = async (data: ICPFormData): Promise<Job | null> => {
    setLoading(true);
    setError(null);
    try {
      const job = await jobService.createJob(data);
      dispatch({ type: 'ADD_JOB', payload: job });
      dispatch({ type: 'SET_ACTIVE_JOB', payload: job.id });
      return job;
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to submit job';
      setError(message);
      return null;
    } finally {
      setLoading(false);
    }
  };

  return { submitJob, loading, error };
}
