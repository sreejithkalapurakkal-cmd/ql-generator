import { useEffect, useState } from 'react';
import { jobService } from '../services/jobService';
import { useAppState } from '../context/AppContext';
import type { Lead } from '../types/lead';

export function useJobResults(jobId: string | null) {
  const { state, dispatch } = useAppState();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const leads: Lead[] = jobId ? (state.leads[jobId] ?? []) : [];

  const fetchLeads = async () => {
    if (!jobId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await jobService.getLeads(jobId);
      dispatch({ type: 'SET_LEADS', payload: { jobId, leads: data } });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to fetch leads';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (jobId) {
      fetchLeads();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  return { leads, loading, error, refetch: fetchLeads };
}
