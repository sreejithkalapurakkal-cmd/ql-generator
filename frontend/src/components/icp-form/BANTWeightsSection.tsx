import { Box, Typography, Slider, Grid } from '@mui/material';
import type { UseFormSetValue, UseFormWatch } from 'react-hook-form';
import type { ICPFormData } from '../../types/icp';

interface Props {
  setValue: UseFormSetValue<ICPFormData>;
  watch: UseFormWatch<ICPFormData>;
}

const BANT_LABELS = [
  { key: 'budget' as const, label: 'Budget', color: '#1976d2' },
  { key: 'authority' as const, label: 'Authority', color: '#9c27b0' },
  { key: 'need' as const, label: 'Need', color: '#2e7d32' },
  { key: 'timeline' as const, label: 'Timeline', color: '#ed6c02' },
];

export default function BANTWeightsSection({ setValue, watch }: Props) {
  const weights = watch('bantWeights');
  const total = (weights?.budget ?? 0) + (weights?.authority ?? 0) + (weights?.need ?? 0) + (weights?.timeline ?? 0);
  const isValid = Math.abs(total - 1.0) < 0.01;

  const handleChange = (key: 'budget' | 'authority' | 'need' | 'timeline', value: number) => {
    setValue(`bantWeights.${key}`, Math.round(value * 100) / 100);
  };

  return (
    <Box>
      <Typography variant="h6" gutterBottom>BANT Weights</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Allocate weights across Budget, Authority, Need, and Timeline. Total must equal 1.0.
      </Typography>
      <Grid container spacing={2}>
        {BANT_LABELS.map(({ key, label, color }) => (
          <Grid item xs={12} key={key}>
            <Box display="flex" alignItems="center" gap={2}>
              <Typography sx={{ minWidth: 80, color }}>{label}</Typography>
              <Slider
                value={weights?.[key] ?? 0.25}
                onChange={(_e, v) => handleChange(key, v as number)}
                min={0}
                max={1}
                step={0.05}
                valueLabelDisplay="auto"
                valueLabelFormat={(v) => v.toFixed(2)}
                sx={{ color }}
              />
              <Typography sx={{ minWidth: 40, textAlign: 'right' }}>
                {(weights?.[key] ?? 0.25).toFixed(2)}
              </Typography>
            </Box>
          </Grid>
        ))}
      </Grid>
      <Typography
        variant="body2"
        sx={{ mt: 1, color: isValid ? 'success.main' : 'error.main', fontWeight: 600 }}
      >
        Total: {total.toFixed(2)} {isValid ? '' : '(must equal 1.00)'}
      </Typography>
    </Box>
  );
}
