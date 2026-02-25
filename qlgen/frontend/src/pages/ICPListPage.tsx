import React, { useEffect, useState } from 'react';
import {
  Box, Typography, Button, Paper, Grid, Chip, CircularProgress,
  Dialog, DialogTitle, DialogContent, DialogContentText, DialogActions,
  IconButton, Menu, MenuItem, Snackbar, Alert,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import RocketLaunchIcon from '@mui/icons-material/RocketLaunch';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import { useNavigate } from 'react-router-dom';
import { listICPs, deleteICP } from '../api/icpApi';
import { startPipeline } from '../api/pipelineApi';
import { ICPConfig } from '../types';

const ICPListPage: React.FC = () => {
  const navigate = useNavigate();
  const [icps, setIcps] = useState<ICPConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [menuAnchor, setMenuAnchor] = useState<{ el: HTMLElement; id: string } | null>(null);
  const [snack, setSnack] = useState({ open: false, msg: '', severity: 'success' as 'success' | 'error' });

  const fetchICPs = () => {
    setLoading(true);
    listICPs()
      .then((res) => setIcps(res.data))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchICPs(); }, []);

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      await deleteICP(deleteTarget);
      setSnack({ open: true, msg: 'ICP deleted', severity: 'success' });
      fetchICPs();
    } catch {
      setSnack({ open: true, msg: 'Failed to delete ICP', severity: 'error' });
    } finally {
      setDeleteTarget(null);
    }
  };

  const handleRunPipeline = async (icpId: string) => {
    setMenuAnchor(null);
    try {
      const res = await startPipeline({ icp_config_id: icpId, options: { max_companies: 15, max_contacts_per_company: 5 } });
      setSnack({ open: true, msg: 'Pipeline started', severity: 'success' });
      navigate(`/pipeline/${res.data.id}`);
    } catch (err: any) {
      setSnack({ open: true, msg: err?.response?.data?.detail || 'Failed to start pipeline', severity: 'error' });
    }
  };

  return (
    <Box>
      {/* Page header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 3 }}>
        <Box>
          <Typography sx={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.14em', color: '#F4693B', mb: '5px' }}>
            Configuration
          </Typography>
          <Typography sx={{ fontSize: 22, fontWeight: 700, color: '#141414', letterSpacing: '-0.3px' }}>
            Saved ICPs
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

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
          <CircularProgress sx={{ color: '#5C2D8F' }} />
        </Box>
      ) : icps.length === 0 ? (
        <Box sx={{ textAlign: 'center', py: 10 }}>
          <Typography sx={{ fontSize: 44, mb: 2, opacity: 0.25 }}>◈</Typography>
          <Typography sx={{ fontSize: 17, fontWeight: 700, color: '#3D3D3D', mb: 1 }}>
            No ICP configurations yet
          </Typography>
          <Typography sx={{ fontSize: 14, color: '#ADADAD', mb: 3 }}>
            Create your first ICP to start generating qualified leads.
          </Typography>
          <Button variant="contained" onClick={() => navigate('/icp/new')} sx={{ bgcolor: '#5C2D8F', '&:hover': { bgcolor: '#4a2272' } }}>
            Create ICP Configuration
          </Button>
        </Box>
      ) : (
        <Grid container spacing={2}>
          {icps.map((icp) => {
            const cfg = icp.config as any;
            const industries: string[] = cfg?.industry_types?.slice(0, 3).map((i: any) => i.vertical) || [];
            return (
              <Grid size={{ xs: 12, sm: 6, lg: 4 }} key={icp.id}>
                <Paper
                  sx={{
                    p: '20px',
                    borderRadius: '10px',
                    border: '1px solid #EBEBEB',
                    boxShadow: '0 1px 4px rgba(0,0,0,.07),0 4px 12px rgba(0,0,0,.04)',
                    position: 'relative',
                    overflow: 'hidden',
                    transition: 'all .2s ease',
                    cursor: 'pointer',
                    '&::before': {
                      content: '""',
                      position: 'absolute', top: 0, left: 0, right: 0,
                      height: 3,
                      background: 'linear-gradient(90deg, #5C2D8F, #7B4DB5)',
                      opacity: 0,
                      transition: 'opacity .2s',
                    },
                    '&:hover': {
                      boxShadow: '0 4px 16px rgba(0,0,0,.1),0 1px 4px rgba(0,0,0,.06)',
                      borderColor: '#D6D6D6',
                      transform: 'translateY(-1px)',
                      '&::before': { opacity: 1 },
                    },
                  }}
                >
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1 }}>
                    <Box sx={{ flex: 1, minWidth: 0 }}>
                      <Typography sx={{ fontSize: 15, fontWeight: 700, color: '#141414', letterSpacing: '-0.2px', mb: '2px' }}>
                        {icp.name}
                      </Typography>
                      <Typography sx={{ fontSize: 12, color: '#ADADAD' }}>
                        {icp.created_at ? new Date(icp.created_at).toLocaleDateString() : '-'}
                      </Typography>
                    </Box>
                    <IconButton
                      size="small"
                      onClick={(e) => { e.stopPropagation(); setMenuAnchor({ el: e.currentTarget, id: icp.id! }); }}
                      sx={{ color: '#ADADAD', ml: 1, '&:hover': { bgcolor: '#F5F5F5', color: '#3D3D3D' } }}
                    >
                      <MoreVertIcon sx={{ fontSize: 18 }} />
                    </IconButton>
                  </Box>

                  {icp.description && (
                    <Typography sx={{ fontSize: 12.5, color: '#858585', mb: 1.5, lineHeight: 1.5 }}>
                      {icp.description}
                    </Typography>
                  )}

                  {industries.length > 0 && (
                    <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', mb: 2 }}>
                      {industries.map((ind) => (
                        <Chip
                          key={ind}
                          label={ind}
                          size="small"
                          sx={{ bgcolor: '#F5F5F5', color: '#5C5C5C', border: '1px solid #EBEBEB', fontSize: 12, height: 24, borderRadius: '6px' }}
                        />
                      ))}
                    </Box>
                  )}

                  <Button
                    variant="contained"
                    size="small"
                    fullWidth
                    startIcon={<RocketLaunchIcon sx={{ fontSize: 13 }} />}
                    onClick={() => handleRunPipeline(icp.id!)}
                    sx={{ bgcolor: '#5C2D8F', '&:hover': { bgcolor: '#4a2272' }, fontSize: 13, py: 0.75 }}
                  >
                    Run Pipeline
                  </Button>
                </Paper>
              </Grid>
            );
          })}
        </Grid>
      )}

      {/* Context menu */}
      <Menu
        anchorEl={menuAnchor?.el}
        open={!!menuAnchor}
        onClose={() => setMenuAnchor(null)}
        PaperProps={{
          sx: { borderRadius: '10px', border: '1px solid #EBEBEB', boxShadow: '0 8px 32px rgba(0,0,0,.12),0 2px 8px rgba(0,0,0,.06)', minWidth: 160 },
        }}
      >
        <MenuItem
          onClick={() => { navigate(`/icp/${menuAnchor?.id}/edit`); setMenuAnchor(null); }}
          sx={{ fontSize: 13, fontWeight: 500, gap: 1.5, color: '#3D3D3D', py: '9px' }}
        >
          <EditIcon sx={{ fontSize: 15, color: '#ADADAD' }} /> Edit
        </MenuItem>
        <Box sx={{ height: 1, bgcolor: '#EBEBEB', my: '4px' }} />
        <MenuItem
          onClick={() => { setDeleteTarget(menuAnchor!.id); setMenuAnchor(null); }}
          sx={{ fontSize: 13, fontWeight: 500, gap: 1.5, color: '#D93025', py: '9px' }}
        >
          <DeleteIcon sx={{ fontSize: 15 }} /> Delete
        </MenuItem>
      </Menu>

      {/* Delete confirmation dialog */}
      <Dialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        PaperProps={{ sx: { borderRadius: '14px', p: 1, maxWidth: 420 } }}
      >
        <DialogTitle sx={{ fontSize: 18, fontWeight: 700, letterSpacing: '-0.3px' }}>
          Delete ICP?
        </DialogTitle>
        <DialogContent>
          <DialogContentText sx={{ fontSize: 14, color: '#858585', lineHeight: 1.6 }}>
            This will permanently delete the ICP configuration. This action cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2, gap: 1 }}>
          <Button onClick={() => setDeleteTarget(null)} variant="outlined" sx={{ borderColor: '#D6D6D6', color: '#3D3D3D', '&:hover': { borderColor: '#ADADAD', bgcolor: '#FAFAFA' } }}>
            Cancel
          </Button>
          <Button onClick={handleDelete} variant="contained" sx={{ bgcolor: '#D93025', '&:hover': { bgcolor: '#b91c1c' } }}>
            Delete
          </Button>
        </DialogActions>
      </Dialog>

      <Snackbar
        open={snack.open}
        autoHideDuration={3000}
        onClose={() => setSnack((s) => ({ ...s, open: false }))}
        anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
      >
        <Alert severity={snack.severity}>{snack.msg}</Alert>
      </Snackbar>
    </Box>
  );
};

export default ICPListPage;
