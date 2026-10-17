import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import PersonOutlineRoundedIcon from '@mui/icons-material/PersonOutlineRounded';
import { Box, Button, Chip, Stack, Typography } from '@mui/material';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';

import { dateTime, monthLabel } from '@/shared/lib/format';

import type { CaseDetail } from '../api/types';
import { STATE } from '../model/labels';
import { ReassignControl, UnmaskControl } from './CaseControls';
import { OverdueChip, StateChip } from './StateChip';

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <Box sx={{ minWidth: 0 }}>
      <Typography variant="caption" component="p" sx={{ color: 'text.secondary' }}>{label}</Typography>
      {typeof children === 'string'
        ? <Typography variant="subtitle1" component="p" noWrap title={children}>{children}</Typography>
        : children}
    </Box>
  );
}

export function CaseHeader({ c }: { c: CaseDetail }) {
  const sla = c.policy.decision_sla_days;
  return (
    <Stack component="header" sx={{ gap: 2 }}>
      <Box>
        <Button component={Link} to="/review" startIcon={<ArrowBackIcon />} size="small" sx={{ ml: -1 }}>Review queue</Button>
      </Box>
      <Stack direction={{ xs: 'column', md: 'row' }} sx={{ gap: 2, alignItems: { md: 'flex-start' } }}>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Stack direction="row" sx={{ gap: 1.25, alignItems: 'center', flexWrap: 'wrap' }}>
            <Typography variant="h1" sx={{ fontFamily: 'monospace', fontSize: { xs: '1.5rem', md: '1.875rem' }, letterSpacing: 0 }}>
              {c.ticket}
            </Typography>
            <StateChip state={c.state} size="medium" />
            {c.overdue && <OverdueChip days={c.days_open} size="medium" />}
            <Chip size="medium" variant="outlined" icon={<PersonOutlineRoundedIcon />} label={c.assignee ? `With ${c.assignee.name}` : 'At the division'} />
          </Stack>
          <Typography variant="body1" sx={{ color: 'text.secondary', mt: 0.75, maxWidth: '70ch' }}>
            {STATE[c.state].hint}. Decide within {sla} {sla === 1 ? 'day' : 'days'} of opening; this case has been open {c.days_open} {c.days_open === 1 ? 'day' : 'days'}.
          </Typography>
        </Box>
        <ReassignControl c={c} />
      </Stack>
      <Box sx={{ display: 'grid', gap: 2, p: 2, borderRadius: 2, bgcolor: 'background.paper', border: 1, borderColor: 'divider',
        gridTemplateColumns: { xs: 'repeat(2, minmax(0, 1fr))', sm: 'repeat(3, minmax(0, 1fr))', md: 'repeat(6, minmax(0, 1fr))' } }}>
        <Fact label="Section">{c.section ?? 'Not mapped yet'}</Fact>
        <Fact label="DISCOM">{c.discom}</Fact>
        <Fact label="Bill month">{monthLabel(c.bill_month)}</Fact>
        <Fact label="Service number"><UnmaskControl c={c} /></Fact>
        <Fact label="With">{c.assignee?.name ?? 'Unassigned, at the division'}</Fact>
        <Fact label="Opened">{`${dateTime(c.created_at)}, ${c.channel === 'whatsapp' ? 'WhatsApp' : 'web app'}`}</Fact>
      </Box>
    </Stack>
  );
}
