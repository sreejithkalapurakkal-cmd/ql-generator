import { Box, Typography } from '@mui/material';
import SearchOffIcon from '@mui/icons-material/SearchOff';

interface EmptyStateProps {
  title: string;
  description?: string;
}

export default function EmptyState({ title, description }: EmptyStateProps) {
  return (
    <Box display="flex" flexDirection="column" alignItems="center" justifyContent="center" py={8}>
      <SearchOffIcon sx={{ fontSize: 64, color: 'text.disabled', mb: 2 }} />
      <Typography variant="h6" color="text.secondary">
        {title}
      </Typography>
      {description && (
        <Typography variant="body2" color="text.disabled" sx={{ mt: 1 }}>
          {description}
        </Typography>
      )}
    </Box>
  );
}
