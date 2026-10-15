import { Box, Chip, Stack, Tooltip, Typography } from '@mui/material';

import { useHealth, type Modes } from '@/shared/api/health';

const LABELS: Array<[keyof Modes, string]> = [
  ['vision', 'Bill reading'],
  ['language_model', 'Explanation'],
  ['voice', 'Telugu voice'],
  ['listening', 'Voice questions'],
  ['whatsapp', 'WhatsApp channel'],
];

const MODE_TEXT: Record<string, string> = { live: 'on', off: 'off', template: 'fixed templates' };

/** Says plainly which steps are running, so nobody mistakes a switched-off reader for a broken one. */
export function ModeStatus() {
  const { data, isError } = useHealth();
  if (isError) return <Chip size="small" variant="outlined" label="Server not reachable" color="error" />;
  if (!data) return null;
  const reading = data.modes.vision === 'live';
  const detail = (
    <Stack sx={{ gap: 0.5, py: 0.5 }}>
      {LABELS.map(([key, label]) => (
        <Typography key={key} variant="caption">
          {label}: <b>{MODE_TEXT[data.modes[key]] ?? data.modes[key]}</b>
        </Typography>
      ))}
    </Stack>
  );
  return (
    <Tooltip title={detail}>
      <Chip
        size="small"
        variant="outlined"
        tabIndex={0}
        icon={<Box component="span" sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: reading ? 'success.main' : 'warning.main' }} />}
        label={reading ? 'Bill reading on' : 'Bill reading off'}
        sx={{ bgcolor: 'background.paper', pl: 0.75 }}
      />
    </Tooltip>
  );
}
