import { Button, Stack, Typography } from '@mui/material';

import type { Language } from '../api/types';
import { FAILURE_TEXT } from '../model/failures';

interface FailureLineProps {
  text: string;
  reference: string | null;
  language: Language;
  onRetry?: (() => void) | undefined;
}

/** A failed turn or load, in the chat's language, centred in the thread like a WhatsApp system note. */
export function FailureLine({ text, reference, language, onRetry }: FailureLineProps) {
  const t = FAILURE_TEXT[language];
  return (
    <Stack role="alert" dir="auto"
      sx={{ mx: 'auto', mt: 1.5, px: 1.5, py: 0.75, width: 'fit-content', maxWidth: '86%', borderRadius: '8px', alignItems: 'center',
        textAlign: 'center', bgcolor: 'error.light', color: 'error.dark' }}>
      <Typography variant="caption" component="p">{text}</Typography>
      {reference && (
        <Typography variant="caption" component="p" sx={{ opacity: 0.8, fontSize: '0.6875rem' }}>
          {t.reference} {reference}
        </Typography>
      )}
      {onRetry && (
        <Button size="small" color="error" onClick={onRetry} sx={{ mt: 0.25, minHeight: 28, py: 0 }}>{t.retry}</Button>
      )}
    </Stack>
  );
}
