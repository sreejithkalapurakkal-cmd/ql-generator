import { TextField, Typography, Chip, Box } from '@mui/material';
import { useState } from 'react';
import type { UseFormSetValue, UseFormWatch } from 'react-hook-form';
import type { ICPFormData } from '../../types/icp';

interface Props {
  setValue: UseFormSetValue<ICPFormData>;
  watch: UseFormWatch<ICPFormData>;
  errors: Record<string, unknown>;
}

export default function GeographySection({ setValue, watch, errors }: Props) {
  const [input, setInput] = useState('');
  const geographies = watch('icpProfile.geographies') || [];

  const add = () => {
    const trimmed = input.trim();
    if (trimmed && !geographies.includes(trimmed)) {
      setValue('icpProfile.geographies', [...geographies, trimmed]);
      setInput('');
    }
  };

  const remove = (item: string) => {
    setValue('icpProfile.geographies', geographies.filter((g: string) => g !== item));
  };

  const geoError = (errors as { icpProfile?: { geographies?: { message?: string } } })
    ?.icpProfile?.geographies?.message;

  return (
    <Box>
      <Typography variant="h6" gutterBottom>Target Geographies</Typography>
      <TextField
        label="Add Geography"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); add(); } }}
        fullWidth
        size="small"
        helperText={geoError || 'Press Enter to add (e.g., US, UK, Germany)'}
        error={!!geoError}
      />
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 1 }}>
        {geographies.map((geo: string) => (
          <Chip key={geo} label={geo} onDelete={() => remove(geo)} size="small" color="secondary" variant="outlined" />
        ))}
      </Box>
    </Box>
  );
}
