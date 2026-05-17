import React, { createContext, useContext, useState, useMemo } from 'react';
import { useLocation } from 'react-router-dom';
import type { PageContext } from '../types';

interface PageContextValue {
  pageContext: PageContext;
  setCompanyId: (id: string | null) => void;
}

const PageCtx = createContext<PageContextValue>({
  pageContext: { route: '/', page_type: 'Unknown' },
  setCompanyId: () => {},
});

// eslint-disable-next-line react-refresh/only-export-components
export function usePageContext() {
  return useContext(PageCtx);
}

function derivePageType(pathname: string): string {
  if (pathname.startsWith('/leads/')) return 'LeadsPage';
  if (pathname.startsWith('/pipeline/')) return 'PipelinePage';
  if (pathname === '/icp/new' || pathname.match(/^\/icp\/[^/]+\/edit$/)) return 'ICPConfigPage';
  if (pathname === '/icp') return 'ICPListPage';
  if (pathname === '/all-leads') return 'AllLeadsPage';
  if (pathname === '/dashboard') return 'DashboardPage';
  if (pathname === '/welcome' || pathname === '/') return 'WelcomePage';
  if (pathname.startsWith('/tracking/')) return 'TrackingListDetailPage';
  if (pathname === '/tracking') return 'TrackingListsPage';
  if (pathname === '/signals') return 'SignalFeedPage';
  if (pathname === '/signals/rules') return 'SignalRulesPage';
  if (pathname === '/ingest') return 'IngestPage';
  return 'Unknown';
}

function extractRunId(pathname: string): string | undefined {
  const leadMatch = pathname.match(/^\/leads\/([^/]+)/);
  if (leadMatch) return leadMatch[1];
  const pipeMatch = pathname.match(/^\/pipeline\/([^/]+)/);
  if (pipeMatch) return pipeMatch[1];
  return undefined;
}

function extractIcpId(pathname: string): string | undefined {
  const match = pathname.match(/^\/icp\/([^/]+)\/edit/);
  if (match) return match[1];
  return undefined;
}

export const PageContextProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const location = useLocation();
  const [companyId, setCompanyId] = useState<string | null>(null);

  const pageContext = useMemo<PageContext>(() => ({
    route: location.pathname,
    page_type: derivePageType(location.pathname),
    run_id: extractRunId(location.pathname),
    icp_id: extractIcpId(location.pathname),
    company_id: companyId || undefined,
  }), [location.pathname, companyId]);

  const value = useMemo<PageContextValue>(() => ({
    pageContext,
    setCompanyId,
  }), [pageContext]);

  return <PageCtx.Provider value={value}>{children}</PageCtx.Provider>;
};
