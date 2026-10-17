import { Alert, Box, Button, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, MenuItem, Stack, TextField, Typography } from '@mui/material';
import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';

import { DescriptionField, descriptionOk, SOURCE_LABEL, STAFF_SOURCES, TypeSelect, type StaffSource } from '@/features/complaints';
import { DISCOMS, type Discom } from '@/shared/api/types';
import { UnitPicker } from '@/shared/components/UnitPicker';
import { USC_HINT } from '@/shared/lib/serviceNumber';

import { useCreateComplaint } from '../api/createApi';
import { draftProblems, EMPTY_DRAFT, toBody, type StaffDraft } from '../model/newComplaint';
import { complaintPath } from './ComplaintsTable';

interface NewComplaintDialogProps {
  open: boolean;
  onClose: () => void;
  /** Set when the account sees one DISCOM only, so the choice is made for them. */
  fixedDiscom: Discom | null;
}

/** Log a complaint from a call, a walk-in or the field. It opens in the inbox like any other. */
export function NewComplaintDialog({ open, onClose, fixedDiscom }: NewComplaintDialogProps) {
  const navigate = useNavigate();
  const create = useCreateComplaint();
  const [draft, setDraft] = useState<StaffDraft>({ ...EMPTY_DRAFT, discom: fixedDiscom ?? '' });
  const [tried, setTried] = useState(false);
  const set = <K extends keyof StaffDraft>(key: K, value: StaffDraft[K]) => setDraft((d) => ({ ...d, [key]: value }));
  const problems = draftProblems(draft);
  const show = (bad: boolean) => tried && bad;

  const close = () => {
    if (create.isPending) return;
    setDraft({ ...EMPTY_DRAFT, discom: fixedDiscom ?? '' });
    setTried(false);
    create.reset();
    onClose();
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setTried(true);
    const body = toBody(draft);
    if (!body || Object.values(problems).some(Boolean) || !descriptionOk(draft.description)) return;
    create.mutate(body, { onSuccess: (detail) => navigate(complaintPath(detail.ticket)) });
  };

  return (
    <Dialog open={open} onClose={close} fullWidth maxWidth="sm" aria-labelledby="new-complaint-title">
      <Box component="form" onSubmit={submit} noValidate>
        <DialogTitle id="new-complaint-title" sx={{ pb: 0.5 }}>New complaint</DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ color: 'text.secondary', mb: 2.5 }}>
            For a call, a walk-in or something seen in the field. If you add the caller&apos;s mobile, updates reach them on WhatsApp.
          </Typography>
          <Stack sx={{ gap: 2.25 }}>
            {create.isError && <Alert severity="error">{create.error.message}</Alert>}
            <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' } }}>
              <TextField select label="Source" required value={draft.source} error={show(problems.source)}
                helperText={show(problems.source) ? 'Pick where this came from.' : ' '}
                onChange={(e) => set('source', e.target.value as StaffSource)}>
                {STAFF_SOURCES.map((s) => <MenuItem key={s} value={s}>{SOURCE_LABEL[s]}</MenuItem>)}
              </TextField>
              <TextField select label="DISCOM" required value={draft.discom} disabled={Boolean(fixedDiscom)} error={show(problems.discom)}
                helperText={show(problems.discom) ? 'Pick the DISCOM.' : ' '}
                onChange={(e) => setDraft((d) => ({ ...d, discom: e.target.value as Discom, section: null }))}>
                {DISCOMS.map((d) => <MenuItem key={d} value={d}>{d}</MenuItem>)}
              </TextField>
            </Box>
            <TypeSelect fullWidth required value={draft.type} onChange={(v) => set('type', v)} error={show(problems.type)}
              helperText={show(problems.type) ? 'Pick the type that fits best.' : 'Grouped as Billing, Meter and Supply.'} />
            <UnitPicker label="Section (optional)" kind="section" value={draft.section} onChange={(v) => set('section', v)}
              disabled={!draft.discom} {...(draft.discom ? { discom: draft.discom } : {})}
              helperText={draft.discom ? 'Only sections you work in are accepted. Leave empty to place it from the service number.' : 'Pick the DISCOM first.'} />
            <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' } }}>
              <TextField label="Service number (optional)" value={draft.usc} onChange={(e) => set('usc', e.target.value)}
                error={problems.usc} helperText={problems.usc ? USC_HINT : 'Stored masked.'}
                slotProps={{ htmlInput: { autoComplete: 'off', spellCheck: false, inputMode: 'numeric' } }} />
              <TextField label="Caller mobile (optional)" value={draft.mobile} onChange={(e) => set('mobile', e.target.value)}
                error={problems.mobile} helperText={problems.mobile ? 'Enter a 10 digit Indian mobile.' : 'Updates go here on WhatsApp.'}
                slotProps={{ htmlInput: { inputMode: 'tel', autoComplete: 'off' } }} />
            </Box>
            <DescriptionField label="What is the problem?" value={draft.description} onChange={(v) => set('description', v)} showEmpty={tried}
              placeholder="In the caller's words, as plainly as you can." />
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2.5 }}>
          <Button onClick={close} disabled={create.isPending}>Cancel</Button>
          <Button type="submit" variant="contained" disabled={create.isPending}
            startIcon={create.isPending ? <CircularProgress size={16} color="inherit" aria-hidden /> : undefined}>
            {create.isPending ? 'Logging' : 'Log complaint'}
          </Button>
        </DialogActions>
      </Box>
    </Dialog>
  );
}
