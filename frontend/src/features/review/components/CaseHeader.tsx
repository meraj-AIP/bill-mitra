import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import PersonOutlineRoundedIcon from '@mui/icons-material/PersonOutlineRounded';
import { Box, Button, Chip, Stack, Typography } from '@mui/material';
import { Link } from 'react-router-dom';

import { SenderChip } from '@/features/complaints';
import { dateTime, monthLabel } from '@/shared/lib/format';

import type { CaseDetail } from '../api/types';
import { headline } from '../model/headline';
import { ReassignControl, UnmaskControl } from './CaseControls';
import { CaseSnapshot } from './CaseSnapshot';
import { OverdueChip, StateChip } from './StateChip';

/** What the case is (the flag, said plainly), where it stands, and the facts behind it in one row. */
export function CaseHeader({ c }: { c: CaseDetail }) {
  return (
    <Stack component="header" sx={{ gap: 2 }}>
      <Stack direction="row" sx={{ gap: 2, alignItems: 'flex-start' }}>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Stack direction="row" sx={{ gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
            <Button component={Link} to="/review" startIcon={<ArrowBackIcon />} size="small" sx={{ ml: -1 }}>Review queue</Button>
            <Typography variant="caption" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>{c.ticket}</Typography>
            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
              {`Opened ${dateTime(c.created_at)} on ${c.channel === 'whatsapp' ? 'WhatsApp' : 'the web app'}`}
            </Typography>
          </Stack>
          <Stack direction="row" sx={{ gap: 1, alignItems: 'center', flexWrap: 'wrap', mt: 0.5 }}>
            <Typography variant="h2" component="h1" sx={{ mr: 0.5 }}>{headline(c)}</Typography>
            <StateChip state={c.state} />
            {c.overdue && <OverdueChip days={c.days_open} />}
          </Stack>
          <Stack direction="row" sx={{ gap: 1, alignItems: 'center', flexWrap: 'wrap', mt: 0.75, color: 'text.secondary' }}>
            <Typography variant="body2">{`${[c.section ?? 'Section not mapped', c.discom].join(', ')} · ${monthLabel(c.bill_month)} bill · Service`}</Typography>
            <UnmaskControl c={c} inline />
            <Chip size="small" variant="outlined" icon={<PersonOutlineRoundedIcon />} label={c.assignee ? `With ${c.assignee.name}` : 'At the division'} />
            <SenderChip check={c.sender} />
          </Stack>
        </Box>
        <ReassignControl c={c} />
      </Stack>
      <CaseSnapshot c={c} />
    </Stack>
  );
}
