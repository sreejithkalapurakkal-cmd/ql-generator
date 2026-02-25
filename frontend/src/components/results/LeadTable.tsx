import { useState } from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TableSortLabel,
  Paper,
  Typography,
  Chip,
} from '@mui/material';
import { formatCurrency, formatEmployeeCount, formatScore } from '../../lib/formatters';
import type { Lead } from '../../types/lead';

type SortKey = 'rank' | 'companyName' | 'totalScore' | 'employeeCount' | 'estimatedRevenue';

interface Props {
  leads: Lead[];
  onRowClick: (lead: Lead) => void;
}

export default function LeadTable({ leads, onRowClick }: Props) {
  const [sortBy, setSortBy] = useState<SortKey>('rank');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');

  const handleSort = (key: SortKey) => {
    if (sortBy === key) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(key);
      setSortDir(key === 'rank' ? 'asc' : 'desc');
    }
  };

  const sorted = [...leads].sort((a, b) => {
    let aVal: number | string;
    let bVal: number | string;
    switch (sortBy) {
      case 'rank': aVal = a.rank; bVal = b.rank; break;
      case 'companyName': aVal = a.companyName; bVal = b.companyName; break;
      case 'totalScore': aVal = a.bantScore.total; bVal = b.bantScore.total; break;
      case 'employeeCount': aVal = a.employeeCount ?? 0; bVal = b.employeeCount ?? 0; break;
      case 'estimatedRevenue': aVal = a.estimatedRevenue ?? 0; bVal = b.estimatedRevenue ?? 0; break;
      default: aVal = a.rank; bVal = b.rank;
    }
    if (aVal < bVal) return sortDir === 'asc' ? -1 : 1;
    if (aVal > bVal) return sortDir === 'asc' ? 1 : -1;
    return 0;
  });

  const getScoreColor = (score: number): 'success' | 'warning' | 'error' | 'default' => {
    if (score >= 7) return 'success';
    if (score >= 4) return 'warning';
    return 'error';
  };

  return (
    <TableContainer component={Paper} variant="outlined">
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>
              <TableSortLabel active={sortBy === 'rank'} direction={sortBy === 'rank' ? sortDir : 'asc'} onClick={() => handleSort('rank')}>
                #
              </TableSortLabel>
            </TableCell>
            <TableCell>
              <TableSortLabel active={sortBy === 'companyName'} direction={sortBy === 'companyName' ? sortDir : 'asc'} onClick={() => handleSort('companyName')}>
                Company
              </TableSortLabel>
            </TableCell>
            <TableCell>Industry</TableCell>
            <TableCell align="right">
              <TableSortLabel active={sortBy === 'employeeCount'} direction={sortBy === 'employeeCount' ? sortDir : 'desc'} onClick={() => handleSort('employeeCount')}>
                Employees
              </TableSortLabel>
            </TableCell>
            <TableCell align="right">
              <TableSortLabel active={sortBy === 'estimatedRevenue'} direction={sortBy === 'estimatedRevenue' ? sortDir : 'desc'} onClick={() => handleSort('estimatedRevenue')}>
                Revenue
              </TableSortLabel>
            </TableCell>
            <TableCell>Location</TableCell>
            <TableCell align="center">
              <TableSortLabel active={sortBy === 'totalScore'} direction={sortBy === 'totalScore' ? sortDir : 'desc'} onClick={() => handleSort('totalScore')}>
                Score
              </TableSortLabel>
            </TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {sorted.map((lead) => (
            <TableRow
              key={lead.id}
              hover
              sx={{ cursor: 'pointer' }}
              onClick={() => onRowClick(lead)}
            >
              <TableCell>
                <Typography variant="body2" fontWeight={600}>{lead.rank}</Typography>
              </TableCell>
              <TableCell>
                <Typography variant="body2" fontWeight={500}>{lead.companyName}</Typography>
                <Typography variant="caption" color="text.secondary">{lead.domain}</Typography>
              </TableCell>
              <TableCell>
                <Typography variant="body2">{lead.industry || '-'}</Typography>
              </TableCell>
              <TableCell align="right">{formatEmployeeCount(lead.employeeCount)}</TableCell>
              <TableCell align="right">{formatCurrency(lead.estimatedRevenue)}</TableCell>
              <TableCell>{lead.location || '-'}</TableCell>
              <TableCell align="center">
                <Chip
                  label={formatScore(lead.bantScore.total)}
                  color={getScoreColor(lead.bantScore.total)}
                  size="small"
                />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
