import React, { createContext, useContext, useReducer } from 'react';
import type { Job, JobProgress } from '../types/job';
import type { Lead } from '../types/lead';

interface AppState {
  jobs: Job[];
  activeJobId: string | null;
  jobProgress: Record<string, JobProgress>;
  leads: Record<string, Lead[]>;
}

type AppAction =
  | { type: 'SET_JOBS'; payload: Job[] }
  | { type: 'ADD_JOB'; payload: Job }
  | { type: 'UPDATE_JOB'; payload: Job }
  | { type: 'SET_ACTIVE_JOB'; payload: string | null }
  | { type: 'UPDATE_PROGRESS'; payload: { jobId: string; progress: JobProgress } }
  | { type: 'SET_LEADS'; payload: { jobId: string; leads: Lead[] } };

const initialState: AppState = {
  jobs: [],
  activeJobId: null,
  jobProgress: {},
  leads: {},
};

function appReducer(state: AppState, action: AppAction): AppState {
  switch (action.type) {
    case 'SET_JOBS':
      return { ...state, jobs: action.payload };
    case 'ADD_JOB':
      return { ...state, jobs: [action.payload, ...state.jobs] };
    case 'UPDATE_JOB':
      return {
        ...state,
        jobs: state.jobs.map((j) =>
          j.id === action.payload.id ? action.payload : j
        ),
      };
    case 'SET_ACTIVE_JOB':
      return { ...state, activeJobId: action.payload };
    case 'UPDATE_PROGRESS':
      return {
        ...state,
        jobProgress: {
          ...state.jobProgress,
          [action.payload.jobId]: action.payload.progress,
        },
      };
    case 'SET_LEADS':
      return {
        ...state,
        leads: {
          ...state.leads,
          [action.payload.jobId]: action.payload.leads,
        },
      };
    default:
      return state;
  }
}

const AppContext = createContext<{
  state: AppState;
  dispatch: React.Dispatch<AppAction>;
} | null>(null);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(appReducer, initialState);
  return (
    <AppContext.Provider value={{ state, dispatch }}>
      {children}
    </AppContext.Provider>
  );
}

export function useAppState() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useAppState must be used within AppProvider');
  return ctx;
}
