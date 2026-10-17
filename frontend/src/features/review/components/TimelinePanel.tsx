import { Box, Typography } from '@mui/material';

import { TimelineText } from '@/features/complaints';
import { dateTime } from '@/shared/lib/format';

import type { CaseDetail, TimelineEntry } from '../api/types';
import { actorName } from '../model/labels';
import { Panel } from './Panel';

const DOT: Record<TimelineEntry['actor']['kind'], string> = { system: 'grey.400', consumer: 'info.main', staff: 'primary.main' };

function Entry({ e, last }: { e: TimelineEntry; last: boolean }) {
  return (
    <Box component="li" sx={{ position: 'relative', pl: 3, pb: last ? 0 : 2,
      // The rail runs from this dot down to the next one; the last entry has none.
      '&::before': last ? undefined : { content: '""', position: 'absolute', left: 5, top: 14, bottom: 0, width: '2px', bgcolor: 'divider' } }}>
      <Box aria-hidden sx={{ position: 'absolute', left: 0, top: 4, width: 12, height: 12, borderRadius: '50%', bgcolor: DOT[e.actor.kind],
        border: 2, borderColor: 'background.paper', boxShadow: 1 }} />
      <Typography variant="caption" component="p" sx={{ color: 'text.secondary' }}>
        <Box component="time" dateTime={e.at}>{dateTime(e.at)}</Box>
        {', '}
        <Box component="span" sx={{ fontWeight: 600, color: 'text.primary' }}>{actorName(e.actor)}</Box>
      </Typography>
      <TimelineText e={e} />
    </Box>
  );
}

/** Everything that happened on the case, oldest first, as the server recorded it. */
export function TimelinePanel({ c }: { c: CaseDetail }) {
  const entries = c.timeline;
  return (
    <Panel title="Timeline" caption="Every step on this case, oldest first. Automatic steps show as System.">
      {entries.length === 0 ? (
        <Typography variant="body2" sx={{ color: 'text.secondary' }}>Nothing recorded yet.</Typography>
      ) : (
        <Box component="ol" aria-label="Case timeline" tabIndex={0}
          sx={{ listStyle: 'none', m: 0, p: 0, pt: 0.5, maxHeight: 520, overflowY: 'auto', overscrollBehavior: 'contain', borderRadius: 1 }}>
          {entries.map((e, i) => <Entry key={`${e.at}-${i}`} e={e} last={i === entries.length - 1} />)}
        </Box>
      )}
    </Panel>
  );
}
