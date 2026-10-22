import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import AutoAwesomeOutlinedIcon from '@mui/icons-material/AutoAwesomeOutlined';
import { Box, Button, Chip, Stack, Typography } from '@mui/material';
import { Link } from 'react-router-dom';

import { DemoChip, PriorityChip, SenderChip, StatusChip, type ComplaintDetail } from '@/features/complaints';

import { sourceOf } from './ComplaintSnapshot';

interface DetailHeaderProps {
  complaint: ComplaintDetail;
  backTo: string;
  /** Opens AI assist; null hides the button for accounts that cannot reply. */
  onAssist: (() => void) | null;
}

/** What the complaint is, where it came from and where it stands, on two short lines. Due and whose move are in the
 * snapshot under it. */
export function DetailHeader({ complaint: c, backTo, onAssist }: DetailHeaderProps) {
  return (
    <Stack direction={{ xs: 'column', sm: 'row' }} component="header" sx={{ gap: 1.5, alignItems: { sm: 'flex-end' } }}>
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Stack direction="row" sx={{ gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
          <Button component={Link} to={backTo} size="small" startIcon={<ArrowBackIcon />} sx={{ ml: -1 }}>Complaints</Button>
          <Typography variant="caption" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>{c.ticket}</Typography>
          {c.demo && <DemoChip />}
        </Stack>
        <Stack direction="row" sx={{ gap: 1, alignItems: 'center', flexWrap: 'wrap', mt: 0.5 }}>
          <Typography variant="h2" component="h1" sx={{ mr: 0.5 }}>{c.type_label ?? 'Complaint'}</Typography>
          <StatusChip status={c.status} />
          {c.priority && c.priority !== 'normal' && <PriorityChip priority={c.priority} />}
          <SenderChip check={c.sender} staffRaised={Boolean(c.raised_by)} />
          {c.delivery_failed && <Chip size="small" color="error" variant="outlined" label="Last reply not delivered" />}
        </Stack>
        <Typography variant="body2" sx={{ color: 'text.secondary', mt: 0.5 }}>
          {[c.section, c.discom].filter(Boolean).join(', ') || 'Not placed yet'}
          {c.service_masked ? ` · Service ${c.service_masked}` : ''}
          {` · ${sourceOf(c)}`}
        </Typography>
      </Box>
      {onAssist && (
        <Button variant="outlined" startIcon={<AutoAwesomeOutlinedIcon />} onClick={onAssist} sx={{ flexShrink: 0 }}>AI assist</Button>
      )}
    </Stack>
  );
}
