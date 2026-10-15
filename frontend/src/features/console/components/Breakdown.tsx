import { Box, LinearProgress, Paper, Skeleton, Stack, Typography } from '@mui/material';

import { formatCount } from '@/shared/lib/format';

const INTENT_LABEL: Record<string, string> = {
  why_high: 'Why is it high?',
  next_bill: 'Next bill',
  save: 'How to save',
  gruha_jyothi: 'Gruha Jyothi',
  explain_fsa: 'What is FSA?',
  explain_true_up: 'What is true-up?',
  explain_fixed: 'Fixed charge',
  explain_customer: 'Customer charge',
  explain_duty: 'Electricity duty',
  due: 'Due date',
  complain: 'Complaint',
  power_cut: 'Power cut',
  what_if: 'What if',
  off_topic: 'Off topic',
  greeting: 'Greeting',
  help: 'Help',
};

const LANGUAGE_LABEL: Record<string, string> = { te: 'Telugu', en: 'English', hi: 'Hindi', ur: 'Urdu' };

interface BreakdownProps {
  title: string;
  caption: string;
  rows: Array<{ label: string; count: number }> | undefined;
}

function Breakdown({ title, caption, rows }: BreakdownProps) {
  const total = rows?.reduce((sum, r) => sum + r.count, 0) ?? 0;
  return (
    <Paper variant="outlined" sx={{ p: 2, height: '100%' }}>
      <Typography variant="h3" component="h2">{title}</Typography>
      <Typography variant="caption" sx={{ color: 'text.secondary' }}>
        {caption}
      </Typography>
      <Stack sx={{ gap: 1.25, mt: 1.5 }}>
        {!rows && [0, 1, 2, 3].map((i) => <Skeleton key={i} height={28} />)}
        {rows?.length === 0 && <Typography variant="body2">No data yet.</Typography>}
        {rows?.map((row) => (
          <Box key={row.label}>
            <Stack direction="row" sx={{ justifyContent: 'space-between' }}>
              <Typography variant="body2">{row.label}</Typography>
              <Typography variant="body2" sx={{ fontVariantNumeric: 'tabular-nums', color: 'text.secondary' }}>
                {formatCount(row.count)} · {total ? Math.round((row.count / total) * 100) : 0}%
              </Typography>
            </Stack>
            <LinearProgress variant="determinate" value={total ? (row.count / total) * 100 : 0}
              sx={{ height: 6, borderRadius: 3, mt: 0.5, bgcolor: 'grey.100' }} />
          </Box>
        ))}
      </Stack>
    </Paper>
  );
}

export function IntentBreakdown({ rows }: { rows: Array<{ intent: string; count: number }> | undefined }) {
  return (
    <Breakdown title="What people ask" caption="Top questions after a bill"
      rows={rows?.map((r) => ({ label: INTENT_LABEL[r.intent] ?? r.intent, count: r.count }))} />
  );
}

export function LanguageBreakdown({ rows }: { rows: Array<{ language: string; count: number }> | undefined }) {
  return (
    <Breakdown title="Languages" caption="Reply language chosen by the consumer"
      rows={rows?.map((r) => ({ label: LANGUAGE_LABEL[r.language] ?? r.language, count: r.count }))} />
  );
}
