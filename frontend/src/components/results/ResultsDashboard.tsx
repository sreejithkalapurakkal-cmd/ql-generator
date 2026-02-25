import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Box, Typography, Card, CardContent, Grid, Alert } from '@mui/material';
import LeadTable from './LeadTable';
import LeadDetailDrawer from './LeadDetailDrawer';
import BANTScoreCard from './BANTScoreCard';
import ScoreDistributionChart from './ScoreDistributionChart';
import ExportButton from './ExportButton';
import LoadingSpinner from '../shared/LoadingSpinner';
import EmptyState from '../shared/EmptyState';
import { useJobResults } from '../../hooks/useJobResults';
import { formatScore } from '../../lib/formatters';
import type { Lead } from '../../types/lead';

export default function ResultsDashboard() {
  const [searchParams] = useSearchParams();
  const jobId = searchParams.get('jobId');
  const { leads, loading, error } = useJobResults(jobId);
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);

  if (!jobId) {
    return <EmptyState title="No job selected" description="Select a completed job to view results." />;
  }

  if (loading) {
    return <LoadingSpinner message="Loading results..." />;
  }

  if (error) {
    return <Alert severity="error">{error}</Alert>;
  }

  if (leads.length === 0) {
    return <EmptyState title="No leads found" description="The search did not return any matching companies." />;
  }

  const avgScore = leads.reduce((sum, l) => sum + l.bantScore.total, 0) / leads.length;
  const topLead = leads[0];

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4">Results</Typography>
          <Typography variant="body2" color="text.secondary">
            Job: {jobId.slice(0, 8)}... | {leads.length} leads found
          </Typography>
        </Box>
        <ExportButton leads={leads} />
      </Box>

      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="subtitle2" color="text.secondary">Total Leads</Typography>
              <Typography variant="h4">{leads.length}</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="subtitle2" color="text.secondary">Avg Score</Typography>
              <Typography variant="h4">{formatScore(avgScore)}/10</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="subtitle2" color="text.secondary">Top Lead</Typography>
              <Typography variant="h6">{topLead.companyName}</Typography>
              <Typography variant="body2" color="primary">
                {formatScore(topLead.bantScore.total)}/10
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <ScoreDistributionChart leads={leads} />
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="subtitle2" gutterBottom>Top Lead BANT Breakdown</Typography>
              <BANTScoreCard score={topLead.bantScore} />
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <LeadTable leads={leads} onRowClick={setSelectedLead} />

      <LeadDetailDrawer
        lead={selectedLead}
        open={!!selectedLead}
        onClose={() => setSelectedLead(null)}
      />
    </Box>
  );
}
