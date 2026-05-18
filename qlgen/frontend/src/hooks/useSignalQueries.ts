/**
 * React Query hooks for signal-related data fetching.
 * Provides caching, background refetch, and optimistic updates.
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getSignalFeed, getDashboardSignalStats, saveSignal, unsaveSignal,
  snoozeSignal, dismissSignal, type SignalFeedResponse, type DashboardSignalStats,
} from '../api/signalApi';
import type { SignalFeedTab } from '../types';

// ── Query Keys ──

export const signalKeys = {
  all: ['signals'] as const,
  feed: (params: { tab?: SignalFeedTab; signal_type?: string; priority?: string; offset?: number }) =>
    ['signals', 'feed', params] as const,
  dashboardStats: () => ['signals', 'dashboard-stats'] as const,
};

// ── Queries ──

export function useSignalFeed(params: {
  tab?: SignalFeedTab;
  signal_type?: string;
  priority?: string;
  limit?: number;
  offset?: number;
}) {
  return useQuery({
    queryKey: signalKeys.feed(params),
    queryFn: async () => {
      const res = await getSignalFeed(params);
      return res.data;
    },
    staleTime: 30_000,
    refetchInterval: 30_000, // Auto-refresh every 30s
  });
}

export function useDashboardSignalStats() {
  return useQuery({
    queryKey: signalKeys.dashboardStats(),
    queryFn: async () => {
      const res = await getDashboardSignalStats();
      return res.data;
    },
    staleTime: 60_000, // Cache for 60s
  });
}

// ── Mutations with optimistic updates ──

export function useSaveSignal() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (signalId: string) => saveSignal(signalId),
    onMutate: async (signalId) => {
      // Optimistically update feed cache
      await queryClient.cancelQueries({ queryKey: ['signals', 'feed'] });

      queryClient.setQueriesData<SignalFeedResponse>(
        { queryKey: ['signals', 'feed'] },
        (old) => {
          if (!old) return old;
          return {
            ...old,
            signals: old.signals.map(s =>
              s.id === signalId ? { ...s, is_saved: true } : s
            ),
          };
        }
      );
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['signals', 'feed'] });
    },
  });
}

export function useUnsaveSignal() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (signalId: string) => unsaveSignal(signalId),
    onMutate: async (signalId) => {
      await queryClient.cancelQueries({ queryKey: ['signals', 'feed'] });
      queryClient.setQueriesData<SignalFeedResponse>(
        { queryKey: ['signals', 'feed'] },
        (old) => {
          if (!old) return old;
          return {
            ...old,
            signals: old.signals.map(s =>
              s.id === signalId ? { ...s, is_saved: false } : s
            ),
          };
        }
      );
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['signals', 'feed'] });
    },
  });
}

export function useDismissSignal() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (signalId: string) => dismissSignal(signalId),
    onMutate: async (signalId) => {
      await queryClient.cancelQueries({ queryKey: ['signals', 'feed'] });
      queryClient.setQueriesData<SignalFeedResponse>(
        { queryKey: ['signals', 'feed'] },
        (old) => {
          if (!old) return old;
          return {
            ...old,
            signals: old.signals.filter(s => s.id !== signalId),
            total: Math.max(0, old.total - 1),
          };
        }
      );
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['signals'] });
    },
  });
}

export function useSnoozeSignal() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ signalId, hours }: { signalId: string; hours: number }) =>
      snoozeSignal(signalId, hours),
    onMutate: async ({ signalId }) => {
      await queryClient.cancelQueries({ queryKey: ['signals', 'feed'] });
      queryClient.setQueriesData<SignalFeedResponse>(
        { queryKey: ['signals', 'feed'] },
        (old) => {
          if (!old) return old;
          return {
            ...old,
            signals: old.signals.filter(s => s.id !== signalId),
            total: Math.max(0, old.total - 1),
          };
        }
      );
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['signals'] });
    },
  });
}
