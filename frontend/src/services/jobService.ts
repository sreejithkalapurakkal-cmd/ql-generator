import api from './api';
import type { ICPFormData } from '../types/icp';
import type { Job } from '../types/job';
import type { Lead } from '../types/lead';

export const jobService = {
  createJob: async (data: ICPFormData): Promise<Job> => {
    const response = await api.post<Job>('/jobs', data);
    return response.data;
  },

  getJobs: async (): Promise<Job[]> => {
    const response = await api.get<Job[]>('/jobs');
    return response.data;
  },

  getJob: async (jobId: string): Promise<Job> => {
    const response = await api.get<Job>(`/jobs/${jobId}`);
    return response.data;
  },

  getLeads: async (jobId: string): Promise<Lead[]> => {
    const response = await api.get<Lead[]>(`/jobs/${jobId}/leads`);
    return response.data;
  },

  healthCheck: async (): Promise<boolean> => {
    try {
      await api.get('/health');
      return true;
    } catch {
      return false;
    }
  },
};
