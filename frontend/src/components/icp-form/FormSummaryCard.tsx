import { Card, CardContent, Typography, Chip, Box, Divider } from '@mui/material';
import type { ICPFormData } from '../../types/icp';

interface Props {
  data: ICPFormData;
}

export default function FormSummaryCard({ data }: Props) {
  const { icpProfile: icp, bantWeights: bant, maxResults } = data;

  return (
    <Card variant="outlined">
      <CardContent>
        <Typography variant="h6" gutterBottom>Review Summary</Typography>

        <Typography variant="subtitle2" color="text.secondary">Industries</Typography>
        <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', mb: 1 }}>
          {icp.industries.map((i) => <Chip key={i} label={i} size="small" />)}
        </Box>

        <Typography variant="subtitle2" color="text.secondary">Company Size</Typography>
        <Typography variant="body2" sx={{ mb: 1 }}>
          {icp.companySizeRange.min} - {icp.companySizeRange.max} employees
        </Typography>

        <Typography variant="subtitle2" color="text.secondary">Revenue Range</Typography>
        <Typography variant="body2" sx={{ mb: 1 }}>
          ${icp.revenueRange.min.toLocaleString()} - ${icp.revenueRange.max.toLocaleString()}
        </Typography>

        <Typography variant="subtitle2" color="text.secondary">Geographies</Typography>
        <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', mb: 1 }}>
          {icp.geographies.map((g) => <Chip key={g} label={g} size="small" variant="outlined" />)}
        </Box>

        {icp.techStack.length > 0 && (
          <>
            <Typography variant="subtitle2" color="text.secondary">Tech Stack</Typography>
            <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', mb: 1 }}>
              {icp.techStack.map((t) => <Chip key={t} label={t} size="small" color="primary" variant="outlined" />)}
            </Box>
          </>
        )}

        <Divider sx={{ my: 1.5 }} />

        <Typography variant="subtitle2" color="text.secondary">BANT Weights</Typography>
        <Typography variant="body2">
          B: {bant.budget} | A: {bant.authority} | N: {bant.need} | T: {bant.timeline}
        </Typography>

        <Typography variant="subtitle2" color="text.secondary" sx={{ mt: 1 }}>Max Results</Typography>
        <Typography variant="body2">{maxResults}</Typography>
      </CardContent>
    </Card>
  );
}
