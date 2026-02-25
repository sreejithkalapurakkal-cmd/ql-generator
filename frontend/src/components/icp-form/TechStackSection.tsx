import { TextField, Typography, Chip, Box } from '@mui/material';
import { useState } from 'react';
import type { UseFormSetValue, UseFormWatch } from 'react-hook-form';
import type { ICPFormData } from '../../types/icp';

interface Props {
  setValue: UseFormSetValue<ICPFormData>;
  watch: UseFormWatch<ICPFormData>;
}

export default function TechStackSection({ setValue, watch }: Props) {
  const [input, setInput] = useState('');
  const techStack = watch('icpProfile.techStack') || [];

  const add = () => {
    const trimmed = input.trim();
    if (trimmed && !techStack.includes(trimmed)) {
      setValue('icpProfile.techStack', [...techStack, trimmed]);
      setInput('');
    }
  };

  const remove = (item: string) => {
    setValue('icpProfile.techStack', techStack.filter((t: string) => t !== item));
  };

  return (
    <Box>
      <Typography variant="h6" gutterBottom>Technology Stack</Typography>
      <TextField
        label="Add Technology"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); add(); } }}
        fullWidth
        size="small"
        helperText="Press Enter to add (e.g., AWS, Kubernetes, Python)"
      />
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 1 }}>
        {techStack.map((tech: string) => (
          <Chip key={tech} label={tech} onDelete={() => remove(tech)} size="small" color="primary" variant="outlined" />
        ))}
      </Box>
    </Box>
  );
}
