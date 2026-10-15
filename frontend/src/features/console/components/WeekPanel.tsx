import { Box, Button, Paper, Stack, Typography } from '@mui/material';
import { Link } from 'react-router-dom';

import { formatCount } from '@/shared/lib/format';

import type { Summary, WeekCounts } from '../api/consoleApi';
import { TileGroup, type Tile } from './TileGroup';

const rate = (w: WeekCounts) => (w.bills ? Math.round((w.mismatches / w.bills) * 100) : 0);

function versus(now: number, before: number, unit = ''): string {
  if (now === before) return 'Same as last week';
  return `${now > before ? 'Up' : 'Down'} from ${formatCount(before)}${unit} last week`;
}

function weekTiles(d: Summary): Tile[] {
  const { this_week: now, last_week: before, failed_deliveries: failed } = d.week;
  const tiles: Tile[] = [
    { label: 'Bills read', value: formatCount(now.bills), note: versus(now.bills, before.bills) },
    { label: 'Mismatch rate', value: `${rate(now)}%`, note: versus(rate(now), rate(before), '%') },
    { label: 'Complaints opened', value: formatCount(now.opened), note: versus(now.opened, before.opened) },
    { label: 'Complaints closed', value: formatCount(now.closed), note: versus(now.closed, before.closed) },
  ];
  if (failed) tiles.push({ label: 'Replies not delivered', value: formatCount(failed), note: 'Open complaints waiting on a resend', emphasis: 'alert' });
  return tiles;
}

/** Where consumers drop off between sending a photo and raising a complaint. */
function Funnel({ d }: { d: Summary }) {
  // Read attempts were logged later than bills, so older windows can have bills without reads; skip the step then.
  const photos: Array<[string, number]> = d.reads.total >= d.bills_read ? [['Photos received', d.reads.total]] : [];
  const steps: Array<[string, number]> = [
    ...photos,
    ['Read and checked', d.bills_read],
    ['Possible overcharge', d.audit.mismatch ?? 0],
    ['Complaint raised', d.complaints],
  ];
  const top = Math.max(1, ...steps.map(([, n]) => n));
  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Typography variant="overline" component="h2" sx={{ color: 'text.secondary' }}>From photo to complaint, last {d.days} days</Typography>
      <Stack component="ol" sx={{ m: 0, p: 0, listStyle: 'none', gap: 1, mt: 1 }}>
        {steps.map(([label, n]) => (
          <Stack component="li" key={label} direction="row" sx={{ gap: 1.5, alignItems: 'center' }}>
            <Typography variant="body2" sx={{ width: 150, flexShrink: 0 }}>{label}</Typography>
            <Box sx={{ flex: 1, bgcolor: 'grey.100', borderRadius: 0.5, height: 14, overflow: 'hidden' }}>
              <Box sx={{ width: `${(n / top) * 100}%`, height: '100%', bgcolor: 'primary.light', transition: 'width 400ms' }} />
            </Box>
            <Typography variant="body2" sx={{ width: 64, textAlign: 'right', fontVariantNumeric: 'tabular-nums', fontWeight: 600 }}>
              {formatCount(n)}
            </Typography>
          </Stack>
        ))}
      </Stack>
    </Paper>
  );
}

export function WeekPanel({ data }: { data: Summary | undefined }) {
  if (!data) return null;
  return (
    <Stack sx={{ gap: 2 }}>
      <TileGroup title="This week" columns={4} tiles={weekTiles(data)} />
      {data.week.failed_deliveries > 0 && (
        <Button component={Link} to="/console/complaints?failed=1" variant="outlined" color="error" sx={{ alignSelf: 'flex-start' }}>
          See replies that did not reach consumers
        </Button>
      )}
      <Funnel d={data} />
    </Stack>
  );
}
