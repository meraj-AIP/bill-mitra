import ArrowForwardRoundedIcon from '@mui/icons-material/ArrowForwardRounded';
import AutoAwesomeRoundedIcon from '@mui/icons-material/AutoAwesomeRounded';
import RefreshRoundedIcon from '@mui/icons-material/RefreshRounded';
import { Box, Button, Chip, CircularProgress, Divider, Paper, Skeleton, Stack, Typography } from '@mui/material';

import { CHANNEL_LABEL, SOURCE_LABEL, TRIAGE, type ComplaintDetail } from '@/features/complaints';
import { monthLabel, rupees } from '@/shared/lib/format';

import { useComplaintAssist, useRefreshAssist } from '../api/assistApi';
import type { FocusTarget } from '../model/focus';
import { useNextStep } from './ComplaintAssist';

interface BriefProps {
  complaint: ComplaintDetail;
  /** The assist route needs the reply permission; without it the brief shows the facts only. */
  canReply: boolean;
  onFocus: (target: FocusTarget, key: string) => void;
  onOpenAssist: () => void;
}

const source = (c: ComplaintDetail) => (c.source ? SOURCE_LABEL[c.source] : c.channel ? CHANNEL_LABEL[c.channel] : null);

/** What is on file, as short pairs; what is not on file, named once instead of a grid of blanks. */
function Facts({ c }: { c: ComplaintDetail }) {
  const all: Array<[string, string | null]> = [
    ['Service', c.service_masked], ['Source', source(c)],
    ['Where', [c.discom, c.section].filter(Boolean).join(', ') || null],
    ['Bill month', c.bill_month ? monthLabel(c.bill_month) : null], ['Amount', c.amount ? rupees(c.amount) : null],
    ['Bill check', c.bill ? TRIAGE[c.triage].label : null],
  ];
  const known = all.filter(([, v]) => v);
  const missing = all.filter(([, v]) => !v).map(([k]) => k.toLowerCase());
  return (
    <Stack direction="row" sx={{ gap: { xs: 1.5, sm: 3 }, flexWrap: 'wrap', alignItems: 'baseline' }}>
      {known.map(([label, value]) => (
        <Box key={label} sx={{ minWidth: 0 }}>
          <Typography variant="caption" component="span" sx={{ color: 'text.secondary', mr: 0.75 }}>{label}</Typography>
          <Typography variant="subtitle2" component="span">{value}</Typography>
        </Box>
      ))}
      {missing.length > 0 && (
        <Typography variant="caption" sx={{ color: 'text.disabled' }}>Not on file: {missing.join(', ')}</Typography>
      )}
    </Stack>
  );
}

function Heading({ wordedBy, refreshing, onRefresh, onOpenAssist }: {
  wordedBy: 'ai' | 'rules' | null; refreshing: boolean; onRefresh: () => void; onOpenAssist: () => void;
}) {
  return (
    <Stack direction="row" sx={{ alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
      <Box sx={{ width: 28, height: 28, borderRadius: 1, display: 'grid', placeItems: 'center', bgcolor: 'info.light', color: 'primary.main' }}>
        <AutoAwesomeRoundedIcon sx={{ fontSize: 18 }} />
      </Box>
      <Typography variant="subtitle1" component="h2">AI brief</Typography>
      {wordedBy && <Chip size="small" variant="outlined" label={wordedBy === 'ai' ? 'AI, facts checked' : 'From the rules'} />}
      <Box sx={{ ml: 'auto', display: 'flex', gap: 0.5 }}>
        <Button size="small" color="inherit" onClick={onRefresh} disabled={refreshing}
          startIcon={refreshing ? <CircularProgress size={12} color="inherit" aria-hidden /> : <RefreshRoundedIcon />}>Refresh</Button>
        <Button size="small" onClick={onOpenAssist}>Questions to ask</Button>
      </Box>
    </Stack>
  );
}

function NextStep({ step }: { step: NonNullable<ReturnType<typeof useNextStep>> }) {
  return (
    <>
      <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 1.5, alignItems: { sm: 'center' }, p: 1.25, borderRadius: 1.5, bgcolor: 'grey.50' }}>
        <Button variant="contained" onClick={step.run} disabled={step.pending}
          endIcon={step.pending ? <CircularProgress size={14} color="inherit" aria-hidden /> : <ArrowForwardRoundedIcon />} sx={{ flexShrink: 0 }}>
          {step.label}
        </Button>
        <Typography variant="body2" sx={{ color: 'text.secondary' }}>{step.why}</Typography>
      </Stack>
      {step.error && <Typography variant="caption" sx={{ color: 'error.main' }}>{step.error}</Typography>}
    </>
  );
}

/** The model's read of the complaint: where it stands, what is missing and the next step, or why it is not here. */
function Body({ c, onFocus }: { c: ComplaintDetail; onFocus: BriefProps['onFocus'] }) {
  const assist = useComplaintAssist(c, true);
  const data = assist.data;
  const step = useNextStep(c, data?.next_action ?? null, true, onFocus);
  if (assist.isPending) {
    return (
      <Box aria-busy>
        <Skeleton width="92%" /><Skeleton width="70%" />
        <Typography variant="caption" sx={{ color: 'text.secondary' }}>Reading the complaint and the conversation</Typography>
      </Box>
    );
  }
  if (!data) {
    return (
      <Typography variant="body2" sx={{ color: 'text.secondary' }}>
        The brief is not available right now. <Button size="small" onClick={() => void assist.refetch()}>Try again</Button>
      </Typography>
    );
  }
  return (
    <>
      <Typography variant="body1" sx={{ maxWidth: '75ch' }}>{data.summary}</Typography>
      {data.missing.length > 0 && (
        <Stack direction="row" sx={{ gap: 0.75, flexWrap: 'wrap', alignItems: 'center' }}>
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>Still missing</Typography>
          {data.missing.map((m) => <Chip key={m} size="small" color="warning" variant="outlined" label={m} />)}
        </Stack>
      )}
      {step && <NextStep step={step} />}
    </>
  );
}

/** One shared brief per complaint, written by the model on the server; read here, refreshed on request. */
export function ComplaintBrief({ complaint: c, canReply, onFocus, onOpenAssist }: BriefProps) {
  const assist = useComplaintAssist(c, canReply);
  const refresh = useRefreshAssist(c.ticket);
  return (
    <Paper variant="outlined" sx={{ p: { xs: 2, sm: 2.5 }, display: 'flex', flexDirection: 'column', gap: 1.75, minWidth: 0,
      borderColor: 'info.light', boxShadow: (t) => `inset 3px 0 0 ${t.palette.primary.light}` }}>
      {canReply && (
        <>
          <Heading wordedBy={assist.data?.worded_by ?? null} refreshing={refresh.isPending} onRefresh={() => refresh.mutate()}
            onOpenAssist={onOpenAssist} />
          <Body c={c} onFocus={onFocus} />
          <Divider />
        </>
      )}
      <Facts c={c} />
    </Paper>
  );
}
