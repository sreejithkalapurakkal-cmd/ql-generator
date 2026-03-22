import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider, theme } from 'antd';
import AppLayout from './components/layout/AppLayout';
import ProtectedRoute from './components/ProtectedRoute';
import AdminRoute from './components/AdminRoute';
import WelcomePage from './pages/WelcomePage';
import DashboardPage from './pages/DashboardPage';
import ICPConfigPage from './pages/ICPConfigPage';
import ICPListPage from './pages/ICPListPage';
import PipelinePage from './pages/PipelinePage';
import LeadsPage from './pages/LeadsPage';
import CompanyDetailPage from './pages/CompanyDetailPage';
import AllLeadsPage from './pages/AllLeadsPage';
import ToolsPage from './pages/ToolsPage';
import AuthCallbackPage from './pages/AuthCallbackPage';
import UserManagementPage from './pages/UserManagementPage';
import { AuthProvider } from './context/AuthContext';
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
        <AuthProvider>
          <Routes>
            {/* Public routes */}
            <Route path="/" element={<Navigate to="/welcome" />} />
            <Route path="/welcome" element={<WelcomePage />} />
            <Route path="/login" element={<Navigate to="/welcome" />} />
            <Route path="/auth/callback" element={<AuthCallbackPage />} />

            {/* Protected routes */}
            <Route
              path="/*"
              element={
                <ProtectedRoute>
                  <PageContextProvider>
                    <AppLayout>
                      <Routes>
                        <Route path="/dashboard" element={<DashboardPage />} />
                        <Route path="/icp/new" element={<ICPConfigPage />} />
                        <Route path="/icp/:id/edit" element={<ICPConfigPage />} />
                        <Route path="/icp" element={<ICPListPage />} />
                        <Route path="/pipeline/:runId" element={<PipelinePage />} />
                        <Route path="/all-leads" element={<AllLeadsPage />} />
                        <Route path="/leads/:runId" element={<LeadsPage />} />
                        <Route path="/leads/:runId/company/:companyId" element={<CompanyDetailPage />} />
                        <Route
                          path="/tools"
                          element={
                            <AdminRoute>
                              <ToolsPage />
                            </AdminRoute>
                          }
                        />
                        <Route
                          path="/admin/users"
                          element={
                            <AdminRoute>
                              <UserManagementPage />
                            </AdminRoute>
                          }
                        />
                      </Routes>
                    </AppLayout>
                    <CoPilotPanel />
                  </PageContextProvider>
                </ProtectedRoute>
              }
            />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </ConfigProvider>
  );
}

export default App;
