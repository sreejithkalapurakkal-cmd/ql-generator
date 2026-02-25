import React, { useEffect, useState } from 'react';
import {
  Box, Typography, Button, Paper, Chip, Tooltip, CircularProgress,
  Table, TableHead, TableBody, TableRow, TableCell,
  FormControl, Select, MenuItem, Collapse, IconButton,
} from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
import BusinessIcon from '@mui/icons-material/Business';
import PeopleIcon from '@mui/icons-material/People';
import BarChartIcon from '@mui/icons-material/BarChart';
import LocalFireDepartmentIcon from '@mui/icons-material/LocalFireDepartment';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import { useParams } from 'react-router-dom';
import { getLeadCompanies, getExportUrl } from '../api/leadsApi';
import { Company, BANTScore } from '../types';

// ─── BANT Score chip ──────────────────────────────────────────────────────────
const BANTScoreDisplay: React.FC<{ score: BANTScore | null }> = ({ score }) => {
  if (!score || !score.total_score) {
    return <Chip label="N/A" size="small" sx={{ bgcolor: '#F5F5F5', color: '#ADADAD', height: 22 }} />;
  }
  const total = score.total_score;
  const cfg =
    total >= 16 ? { label: 'HOT',  bg: '#E6F7F1', color: '#1E9B6B' } :
    total >= 12 ? { label: 'WARM', bg: '#FEF3E2', color: '#E0820A' } :
    total >= 9  ? { label: 'COOL', bg: '#F4EFFE', color: '#5C2D8F' } :
                  { label: 'COLD', bg: '#FDECEA', color: '#D93025' };

  return (
    <Tooltip title={`B:${score.budget_score} A:${score.authority_score} N:${score.need_score} T:${score.timing_score}`}>
      <Chip
        label={`${total}/20 ${cfg.label}`}
        size="small"
        sx={{ bgcolor: cfg.bg, color: cfg.color, fontWeight: 700, fontSize: 11, height: 22, cursor: 'default' }}
      />
    </Tooltip>
  );
};

// ─── BANT detail panel ────────────────────────────────────────────────────────
const BANTDetailPanel: React.FC<{ score: BANTScore }> = ({ score }) => (
  <Box sx={{ p: '12px 20px', bgcolor: '#FAFAFA' }}>
    <Typography sx={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: '#F4693B', mb: 1.5 }}>
      BANT Breakdown
    </Typography>
    <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 1.5 }}>
      {[
        { key: 'Budget',    score: score.budget_score,    reason: score.budget_reason },
        { key: 'Authority', score: score.authority_score, reason: score.authority_reason },
        { key: 'Need',      score: score.need_score,      reason: score.need_reason },
        { key: 'Timing',    score: score.timing_score,    reason: score.timing_reason },
      ].map(({ key, score: s, reason }) => (
        <Box key={key} sx={{ bgcolor: '#fff', border: '1px solid #EBEBEB', borderRadius: '8px', p: '10px 14px' }}>
          <Typography sx={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: '#ADADAD', mb: 0.5 }}>
            {key} ({s}/5)
          </Typography>
          <Typography sx={{ fontSize: 12.5, color: '#5C5C5C', lineHeight: 1.5 }}>
            {reason || '-'}
          </Typography>
        </Box>
      ))}
    </Box>
    {score.overall_summary && (
      <Box sx={{ mt: 1.5, bgcolor: '#fff', border: '1px solid #EBEBEB', borderRadius: '8px', p: '10px 14px' }}>
        <Typography sx={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: '#ADADAD', mb: 0.5 }}>
          Summary
        </Typography>
        <Typography sx={{ fontSize: 12.5, color: '#5C5C5C', lineHeight: 1.5 }}>
          {score.overall_summary}
        </Typography>
      </Box>
    )}
  </Box>
);

// ─── Summary stat tile ────────────────────────────────────────────────────────
interface StatTileProps { icon: React.ReactNode; label: string; value: string | number; suffix?: string }

const StatTile: React.FC<StatTileProps> = ({ icon, label, value, suffix }) => (
  <Box
    sx={{
      textAlign: 'center', p: '18px 24px', flex: 1, minWidth: 120,
      borderRight: '1px solid #EBEBEB',
      '&:last-child': { borderRight: 'none' },
    }}
  >
    <Typography sx={{ fontSize: 22, fontWeight: 700, color: '#141414', letterSpacing: '-0.5px' }}>
      {value}{suffix && <Typography component="span" sx={{ fontSize: 14, color: '#ADADAD', fontWeight: 500 }}> {suffix}</Typography>}
    </Typography>
    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.5, mt: '3px' }}>
      {icon}
      <Typography sx={{ fontSize: 11, color: '#ADADAD', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        {label}
      </Typography>
    </Box>
  </Box>
);

// ─── Main page ────────────────────────────────────────────────────────────────
const LeadsPage: React.FC = () => {
  const { runId } = useParams<{ runId: string }>();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [sortBy, setSortBy] = useState('bant_score');
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!runId) return;
    setLoading(true);
    getLeadCompanies(runId, { sort_by: sortBy })
      .then((res) => setCompanies(res.data))
      .finally(() => setLoading(false));
  }, [runId, sortBy]);

  const totalContacts = companies.reduce((s, c) => s + c.contacts.length, 0);
  const avgBant =
    companies.length > 0
      ? (companies.reduce((s, c) => s + (c.bant_score?.total_score || 0), 0) / companies.length).toFixed(1)
      : '0';
  const hotLeads = companies.filter((c) => (c.bant_score?.total_score || 0) >= 16).length;
  const warmLeads = companies.filter((c) => { const t = c.bant_score?.total_score || 0; return t >= 12 && t < 16; }).length;

  // Flatten to rows
  const flatRows: any[] = [];
  let serial = 1;
  companies.forEach((company) => {
    if (company.contacts.length > 0) {
      company.contacts.forEach((contact) => {
        flatRows.push({
          key: `${company.id}-${contact.id}`,
          serial: serial++,
          company_name: company.name,
          website: company.website,
          city: [company.city, company.state_region, company.country].filter(Boolean).join(', '),
          contact_name: contact.full_name,
          designation: contact.designation,
          linkedin: contact.linkedin_url,
          email: contact.email,
          phone: contact.phone,
          bant_score: company.bant_score,
          company,
        });
      });
    } else {
      flatRows.push({
        key: company.id,
        serial: serial++,
        company_name: company.name,
        website: company.website,
        city: [company.city, company.state_region, company.country].filter(Boolean).join(', '),
        contact_name: '-',
        designation: '-',
        linkedin: null,
        email: null,
        phone: null,
        bant_score: company.bant_score,
        company,
      });
    }
  });

  const toggleRow = (key: string) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  return (
    <Box>
      {/* Page header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 3 }}>
        <Box>
          <Typography sx={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.14em', color: '#F4693B', mb: '5px' }}>
            Lead Generation
          </Typography>
          <Typography sx={{ fontSize: 22, fontWeight: 700, color: '#141414', letterSpacing: '-0.3px' }}>
            Qualified Leads
          </Typography>
        </Box>
      </Box>

      {/* Summary bar */}
      <Paper
        sx={{
          display: 'flex', flexWrap: 'wrap',
          mb: 2.5, borderRadius: '10px',
          border: '1px solid #EBEBEB',
          boxShadow: '0 1px 4px rgba(0,0,0,.07),0 4px 12px rgba(0,0,0,.04)',
          overflow: 'hidden',
        }}
      >
        <StatTile icon={<BusinessIcon sx={{ fontSize: 13, color: '#ADADAD' }} />} label="Companies" value={companies.length} />
        <StatTile icon={<PeopleIcon sx={{ fontSize: 13, color: '#ADADAD' }} />} label="Contacts" value={totalContacts} />
        <StatTile icon={<BarChartIcon sx={{ fontSize: 13, color: '#ADADAD' }} />} label="Avg BANT" value={avgBant} suffix="/20" />
        <StatTile icon={<LocalFireDepartmentIcon sx={{ fontSize: 13, color: '#ADADAD' }} />} label="Hot / Warm" value={hotLeads} suffix={`/ ${warmLeads}`} />
      </Paper>

      {/* Filter + export bar */}
      <Box sx={{ display: 'flex', gap: 1.25, mb: 2, alignItems: 'center', flexWrap: 'wrap' }}>
        <FormControl size="small" sx={{ width: 180 }}>
          <Select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            sx={{ fontSize: 13, bgcolor: '#fff', borderRadius: '6px' }}
          >
            <MenuItem value="bant_score" sx={{ fontSize: 13 }}>Sort by BANT Score</MenuItem>
            <MenuItem value="company_name" sx={{ fontSize: 13 }}>Sort by Company</MenuItem>
          </Select>
        </FormControl>
        <Box sx={{ ml: 'auto', display: 'flex', gap: 1 }}>
          <Button
            variant="outlined"
            size="small"
            startIcon={<DownloadIcon sx={{ fontSize: 14 }} />}
            onClick={() => window.open(getExportUrl(runId!, 'xlsx'))}
            sx={{ borderColor: '#D6D6D6', color: '#3D3D3D', fontSize: 13, '&:hover': { borderColor: '#ADADAD', bgcolor: '#FAFAFA' } }}
          >
            Export XLSX
          </Button>
          <Button
            variant="outlined"
            size="small"
            startIcon={<DownloadIcon sx={{ fontSize: 14 }} />}
            onClick={() => window.open(getExportUrl(runId!, 'csv'))}
            sx={{ borderColor: '#D6D6D6', color: '#3D3D3D', fontSize: 13, '&:hover': { borderColor: '#ADADAD', bgcolor: '#FAFAFA' } }}
          >
            Export CSV
          </Button>
        </Box>
      </Box>

      {/* Table */}
      <Paper sx={{ borderRadius: '10px', border: '1px solid #EBEBEB', overflow: 'hidden' }}>
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 6 }}>
            <CircularProgress size={32} sx={{ color: '#5C2D8F' }} />
          </Box>
        ) : (
          <Box sx={{ overflowX: 'auto' }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell sx={{ width: 32 }} />
                  <TableCell sx={{ width: 40 }}>#</TableCell>
                  <TableCell>Company</TableCell>
                  <TableCell>Website</TableCell>
                  <TableCell>Location</TableCell>
                  <TableCell>Contact</TableCell>
                  <TableCell>Designation</TableCell>
                  <TableCell>LinkedIn</TableCell>
                  <TableCell>Email</TableCell>
                  <TableCell>Phone</TableCell>
                  <TableCell>BANT Score</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {flatRows.map((row) => {
                  const isExpanded = expandedRows.has(row.key);
                  const hasBant = !!row.company?.bant_score;
                  return (
                    <React.Fragment key={row.key}>
                      <TableRow
                        hover
                        sx={{ cursor: hasBant ? 'pointer' : 'default' }}
                        onClick={() => hasBant && toggleRow(row.key)}
                      >
                        <TableCell sx={{ p: '6px 8px', borderBottom: isExpanded ? 'none' : undefined }}>
                          {hasBant && (
                            <IconButton size="small" sx={{ p: 0.25, color: '#ADADAD' }}>
                              {isExpanded ? <ExpandLessIcon sx={{ fontSize: 16, color: '#5C2D8F' }} /> : <ExpandMoreIcon sx={{ fontSize: 16 }} />}
                            </IconButton>
                          )}
                        </TableCell>
                        <TableCell sx={{ color: '#ADADAD', fontWeight: 500, borderBottom: isExpanded ? 'none' : undefined }}>{row.serial}</TableCell>
                        <TableCell sx={{ fontWeight: 600, color: '#141414', borderBottom: isExpanded ? 'none' : undefined }}>{row.company_name}</TableCell>
                        <TableCell sx={{ borderBottom: isExpanded ? 'none' : undefined }}>
                          {row.website ? (
                            <a href={row.website.startsWith('http') ? row.website : `https://${row.website}`} target="_blank" rel="noreferrer" style={{ color: '#5C2D8F', fontSize: 12.5 }}>
                              {row.website.replace(/^https?:\/\//, '').replace(/\/$/, '')}
                            </a>
                          ) : '-'}
                        </TableCell>
                        <TableCell sx={{ borderBottom: isExpanded ? 'none' : undefined }}>{row.city || '-'}</TableCell>
                        <TableCell sx={{ borderBottom: isExpanded ? 'none' : undefined }}>{row.contact_name || '-'}</TableCell>
                        <TableCell sx={{ borderBottom: isExpanded ? 'none' : undefined }}>
                          {row.designation ? (
                            <Typography sx={{ fontSize: 12, bgcolor: '#F5F5F5', display: 'inline-block', px: 1, borderRadius: 999, color: '#5C5C5C' }}>
                              {row.designation}
                            </Typography>
                          ) : '-'}
                        </TableCell>
                        <TableCell sx={{ borderBottom: isExpanded ? 'none' : undefined }}>
                          {row.linkedin ? (
                            <a href={row.linkedin} target="_blank" rel="noreferrer" style={{ color: '#5C2D8F', fontSize: 12.5 }}>
                              Profile
                            </a>
                          ) : '-'}
                        </TableCell>
                        <TableCell sx={{ fontSize: 12.5, borderBottom: isExpanded ? 'none' : undefined }}>{row.email || '-'}</TableCell>
                        <TableCell sx={{ fontSize: 12.5, borderBottom: isExpanded ? 'none' : undefined }}>{row.phone || '-'}</TableCell>
                        <TableCell sx={{ borderBottom: isExpanded ? 'none' : undefined }}>
                          <BANTScoreDisplay score={row.bant_score} />
                        </TableCell>
                      </TableRow>

                      {/* Expandable BANT detail row */}
                      {hasBant && (
                        <TableRow>
                          <TableCell colSpan={11} sx={{ p: 0, border: 'none' }}>
                            <Collapse in={isExpanded} timeout="auto" unmountOnExit>
                              <BANTDetailPanel score={row.company.bant_score!} />
                            </Collapse>
                          </TableCell>
                        </TableRow>
                      )}
                    </React.Fragment>
                  );
                })}
              </TableBody>
            </Table>

            {flatRows.length === 0 && (
              <Box sx={{ textAlign: 'center', py: 8 }}>
                <Typography sx={{ fontSize: 44, mb: 2, opacity: 0.25 }}>📋</Typography>
                <Typography sx={{ fontSize: 17, fontWeight: 700, color: '#3D3D3D', mb: 1 }}>No leads found</Typography>
                <Typography sx={{ fontSize: 14, color: '#ADADAD' }}>The pipeline didn't produce any results yet.</Typography>
              </Box>
            )}
          </Box>
        )}
      </Paper>

      {/* Sticky export footer */}
      {flatRows.length > 0 && (
        <Box
          sx={{
            position: 'sticky', bottom: 0,
            bgcolor: '#fff', borderTop: '1px solid #EBEBEB',
            p: '14px 32px',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            mt: 2.5, mx: '-32px', mb: '-28px',
            boxShadow: '0 -4px 16px rgba(0,0,0,.06)',
            zIndex: 50,
          }}
        >
          <Typography sx={{ fontSize: 13.5, color: '#858585', fontWeight: 500 }}>
            All {flatRows.length} leads
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25 }}>
            {/* Export format toggle */}
            <Box sx={{ display: 'flex', bgcolor: '#F5F5F5', border: '1px solid #EBEBEB', borderRadius: '8px', p: '3px', gap: '2px' }}>
              {['xlsx', 'csv'].map((fmt) => (
                <Button
                  key={fmt}
                  size="small"
                  onClick={() => window.open(getExportUrl(runId!, fmt as 'xlsx' | 'csv'))}
                  sx={{
                    px: 2, py: 0.75, fontSize: 13, fontWeight: 500, borderRadius: '6px',
                    color: '#858585', minWidth: 'auto',
                    '&:hover': { bgcolor: '#fff', color: '#5C2D8F', boxShadow: '0 1px 3px rgba(0,0,0,.1)' },
                  }}
                >
                  .{fmt}
                </Button>
              ))}
            </Box>
            <Button
              variant="contained"
              size="small"
              startIcon={<DownloadIcon sx={{ fontSize: 14 }} />}
              onClick={() => window.open(getExportUrl(runId!, 'xlsx'))}
              sx={{ bgcolor: '#5C2D8F', '&:hover': { bgcolor: '#4a2272' }, fontSize: 13 }}
            >
              Download Leads →
            </Button>
          </Box>
        </Box>
      )}
    </Box>
  );
};

export default LeadsPage;
