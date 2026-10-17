import { Box, Typography } from '@mui/material';

import { Panel } from '@/shared/components/Panel';
import { dateTime } from '@/shared/lib/format';

import type { ComplaintDetail, TimelineEntry } from '../api/types';

const DOT: Record<TimelineEntry['actor']['kind'], string> = { system: 'grey.400', consumer: 'info.main', staff: 'primary.main' };

function who(a: TimelineEntry['actor']): string {
  if (a.kind === 'system') return 'System';
  return a.name ?? (a.kind === 'consumer' ? 'Consumer' : 'Staff');
}

/** An older server sends no timeline, so the raise and the automatic notes stand in for it. */
function entriesOf(c: ComplaintDetail): TimelineEntry[] {
  if (c.timeline) return c.timeline;
  const raised: TimelineEntry = { at: c.created_at, actor: { kind: 'system', name: null }, text: 'Complaint received' };
  const notes = c.messages.filter((m) => m.author_kind === 'system')
    .map((m): TimelineEntry => ({ at: m.created_at, actor: { kind: 'system', name: null }, text: m.body }));
  return [raised, ...notes];
}

function Entry({ e, last }: { e: TimelineEntry; last: boolean }) {
  return (
    <Box component="li" sx={{ position: 'relative', pl: 3, pb: last ? 0 : 2,
      // The rail runs from this dot to the next one; the last entry has none.
      '&::before': last ? undefined : { content: '""', position: 'absolute', left: 5, top: 14, bottom: 0, width: '2px', bgcolor: 'divider' } }}>
      <Box aria-hidden sx={{ position: 'absolute', left: 0, top: 4, width: 12, height: 12, borderRadius: '50%', bgcolor: DOT[e.actor.kind],
        border: 2, borderColor: 'background.paper' }} />
      <Typography variant="caption" component="p" sx={{ color: 'text.secondary' }}>
        <Box component="time" dateTime={e.at}>{dateTime(e.at)}</Box>
        {', '}
        <Box component="span" sx={{ fontWeight: 600, color: 'text.primary' }}>{who(e.actor)}</Box>
      </Typography>
      <Typography variant="body2" sx={{ overflowWrap: 'anywhere' }}>{e.text}</Typography>
    </Box>
  );
}

export function ComplaintTimeline({ complaint }: { complaint: ComplaintDetail }) {
  const entries = entriesOf(complaint);
  return (
    <Panel title="Timeline" caption="Who did what, oldest first. Automatic steps show as System.">
      <Box component="ol" aria-label="Complaint timeline" sx={{ listStyle: 'none', m: 0, p: 0, pt: 0.5 }}>
        {entries.map((e, i) => <Entry key={`${e.at}-${i}`} e={e} last={i === entries.length - 1} />)}
      </Box>
    </Panel>
  );
}
