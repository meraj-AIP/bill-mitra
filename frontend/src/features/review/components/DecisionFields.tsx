import { InputAdornment, LinearProgress, Stack, TextField, ToggleButton, ToggleButtonGroup, Typography } from '@mui/material';

import { formatCount } from '@/shared/lib/format';

import type { CaseDetail, DecisionKind, Preview } from '../api/types';
import type { DecisionDraft } from '../model/decision';
import { DECISION_KIND } from '../model/labels';

const KINDS: DecisionKind[] = ['correct', 'corrected_reading', 'custom'];

/** Three choices side by side; the one picked says what it does underneath, because it decides every field below. */
export function KindChoice({ value, onChange }: { value: DecisionKind; onChange: (kind: DecisionKind) => void }) {
  return (
    <Stack sx={{ gap: 0.75 }}>
      <ToggleButtonGroup exclusive fullWidth size="small" value={value} aria-label="Decision"
        onChange={(_, k: DecisionKind | null) => k && onChange(k)}
        sx={{ '& .MuiToggleButton-root': { textTransform: 'none', fontWeight: 600, py: 0.75, lineHeight: 1.3 } }}>
        {KINDS.map((k) => <ToggleButton key={k} value={k} color="primary">{DECISION_KIND[k].label}</ToggleButton>)}
      </ToggleButtonGroup>
      <Typography variant="caption" sx={{ color: 'text.secondary' }}>{DECISION_KIND[value].hint}</Typography>
    </Stack>
  );
}

interface AmountFieldsProps {
  c: CaseDetail;
  draft: DecisionDraft;
  onDraft: (changes: Partial<DecisionDraft>) => void;
  preview: { data: Preview | undefined; isFetching: boolean; error: Error | null };
  problems: { reading: string | null; reduction: string | null };
}

const printed = (v: number | null | undefined) => (v === null || v === undefined ? 'not printed' : formatCount(v));

function ReadingField({ c, draft, onDraft, preview, problems }: AmountFieldsProps) {
  const previous = c.bill?.previous_reading ?? null;
  const helper = preview.error?.message ?? problems.reading
    ?? `Printed: ${printed(c.bill?.present_reading)}. Previous: ${printed(previous)}.`;
  return (
    <Stack sx={{ gap: 1 }}>
      <TextField label="Corrected present reading" type="number" value={draft.reading} onChange={(e) => onDraft({ reading: e.target.value })}
        error={Boolean(problems.reading ?? preview.error)} helperText={helper}
        slotProps={{ htmlInput: { min: previous ?? 0, step: 1, inputMode: 'numeric' } }} fullWidth size="small" />
      {preview.isFetching && <LinearProgress aria-label="The engine is repricing the bill" />}
      {preview.data && !preview.isFetching && (
        <Typography variant="body2" sx={{ color: 'text.secondary' }}>
          The engine reprices the month at {formatCount(preview.data.corrected_units)} units, with the tariff, load, period and Gruha Jyothi of this bill. Surcharge, interest and rounding stay as printed.
        </Typography>
      )}
    </Stack>
  );
}

function ReductionField({ draft, onDraft, problems }: AmountFieldsProps) {
  return (
    <TextField label="Amount to take off" type="number" value={draft.reduction} onChange={(e) => onDraft({ reduction: e.target.value })}
      error={Boolean(problems.reduction)} helperText={problems.reduction ?? 'In rupees, from the printed amount.'}
      slotProps={{ input: { startAdornment: <InputAdornment position="start">Rs</InputAdornment> }, htmlInput: { min: 0, step: 1 } }}
      fullWidth size="small" />
  );
}

/** The corrected reading goes to the engine as the AE types; the custom amount is the AE's own figure. */
export function AmountFields(props: AmountFieldsProps) {
  if (props.draft.kind === 'corrected_reading') return <ReadingField {...props} />;
  if (props.draft.kind === 'custom') return <ReductionField {...props} />;
  return null;
}
