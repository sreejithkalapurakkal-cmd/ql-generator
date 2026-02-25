import { useEffect, useRef } from 'react';
import { connectSSE } from '../services/sseClient';
import { useAppState } from '../context/AppContext';
import { jobService } from '../services/jobService';

export function useJobStatus(jobId: string | null) {
  const { dispatch } = useAppState();
  const cleanupRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    if (!jobId) return;

    cleanupRef.current = connectSSE(jobId, {
      onStatus: (progress) => {
        dispatch({
          type: 'UPDATE_PROGRESS',
          payload: { jobId, progress },
        });
      },
      onComplete: async ({ totalLeads }) => {
        dispatch({
          type: 'UPDATE_PROGRESS',
          payload: {
            jobId,
            progress: { stage: 'COMPLETED', message: `Found ${totalLeads} leads`, progress: 100 },
          },
        });
        // Refresh job details
        try {
          const job = await jobService.getJob(jobId);
          dispatch({ type: 'UPDATE_JOB', payload: job });
        } catch {
          // ignore
        }
      },
      onError: (message) => {
        dispatch({
          type: 'UPDATE_PROGRESS',
          payload: {
            jobId,
            progress: { stage: 'FAILED', message, progress: 0 },
          },
        });
      },
    });

    return () => {
      cleanupRef.current?.();
    };
  }, [jobId, dispatch]);
}
