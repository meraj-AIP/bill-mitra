import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import AddRoundedIcon from '@mui/icons-material/AddRounded';
import FileDownloadOutlinedIcon from '@mui/icons-material/FileDownloadOutlined';
import InboxOutlinedIcon from '@mui/icons-material/InboxOutlined';
import { Box, Button, Container, Stack } from '@mui/material';
import { useState } from 'react';
import { Link } from 'react-router-dom';

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

export function ComplaintsInboxPage() {
  const { account } = useAuth();
  const params = useInboxParams();
  const { query } = params;
  const result = useInbox(query);
  const scopedTo = spansDiscoms(account) ? null : scopeLabel(account);
  const { filtered } = params;
  const canCreate = can(account, 'complaints.create');
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
    <EmptyState icon={<InboxOutlinedIcon />} title="No complaints match these filters"
      hint="Try another status, type or source, or clear the ticket search."
      action={<Button variant="outlined" onClick={params.clearFilters}>Clear filters</Button>} />
  ) : (
    <EmptyState icon={<InboxOutlinedIcon />} title="No complaints yet"
      hint="A complaint appears here when a consumer raises one, or when staff log one for a caller." />
  );

  return (
    <Container maxWidth="lg" sx={{ py: { xs: 3, md: 5 } }}>
      <Stack sx={{ gap: 3 }}>
        <Box>
          <Button component={Link} to="/console" startIcon={<ArrowBackIcon />} size="small" sx={{ ml: -1, mb: 1 }}>Console</Button>
          <PageHeader eyebrow={scopedTo ? `${scopedTo} complaints` : 'All DISCOMs'} title="Complaints inbox"
            lead="Every complaint raised in Bill Mitra. Open one to see the bill, the charges check and the conversation, and to reply."
            actions={
              <Stack direction="row" sx={{ gap: 1, flexWrap: 'wrap' }}>
                <Button variant="outlined" href={exportUrl(query)} download startIcon={<FileDownloadOutlinedIcon />}>
                  Export CSV
                </Button>
                {canCreate && (
                  <Button variant="contained" startIcon={<AddRoundedIcon />} onClick={() => setCreating(true)}>New complaint</Button>
                )}
              </Stack>
            } />
        </Box>
        <InboxFilters query={query} showDiscom={!scopedTo} onFilter={params.setFilter} onFailed={params.setFailed} onSort={params.setSort} />
        <BulkBar tickets={[...selected]} onDone={() => setSelected(new Set())} />
        <ListPanel result={result} page={query.page} pageSize={query.pageSize} onPage={params.setPage} onPageSize={params.setPageSize}
          empty={empty}>
          {(rows, dimmed) => <ComplaintsTable rows={rows} loadingRows={query.pageSize} dimmed={dimmed}
            selection={{ selected, onToggle: toggle, onToggleAll: toggleAll }} />}
        </ListPanel>
      </Stack>
      {canCreate && (
        <NewComplaintDialog open={creating} onClose={() => setCreating(false)} fixedDiscom={spansDiscoms(account) ? null : account?.discom ?? null} />
      )}
    </Container>
  );
}
