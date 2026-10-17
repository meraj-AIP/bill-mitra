import { Alert, Grid } from '@mui/material';

import type { Queues } from '@/shared/api/health';
import { StatTile } from '@/shared/components/StatTile';
import { formatCount } from '@/shared/lib/format';

const QUEUES: Array<[keyof Omit<Queues, 'oldest_queued_s'>, string]> = [
  ['inbox', 'Incoming messages'],
  ['outbox', 'Outgoing messages'],
  ['extract', 'Bill reads'],
];

function age(seconds: number | null): string {
  if (seconds === null) return 'Nothing waiting';
  if (seconds < 120) return `${formatCount(Math.round(seconds))} s`;
  if (seconds < 7200) return `${formatCount(Math.round(seconds / 60))} min`;
  return `${formatCount(Math.round(seconds / 3600))} h`;
}

/** Waiting and parked counts per queue, from /api/health. Undefined while loading draws skeletons. */
export function QueueCounts({ queues, loading }: { queues: Queues | undefined; loading: boolean }) {
  if (!queues && !loading) return <Alert severity="info">This server does not report queue counts yet.</Alert>;
  return (
    <Grid container spacing={2}>
      {QUEUES.map(([key, label]) => {
        const q = queues?.[key];
        return (
          <Grid key={key} size={{ xs: 6, md: 3 }}>
            <StatTile label={label} value={q && formatCount(q.queued)} note={q ? `${formatCount(q.failed)} parked` : undefined}
              emphasis={q && q.failed > 0 ? 'alert' : 'default'} />
          </Grid>
        );
      })}
      <Grid size={{ xs: 6, md: 3 }}>
        <StatTile label="Oldest waiting" value={queues && age(queues.oldest_queued_s)} note="Across all queues" />
      </Grid>
    </Grid>
  );
}
