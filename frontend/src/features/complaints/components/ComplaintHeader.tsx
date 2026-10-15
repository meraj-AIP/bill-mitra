import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { Box, Button, Chip, Stack, Typography } from '@mui/material';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';

import { dateTime, monthLabel, rupees } from '@/shared/lib/format';

import type { ComplaintDetail, ComplaintStatus } from '../api/types';
import { CHANNEL_LABEL, STATUS_TONE } from '../model/labels';

export function StatusChip({ status, size = 'small' }: { status: ComplaintStatus; size?: 'small' | 'medium' }) {
  const tone = STATUS_TONE[status] ?? 'default';
  return <Chip size={size} label={status} color={tone} variant={status === 'Open' ? 'filled' : 'outlined'} />;
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <Box sx={{ minWidth: 0 }}>
      <Typography variant="caption" component="p" sx={{ color: 'text.secondary' }}>{label}</Typography>
      <Typography variant="subtitle1" component="p" noWrap sx={{ fontVariantNumeric: 'tabular-nums' }}>{value}</Typography>
    </Box>
  );
}

interface ComplaintHeaderProps {
  complaint: ComplaintDetail;
  backTo: string;
  backLabel: string;
  actions?: ReactNode;
}

export function ComplaintHeader({ complaint, backTo, backLabel, actions }: ComplaintHeaderProps) {
  const month = complaint.bill_month ?? complaint.bill?.bill_month ?? null;
  return (
    <Stack component="header" sx={{ gap: 2 }}>
      <Box>
        <Button component={Link} to={backTo} startIcon={<ArrowBackIcon />} size="small" sx={{ ml: -1 }}>{backLabel}</Button>
      </Box>
      <Stack direction={{ xs: 'column', md: 'row' }} sx={{ gap: 2, alignItems: { md: 'flex-start' } }}>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Stack direction="row" sx={{ gap: 1.5, alignItems: 'center', flexWrap: 'wrap' }}>
            <Typography variant="h1" sx={{ fontFamily: 'monospace', fontSize: { xs: '1.5rem', md: '1.875rem' }, letterSpacing: 0 }}>
              {complaint.ticket}
            </Typography>
            <StatusChip status={complaint.status} size="medium" />
          </Stack>
          <Typography variant="body1" sx={{ color: 'text.secondary', mt: 0.75, maxWidth: '70ch' }}>{complaint.issue}</Typography>
        </Box>
        {actions}
      </Stack>
      <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: 'repeat(2, minmax(0, 1fr))', sm: 'repeat(3, minmax(0, 1fr))', md: 'repeat(5, minmax(0, 1fr))' },
        p: 2, borderRadius: 2, bgcolor: 'background.paper', border: 1, borderColor: 'divider' }}>
        <Fact label="DISCOM" value={complaint.discom ?? complaint.bill?.discom ?? 'Unknown'} />
        <Fact label="Bill month" value={monthLabel(month)} />
        <Fact label="Amount in question" value={complaint.amount ? rupees(complaint.amount) : 'Not stated'} />
        <Fact label="Raised" value={dateTime(complaint.created_at)} />
        <Fact label="Raised on" value={complaint.channel ? CHANNEL_LABEL[complaint.channel] : 'Unknown'} />
      </Box>
    </Stack>
  );
}
