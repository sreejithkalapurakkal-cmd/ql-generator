import { TextField, Grid, Typography, Chip, Box } from '@mui/material';
import { useState } from 'react';
import type { UseFormRegister, UseFormSetValue, UseFormWatch } from 'react-hook-form';
import type { ICPFormData } from '../../types/icp';

interface Props {
  register: UseFormRegister<ICPFormData>;
  setValue: UseFormSetValue<ICPFormData>;
  watch: UseFormWatch<ICPFormData>;
  errors: Record<string, unknown>;
}

export default function CompanyProfileSection({ register, setValue, watch, errors }: Props) {
  const [industryInput, setIndustryInput] = useState('');
  const industries = watch('icpProfile.industries') || [];

  const addIndustry = () => {
    const trimmed = industryInput.trim();
    if (trimmed && !industries.includes(trimmed)) {
      setValue('icpProfile.industries', [...industries, trimmed]);
      setIndustryInput('');
    }
  };

  const removeIndustry = (industry: string) => {
    setValue('icpProfile.industries', industries.filter((i: string) => i !== industry));
  };

  const getError = (path: string): string | undefined => {
    const parts = path.split('.');
    let current: unknown = errors;
    for (const part of parts) {
      if (current && typeof current === 'object' && part in current) {
        current = (current as Record<string, unknown>)[part];
      } else {
        return undefined;
      }
    }
    if (current && typeof current === 'object' && 'message' in current) {
      return (current as { message: string }).message;
    }
    return undefined;
  };

  return (
    <Box>
      <Typography variant="h6" gutterBottom>Company Profile</Typography>
      <Grid container spacing={2}>
        <Grid item xs={12}>
          <TextField
            label="Add Industry"
            value={industryInput}
            onChange={(e) => setIndustryInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addIndustry(); } }}
            fullWidth
            size="small"
            helperText={getError('icpProfile.industries') || 'Press Enter to add'}
            error={!!getError('icpProfile.industries')}
          />
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 1 }}>
            {industries.map((ind: string) => (
              <Chip key={ind} label={ind} onDelete={() => removeIndustry(ind)} size="small" />
            ))}
          </Box>
        </Grid>
        <Grid item xs={6}>
          <TextField
            label="Min Employees"
            type="number"
            {...register('icpProfile.companySizeRange.min', { valueAsNumber: true })}
            fullWidth
            size="small"
            error={!!getError('icpProfile.companySizeRange')}
            helperText={getError('icpProfile.companySizeRange')}
          />
        </Grid>
        <Grid item xs={6}>
          <TextField
            label="Max Employees"
            type="number"
            {...register('icpProfile.companySizeRange.max', { valueAsNumber: true })}
            fullWidth
            size="small"
          />
        </Grid>
        <Grid item xs={6}>
          <TextField
            label="Min Revenue ($)"
            type="number"
            {...register('icpProfile.revenueRange.min', { valueAsNumber: true })}
            fullWidth
            size="small"
            error={!!getError('icpProfile.revenueRange')}
            helperText={getError('icpProfile.revenueRange')}
          />
        </Grid>
        <Grid item xs={6}>
          <TextField
            label="Max Revenue ($)"
            type="number"
            {...register('icpProfile.revenueRange.max', { valueAsNumber: true })}
            fullWidth
            size="small"
          />
        </Grid>
      </Grid>
    </Box>
  );
}
