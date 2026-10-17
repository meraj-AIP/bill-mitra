import ChevronRightRoundedIcon from '@mui/icons-material/ChevronRightRounded';
import { Box, ListItemButton, Skeleton, Stack, Typography } from '@mui/material';

import { dateTime } from '@/shared/lib/format';

import type { AlertItem } from '../api/types';
import { alertHref, kindLabel } from '../model/labels';

interface AlertRowProps {
  alert: AlertItem;
  onOpen: (alert: AlertItem) => void;
  /** The popover shows one line of body; the page shows it all. */
  compact?: boolean;
}

export function AlertRow({ alert, onOpen, compact = false }: AlertRowProps) {
  const meta = [kindLabel(alert.kind), alert.unit_name, alert.ticket, dateTime(alert.created_at)].filter(Boolean).join(', ');
  return (
    <ListItemButton onClick={() => onOpen(alert)} divider alignItems="flex-start"
      aria-label={`${alert.read ? '' : 'Unread. '}${alert.title}`}
      sx={{ gap: 1.5, py: 1.5, px: { xs: 2, sm: 2.5 }, bgcolor: alert.read ? 'transparent' : 'action.hover' }}>
      <Box aria-hidden sx={{ width: 8, height: 8, mt: 0.875, borderRadius: '50%', flexShrink: 0, bgcolor: alert.read ? 'transparent' : 'primary.main' }} />
      <Stack sx={{ flex: 1, minWidth: 0, gap: 0.25 }}>
        <Typography variant="subtitle2" component="p" sx={{ fontWeight: alert.read ? 500 : 700 }}>{alert.title}</Typography>
        <Typography variant="body2" noWrap={compact} sx={{ color: 'text.secondary' }}>{alert.body}</Typography>
        <Typography variant="caption" sx={{ color: 'text.secondary' }}>{meta}</Typography>
      </Stack>
      {alertHref(alert) && <ChevronRightRoundedIcon aria-hidden sx={{ color: 'text.secondary', mt: 0.5 }} />}
    </ListItemButton>
  );
}

export function AlertRowSkeleton() {
  return (
    <Box sx={{ px: 2.5, py: 1.5, borderBottom: 1, borderColor: 'divider' }}>
      <Skeleton width="50%" />
      <Skeleton width="80%" />
    </Box>
  );
}
