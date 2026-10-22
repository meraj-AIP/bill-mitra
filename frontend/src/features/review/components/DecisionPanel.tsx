import GavelOutlinedIcon from '@mui/icons-material/GavelOutlined';
import { Alert, Box, Button, CircularProgress, MenuItem, Stack, TextField, Typography } from '@mui/material';
import { useState, type FormEvent } from 'react';

import { SendStatus } from '@/shared/components/SendStatus';
import { useDebounced } from '@/shared/hooks/useDebounced';
import { rupees } from '@/shared/lib/format';

import { useDecide, usePreview } from '../api/reviewApi';
import type { CaseDetail, DecisionKind, ReasonCode } from '../api/types';
import { emptyDraft, evidenceOptions, outcomeOf, parseAmount, problemsOf, toBody, withCited, type DecisionDraft, type Outcome } from '../model/decision';
import { MIN_NOTE, REASON } from '../model/labels';
import { DecisionSummary } from './DecisionSummary';
import { AmountFields, KindChoice } from './DecisionFields';
import { EvidencePicker } from './EvidencePicker';
import { Panel } from './Panel';
import { useConfirm, type ConfirmOptions } from '@/shared/feedback';

const NOTE_LIMIT = 1000;

function NoteField({ value, onChange, error }: { value: string; onChange: (v: string) => void; error: string | null }) {
  const length = value.trim().length;
  const short = length < MIN_NOTE;
  return (
    <TextField label="Note for the record" multiline minRows={3} value={value} onChange={(e) => onChange(e.target.value)}
      error={Boolean(error) || value.length > NOTE_LIMIT}
      placeholder="What you checked and why this is the right outcome. The approver and the audit log read this."
      helperText={<Box component="span" aria-live="polite" sx={{ fontVariantNumeric: 'tabular-nums', color: short ? 'text.secondary' : 'success.dark' }}>
        {short ? `${length} of at least ${MIN_NOTE} characters` : `${length} characters`}
      </Box>} />
  );
}

function ReasonField({ kind, value, onChange, error }: { kind: DecisionKind; value: ReasonCode | ''; onChange: (r: ReasonCode) => void; error: string | null }) {
  // Bill is correct pairs with its own reason; a reduction needs one of the others.
  const options = (Object.keys(REASON) as ReasonCode[]).filter((r) => (kind === 'correct') === (r === 'bill_correct') || r === 'other');
  return (
    <TextField select label="Reason" value={value} onChange={(e) => onChange(e.target.value as ReasonCode)}
      error={Boolean(error)} helperText={error ?? 'Shown to the consumer in their language.'} sx={{ maxWidth: 420 }}>
      {options.map((r) => <MenuItem key={r} value={r}>{REASON[r]}</MenuItem>)}
    </TextField>
  );
}

function SubmitRow({ pending, disabled, needsApproval }: { pending: boolean; disabled: boolean; needsApproval: boolean }) {
  return (
    <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 1.5, alignItems: { sm: 'center' } }}>
      <Typography variant="caption" sx={{ color: 'text.secondary', flex: 1 }}>
        Rules the server also enforces: a reason, a note of {MIN_NOTE} or more characters and at least one piece of evidence.
      </Typography>
      <Button type="submit" variant="contained" size="large" disabled={pending || disabled}
        startIcon={pending ? <CircularProgress size={16} color="inherit" aria-hidden /> : <GavelOutlinedIcon />}>
        {needsApproval ? 'Send for approval' : 'Record decision'}
      </Button>
    </Stack>
  );
}

const reasonFor = (kind: DecisionKind, current: ReasonCode | ''): ReasonCode | '' => {
  if (kind === 'correct') return 'bill_correct';
  return current === 'bill_correct' ? '' : current;
};

/** The field messages can sit off screen above the button, so a blocked submit says what is missing here too. */
function Blocking({ items }: { items: string[] }) {
  if (items.length === 0) return null;
  return <Alert severity="warning" role="alert">Before you record this: {items.join(' ')}</Alert>;
}

/** Recording a decision. Every figure comes from the engine preview or the AE's own typed amount. */
/** What recording the decision does, in the words the AE will be held to. */
function decisionConfirm(kind: DecisionKind, o: Outcome): ConfirmOptions {
  if (kind === 'correct') {
    return { title: 'Record the bill as correct?', confirmLabel: 'Record decision',
      body: 'The bill stands as printed.', points: ['The consumer is told the bill is correct.', 'The case closes.'] };
  }
  const change = o.original !== null && o.revised !== null ? `The bill goes from ${rupees(o.original)} to ${rupees(o.revised)}.` : undefined;
  return { title: 'Record this revision?', confirmLabel: o.needsApproval ? 'Send for approval' : 'Record decision', tone: 'warning', body: change,
    points: o.needsApproval
      ? ['It is above your limit, so a billing approver must approve it first.', 'Nothing changes for the consumer until then.']
      : ['The consumer is told the revised amount.', 'The revision then waits to be entered in the DISCOM billing system.'] };
}

export function DecisionPanel({ c, initial }: { c: CaseDetail; initial: DecisionDraft }) {
  const decide = useDecide(c.ticket);
  const confirm = useConfirm();
  const [draft, setDraft] = useState<DecisionDraft>(initial);
  const [checked, setChecked] = useState(false);
  const reading = useDebounced(draft.kind === 'corrected_reading' ? parseAmount(draft.reading) : null, 400);
  const preview = usePreview(c.ticket, reading);
  // A stale preview for an earlier reading must never be shown as this reading's result.
  const fresh = reading !== null && parseAmount(draft.reading) === reading ? preview.data : undefined;
  const outcome = outcomeOf(draft, c, fresh);
  const problems = problemsOf(draft, c, outcome);
  const show = (key: keyof typeof problems) => (checked ? problems[key] : null);
  const blocking = checked ? Object.values(problems).filter((p): p is string => Boolean(p)) : [];
  // A reading that does not lower the bill is worth saying at once, not only on submit.
  const readingProblem = show('reading') ?? (fresh && fresh.reduction <= 0 ? problems.reading : null);
  const patch = (changes: Partial<DecisionDraft>) => { decide.reset(); setDraft((d) => ({ ...d, ...changes })); };
  const setKind = (kind: DecisionKind) => patch({ kind, reason: reasonFor(kind, draft.reason) });

  // The engine's answer for the reading on screen is needed before a corrected reading can be sent.
  const waiting = draft.kind === 'corrected_reading' && (!fresh || preview.isFetching);

  const submit = async (event?: FormEvent) => {
    event?.preventDefault();
    setChecked(true);
    if (waiting || Object.values(problems).some(Boolean)) return;
    if (!(await confirm(decisionConfirm(draft.kind, outcome)))) return;
    decide.mutate(toBody(draft), { onSuccess: () => { setDraft(emptyDraft()); setChecked(false); } });
  };

  return (
    <Panel title="Decision" tone="primary" caption="Look at the bill, the history and anything the consumer sent, then record what happens to this bill.">
      <Stack component="form" noValidate onSubmit={(e) => void submit(e)} sx={{ gap: 2.5 }}>
        <KindChoice value={draft.kind} onChange={setKind} />
        <AmountFields c={c} draft={draft} onDraft={patch} preview={{ data: fresh, isFetching: preview.isFetching, error: preview.error }}
          problems={{ reading: readingProblem, reduction: show('reduction') }} />
        <ReasonField kind={draft.kind} value={draft.reason} onChange={(reason) => patch({ reason })} error={show('reason')} />
        <NoteField value={draft.note} onChange={(note) => patch({ note })} error={show('note')} />
        <EvidencePicker options={withCited(evidenceOptions(c), initial.evidence)} value={draft.evidence} onChange={(evidence) => patch({ evidence })} error={show('evidence')} />
        <DecisionSummary kind={draft.kind} outcome={outcome} c={c} />
        <Blocking items={blocking} />
        <SendStatus state={decide} />
        <SubmitRow pending={decide.isPending} disabled={waiting && preview.isFetching} needsApproval={outcome.needsApproval} />
      </Stack>
    </Panel>
  );
}
