import ErrorOutlineIcon from '@mui/icons-material/ErrorOutlineOutlined';
import { Box, Button, Stack, Typography } from '@mui/material';
import type { ReactNode } from 'react';

interface EmptyStateProps {
  title: string;
  hint?: ReactNode;
  icon?: ReactNode;
  action?: ReactNode;
}

export function EmptyState({ title, hint, icon, action }: EmptyStateProps) {
  return (
    <Stack sx={{ alignItems: 'center', justifyContent: 'center', py: 6, px: 2, gap: 1, color: 'text.secondary', textAlign: 'center' }}>
      {icon && (
        <Box sx={{ display: 'grid', placeItems: 'center', width: 48, height: 48, borderRadius: 2, bgcolor: 'grey.100', color: 'primary.light', mb: 0.5 }}>
          {icon}
        </Box>
      )}
      <Typography variant="h3" component="p" sx={{ color: 'text.primary' }}>
        {title}
      </Typography>
      {hint && (
        <Typography variant="body2" sx={{ maxWidth: '46ch' }}>
          {hint}
        </Typography>
      )}
      {action && <Box sx={{ mt: 1.5 }}>{action}</Box>}
    </Stack>
  );
}

interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
}

export function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <Stack direction="row" role="alert"
      sx={{ p: 2, gap: 1.5, alignItems: 'center', borderRadius: 2, border: 1, borderColor: 'error.light', bgcolor: 'error.light' }}>
      <ErrorOutlineIcon color="error" />
      <Typography variant="body2" sx={{ flex: 1, color: 'error.dark' }}>
        {message}
      </Typography>
      {onRetry && (
        <Button size="small" color="error" onClick={onRetry}>
          Try again
        </Button>
      )}
    </Stack>
  );
}
