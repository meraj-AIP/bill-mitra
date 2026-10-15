import { Box, Chip, Paper, Skeleton, Stack, Typography } from '@mui/material';

import { useHealth } from '@/shared/api/health';
import { ErrorState } from '@/shared/components/States';

import { CAPABILITIES, RUNNING } from '../model/copy';

function statusLabel(mode: string): string {
  return mode.charAt(0).toUpperCase() + mode.slice(1);
}

/** Read from /api/health on every visit, so the page never claims a step is on when the server has it off. */
export function LiveStatus() {
  const health = useHealth();
  if (health.isError) return <ErrorState message="Could not reach the server for its status." onRetry={() => void health.refetch()} />;
  const modes = health.data?.modes;
  return (
    <Paper variant="outlined" component="ul" sx={{ m: 0, p: 0, listStyle: 'none' }}>
      {CAPABILITIES.map(({ key, label, on, off }, i) => {
        const mode = modes?.[key];
        const running = mode !== undefined && RUNNING.has(mode);
        return (
          <Stack component="li" key={key} direction={{ xs: 'column', sm: 'row' }}
            sx={{ gap: { xs: 0.75, sm: 2 }, px: 2, py: 1.5, alignItems: { sm: 'center' }, borderTop: i ? 1 : 0, borderColor: 'divider' }}>
            <Typography variant="subtitle2" component="p" sx={{ width: { sm: 200 }, flexShrink: 0 }}>{label}</Typography>
            <Box sx={{ width: { sm: 170 }, flexShrink: 0 }}>
              {mode === undefined ? <Skeleton width={80} height={24} /> : (
                <Chip size="small" variant="outlined" label={statusLabel(mode)} color={running ? 'success' : 'default'} />
              )}
            </Box>
            <Typography variant="body2" sx={{ color: 'text.secondary', flex: 1 }}>
              {mode === undefined ? '' : running ? on : off}
            </Typography>
          </Stack>
        );
      })}
    </Paper>
  );
}
