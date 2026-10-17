import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import AutoAwesomeOutlinedIcon from '@mui/icons-material/AutoAwesomeOutlined';
import { Box, Button, Chip, Stack, Typography } from '@mui/material';
import { Link } from 'react-router-dom';

import { DemoChip, DueChip, PriorityChip, StatusChip, type ComplaintDetail } from '@/features/complaints';
import { dateTime } from '@/shared/lib/format';

interface DetailHeaderProps {
  complaint: ComplaintDetail;
  backTo: string;
  /** Opens AI assist; null hides the button for accounts that cannot reply. */
  onAssist: (() => void) | null;
}

/** Ticket, what it is about and where it stands, on two short lines. */
export function DetailHeader({ complaint: c, backTo, onAssist }: DetailHeaderProps) {
  return (
    <Stack direction={{ xs: 'column', sm: 'row' }} component="header" sx={{ gap: 1.5, alignItems: { sm: 'flex-end' } }}>
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Stack direction="row" sx={{ gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
          <Button component={Link} to={backTo} size="small" startIcon={<ArrowBackIcon />} sx={{ ml: -1 }}>Complaints</Button>
          <Typography variant="caption" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>{c.ticket}</Typography>
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>Raised {dateTime(c.created_at)}</Typography>
          {c.demo && <DemoChip />}
        </Stack>
        <Stack direction="row" sx={{ gap: 1, alignItems: 'center', flexWrap: 'wrap', mt: 0.5 }}>
          <Typography variant="h2" component="h1" sx={{ mr: 0.5 }}>{c.type_label ?? 'Complaint'}</Typography>
          <StatusChip status={c.status} />
          {c.priority && <PriorityChip priority={c.priority} />}
          <DueChip c={c} />
          {c.waiting_on === 'consumer' && <Chip size="small" color="info" label="Waiting on consumer" />}
        </Stack>
      </Box>
      {onAssist && (
        <Button variant="outlined" startIcon={<AutoAwesomeOutlinedIcon />} onClick={onAssist} sx={{ flexShrink: 0 }}>AI assist</Button>
      )}
    </Stack>
  );
}
