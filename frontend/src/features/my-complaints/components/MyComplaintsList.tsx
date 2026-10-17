import ChevronRightRoundedIcon from '@mui/icons-material/ChevronRightRounded';
import { Box, Chip, Divider, Skeleton, Stack, Typography } from '@mui/material';
import { Fragment } from 'react';
import { Link } from 'react-router-dom';

import { dateTime, monthLabel } from '@/shared/lib/format';

import type { MyComplaintRow } from '../api/types';
import { statusOf } from '../model/status';

function Row({ c }: { c: MyComplaintRow }) {
  const s = statusOf(c.status, c.status_label);
  const meta = [dateTime(c.created_at), c.bill_month ? monthLabel(c.bill_month) : null, c.service_masked ? `service no. ${c.service_masked}` : null]
    .filter(Boolean).join(', ');
  return (
    <Stack component={Link} to={`/complaints/${encodeURIComponent(c.ticket)}`} direction="row"
      sx={{ px: { xs: 2, sm: 2.5 }, py: 1.75, gap: 2, alignItems: 'center', color: 'inherit', textDecoration: 'none',
        transition: 'background-color 200ms', '&:hover': { bgcolor: 'action.hover' }, '&:focus-visible': { outlineOffset: -2 } }}>
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Stack direction="row" sx={{ gap: 1, alignItems: 'center', flexWrap: 'wrap', mb: 0.25 }}>
          <Typography variant="subtitle1" component="p">{c.type_label}</Typography>
          <Chip size="small" label={s.label} color={s.tone} variant={s.tone === 'warning' ? 'filled' : 'outlined'} />
        </Stack>
        <Typography variant="caption" component="p" sx={{ color: 'text.secondary', fontVariantNumeric: 'tabular-nums' }}>
          <Box component="span" sx={{ fontFamily: 'monospace', mr: 1 }}>{c.ticket}</Box>{meta}
        </Typography>
      </Box>
      <ChevronRightRoundedIcon sx={{ color: 'text.disabled' }} aria-hidden />
    </Stack>
  );
}

export function MyComplaintsList({ rows, loadingRows, dimmed }: { rows: MyComplaintRow[] | undefined; loadingRows: number; dimmed: boolean }) {
  if (!rows) {
    return (
      <Stack aria-busy aria-label="Loading your complaints">
        {Array.from({ length: Math.min(loadingRows, 5) }, (_, i) => (
          <Box key={i} sx={{ px: 2.5, py: 1.75 }}><Skeleton width="45%" /><Skeleton width="70%" height={16} /></Box>
        ))}
      </Stack>
    );
  }
  return (
    <Box component="nav" aria-label="Your complaints" sx={{ opacity: dimmed ? 0.6 : 1, transition: 'opacity 200ms' }}>
      {rows.map((c, i) => (
        <Fragment key={c.ticket}>
          {i > 0 && <Divider />}
          <Row c={c} />
        </Fragment>
      ))}
    </Box>
  );
}
