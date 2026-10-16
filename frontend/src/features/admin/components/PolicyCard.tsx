import {
  Alert, Box, Button, CircularProgress, FormControlLabel, InputAdornment, Paper, Stack, Switch, TextField, Typography,
} from '@mui/material';
import { useState, type FormEvent, type ReactNode } from 'react';

import type { Policy } from '@/features/review';
import { rupees } from '@/shared/lib/format';

import { useSavePolicy } from '../api/policyApi';

type Draft = Record<'ae_limit' | 'spike_ratio' | 'spike_min_increase' | 'min_history_months' | 'decision_sla_days', string>;

const toDraft = (p: Policy): Draft => ({
  ae_limit: p.ae_limit === null ? '' : String(p.ae_limit),
  spike_ratio: String(p.spike_ratio),
  spike_min_increase: String(p.spike_min_increase),
  min_history_months: String(p.min_history_months),
  decision_sla_days: String(p.decision_sla_days),
});

function problemsOf(d: Draft): Partial<Record<keyof Draft, string>> {
  const out: Partial<Record<keyof Draft, string>> = {};
  if (d.ae_limit.trim() && !(Number(d.ae_limit) > 0)) out.ae_limit = 'Enter an amount above zero, or leave it empty for no limit.';
  if (!(Number(d.spike_ratio) > 1)) out.spike_ratio = 'Use a number above 1, such as 2.';
  if (!(Number(d.spike_min_increase) >= 0) || !d.spike_min_increase.trim()) out.spike_min_increase = 'Enter zero or more.';
  if (!Number.isInteger(Number(d.min_history_months)) || Number(d.min_history_months) < 1) out.min_history_months = 'Use a whole number of months, 1 or more.';
  if (!Number.isInteger(Number(d.decision_sla_days)) || Number(d.decision_sla_days) < 1) out.decision_sla_days = 'Use a whole number of days, 1 or more.';
  return out;
}

function Row({ title, hint, children }: { title: string; hint: string; children: ReactNode }) {
  return (
    <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: { xs: 1, sm: 3 }, py: 2, borderTop: 1, borderColor: 'divider' }}>
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Typography variant="subtitle2" component="p">{title}</Typography>
        <Typography variant="caption" component="p" sx={{ color: 'text.secondary', maxWidth: '52ch' }}>{hint}</Typography>
      </Box>
      <Box sx={{ width: { sm: 240 }, flexShrink: 0 }}>{children}</Box>
    </Stack>
  );
}

function ApprovalNote({ limit, custom }: { limit: number | null; custom: boolean }) {
  if (limit === null && !custom) {
    return <Alert severity="info" sx={{ mb: 2 }}>No approval needed. Section AEs decide every case on their own, whatever the amount.</Alert>;
  }
  const parts = [
    limit === null ? null : `corrected readings that reduce a bill by more than ${rupees(limit)}`,
    custom ? 'every custom reduction' : null,
  ].filter(Boolean);
  return <Alert severity="warning" variant="outlined" sx={{ mb: 2 }}>A second person approves {parts.join(', and ')}.</Alert>;
}

const RS = { input: { startAdornment: <InputAdornment position="start">Rs</InputAdornment> } };

/** One DISCOM's rules for what the engine flags and who must sign off. Mount with a key per DISCOM. */
export function PolicyCard({ policy }: { policy: Policy }) {
  const save = useSavePolicy();
  const [draft, setDraft] = useState<Draft>(() => toDraft(policy));
  const [custom, setCustom] = useState(policy.custom_needs_approval);
  const problems = problemsOf(draft);
  const dirty = JSON.stringify(draft) !== JSON.stringify(toDraft(policy)) || custom !== policy.custom_needs_approval;
  const noLimit = !draft.ae_limit.trim();
  const field = (key: keyof Draft) => ({
    value: draft[key], size: 'small' as const, fullWidth: true, type: 'number',
    error: Boolean(problems[key]), helperText: problems[key] ?? ' ',
    onChange: (e: { target: { value: string } }) => { save.reset(); setDraft((d) => ({ ...d, [key]: e.target.value })); },
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (Object.keys(problems).length > 0) return;
    save.mutate({
      discom: policy.discom, custom_needs_approval: custom, ae_limit: noLimit ? null : Number(draft.ae_limit),
      spike_ratio: Number(draft.spike_ratio), spike_min_increase: Number(draft.spike_min_increase),
      min_history_months: Number(draft.min_history_months), decision_sla_days: Number(draft.decision_sla_days),
    });
  };

  return (
    <Paper component="form" variant="outlined" noValidate onSubmit={submit} aria-labelledby={`policy-${policy.discom}`} sx={{ p: { xs: 2, sm: 3 } }}>
      <Typography id={`policy-${policy.discom}`} variant="h2" sx={{ mb: 1.5 }}>{policy.discom}</Typography>
      <ApprovalNote limit={noLimit ? null : Number(draft.ae_limit) || 0} custom={custom} />
      <Row title="AE limit" hint="The most a section AE can take off a bill alone after correcting the reading. Leave empty for no limit.">
        <TextField {...field('ae_limit')} label="Limit" placeholder="No limit" slotProps={RS} />
      </Row>
      <Row title="Custom reductions need approval" hint="When on, any reduction typed in by hand waits for a billing approver.">
        <FormControlLabel control={<Switch checked={custom} onChange={(e) => { save.reset(); setCustom(e.target.checked); }} />}
          label={custom ? 'Needs approval' : 'AE decides'} />
      </Row>
      <Row title="Spike ratio" hint="A bill is flagged when its units are more than this many times the household's usual month.">
        <TextField {...field('spike_ratio')} label="Times usual" slotProps={{ htmlInput: { step: 0.1, min: 1 } }} />
      </Row>
      <Row title="Minimum increase" hint="And only when it costs at least this much more than a usual month would.">
        <TextField {...field('spike_min_increase')} label="Amount" slotProps={RS} />
      </Row>
      <Row title="Months of history" hint="Fewer months than this and the bill is not compared at all.">
        <TextField {...field('min_history_months')} label="Months" slotProps={{ htmlInput: { step: 1, min: 1 } }} />
      </Row>
      <Row title="Days to decide" hint="A case open longer than this many calendar days is marked overdue.">
        <TextField {...field('decision_sla_days')} label="Days" slotProps={{ htmlInput: { step: 1, min: 1 } }} />
      </Row>
      {save.error && <Alert severity="error" sx={{ mb: 2 }}>{save.error.message}</Alert>}
      <Stack direction="row" sx={{ gap: 1.5, alignItems: 'center', justifyContent: 'flex-end', pt: 2, borderTop: 1, borderColor: 'divider' }}>
        {save.isSuccess && !dirty && <Typography variant="body2" role="status" sx={{ color: 'success.dark' }}>Saved</Typography>}
        <Button disabled={!dirty || save.isPending} onClick={() => { setDraft(toDraft(policy)); setCustom(policy.custom_needs_approval); }}>Undo changes</Button>
        <Button type="submit" variant="contained" disabled={!dirty || save.isPending}
          startIcon={save.isPending ? <CircularProgress size={16} color="inherit" aria-hidden /> : null}>
          Save {policy.discom}
        </Button>
      </Stack>
    </Paper>
  );
}
