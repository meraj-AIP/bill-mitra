import { Alert, AlertTitle, Button, Typography, type SxProps, type Theme } from '@mui/material';

import { describeError } from './errors';

interface ErrorNoticeProps {
  error: unknown;
  /** The action's name for the title, e.g. "The reply" did not go through. */
  action?: string | undefined;
  /** A fixed title, for a load ("Could not load this bill") where an action name reads oddly. */
  title?: string | undefined;
  onRetry?: (() => void) | undefined;
  /** Loading data is always safe to repeat, so Try again shows whatever the failure was. */
  retrySafe?: boolean;
  sx?: SxProps<Theme> | undefined;
}

/** Every error on screen, in the same words as everywhere else: what happened, what to do, the reference for
 * support, and Try again only where repeating cannot do something twice. */
export function ErrorNotice({ error, action, title, onRetry, retrySafe = false, sx }: ErrorNoticeProps) {
  if (!error) return null;
  const said = describeError(error, action);
  const retry = onRetry && (retrySafe || said.retry);
  return (
    <Alert severity={said.severity} role="alert" sx={sx ?? {}}
      action={retry ? <Button color="inherit" size="small" onClick={onRetry}>Try again</Button> : undefined}>
      <AlertTitle>{title ?? said.title}</AlertTitle>
      {said.message}
      {said.ref && (
        <Typography variant="caption" component="p" sx={{ mt: 0.5, opacity: 0.8, fontVariantNumeric: 'tabular-nums' }}>
          Reference {said.ref}
        </Typography>
      )}
    </Alert>
  );
}
