import { Alert, CircularProgress } from '@mui/material';

/** The parts of a mutation (or an upload) this needs; a useMutation result fits as is. */
export interface SendState {
  isPending: boolean;
  isPaused: boolean;
  failureCount: number;
  error: Error | null;
}

interface SendStatusProps {
  state: SendState;
}

/** Waiting for the connection, or retrying. Nothing while all is well, and nothing on failure: the action's own
 * message says what went wrong. */
export function SendStatus({ state }: SendStatusProps) {
  const spinner = <CircularProgress size={16} color="inherit" aria-hidden />;
  if (state.isPaused) {
    return <Alert severity="info" icon={spinner}>You are offline. This will be sent when the connection is back.</Alert>;
  }
  if (state.isPending && state.failureCount > 0) {
    return <Alert severity="info" icon={spinner} role="status">Retrying. The connection is slow, please keep this page open.</Alert>;
  }
  // A failure is reported once, as a message from the action itself (App.tsx), with Try again where it is safe.
  return null;
}
