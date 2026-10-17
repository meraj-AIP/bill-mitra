import { Alert, Button, CircularProgress } from '@mui/material';

import { errorText, isTransient } from '@/shared/api/retry';

/** The parts of a mutation (or an upload) this needs; a useMutation result fits as is. */
export interface SendState {
  isPending: boolean;
  isPaused: boolean;
  failureCount: number;
  error: Error | null;
}

interface SendStatusProps {
  state: SendState;
  /** Offered when the failure may clear on its own. A 4xx needs a change from the person, not a retry. */
  onTryAgain?: (() => void) | undefined;
}

/** Waiting for the connection, retrying, or given up with a clear Try again. Nothing while all is well. */
export function SendStatus({ state, onTryAgain }: SendStatusProps) {
  const spinner = <CircularProgress size={16} color="inherit" aria-hidden />;
  if (state.isPaused) {
    return <Alert severity="info" icon={spinner}>You are offline. This will be sent when the connection is back.</Alert>;
  }
  if (state.isPending && state.failureCount > 0) {
    return <Alert severity="info" icon={spinner} role="status">Retrying. The connection is slow, please keep this page open.</Alert>;
  }
  if (!state.error) return null;
  const action = onTryAgain && isTransient(state.error)
    ? <Button color="inherit" size="small" onClick={onTryAgain}>Try again</Button>
    : undefined;
  return <Alert severity="error" action={action}>{errorText(state.error)}</Alert>;
}
