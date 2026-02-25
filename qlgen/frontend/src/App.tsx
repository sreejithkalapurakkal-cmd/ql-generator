import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider, createTheme, CssBaseline } from '@mui/material';
import AppLayout from './components/layout/AppLayout';
import DashboardPage from './pages/DashboardPage';
import ICPConfigPage from './pages/ICPConfigPage';
import ICPListPage from './pages/ICPListPage';
import PipelinePage from './pages/PipelinePage';
import LeadsPage from './pages/LeadsPage';

const theme = createTheme({
  palette: {
    primary: { main: '#5C2D8F', dark: '#4a2272', light: '#7B4DB5', contrastText: '#fff' },
    secondary: { main: '#F4693B' },
    success: { main: '#1E9B6B' },
    error: { main: '#D93025' },
    warning: { main: '#E0820A' },
    background: { default: '#FAFAFA', paper: '#FFFFFF' },
    text: { primary: '#242424', secondary: '#858585' },
  },
  typography: {
    fontFamily: "'DM Sans', sans-serif",
    button: { textTransform: 'none', fontWeight: 500, letterSpacing: '-0.1px' },
  },
  shape: { borderRadius: 10 },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: 500,
          fontSize: '14px',
          letterSpacing: '-0.1px',
          boxShadow: 'none',
          '&:hover': { boxShadow: 'none' },
        },
        contained: {
          boxShadow: '0 1px 3px rgba(92,45,143,.3)',
          '&:hover': { boxShadow: '0 2px 8px rgba(92,45,143,.35)' },
        },
      },
    },
    MuiTextField: {
      defaultProps: { size: 'small' },
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            fontSize: '14px',
            '&:hover .MuiOutlinedInput-notchedOutline': { borderColor: '#ADADAD' },
            '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
              borderColor: '#5C2D8F',
              boxShadow: '0 0 0 3px rgba(92,45,143,.12)',
            },
          },
        },
      },
    },
    MuiSelect: {
      defaultProps: { size: 'small' },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          border: '1px solid #EBEBEB',
          boxShadow: '0 1px 4px rgba(0,0,0,.07),0 4px 12px rgba(0,0,0,.04)',
        },
      },
    },
    MuiTableHead: {
      styleOverrides: {
        root: {
          '& .MuiTableCell-head': {
            background: '#FAFAFA',
            fontWeight: 600,
            fontSize: '11px',
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            color: '#858585',
            borderBottom: '1px solid #EBEBEB',
            padding: '11px 14px',
          },
        },
      },
    },
    MuiTableBody: {
      styleOverrides: {
        root: {
          '& .MuiTableCell-body': {
            fontSize: '13.5px',
            color: '#3D3D3D',
            padding: '11px 14px',
            borderBottom: '1px solid #F5F5F5',
          },
          '& .MuiTableRow-root:last-child .MuiTableCell-body': {
            borderBottom: 'none',
          },
          '& .MuiTableRow-root:hover .MuiTableCell-body': {
            background: '#FAFAFA',
          },
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: { fontSize: '12px', fontWeight: 600, height: 22, borderRadius: 999 },
      },
    },
  },
});

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
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
    </ThemeProvider>
  );
}

export default App;
