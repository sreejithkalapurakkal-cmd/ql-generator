import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider, theme } from 'antd';
import AppLayout from './components/layout/AppLayout';
import WelcomePage from './pages/WelcomePage';
import DashboardPage from './pages/DashboardPage';
import ICPConfigPage from './pages/ICPConfigPage';
import ICPListPage from './pages/ICPListPage';
import PipelinePage from './pages/PipelinePage';
import LeadsPage from './pages/LeadsPage';
import { PageContextProvider } from './context/PageContextProvider';
import CoPilotPanel from './components/CoPilotPanel';

function App() {
  return (
    <ConfigProvider
      theme={{
        algorithm: theme.defaultAlgorithm,
        token: {
          colorPrimary: '#5C2D8F',
          colorSuccess: '#1E9B6B',
          colorWarning: '#E0820A',
          colorError: '#D93025',
          borderRadius: 10,
          fontFamily: "'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
        },
      }}
    >
      <BrowserRouter>
        <PageContextProvider>
          <AppLayout>
            <Routes>
              <Route path="/" element={<Navigate to="/welcome" />} />
              <Route path="/welcome" element={<WelcomePage />} />
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/icp/new" element={<ICPConfigPage />} />
              <Route path="/icp/:id/edit" element={<ICPConfigPage />} />
              <Route path="/icp" element={<ICPListPage />} />
              <Route path="/pipeline/:runId" element={<PipelinePage />} />
              <Route path="/leads/:runId" element={<LeadsPage />} />
            </Routes>
          </AppLayout>
          <CoPilotPanel />
        </PageContextProvider>
      </BrowserRouter>
    </ConfigProvider>
  );
}

export default App;
