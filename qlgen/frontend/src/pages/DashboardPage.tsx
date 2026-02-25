import React, { useEffect, useState } from 'react';
import {
  Box, Typography, Button, Paper, Grid, Table, TableHead, TableBody,
  TableRow, TableCell, Chip, CircularProgress, Snackbar, Alert,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import RocketLaunchIcon from '@mui/icons-material/RocketLaunch';
import BusinessIcon from '@mui/icons-material/Business';
import PeopleIcon from '@mui/icons-material/People';
import TuneIcon from '@mui/icons-material/Tune';
import { useNavigate } from 'react-router-dom';
import { listICPs } from '../api/icpApi';
import { listPipelineRuns } from '../api/pipelineApi';
import { ICPConfig, PipelineRun } from '../types';

const statusChip = (status: string) => {
  const map: Record<string, { color: string; bg: string }> = {
    pending:   { color: '#858585', bg: '#F5F5F5' },
    running:   { color: '#5C2D8F', bg: '#F4EFFE' },
    completed: { color: '#1E9B6B', bg: '#E6F7F1' },
    failed:    { color: '#D93025', bg: '#FDECEA' },
  };
  const s = map[status] || map.pending;
  return (
    <Chip
      label={status.toUpperCase()}
      size="small"
      sx={{ bgcolor: s.bg, color: s.color, fontWeight: 700, fontSize: 11, height: 22, border: 'none' }}
    />
  );
};

interface MetricTileProps {
  icon: string;
  label: string;
  value: string | number;
}

const MetricTile: React.FC<MetricTileProps> = ({ icon, label, value }) => (
  <Paper
    sx={{
      p: '22px 24px',
      position: 'relative',
      overflow: 'hidden',
      border: '1px solid #EBEBEB',
      boxShadow: '0 1px 4px rgba(0,0,0,.07),0 4px 12px rgba(0,0,0,.04)',
      borderRadius: '10px',
      '&::after': {
        content: '""',
        position: 'absolute', right: -20, top: -20,
        width: 80, height: 80,
        borderRadius: '50%',
        background: '#F4EFFE',
        opacity: 0.6,
      },
    }}
  >
    <Box
      sx={{
        position: 'absolute', right: 20, top: '50%', transform: 'translateY(-50%)',
        width: 40, height: 40,
        bgcolor: '#FFF0EB',
        borderRadius: '10px',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 18, zIndex: 1,
      }}
    >
      {icon}
    </Box>
    <Typography sx={{ fontSize: 12, color: '#858585', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.04em', position: 'relative', zIndex: 1 }}>
      {label}
    </Typography>
    <Typography sx={{ fontSize: 30, fontWeight: 700, color: '#141414', letterSpacing: '-1px', mt: '4px', position: 'relative', zIndex: 1 }}>
      {value}
    </Typography>
  </Paper>
);

const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const [icps, setIcps] = useState<ICPConfig[]>([]);
  const [runs, setRuns] = useState<PipelineRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [snack, setSnack] = useState({ open: false, msg: '', severity: 'success' as 'success' | 'error' });

  useEffect(() => {
    Promise.all([listICPs(), listPipelineRuns()])
      .then(([icpRes, runRes]) => {
        setIcps(icpRes.data);
        setRuns(runRes.data);
      })
      .catch(() => setSnack({ open: true, msg: 'Failed to load data', severity: 'error' }))
      .finally(() => setLoading(false));
  }, []);

  const completedRuns = runs.filter((r) => r.status === 'completed');
  const totalCompanies = completedRuns.reduce((s, r) => s + r.companies_found, 0);
  const totalContacts = completedRuns.reduce((s, r) => s + r.contacts_found, 0);

  return (
    <Box>
      {/* Page header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 3 }}>
        <Box>
          <Typography sx={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.14em', color: '#F4693B', mb: '5px' }}>
            Overview
          </Typography>
          <Typography sx={{ fontSize: 22, fontWeight: 700, color: '#141414', letterSpacing: '-0.3px' }}>
            Dashboard
          </Typography>
        </Box>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => navigate('/icp/new')}
          sx={{ bgcolor: '#5C2D8F', '&:hover': { bgcolor: '#4a2272' } }}
        >
          New Run
        </Button>
      </Box>

      {/* Metric tiles */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <MetricTile icon="🎯" label="ICP Configurations" value={icps.length} />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <MetricTile icon="📈" label="Pipeline Runs" value={runs.length} />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <MetricTile icon="🏭" label="Companies Found" value={totalCompanies} />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <MetricTile icon="👥" label="Contacts Found" value={totalContacts} />
        </Grid>
      </Grid>

      {/* Recent runs */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
        <Box>
          <Typography sx={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.14em', color: '#F4693B', mb: '5px' }}>
            Recent Activity
          </Typography>
          <Typography sx={{ fontSize: 16, fontWeight: 700, color: '#3D3D3D' }}>
            Recent Runs
          </Typography>
        </Box>
      </Box>

      <Paper sx={{ borderRadius: '10px', overflow: 'hidden' }}>
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 6 }}>
            <CircularProgress size={32} sx={{ color: '#5C2D8F' }} />
          </Box>
        ) : runs.length === 0 ? (
          <Box sx={{ textAlign: 'center', py: 8, px: 3 }}>
            <Typography sx={{ fontSize: 44, mb: 2, opacity: 0.25 }}>🚀</Typography>
            <Typography sx={{ fontSize: 17, fontWeight: 700, color: '#3D3D3D', mb: 1 }}>
              No pipeline runs yet
            </Typography>
            <Typography sx={{ fontSize: 14, color: '#ADADAD', mb: 3 }}>
              Create an ICP configuration to get started.
            </Typography>
            <Button variant="contained" onClick={() => navigate('/icp/new')} sx={{ bgcolor: '#5C2D8F', '&:hover': { bgcolor: '#4a2272' } }}>
              Create ICP Configuration
            </Button>
          </Box>
        ) : (
          <Box sx={{ overflowX: 'auto' }}>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Status</TableCell>
                  <TableCell>Companies</TableCell>
                  <TableCell>Contacts</TableCell>
                  <TableCell>Started</TableCell>
                  <TableCell>Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {runs.map((run) => (
                  <TableRow key={run.id} hover>
                    <TableCell>{statusChip(run.status)}</TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
                        <BusinessIcon sx={{ fontSize: 14, color: '#ADADAD' }} />
                        {run.companies_found}
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
                        <PeopleIcon sx={{ fontSize: 14, color: '#ADADAD' }} />
                        {run.contacts_found}
                      </Box>
                    </TableCell>
                    <TableCell sx={{ color: '#858585' }}>
                      {run.started_at ? new Date(run.started_at).toLocaleString() : '-'}
                    </TableCell>
                    <TableCell>
                      {run.status === 'running' && (
                        <Button
                          size="small"
                          variant="outlined"
                          startIcon={<RocketLaunchIcon sx={{ fontSize: 13 }} />}
                          onClick={() => navigate(`/pipeline/${run.id}`)}
                          sx={{ borderColor: '#5C2D8F', color: '#5C2D8F', fontSize: 12, py: 0.5 }}
                        >
                          View Progress
                        </Button>
                      )}
                      {run.status === 'completed' && (
                        <Button
                          size="small"
                          variant="contained"
                          startIcon={<TuneIcon sx={{ fontSize: 13 }} />}
                          onClick={() => navigate(`/leads/${run.id}`)}
                          sx={{ bgcolor: '#5C2D8F', '&:hover': { bgcolor: '#4a2272' }, fontSize: 12, py: 0.5 }}
                        >
                          View Leads
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Box>
        )}
      </Paper>

      <Snackbar
        open={snack.open}
        autoHideDuration={3000}
        onClose={() => setSnack((s) => ({ ...s, open: false }))}
        anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
      >
        <Alert severity={snack.severity} sx={{ fontFamily: "'DM Sans', sans-serif" }}>
          {snack.msg}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default DashboardPage;
