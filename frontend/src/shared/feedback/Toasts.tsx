import CloseRoundedIcon from '@mui/icons-material/CloseRounded';
import { Alert, AlertTitle, Box, Button, IconButton, Stack, Typography } from '@mui/material';

import { dismiss, useToasts, type Toast } from './store';

function Actions({ t }: { t: Toast }) {
  return (
    <Stack direction="row" sx={{ alignItems: 'center', gap: 0.5 }}>
      {t.action && (
        <Button color="inherit" size="small" onClick={() => { dismiss(t.id); t.action?.run(); }} sx={{ whiteSpace: 'nowrap' }}>
          {t.action.label}
        </Button>
      )}
      <IconButton color="inherit" size="small" aria-label="Dismiss" onClick={() => dismiss(t.id)}>
        <CloseRoundedIcon fontSize="small" />
      </IconButton>
    </Stack>
  );
}

/** The message stack, bottom left, above dialogs. Errors are announced at once; the rest politely. */
export function Toasts() {
  const toasts = useToasts();
  return (
    <Box aria-live="polite" sx={{ position: 'fixed', left: { xs: 16, sm: 24 }, right: { xs: 16, sm: 'auto' }, bottom: { xs: 16, sm: 24 },
      zIndex: 'snackbar', width: { sm: 420 }, pointerEvents: 'none' }}>
      <Stack sx={{ gap: 1 }}>
        {toasts.map((t) => (
          <Alert key={t.id} severity={t.severity} variant="filled" role={t.severity === 'error' ? 'alert' : 'status'}
            action={<Actions t={t} />} sx={{ pointerEvents: 'auto', boxShadow: 6, alignItems: 'flex-start' }}>
            <AlertTitle sx={{ mb: t.message ? 0.25 : 0 }}>{t.title}</AlertTitle>
            {t.message}
            {t.reference && (
              <Typography variant="caption" component="p" sx={{ mt: 0.5, opacity: 0.85 }}>Reference {t.reference}</Typography>
            )}
          </Alert>
        ))}
      </Stack>
    </Box>
  );
}
