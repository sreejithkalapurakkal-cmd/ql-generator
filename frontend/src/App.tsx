import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider, CssBaseline } from '@mui/material';
import theme from './theme/theme';
import { AppProvider } from './context/AppContext';
import AppShell from './components/layout/AppShell';
import ErrorBoundary from './components/layout/ErrorBoundary';
import LoadingSpinner from './components/shared/LoadingSpinner';

const ICPFormPage = lazy(() => import('./components/icp-form/ICPFormPage'));
const JobListPage = lazy(() => import('./components/job-tracker/JobListPage'));
const ResultsDashboard = lazy(() => import('./components/results/ResultsDashboard'));

export default function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <ErrorBoundary>
        <AppProvider>
          <BrowserRouter>
            <Routes>
              <Route element={<AppShell />}>
                <Route
                  path="/"
                  element={
                    <Suspense fallback={<LoadingSpinner />}>
                      <ICPFormPage />
                    </Suspense>
                  }
                />
                <Route
                  path="/jobs"
                  element={
                    <Suspense fallback={<LoadingSpinner />}>
                      <JobListPage />
                    </Suspense>
                  }
                />
                <Route
                  path="/results"
                  element={
                    <Suspense fallback={<LoadingSpinner />}>
                      <ResultsDashboard />
                    </Suspense>
                  }
                />
              </Route>
            </Routes>
          </BrowserRouter>
        </AppProvider>
      </ErrorBoundary>
    </ThemeProvider>
  );
}
