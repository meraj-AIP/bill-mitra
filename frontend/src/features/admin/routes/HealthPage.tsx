import { Box, Button, Chip, Container, Grid, Paper, Stack, Typography } from '@mui/material';
import { Link } from 'react-router-dom';

import { PageHeader } from '@/shared/components/PageHeader';
import { ErrorState } from '@/shared/components/States';
import { StatTile } from '@/shared/components/StatTile';
import { formatCount } from '@/shared/lib/format';

import { useSystemHealth, type SystemHealth } from '../api/healthApi';

const PROVIDERS: Array<[keyof SystemHealth['modes'], string, string]> = [
  ['vision', 'Bill reading', 'OpenAI vision'],
  ['language_model', 'Explanations', 'OpenAI text, checked by the number guard'],
  ['voice', 'Telugu voice notes', 'Sarvam'],
  ['listening', 'Voice questions', 'Soniox'],
  ['whatsapp', 'WhatsApp', 'Meta Cloud API'],
];
const GOOD = new Set(['live', 'connected']);

function Providers({ modes }: { modes: SystemHealth['modes'] }) {
  return (
    <Paper variant="outlined">
      {PROVIDERS.map(([key, label, via]) => (
        <Stack key={key} direction="row" sx={{ px: 2, py: 1.5, gap: 2, alignItems: 'center', borderBottom: 1, borderColor: 'divider',
          '&:last-of-type': { borderBottom: 0 } }}>
          <Box sx={{ flex: 1 }}>
            <Typography variant="subtitle1" component="p">{label}</Typography>
            <Typography variant="caption" sx={{ color: 'text.secondary' }}>{via}</Typography>
          </Box>
          <Chip size="small" label={modes[key]} color={GOOD.has(modes[key]) ? 'success' : 'warning'} variant="outlined" />
        </Stack>
      ))}
    </Paper>
  );
}

function Warnings({ h }: { h: SystemHealth }) {
  const ex = h.explanations;
  const tiles = [
    { label: 'Guard fell back today', value: formatCount(ex.llm_fallback), note: `${formatCount(ex.llm_pass)} AI explanations passed`, alert: ex.llm_fallback > 0 },
    { label: 'Bills not read today', value: formatCount(h.reads.failed), note: `${formatCount(h.reads.retake)} asked to retake`, alert: h.reads.failed > 0 },
    { label: 'Replies not delivered', value: formatCount(h.failed_deliveries_7d), note: 'Last 7 days', alert: h.failed_deliveries_7d > 0 },
    { label: 'Complaints overdue', value: formatCount(h.complaints_overdue), note: `Open after ${h.reply_days} days`, alert: h.complaints_overdue > 0 },
  ];
  return (
    <Grid container spacing={2}>
      {tiles.map((t) => (
        <Grid key={t.label} size={{ xs: 6, md: 3 }}>
          <StatTile label={t.label} value={t.value} note={t.note} emphasis={t.alert ? 'alert' : 'default'} />
        </Grid>
      ))}
    </Grid>
  );
}

/** One place to see whether consumers are being served right now. Counts only. */
export function HealthPage() {
  const health = useSystemHealth();
  const h = health.data;
  return (
    <Container maxWidth="lg" sx={{ py: { xs: 3, md: 5 } }}>
      <Stack sx={{ gap: 3 }}>
        <PageHeader eyebrow="Admin" title="System health" lead="Which services are on, and anything that went wrong today. Refreshes every minute." />
        {health.isError && <ErrorState message="Could not load system health." onRetry={() => void health.refetch()} />}
        {h && (
          <>
            <Warnings h={h} />
            {h.failed_deliveries_open > 0 && (
              <Button component={Link} to="/console/complaints?failed=1" variant="outlined" color="error" sx={{ alignSelf: 'flex-start' }}>
                {formatCount(h.failed_deliveries_open)} open complaints are waiting on a resend
              </Button>
            )}
            <Providers modes={h.modes} />
          </>
        )}
      </Stack>
    </Container>
  );
}
