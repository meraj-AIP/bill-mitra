import { Box, ButtonBase, InputAdornment, LinearProgress, Stack, TextField, Typography } from '@mui/material';

import { formatCount } from '@/shared/lib/format';

import type { CaseDetail, DecisionKind, Preview } from '../api/types';
import type { DecisionDraft } from '../model/decision';
import { DECISION_KIND } from '../model/labels';

const KINDS: DecisionKind[] = ['correct', 'corrected_reading', 'custom'];

/** Three large choices rather than a select: the choice decides everything below it. */
export function KindChoice({ value, onChange }: { value: DecisionKind; onChange: (kind: DecisionKind) => void }) {
  return (
    <Box role="group" aria-label="Decision" sx={{ display: 'grid', gap: 1, gridTemplateColumns: { xs: '1fr', sm: 'repeat(3, minmax(0, 1fr))' } }}>
      {KINDS.map((k) => {
        const on = value === k;
        return (
          <ButtonBase key={k} aria-pressed={on} onClick={() => onChange(k)}
            sx={{ display: 'block', textAlign: 'left', p: 1.5, borderRadius: 1.5, border: 1.5, transition: 'border-color 200ms, background-color 200ms',
              borderColor: on ? 'primary.main' : 'divider', bgcolor: on ? 'info.light' : 'background.paper',
              '&:hover': { borderColor: 'primary.light' }, '&.Mui-focusVisible': { outline: 2, outlineColor: 'primary.main', outlineOffset: 2 } }}>
            <Typography variant="subtitle2" component="span" sx={{ display: 'block', color: on ? 'primary.main' : 'text.primary' }}>
              {DECISION_KIND[k].label}
            </Typography>
            <Typography variant="caption" component="span" sx={{ display: 'block', color: 'text.secondary', mt: 0.25 }}>{DECISION_KIND[k].hint}</Typography>
          </ButtonBase>
        );
      })}
    </Box>
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
        slotProps={{ htmlInput: { min: previous ?? 0, step: 1, inputMode: 'numeric' } }} sx={{ maxWidth: 320 }} />
      {preview.isFetching && <LinearProgress aria-label="The engine is repricing the bill" sx={{ maxWidth: 320 }} />}
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
      sx={{ maxWidth: 320 }} />
  );
}

/** The corrected reading goes to the engine as the AE types; the custom amount is the AE's own figure. */
export function AmountFields(props: AmountFieldsProps) {
  if (props.draft.kind === 'corrected_reading') return <ReadingField {...props} />;
  if (props.draft.kind === 'custom') return <ReductionField {...props} />;
  return null;
}
