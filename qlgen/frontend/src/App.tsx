import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider, theme } from 'antd';
import AppLayout from './components/layout/AppLayout';
import DashboardPage from './pages/DashboardPage';
import ICPConfigPage from './pages/ICPConfigPage';
import ICPListPage from './pages/ICPListPage';
import PipelinePage from './pages/PipelinePage';
import LeadsPage from './pages/LeadsPage';

function App() {
  return (
    <ConfigProvider
      theme={{
        algorithm: theme.defaultAlgorithm,
        token: { colorPrimary: '#1F4E79', borderRadius: 8 },
      }}
    >
      <BrowserRouter>
        <AppLayout>
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/icp/new" element={<ICPConfigPage />} />
            <Route path="/icp/:id/edit" element={<ICPConfigPage />} />
            <Route path="/icp" element={<ICPListPage />} />
            <Route path="/pipeline/:runId" element={<PipelinePage />} />
            <Route path="/leads/:runId" element={<LeadsPage />} />
          </Routes>
        </AppLayout>
      </BrowserRouter>
    </ConfigProvider>
  );
}

export default App;
