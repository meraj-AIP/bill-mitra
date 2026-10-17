import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import HourglassEmptyRoundedIcon from '@mui/icons-material/HourglassEmptyRounded';
import PersonOutlineRoundedIcon from '@mui/icons-material/PersonOutlineRounded';
import { Box, Button, Chip, Stack, Typography } from '@mui/material';
import { Link } from 'react-router-dom';

import { dateTime } from '@/shared/lib/format';

import type { ComplaintDetail, ComplaintStatus } from '../api/types';
import { holderOf } from '../model/handoff';
import { PRIORITY, STATUS_TONE } from '../model/labels';
import { DemoChip, DueChip } from './DueChip';

export function StatusChip({ status, size = 'small' }: { status: ComplaintStatus; size?: 'small' | 'medium' }) {
  const tone = STATUS_TONE[status] ?? 'default';
  return <Chip size={size} label={status} color={tone} variant={status === 'Open' ? 'filled' : 'outlined'} />;
}

interface PriorityChipProps {
  priority: ComplaintDetail['priority'];
  size?: 'small' | 'medium';
  /** Adds the word priority where no column header says it. */
  spelled?: boolean;
}

export function PriorityChip({ priority, size = 'small', spelled = false }: PriorityChipProps) {
  if (!priority) return null;
  const p = PRIORITY[priority];
  // Only urgent and high need to catch the eye; normal and low stay quiet.
  return <Chip size={size} color={p.tone} variant={p.tone === 'default' ? 'outlined' : 'filled'} label={spelled ? `${p.label} priority` : p.label} />;
}

/** Who holds it now, and whether the next move is the consumer's. */
function HolderChips({ complaint }: { complaint: ComplaintDetail }) {
  const holder = holderOf(complaint);
  return (
    <>
      <Chip size="medium" variant="outlined" icon={<PersonOutlineRoundedIcon />}
        label={holder ? `With ${holder.name}` : 'Not with anyone yet'} />
      {complaint.waiting_on === 'consumer' && (
        <Chip size="medium" color="info" icon={<HourglassEmptyRoundedIcon />} label="Waiting on consumer" />
      )}
    </>
  );
}

interface ComplaintHeaderProps {
  complaint: ComplaintDetail;
  backTo: string;
  backLabel: string;
}

/** Ticket, what the complaint is about, and where it stands, in that order of reading. */
export function ComplaintHeader({ complaint, backTo, backLabel }: ComplaintHeaderProps) {
  const title = complaint.type_label ?? complaint.issue;
  // The consumer's own words already sit under On file, so the lead only carries an issue with no description.
  const lead = complaint.type_label && !complaint.description && complaint.issue !== complaint.type_label ? complaint.issue : null;
  return (
    <Stack component="header" sx={{ gap: 1.5 }}>
      <Box>
        <Button component={Link} to={backTo} startIcon={<ArrowBackIcon />} size="small" sx={{ ml: -1 }}>{backLabel}</Button>
      </Box>
      <Stack direction="row" sx={{ gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
        <Typography component="p" sx={{ fontFamily: 'monospace', fontSize: '0.875rem', fontWeight: 600, color: 'text.secondary', letterSpacing: '0.02em' }}>
          {complaint.ticket}
        </Typography>
        <Typography component="span" aria-hidden sx={{ color: 'text.disabled' }}>/</Typography>
        <Typography variant="caption" component="p" sx={{ color: 'text.secondary' }}>Raised {dateTime(complaint.created_at)}</Typography>
        {complaint.demo && <DemoChip />}
      </Stack>
      <Typography variant="h1" sx={{ maxWidth: '28ch' }}>{title}</Typography>
      {lead && <Typography variant="body1" sx={{ color: 'text.secondary', maxWidth: '65ch' }}>{lead}</Typography>}
      <Stack direction="row" sx={{ gap: 1, flexWrap: 'wrap', alignItems: 'center', pt: 0.5 }}>
        <StatusChip status={complaint.status} size="medium" />
        <PriorityChip priority={complaint.priority} size="medium" spelled />
        <DueChip c={complaint} size="medium" />
        <HolderChips complaint={complaint} />
      </Stack>
    </Stack>
  );
}
