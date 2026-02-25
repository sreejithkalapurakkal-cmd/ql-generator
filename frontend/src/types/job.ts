export type JobStatus = 'PENDING' | 'SEARCHING' | 'ENRICHING' | 'SCORING' | 'COMPLETED' | 'FAILED';

export interface Job {
  id: string;
  status: JobStatus;
  maxResults: number;
  errorMessage: string | null;
  leadCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface JobProgress {
  stage: string;
  message: string;
  progress: number;
}
