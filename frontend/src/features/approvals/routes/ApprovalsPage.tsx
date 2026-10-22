import TaskAltOutlinedIcon from '@mui/icons-material/TaskAltOutlined';
import { Alert, Container, Stack } from '@mui/material';

import { ListPanel } from '@/shared/components/ListPanel';
import { PageHeader } from '@/shared/components/PageHeader';
import { EmptyState } from '@/shared/components/States';

import { useProposals, type BatchResult, type Proposal } from '../api/approvalsApi';
import { ApprovalFilters } from '../components/ApprovalFilters';
import { BatchBar } from '../components/BatchBar';
import { ProposalTable } from '../components/ProposalTable';
import { useApprovalActions } from '../hooks/useApprovalActions';
import { useApprovalParams } from '../hooks/useApprovalParams';

function BatchOutcome({ batch }: { batch: BatchResult & { rows: Proposal[] } }) {
  const ticket = (id: number) => batch.rows.find((p) => p.id === id)?.ticket ?? `#${id}`;
  return (
    <Alert severity={batch.skipped.length ? 'warning' : 'success'}>
      {`Approved ${batch.done.length}.`}
      {batch.skipped.map((s) => <div key={s.id}>{`${ticket(s.id)}: ${s.reason}`}</div>)}
    </Alert>
  );
}

/** What the rules prepared, waiting for an officer. Approve one, or select several and approve them together. */
export function ApprovalsPage() {
  const params = useApprovalParams();
  const result = useProposals(params.query);
  const pending = (result.data?.items ?? []).filter((p) => p.state === 'pending');
  const act = useApprovalActions(pending);
  const waitingView = !params.query.state || params.query.state === 'pending';

  return (
    <Container maxWidth="lg" sx={{ py: { xs: 3, md: 5 } }}>
      <Stack sx={{ gap: 2.5 }}>
        <PageHeader eyebrow="Work" title="Approvals"
          lead="Routine actions the system prepared from the bill check. Nothing is sent or decided until you approve it, and each one is checked again against the complaint when you do." />
        <ApprovalFilters kind={params.query.kind} state={params.query.state} counts={result.data?.counts} onKind={params.setKind} onState={params.setState} />
        {waitingView && (
          <BatchBar onPage={pending.length} chosen={act.chosen.length} busy={act.batchBusy} onAll={act.selectAll} onApprove={act.approveChosen} />
        )}
        {act.batch && <BatchOutcome batch={act.batch} />}
        <ListPanel result={result} page={params.query.page} pageSize={params.query.pageSize} onPage={params.setPage} onPageSize={params.setPageSize}
          empty={<EmptyState icon={<TaskAltOutlinedIcon />} title={waitingView ? 'Nothing waiting' : 'Nothing here'}
            hint="When the rules can prepare a routine reply, request or decision, it appears here for you to approve." />}>
          {(rows, dimmed) => (
            <ProposalTable rows={rows} loadingRows={params.query.pageSize} dimmed={dimmed}
              actions={{ busyId: act.busyId, isSelected: (id) => act.selected.has(id), onSelect: act.toggle,
                onApprove: act.approveOne, onReject: act.rejectOne }} />
          )}
        </ListPanel>
      </Stack>
    </Container>
  );
}
