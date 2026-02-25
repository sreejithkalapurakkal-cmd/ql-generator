import { Button, Menu, MenuItem } from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
import { useState } from 'react';
import type { Lead } from '../../types/lead';

interface Props {
  leads: Lead[];
}

export default function ExportButton({ leads }: Props) {
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);

  const handleExportCSV = () => {
    const headers = [
      'Rank', 'Company', 'Domain', 'Industry', 'Employees', 'Revenue',
      'Location', 'Funding Stage', 'Budget Score', 'Authority Score',
      'Need Score', 'Timeline Score', 'Total Score',
    ];
    const rows = leads.map((l) => [
      l.rank, l.companyName, l.domain, l.industry, l.employeeCount ?? '',
      l.estimatedRevenue ?? '', l.location ?? '', l.fundingStage ?? '',
      l.bantScore.budget, l.bantScore.authority, l.bantScore.need,
      l.bantScore.timeline, l.bantScore.total,
    ]);

    const csv = [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
    downloadFile(csv, 'leads.csv', 'text/csv');
    setAnchorEl(null);
  };

  const handleExportJSON = () => {
    const json = JSON.stringify(leads, null, 2);
    downloadFile(json, 'leads.json', 'application/json');
    setAnchorEl(null);
  };

  return (
    <>
      <Button
        variant="outlined"
        startIcon={<DownloadIcon />}
        onClick={(e) => setAnchorEl(e.currentTarget)}
        disabled={leads.length === 0}
      >
        Export
      </Button>
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={() => setAnchorEl(null)}
      >
        <MenuItem onClick={handleExportCSV}>Export as CSV</MenuItem>
        <MenuItem onClick={handleExportJSON}>Export as JSON</MenuItem>
      </Menu>
    </>
  );
}

function downloadFile(content: string, filename: string, type: string) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
