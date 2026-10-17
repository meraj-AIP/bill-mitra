import AddRoundedIcon from '@mui/icons-material/AddRounded';
import FileDownloadOutlinedIcon from '@mui/icons-material/FileDownloadOutlined';
import InboxOutlinedIcon from '@mui/icons-material/InboxOutlined';
import { Box, Button, Container, Stack } from '@mui/material';
import { useState } from 'react';

import { can, scopeLabel, spansDiscoms, useAuth } from '@/features/auth';
import { ListPanel } from '@/shared/components/ListPanel';
import { PageHeader } from '@/shared/components/PageHeader';
import { EmptyState } from '@/shared/components/States';

import { exportUrl, useInbox } from '../api/consoleApi';
import { BulkBar } from '../components/BulkBar';
import { ComplaintsTable } from '../components/ComplaintsTable';
import { InboxFilters } from '../components/InboxFilters';
import { NewComplaintDialog } from '../components/NewComplaintDialog';
import { useInboxParams } from '../hooks/useInboxParams';

const MINE_HINT = 'Complaints handed to you show here. Choose All I can see for the rest.';

export function ComplaintsInboxPage() {
  const { account } = useAuth();
  const params = useInboxParams();
  const { query } = params;
  const result = useInbox(query);
  const scopedTo = spansDiscoms(account) ? null : scopeLabel(account);
  const { filtered } = params;
  const canCreate = can(account, 'complaints.create');
  // Bulk actions reply and change status, so read-only accounts get neither the checkboxes nor the bar.
  const canBulk = can(account, 'complaints.reply');
  const [creating, setCreating] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const toggle = (ticket: string) => setSelected((now) => {
    const next = new Set(now);
    if (next.has(ticket)) next.delete(ticket); else next.add(ticket);
    return next;
  });
  const toggleAll = (tickets: string[]) => setSelected((now) =>
    tickets.every((t) => now.has(t)) ? new Set([...now].filter((t) => !tickets.includes(t))) : new Set([...now, ...tickets]));

  const empty = filtered ? (
    <EmptyState icon={<InboxOutlinedIcon />} title={params.mine ? 'Nothing is with you right now' : 'No complaints match these filters'}
      hint={params.mine ? MINE_HINT : 'Try another status, type or source, or clear the ticket search.'}
      action={<Button variant="outlined" onClick={params.clearFilters}>Clear filters</Button>} />
  ) : (
    <EmptyState icon={<InboxOutlinedIcon />} title="No complaints yet"
      hint="A complaint appears here when a consumer raises one, or when staff log one for a caller." />
  );

  return (
    <Container maxWidth="lg" sx={{ py: { xs: 3, md: 5 } }}>
      <Stack sx={{ gap: 3 }}>
        <Box>
          <PageHeader {...(scopedTo ? { eyebrow: scopedTo } : {})} title="Complaints"
            actions={
              <Stack direction="row" sx={{ gap: 1, flexWrap: 'wrap' }}>
                <Button href={exportUrl(query)} download startIcon={<FileDownloadOutlinedIcon />}>Export</Button>
                {canCreate && (
                  <Button variant="contained" startIcon={<AddRoundedIcon />} onClick={() => setCreating(true)}>New complaint</Button>
                )}
              </Stack>
            } />
        </Box>
        <InboxFilters query={query} showDiscom={!scopedTo} onFilter={params.setFilter} onFailed={params.setFailed} onSort={params.setSort}
          mine={params.mine} onMine={params.setMine} canHold={canBulk} />
        {canBulk && <BulkBar tickets={[...selected]} onDone={() => setSelected(new Set())} />}
        <ListPanel result={result} page={query.page} pageSize={query.pageSize} onPage={params.setPage} onPageSize={params.setPageSize}
          empty={empty}>
          {(rows, dimmed) => <ComplaintsTable rows={rows} loadingRows={query.pageSize} dimmed={dimmed}
            {...(canBulk ? { selection: { selected, onToggle: toggle, onToggleAll: toggleAll } } : {})} />}
        </ListPanel>
      </Stack>
      {canCreate && (
        <NewComplaintDialog open={creating} onClose={() => setCreating(false)} fixedDiscom={spansDiscoms(account) ? null : account?.discom ?? null} />
      )}
    </Container>
  );
}
