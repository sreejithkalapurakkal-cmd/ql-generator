import { Box, Typography } from '@mui/material';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import type { Lead } from '../../types/lead';

interface Props {
  leads: Lead[];
}

export default function ScoreDistributionChart({ leads }: Props) {
  const buckets = Array.from({ length: 10 }, (_, i) => ({
    range: `${i}-${i + 1}`,
    count: 0,
  }));

  leads.forEach((lead) => {
    const idx = Math.min(Math.floor(lead.bantScore.total), 9);
    buckets[idx].count++;
  });

  return (
    <Box>
      <Typography variant="subtitle2" gutterBottom>
        Score Distribution
      </Typography>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={buckets}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="range" fontSize={12} />
          <YAxis fontSize={12} />
          <Tooltip />
          <Bar dataKey="count" fill="#1976d2" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </Box>
  );
}
