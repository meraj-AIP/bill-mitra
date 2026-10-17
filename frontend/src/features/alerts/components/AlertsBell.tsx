import NotificationsNoneOutlinedIcon from '@mui/icons-material/NotificationsNoneOutlined';
import { Badge, Box, Button, IconButton, List, Popover, Stack, Typography } from '@mui/material';
import { useId, useState } from 'react';
import { Link } from 'react-router-dom';

import { isConsumer, useAuth } from '@/features/auth';
import { ErrorState } from '@/shared/components/States';

import { LATEST_COUNT, useLatestAlerts } from '../api/alertsApi';
import type { AlertItem } from '../api/types';
import { useOpenAlert } from '../hooks/useOpenAlert';
import { badgeText } from '../model/labels';
import { AlertRow, AlertRowSkeleton } from './AlertRow';

interface PopoverBodyProps {
  latest: ReturnType<typeof useLatestAlerts>;
  unread: number;
  onOpen: (alert: AlertItem) => void;
  onClose: () => void;
}

function PopoverBody({ latest, unread, onOpen, onClose }: PopoverBodyProps) {
  const items = latest.data?.items;
  return (
    <>
      <Stack direction="row" sx={{ px: 2.5, py: 1.5, alignItems: 'center', borderBottom: 1, borderColor: 'divider' }}>
        <Typography variant="h3" component="h2" sx={{ flex: 1 }}>Alerts</Typography>
        <Typography variant="caption" sx={{ color: 'text.secondary' }}>{unread > 0 ? `${unread} unread` : 'All read'}</Typography>
      </Stack>
      {latest.isError && <Box sx={{ p: 2 }}><ErrorState message="Could not load alerts." onRetry={() => void latest.refetch()} /></Box>}
      {items?.length === 0 && (
        <Typography variant="body2" sx={{ px: 2.5, py: 3, color: 'text.secondary' }}>Nothing yet. New alerts show up here.</Typography>
      )}
      <List disablePadding aria-label="Latest alerts">
        {latest.isPending && Array.from({ length: 3 }, (_, i) => <AlertRowSkeleton key={i} />)}
        {items?.slice(0, LATEST_COUNT).map((a) => <AlertRow key={a.id} alert={a} onOpen={onOpen} compact />)}
      </List>
      <Box sx={{ p: 1, textAlign: 'right' }}>
        <Button component={Link} to="/alerts" onClick={onClose}>See all</Button>
      </Box>
    </>
  );
}

/** Staff only. Consumers never see it and never send the request. */
export function AlertsBell() {
  const { account } = useAuth();
  const staff = Boolean(account) && !isConsumer(account);
  const latest = useLatestAlerts(staff);
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const close = () => setAnchor(null);
  const open = useOpenAlert(close);
  const id = useId();
  if (!staff) return null;

  const unread = latest.data?.unread ?? 0;
  return (
    <>
      <IconButton onClick={(e) => setAnchor(e.currentTarget)} aria-haspopup="dialog" aria-controls={anchor ? id : undefined}
        aria-label={unread > 0 ? `Alerts, ${unread} unread` : 'Alerts'}>
        <Badge badgeContent={unread > 0 ? badgeText(unread) : null} color="error">
          <NotificationsNoneOutlinedIcon />
        </Badge>
      </IconButton>
      <Popover id={id} open={Boolean(anchor)} anchorEl={anchor} onClose={close}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }} transformOrigin={{ vertical: 'top', horizontal: 'right' }}
        slotProps={{ paper: { sx: { width: { xs: 'calc(100vw - 32px)', sm: 400 }, maxWidth: 400 } } }}>
        <PopoverBody latest={latest} unread={unread} onOpen={open} onClose={close} />
      </Popover>
    </>
  );
}
