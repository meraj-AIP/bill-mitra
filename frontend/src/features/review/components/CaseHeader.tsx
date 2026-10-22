import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import ArrowDownwardRoundedIcon from '@mui/icons-material/ArrowDownwardRounded';
import PersonOutlineRoundedIcon from '@mui/icons-material/PersonOutlineRounded';
import { Box, Button, Chip, Stack, Typography } from '@mui/material';
import { Link } from 'react-router-dom';

import { SenderChip } from '@/features/complaints';
import { dateTime, monthLabel } from '@/shared/lib/format';

import type { CaseDetail } from '../api/types';
import { headline } from '../model/headline';
import { CASE_SECTION } from '../model/labels';
import { ReassignControl, UnmaskControl } from './CaseControls';
import { CaseSnapshot } from './CaseSnapshot';
import { OverdueChip, StateChip } from './StateChip';

interface Step { text: string; action?: { label: string; target: string } }

const DECIDABLE = new Set(['awaiting_review', 'info_requested', 'rejected']);

/** What this viewer should do now, or why there is nothing to do. */
function nextStep(c: CaseDetail): Step {
  if (c.can.decide && DECIDABLE.has(c.state)) {
    const text = c.state === 'rejected' ? 'The approver sent the last decision back. Read their note, then decide again.'
      : c.state === 'info_requested' ? 'The consumer has been asked for more. You can still decide on what is on file.'
        : 'Check the bill and the usual months, then record a decision.';
    return { text, action: { label: 'Record a decision', target: CASE_SECTION.decision } };
  }
  if (DECIDABLE.has(c.state)) {
    return { text: c.state === 'info_requested' ? 'The consumer has been asked for more. The section AE decides once it is in, or on what is on file.'
      : 'Waiting for the section AE to decide. You can follow it here.' };
  }
  if (c.state === 'awaiting_approval') {
    return c.can.approve ? { text: 'A reduction above the AE limit waits for your approval.', action: { label: 'Review the decision', target: CASE_SECTION.approval } }
      : { text: 'A decision is waiting for a billing approver. Nothing to do here until they act.' };
  }
  if (c.state === 'decided') {
    return c.can.mark_applied ? { text: 'Approved. Enter the revision in the DISCOM billing system, then mark it applied.', action: { label: 'Mark applied', target: CASE_SECTION.apply } }
      : { text: 'Decided. Any revision now waits to be entered in the DISCOM billing system.' };
  }
  return { text: 'Closed. The revision is in the official bill and the consumer has been told.' };
}

function NextStep({ c }: { c: CaseDetail }) {
  const step = nextStep(c);
  const go = (id: string) => {
    const el = document.getElementById(id);
    el?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    el?.focus({ preventScroll: true });
  };
  return (
    <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 1.5, alignItems: { sm: 'center' }, px: 2, py: 1.25, borderRadius: 1.5,
      bgcolor: 'background.paper', border: 1, borderColor: step.action ? 'primary.light' : 'divider' }}>
      <Typography variant="body2" sx={{ flex: 1, fontWeight: 500 }}>{step.text}</Typography>
      {step.action && (
        <Button variant="contained" size="small" endIcon={<ArrowDownwardRoundedIcon />} onClick={() => go(step.action!.target)} sx={{ flexShrink: 0 }}>
          {step.action.label}
        </Button>
      )}
    </Stack>
  );
}

/** What the case is (the flag, said plainly), where it stands, the facts behind it and the next step. */
export function CaseHeader({ c }: { c: CaseDetail }) {
  return (
    <Stack component="header" sx={{ gap: 2 }}>
      <Stack direction={{ xs: 'column', md: 'row' }} sx={{ gap: 2, alignItems: { md: 'flex-start' } }}>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Stack direction="row" sx={{ gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
            <Button component={Link} to="/review" startIcon={<ArrowBackIcon />} size="small" sx={{ ml: -1 }}>Review queue</Button>
            <Typography variant="caption" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>{c.ticket}</Typography>
            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
              {`Reading check, opened ${dateTime(c.created_at)} on ${c.channel === 'whatsapp' ? 'WhatsApp' : 'the web app'}`}
            </Typography>
          </Stack>
          <Stack direction="row" sx={{ gap: 1, alignItems: 'center', flexWrap: 'wrap', mt: 0.5 }}>
            <Typography variant="h2" component="h1" sx={{ mr: 0.5 }}>{headline(c)}</Typography>
            <StateChip state={c.state} />
            {c.overdue && <OverdueChip days={c.days_open} />}
            <Chip size="small" variant="outlined" icon={<PersonOutlineRoundedIcon />} label={c.assignee ? `With ${c.assignee.name}` : 'At the division'} />
            <SenderChip check={c.sender} />
          </Stack>
          <Stack direction="row" sx={{ gap: 0.75, alignItems: 'center', flexWrap: 'wrap', mt: 0.5, color: 'text.secondary' }}>
            <Typography variant="body2">
              {`${[c.section ?? 'Section not mapped', c.discom].join(', ')} · ${monthLabel(c.bill_month)} bill · Service`}
            </Typography>
            <UnmaskControl c={c} inline />
          </Stack>
        </Box>
        <ReassignControl c={c} />
      </Stack>
      <CaseSnapshot c={c} />
      <NextStep c={c} />
    </Stack>
  );
}
