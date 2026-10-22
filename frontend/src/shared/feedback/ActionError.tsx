import { Alert, AlertTitle, type SxProps, type Theme } from '@mui/material';

import { describeError } from './errors';

/** A failed action's message beside the form it came from, in the same words as everywhere else. For actions marked
 * `quiet`, so the message is not shown twice. */
export function ActionError({ error, action, sx }: { error: Error | null | undefined; action?: string; sx?: SxProps<Theme> }) {
  if (!error) return null;
  const said = describeError(error, action);
  return (
    <Alert severity={said.severity} sx={sx ?? {}}>
      <AlertTitle>{said.title}</AlertTitle>
      {said.message}
    </Alert>
  );
}
