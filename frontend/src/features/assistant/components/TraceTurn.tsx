import { keyframes } from '@emotion/react';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { Box, ButtonBase, Collapse, Stack, Typography } from '@mui/material';
import { alpha, useTheme } from '@mui/material/styles';

import { clockTime } from '@/shared/lib/format';

import type { StepMode, TraceStep } from '../api/types';
import type { TraceTurn as Turn } from '../model/conversation';

const MODE_LABEL: Record<StepMode, string> = { ai: 'AI', rules: 'Rules', demo: 'Fallback', channel: 'Channel' };

const pulse = keyframes`
  0% { box-shadow: 0 0 0 0 currentColor; }
  100% { box-shadow: 0 0 0 6px transparent; }
`;

const duration = (ms: number) => (ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`);

function Dot({ status }: { status: TraceStep['status'] }) {
  const theme = useTheme();
  const colour = {
    running: theme.palette.primary.main,
    done: theme.palette.secondary.main,
    failed: theme.palette.error.main,
    skipped: theme.palette.text.disabled,
  }[status];
  return (
    <Box aria-label={status} role="img"
      sx={{ width: 11, height: 11, borderRadius: '50%', flexShrink: 0, mt: '5px', color: colour, position: 'relative', zIndex: 1,
        bgcolor: status === 'skipped' ? 'background.paper' : colour, border: 2, borderColor: colour,
        boxShadow: `0 0 0 3px ${theme.palette.background.paper}`,
        animation: status === 'running' ? `${pulse} 1.1s infinite` : 'none',
        '@media (prefers-reduced-motion: reduce)': { animation: 'none' } }} />
  );
}

function ModeChip({ mode }: { mode: StepMode }) {
  const theme = useTheme();
  const colour = theme.palette.step[mode];
  return (
    <Box component="span" sx={{ px: 0.75, py: '1px', borderRadius: 0.75, fontSize: '0.6875rem', fontWeight: 600, lineHeight: 1.5,
      color: colour, bgcolor: alpha(colour, 0.09), border: 1, borderColor: alpha(colour, 0.22) }}>
      {MODE_LABEL[mode]}
    </Box>
  );
}

function Step({ step, last }: { step: TraceStep; last: boolean }) {
  return (
    <Stack direction="row" component="li" sx={{ gap: 1.25, position: 'relative', pb: last ? 0 : 1.5,
      // The rail that joins one dot to the next.
      '&::before': last ? {} : { content: '""', position: 'absolute', left: 5, top: 14, bottom: 0, width: '1px', bgcolor: 'divider' } }}>
      <Dot status={step.status} />
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Stack direction="row" sx={{ gap: 0.75, alignItems: 'center', flexWrap: 'wrap' }}>
          <Typography variant="body2" sx={{ fontWeight: 600, color: step.status === 'skipped' ? 'text.secondary' : 'text.primary' }}>
            {step.label}
          </Typography>
          <ModeChip mode={step.mode} />
          {step.ms != null && (
            <Typography variant="caption" sx={{ ml: 'auto', color: 'text.secondary', fontVariantNumeric: 'tabular-nums' }}>
              {duration(step.ms)}
            </Typography>
          )}
        </Stack>
        {step.detail && (
          <Typography variant="caption" component="p" sx={{ color: 'text.secondary', mt: 0.25, lineHeight: 1.45, wordBreak: 'break-word' }}>
            {step.detail}
          </Typography>
        )}
      </Box>
    </Stack>
  );
}

interface TraceTurnProps {
  turn: Turn;
  open: boolean;
  onToggle: () => void;
}

export function TraceTurn({ turn, open, onToggle }: TraceTurnProps) {
  const total = turn.steps.reduce((sum, s) => sum + (s.ms ?? 0), 0);
  const failed = turn.steps.some((s) => s.status === 'failed');
  const regionId = `trace-${turn.id}`;
  return (
    <Box component="section" sx={{ border: 1, borderColor: 'divider', borderRadius: 2, bgcolor: 'background.paper', overflow: 'hidden' }}>
      <ButtonBase onClick={onToggle} aria-expanded={open} aria-controls={regionId}
        sx={{ width: '100%', justifyContent: 'flex-start', textAlign: 'left', gap: 1, px: 1.75, py: 1.25,
          '&:hover': { bgcolor: 'action.hover' }, '&.Mui-focusVisible': { outline: 2, outlineColor: 'primary.main', outlineOffset: -2 } }}>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography variant="subtitle2" component="h3" noWrap title={turn.title}>{turn.title}</Typography>
          <Typography variant="caption" sx={{ color: failed ? 'error.main' : 'text.secondary', fontVariantNumeric: 'tabular-nums' }}>
            {clockTime(turn.at)}
            {' · '}
            {turn.done ? `${turn.steps.length} ${turn.steps.length === 1 ? 'step' : 'steps'}${total ? `, ${duration(total)}` : ''}` : 'Running'}
            {failed && ', a step failed'}
          </Typography>
        </Box>
        <ExpandMoreIcon sx={{ color: 'text.secondary', transition: 'transform 200ms', transform: open ? 'rotate(180deg)' : 'none' }} />
      </ButtonBase>
      <Collapse in={open} id={regionId}>
        <Box component="ol" sx={{ listStyle: 'none', m: 0, px: 1.75, pt: 0.5, pb: 1.75 }}>
          {turn.steps.length === 0 && <Typography component="li" variant="caption" sx={{ color: 'text.secondary' }}>Starting</Typography>}
          {turn.steps.map((step, i) => <Step key={step.id} step={step} last={i === turn.steps.length - 1} />)}
        </Box>
      </Collapse>
    </Box>
  );
}
