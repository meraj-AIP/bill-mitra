import OpenInFullRounded from '@mui/icons-material/OpenInFullRounded';
import PauseRounded from '@mui/icons-material/PauseRounded';
import PlayArrowRounded from '@mui/icons-material/PlayArrowRounded';
import { Box, Button, Chip, List, ListItemButton, Paper, Stack, ToggleButton, ToggleButtonGroup, Typography } from '@mui/material';
import { useState } from 'react';

import type { JourneyControl } from '../hooks/useJourney';
import { JOURNEYS } from '../model/journeys';
import { NODE_BY_ID, type NodeStatus } from '../model/systemMap';
import { ArchitecturePresenter } from './ArchitecturePresenter';
import { SystemMap } from './SystemMap';

const STATUS: Record<NodeStatus, { label: string; color: 'default' | 'secondary' | 'warning' }> = {
  built: { label: 'In the build', color: 'default' },
  planned: { label: 'Planned', color: 'secondary' },
  external: { label: 'Partner system', color: 'warning' },
};

const mono = { fontFamily: 'monospace', fontSize: '0.75rem' };

function NodeDetail({ id, onBack }: { id: string; onBack: () => void }) {
  const node = NODE_BY_ID.get(id);
  if (!node) return null;
  const status = STATUS[node.status];
  return (
    <Stack sx={{ gap: 1.5 }}>
      <Stack direction="row" sx={{ gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
        <Typography variant="h3" component="h3">{node.title}</Typography>
        <Chip size="small" label={status.label} color={status.color} variant="outlined" />
      </Stack>
      <Typography sx={{ ...mono, color: 'text.secondary' }}>{node.code}</Typography>
      <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
        {node.notes.map((n) => <Typography component="li" variant="body2" key={n} sx={{ mb: 0.5 }}>{n}</Typography>)}
      </Box>
      <Button size="small" onClick={onBack} sx={{ alignSelf: 'flex-start' }}>Back to the journey</Button>
    </Stack>
  );
}

export function JourneyPlayer({ control }: { control: JourneyControl }) {
  const [node, setNode] = useState<string | null>(null);
  const [presenting, setPresenting] = useState(false);
  const journey = JOURNEYS[control.journey];
  const step = journey?.steps[control.step];
  if (!journey || !step) return null;
  const go = (fn: () => void) => () => { setNode(null); fn(); };

  return (
    <Stack sx={{ gap: 2 }}>
      <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 1.5, justifyContent: 'space-between', alignItems: { sm: 'center' } }}>
        <ToggleButtonGroup exclusive size="small" value={control.journey} aria-label="Journey"
          onChange={(_, v: number | null) => { if (v !== null) { setNode(null); control.selectJourney(v); } }}>
          {JOURNEYS.map((j, i) => <ToggleButton key={j.name} value={i}>{j.name}</ToggleButton>)}
        </ToggleButtonGroup>
        <Stack direction="row" sx={{ gap: 1 }}>
          <Button size="small" variant="outlined" disabled={control.step === 0} onClick={go(() => control.goTo(control.step - 1))}>Back</Button>
          <Button size="small" variant="contained" onClick={go(control.toggle)}
            startIcon={control.playing ? <PauseRounded /> : <PlayArrowRounded />}>{control.playing ? 'Pause' : 'Play'}</Button>
          <Button size="small" variant="outlined" disabled={control.step >= control.count - 1} onClick={go(() => control.goTo(control.step + 1))}>Next</Button>
          <Button size="small" variant="outlined" startIcon={<OpenInFullRounded />} onClick={go(() => setPresenting(true))}>Present</Button>
        </Stack>
      </Stack>

      <ArchitecturePresenter open={presenting} onClose={() => setPresenting(false)} control={control} />
      <Paper variant="outlined" sx={{ overflowX: 'auto', p: 1.5 }}>
        <SystemMap hotEdges={node ? [] : step.edges} selected={node} onSelect={(id) => setNode(node === id ? null : id)} />
      </Paper>
      <Stack direction="row" sx={{ gap: 2, flexWrap: 'wrap', color: 'text.secondary', typography: 'caption' }}>
        <span>Solid grey: in the build</span><span>Dashed green: planned</span><span>Amber: DISCOM and partner systems</span><span>Click any box for detail</span>
      </Stack>

      <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', md: 'minmax(0, 1fr) minmax(0, 1.3fr)' } }}>
        <Paper variant="outlined">
          <List dense disablePadding component="ol">
            {journey.steps.map((s, i) => (
              <ListItemButton key={s.title} component="li" selected={i === control.step} onClick={go(() => control.goTo(i))}
                sx={{ gap: 1.5, borderBottom: 1, borderColor: 'divider', '&:last-of-type': { borderBottom: 0 } }}>
                <Typography sx={{ ...mono, color: 'text.secondary', minWidth: 20 }}>{String(i + 1).padStart(2, '0')}</Typography>
                <Typography variant="body2" sx={{ flex: 1 }}>{s.title}</Typography>
                {s.planned && <Chip size="small" label="Planned" color="secondary" variant="outlined" />}
              </ListItemButton>
            ))}
          </List>
        </Paper>
        <Paper variant="outlined" sx={{ p: 2.5, minWidth: 0 }}>
          {node ? <NodeDetail id={node} onBack={() => setNode(null)} /> : (
            <Stack sx={{ gap: 1.5 }}>
              <Typography variant="overline" component="p" sx={{ color: 'primary.light' }}>
                Step {control.step + 1} of {control.count}{step.planned ? ' · planned' : ''}
              </Typography>
              <Typography variant="h3" component="h3">{step.title}</Typography>
              <Typography variant="body2" sx={{ color: 'text.secondary', maxWidth: '60ch' }}>{step.body}</Typography>
              <Box component="pre" sx={{ ...mono, m: 0, p: 1.5, borderRadius: 1, bgcolor: 'grey.100', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                {step.payload}
              </Box>
              <Stack direction="row" sx={{ gap: 0.75, flexWrap: 'wrap' }}>
                {[...new Set(step.edges.flatMap((e) => e.split('>')))].map((id) => (
                  <Chip key={id} size="small" variant="outlined" label={NODE_BY_ID.get(id)?.title ?? id} onClick={() => setNode(id)} />
                ))}
              </Stack>
            </Stack>
          )}
        </Paper>
      </Box>
    </Stack>
  );
}
