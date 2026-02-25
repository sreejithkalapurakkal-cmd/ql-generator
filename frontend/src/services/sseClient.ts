import type { JobProgress } from '../types/job';

export interface SSECallbacks {
  onStatus: (progress: JobProgress) => void;
  onComplete: (data: { totalLeads: number }) => void;
  onError: (message: string) => void;
}

export function connectSSE(jobId: string, callbacks: SSECallbacks): () => void {
  let retries = 0;
  const maxRetries = 5;
  let eventSource: EventSource | null = null;

  function connect() {
    eventSource = new EventSource(`/api/v1/jobs/${jobId}/stream`);

    eventSource.addEventListener('status', (e: MessageEvent) => {
      retries = 0;
      const data = JSON.parse(e.data) as JobProgress;
      callbacks.onStatus(data);
    });

    eventSource.addEventListener('complete', (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      callbacks.onComplete({ totalLeads: data.totalLeads });
      eventSource?.close();
    });

    eventSource.addEventListener('error', (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      callbacks.onError(data.message);
      eventSource?.close();
    });

    eventSource.onerror = () => {
      eventSource?.close();
      if (retries < maxRetries) {
        const delay = Math.min(1000 * 2 ** retries, 30000);
        retries++;
        setTimeout(connect, delay);
      }
    };
  }

  connect();

  return () => {
    eventSource?.close();
  };
}
