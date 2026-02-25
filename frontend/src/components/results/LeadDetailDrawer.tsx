import {
  Drawer,
  Box,
  Typography,
  IconButton,
  Divider,
  Chip,
  Link,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import BANTScoreCard from './BANTScoreCard';
import { formatCurrency, formatEmployeeCount } from '../../lib/formatters';
import type { Lead } from '../../types/lead';

interface Props {
  lead: Lead | null;
  open: boolean;
  onClose: () => void;
}

export default function LeadDetailDrawer({ lead, open, onClose }: Props) {
  if (!lead) return null;

  return (
    <Drawer anchor="right" open={open} onClose={onClose} sx={{ '& .MuiDrawer-paper': { width: 420, p: 3 } }}>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h6">{lead.companyName}</Typography>
        <IconButton onClick={onClose} size="small">
          <CloseIcon />
        </IconButton>
      </Box>

      {lead.domain && (
        <Link href={`https://${lead.domain}`} target="_blank" rel="noopener" variant="body2" sx={{ mb: 2, display: 'block' }}>
          {lead.domain}
        </Link>
      )}

      <Divider sx={{ mb: 2 }} />

      <Typography variant="subtitle2" color="text.secondary">Industry</Typography>
      <Typography variant="body2" sx={{ mb: 1.5 }}>{lead.industry || 'N/A'}</Typography>

      <Typography variant="subtitle2" color="text.secondary">Employees</Typography>
      <Typography variant="body2" sx={{ mb: 1.5 }}>{formatEmployeeCount(lead.employeeCount)}</Typography>

      <Typography variant="subtitle2" color="text.secondary">Revenue</Typography>
      <Typography variant="body2" sx={{ mb: 1.5 }}>{formatCurrency(lead.estimatedRevenue)}</Typography>

      <Typography variant="subtitle2" color="text.secondary">Location</Typography>
      <Typography variant="body2" sx={{ mb: 1.5 }}>{lead.location || 'N/A'}</Typography>

      <Typography variant="subtitle2" color="text.secondary">Funding Stage</Typography>
      <Typography variant="body2" sx={{ mb: 1.5 }}>{lead.fundingStage || 'N/A'}</Typography>

      {lead.techStack.length > 0 && (
        <>
          <Typography variant="subtitle2" color="text.secondary">Tech Stack</Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 1.5 }}>
            {lead.techStack.map((t) => (
              <Chip key={t} label={t} size="small" variant="outlined" />
            ))}
          </Box>
        </>
      )}

      {lead.description && (
        <>
          <Typography variant="subtitle2" color="text.secondary">Description</Typography>
          <Typography variant="body2" sx={{ mb: 1.5 }}>{lead.description}</Typography>
        </>
      )}

      <Divider sx={{ my: 2 }} />

      <BANTScoreCard score={lead.bantScore} />

      {lead.bantScore.reasoning && (
        <>
          <Divider sx={{ my: 2 }} />
          <Typography variant="subtitle2" color="text.secondary">Scoring Reasoning</Typography>
          <Typography variant="body2" sx={{ whiteSpace: 'pre-line', mt: 0.5 }}>
            {lead.bantScore.reasoning}
          </Typography>
        </>
      )}
    </Drawer>
  );
}
