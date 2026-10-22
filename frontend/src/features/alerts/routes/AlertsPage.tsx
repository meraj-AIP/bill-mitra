import DoneAllOutlinedIcon from '@mui/icons-material/DoneAllOutlined';
import NotificationsNoneOutlinedIcon from '@mui/icons-material/NotificationsNoneOutlined';
import { Button, CircularProgress, Container, List, Stack, ToggleButton, ToggleButtonGroup } from '@mui/material';

import { ListPanel } from '@/shared/components/ListPanel';
import { PageHeader } from '@/shared/components/PageHeader';
import { EmptyState } from '@/shared/components/States';

import { useAlerts, useMarkAllRead } from '../api/alertsApi';
import { AlertRow, AlertRowSkeleton } from '../components/AlertRow';
import { useAlertsParams } from '../hooks/useAlertsParams';
import { useOpenAlert } from '../hooks/useOpenAlert';

export function AlertsPage() {
  const { query, setPage, setPageSize, setUnread } = useAlertsParams();
  const result = useAlerts(query);
  const markAll = useMarkAllRead();
  const open = useOpenAlert();
  const unread = result.data?.unread ?? 0;

  const empty = query.unread ? (
    <EmptyState icon={<DoneAllOutlinedIcon />} title="No unread alerts" hint="You are up to date."
      action={<Button variant="outlined" onClick={() => setUnread(false)}>Show all alerts</Button>} />
  ) : (
    <EmptyState icon={<NotificationsNoneOutlinedIcon />} title="No alerts yet"
      hint="Overdue cases, misreads found from the next bill and the daily summary show up here." />
  );

  return (
    <Container maxWidth="lg" sx={{ py: { xs: 3, md: 5 } }}>
      <Stack sx={{ gap: 3 }}>
        <PageHeader title="Alerts" lead="What needs your attention in your units. Opening an alert marks it read."
          actions={(
            <Button variant="outlined" disabled={unread === 0 || markAll.isPending} onClick={() => markAll.mutate()}
              startIcon={markAll.isPending ? <CircularProgress size={16} color="inherit" aria-hidden /> : <DoneAllOutlinedIcon />}>
              Mark all read
            </Button>
          )} />
        <ToggleButtonGroup exclusive size="small" sx={{ alignSelf: 'flex-start' }} value={query.unread ? 'unread' : 'all'} aria-label="Which alerts"
          onChange={(_e, value: string | null) => value && setUnread(value === 'unread')}>
          <ToggleButton value="all">All</ToggleButton>
          <ToggleButton value="unread">{unread > 0 ? `Unread (${unread})` : 'Unread'}</ToggleButton>
        </ToggleButtonGroup>
        <ListPanel result={result} page={query.page} pageSize={query.pageSize} onPage={setPage} onPageSize={setPageSize} empty={empty}>
          {(rows, dimmed) => (
            <List disablePadding aria-label="Alerts" sx={{ opacity: dimmed ? 0.6 : 1 }}>
              {!rows && Array.from({ length: 4 }, (_, i) => <AlertRowSkeleton key={i} />)}
              {rows?.map((a) => <AlertRow key={a.id} alert={a} onOpen={open} />)}
            </List>
          )}
        </ListPanel>
      </Stack>
    </Container>
  );
}
