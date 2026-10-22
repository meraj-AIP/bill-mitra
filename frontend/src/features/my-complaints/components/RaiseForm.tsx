import { Box, Button, CircularProgress, Stack, Typography } from '@mui/material';
import { useState, type FormEvent, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';

import { DescriptionField } from '@/features/complaints';
import { SendStatus } from '@/shared/components/SendStatus';

import { useRaiseComplaint } from '../api/myComplaintsApi';
import { toRequest, type Draft } from '../model/draft';
import { ConnectionFields } from './ConnectionFields';
import { TypePicker } from './TypePicker';
import { useConfirm } from '@/shared/feedback';

function Step({ n, title, hint, children }: { n: number; title: string; hint?: string; children: ReactNode }) {
  return (
    <Box component="fieldset" sx={{ border: 0, m: 0, p: 0, minWidth: 0 }}>
      <Stack direction="row" component="legend" sx={{ gap: 1.25, alignItems: 'baseline', p: 0, mb: 1.5 }}>
        <Typography component="span" sx={{ fontVariantNumeric: 'tabular-nums', color: 'text.secondary', fontWeight: 600, fontSize: '0.8125rem' }}>{n}</Typography>
        <Box>
          <Typography variant="h3" component="span" sx={{ display: 'block' }}>{title}</Typography>
          {hint && <Typography variant="body2" component="span" sx={{ display: 'block', color: 'text.secondary' }}>{hint}</Typography>}
        </Box>
      </Stack>
      {children}
    </Box>
  );
}

function SendButton({ pending }: { pending: boolean }) {
  return (
    <Box>
      <Button type="submit" variant="contained" size="large" disabled={pending}
        startIcon={pending ? <CircularProgress size={16} color="inherit" aria-hidden /> : undefined}>
        {pending ? 'Sending' : 'Send complaint'}
      </Button>
    </Box>
  );
}

/** Raise a complaint. Only the type, DISCOM and a description are needed; the rest helps us find the connection. */
export function RaiseForm({ initialBill }: { initialBill: string | null }) {
  const navigate = useNavigate();
  const raise = useRaiseComplaint();
  const [draft, setDraft] = useState<Draft>({ type: null, discom: null, usc: '', billId: initialBill ?? '', description: '' });
  const [tried, setTried] = useState(false);
  const set = <K extends keyof Draft>(key: K) => (value: Draft[K]) => setDraft((d) => ({ ...d, [key]: value }));
  const noType = tried && !draft.type;

  const confirm = useConfirm();
  const submit = async (event?: FormEvent) => {
    event?.preventDefault();
    setTried(true);
    const body = toRequest(draft);
    if (!body || !(await confirm({ title: 'Send this complaint?', confirmLabel: 'Send complaint',
      body: draft.type ? `${draft.type.label}, ${body.discom}.` : undefined,
      points: ['You get a ticket number straight away.', 'We reply here and tell you each time it moves.'] }))) return;
    raise.mutate(body, { onSuccess: (c) => navigate(`/complaints/${encodeURIComponent(c.ticket)}`) });
  };

  return (
    <Stack component="form" onSubmit={(e) => void submit(e)} noValidate sx={{ gap: 4 }}>
      <Step n={1} title="What is the problem?" hint="Pick the one closest to yours.">
        <TypePicker value={draft.type?.code ?? ''} onChange={set('type')} error={noType} />
        {noType && <Typography variant="caption" sx={{ color: 'error.main', mt: 0.75, display: 'block' }}>Please pick a problem.</Typography>}
      </Step>
      <Step n={2} title="Your connection" hint="Your service number (USC) is printed at the top of your bill.">
        <ConnectionFields discom={draft.discom} usc={draft.usc} billId={draft.billId} tried={tried} needsBill={Boolean(draft.type?.needs_bill)}
          onDiscom={set('discom')} onUsc={set('usc')} onBill={set('billId')} />
      </Step>
      <Step n={3} title="Tell us what happened" hint="A line or two is enough.">
        <DescriptionField label="Describe the problem" value={draft.description} onChange={set('description')} showEmpty={tried}
          placeholder="For example: my bill doubled this month but my usage is the same." />
      </Step>
      <SendStatus state={raise} />
      <SendButton pending={raise.isPending} />
    </Stack>
  );
}
