import { Chip } from '@mui/material';
import type { JobStatus } from '../../types/job';

const statusConfig: Record<JobStatus, { color: 'default' | 'primary' | 'secondary' | 'error' | 'info' | 'success' | 'warning'; label: string }> = {
  PENDING: { color: 'default', label: 'Pending' },
  SEARCHING: { color: 'info', label: 'Searching' },
  ENRICHING: { color: 'primary', label: 'Enriching' },
  SCORING: { color: 'secondary', label: 'Scoring' },
  COMPLETED: { color: 'success', label: 'Completed' },
  FAILED: { color: 'error', label: 'Failed' },
};

interface Props {
  status: JobStatus;
}

export default function JobStatusBadge({ status }: Props) {
  const config = statusConfig[status] || { color: 'default' as const, label: status };
  return <Chip label={config.label} color={config.color} size="small" />;
}
