import CloseFullscreenRounded from '@mui/icons-material/CloseFullscreenRounded';
import NavigateBeforeRounded from '@mui/icons-material/NavigateBeforeRounded';
import NavigateNextRounded from '@mui/icons-material/NavigateNextRounded';
import PauseRounded from '@mui/icons-material/PauseRounded';
import PlayArrowRounded from '@mui/icons-material/PlayArrowRounded';
import { Box, Button, Dialog, IconButton, Stack, ToggleButton, ToggleButtonGroup, Tooltip, Typography, Zoom } from '@mui/material';
import { useEffect, useRef, useState, type RefObject } from 'react';

import { STEP_MS, type JourneyControl } from '../hooks/useJourney';
import { JOURNEYS } from '../model/journeys';
import { SystemMap } from './SystemMap';

const mono = { fontFamily: 'monospace', fontSize: '0.8rem' };
const calm = { '@media (prefers-reduced-motion: reduce)': { animation: 'none', transition: 'none' } };

/** One segment per step; the current one fills while the journey plays, so the room sees the pace. */
function Progress({ control }: { control: JourneyControl }) {
  return (
    <Stack direction="row" sx={{ gap: 0.5, '@keyframes fill': { from: { transform: 'scaleX(0)' }, to: { transform: 'scaleX(1)' } } }}>
      {Array.from({ length: control.count }, (_, i) => (
        <Box key={i} onClick={() => control.goTo(i)} aria-hidden
          sx={{ flex: 1, height: 4, borderRadius: 2, bgcolor: 'divider', overflow: 'hidden', cursor: 'pointer' }}>
          <Box key={`${control.journey}-${control.step}-${control.playing}`}
            sx={{ height: '100%', bgcolor: 'secondary.main', transformOrigin: 'left',
              transform: i < control.step || (i === control.step && !control.playing) ? 'scaleX(1)' : 'scaleX(0)',
              animation: i === control.step && control.playing ? `fill ${STEP_MS}ms linear forwards` : 'none', ...calm }} />
        </Box>
      ))}
    </Stack>
  );
}

function Caption({ control }: { control: JourneyControl }) {
  const step = JOURNEYS[control.journey]?.steps[control.step];
  if (!step) return null;
  return (
    <Box key={`${control.journey}-${control.step}`}
      sx={{ display: 'grid', gap: 3, gridTemplateColumns: { xs: '1fr', md: 'minmax(0, 1.1fr) minmax(0, 1fr)' }, alignItems: 'start',
        '@keyframes rise': { from: { opacity: 0, transform: 'translateY(14px)' }, to: { opacity: 1, transform: 'none' } },
        animation: 'rise 520ms cubic-bezier(0.22, 1, 0.36, 1)', ...calm }}>
      <Box>
        <Typography variant="overline" component="p" sx={{ color: 'secondary.main' }}>
          Step {control.step + 1} of {control.count}{step.planned ? ', planned' : ''}
        </Typography>
        <Typography variant="h2" component="h3">{step.title}</Typography>
        <Typography variant="body1" sx={{ color: 'text.secondary', mt: 1, maxWidth: '62ch' }}>{step.body}</Typography>
      </Box>
      <Box component="pre" sx={{ ...mono, m: 0, p: 2, borderRadius: 1.5, bgcolor: 'grey.100', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
        {step.payload}
      </Box>
    </Box>
  );
}

/** Real browser full screen when allowed; the dialog already fills the window when it is not. */
function useBrowserFullscreen(target: RefObject<HTMLDivElement | null>, open: boolean) {
  const [on, setOn] = useState(false);
  useEffect(() => {
    const sync = () => setOn(document.fullscreenElement !== null);
    document.addEventListener('fullscreenchange', sync);
    return () => document.removeEventListener('fullscreenchange', sync);
  }, []);
  useEffect(() => {
    if (!open && document.fullscreenElement) void document.exitFullscreen().catch(() => undefined);
  }, [open]);
  const toggle = () => {
    if (document.fullscreenElement) void document.exitFullscreen().catch(() => undefined);
    else void target.current?.requestFullscreen().catch(() => undefined);
  };
  return { on, toggle };
}

function useKeys(open: boolean, control: JourneyControl, toggleScreen: () => void) {
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLElement && e.target.closest('button, [role="button"]') && e.key === ' ') return;
      const actions: Record<string, () => void> = {
        ArrowRight: () => control.goTo(control.step + 1), PageDown: () => control.goTo(control.step + 1),
        ArrowLeft: () => control.goTo(control.step - 1), PageUp: () => control.goTo(control.step - 1),
        ' ': control.toggle, Home: () => control.goTo(0), End: () => control.goTo(control.count - 1),
        f: toggleScreen, F: toggleScreen,
        ...Object.fromEntries(JOURNEYS.map((_, i) => [String(i + 1), () => control.selectJourney(i)])),
      };
      const act = actions[e.key];
      if (act) { e.preventDefault(); act(); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, control, toggleScreen]);
}

export function ArchitecturePresenter({ open, onClose, control }: { open: boolean; onClose: () => void; control: JourneyControl }) {
  const stage = useRef<HTMLDivElement>(null);
  const screen = useBrowserFullscreen(stage, open);
  useKeys(open, control, screen.toggle);
  const step = JOURNEYS[control.journey]?.steps[control.step];

  return (
    <Dialog fullScreen open={open} onClose={onClose} slots={{ transition: Zoom }} aria-label="Architecture presentation"
      slotProps={{ transition: { timeout: { enter: 420, exit: 260 } }, paper: { ref: stage, sx: { bgcolor: 'background.default' } } }}>
      <Stack sx={{ height: '100%', px: { xs: 2, md: 5 }, py: { xs: 2, md: 3 }, gap: 2.5 }}>
        <Stack direction="row" sx={{ gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
          <Typography variant="h3" component="h2" sx={{ mr: 'auto' }}>Bill Mitra, end to end</Typography>
          <ToggleButtonGroup exclusive size="small" value={control.journey} aria-label="Journey"
            onChange={(_, v: number | null) => { if (v !== null) control.selectJourney(v); }}>
            {JOURNEYS.map((j, i) => <ToggleButton key={j.name} value={i}>{j.name}</ToggleButton>)}
          </ToggleButtonGroup>
          <Tooltip title={screen.on ? 'Leave full screen (F)' : 'Full screen (F)'}>
            <Button size="small" variant="outlined" onClick={screen.toggle}>{screen.on ? 'Exit full screen' : 'Full screen'}</Button>
          </Tooltip>
          <Tooltip title="Minimise (Esc)">
            <IconButton onClick={onClose} aria-label="Minimise the presentation"><CloseFullscreenRounded /></IconButton>
          </Tooltip>
        </Stack>
        <Progress control={control} />
        <Box sx={{ flex: 1, minHeight: 0, borderRadius: 2, border: 1, borderColor: 'divider', bgcolor: 'background.paper', p: { xs: 1, md: 2 } }}>
          <SystemMap fit focus hotEdges={step?.edges ?? []} selected={null} onSelect={() => undefined} />
        </Box>
        <Stack direction={{ xs: 'column', md: 'row' }} sx={{ gap: 3, alignItems: { md: 'flex-end' } }}>
          <Box sx={{ flex: 1, minWidth: 0 }}><Caption control={control} /></Box>
          <Stack direction="row" sx={{ gap: 1, alignItems: 'center' }}>
            <IconButton onClick={() => control.goTo(control.step - 1)} disabled={control.step === 0} aria-label="Previous step"><NavigateBeforeRounded /></IconButton>
            <Button variant="contained" onClick={control.toggle} startIcon={control.playing ? <PauseRounded /> : <PlayArrowRounded />} sx={{ minWidth: 112 }}>
              {control.playing ? 'Pause' : 'Play'}
            </Button>
            <IconButton onClick={() => control.goTo(control.step + 1)} disabled={control.step >= control.count - 1} aria-label="Next step"><NavigateNextRounded /></IconButton>
          </Stack>
        </Stack>
        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
          Left and right arrows to step, space to play or pause, 1 or 2 to switch journey, F for full screen, Esc to minimise.
        </Typography>
      </Stack>
    </Dialog>
  );
}
