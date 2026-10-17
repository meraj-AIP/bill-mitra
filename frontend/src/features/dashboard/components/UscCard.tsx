import { Alert, Box, Paper, Typography } from '@mui/material';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import type { Discom } from '@/shared/api/types';
import type { Language } from '@/shared/lib/languages';
import { bareUsc, uscShapeOk } from '@/shared/lib/serviceNumber';

import type { BillReport } from '../api/types';
import { useUscStart, useUscVerify } from '../api/uscApi';
import { UscCodeStep } from './UscCodeStep';
import { UscNumberStep } from './UscNumberStep';

// The server limits codes per hour, not per minute; this pause just stops double taps on resend.
const RESEND_SECONDS = 60;

interface Sent { message: string | null; resendAt: number }

/** Get the bill from the DISCOM with the service number, after a code sent to the registered mobile. */
export function UscCard({ language }: { language: Language }) {
  const navigate = useNavigate();
  const start = useUscStart(language);
  const verify = useUscVerify(language);
  const [discom, setDiscom] = useState<Discom | null>(null);
  const [usc, setUsc] = useState('');
  const [sent, setSent] = useState<Sent | null>(null);
  const [unsaved, setUnsaved] = useState<string | null>(null);
  const request = discom && uscShapeOk(usc) ? { discom, service_number: bareUsc(usc) } : null;

  const open = (report: BillReport) => {
    if (report.id) navigate(`/bills/${encodeURIComponent(report.id)}?lang=${language}`);
    else setUnsaved(report.outcome_reason ?? 'We could not read this bill. Please upload a photo of it instead.');
  };

  const send = () => {
    if (!request) return;
    setUnsaved(null);
    start.mutate(request, {
      onSuccess: ({ message, report }) => {
        // In development the server skips the code and the bill comes straight back.
        if (report) open(report);
        else setSent({ message, resendAt: Date.now() + RESEND_SECONDS * 1000 });
      },
    });
  };

  const reset = () => { setSent(null); start.reset(); verify.reset(); setUnsaved(null); };
  const errorText = verify.error?.message ?? start.error?.message ?? null;

  return (
    <Paper variant="outlined" component="section" aria-labelledby="usc-title" sx={{ p: { xs: 2, sm: 3 } }}>
      <Box sx={{ mb: 2.5 }}>
        <Typography variant="h2" id="usc-title">Get my bill with my USC</Typography>
        <Typography variant="body2" sx={{ color: 'text.secondary', maxWidth: '62ch' }}>
          No photo at hand? We can fetch your latest bill from your DISCOM. To keep it private, we first send a code to the mobile number registered with the connection.
        </Typography>
      </Box>
      {unsaved && <Alert severity="warning" sx={{ mb: 2 }}>{unsaved}</Alert>}
      {sent ? (
        <UscCodeStep message={sent.message} resendAt={sent.resendAt} verifying={verify.isPending} resending={start.isPending}
          error={errorText} onResend={send} onChangeNumber={reset}
          onVerify={(code) => request && verify.mutate({ ...request, code }, { onSuccess: open })} />
      ) : (
        <UscNumberStep discom={discom} usc={usc} onDiscom={setDiscom} onUsc={setUsc} pending={start.isPending}
          error={start.error?.message ?? null} onSend={send} />
      )}
    </Paper>
  );
}
