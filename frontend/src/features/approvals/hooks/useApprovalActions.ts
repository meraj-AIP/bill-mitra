import { useState } from 'react';

import { useApprove, useApproveMany, useReject, type Proposal } from '../api/approvalsApi';

/** Selection, single and batch approval, and what to tell the officer afterwards. */
export function useApprovalActions(pending: Proposal[]) {
  const approve = useApprove();
  const reject = useReject();
  const many = useApproveMany();
  const [selected, setSelected] = useState<ReadonlySet<number>>(new Set());
  // The rows a batch was sent from, so its skipped ids still have tickets after the list refreshes.
  const [sentFrom, setSentFrom] = useState<Proposal[]>([]);

  const chosen = pending.filter((p) => selected.has(p.id)).map((p) => p.id);
  const running = [approve, reject].find((m) => m.isPending);
  return {
    selected,
    chosen,
    busyId: running?.variables ?? null,
    batchBusy: many.isPending,
    failed: [approve, reject, many].find((m) => m.isError),
    stale: approve.data?.state === 'stale' ? approve.data : null,
    batch: many.data ? { ...many.data, rows: sentFrom } : null,
    toggle: (id: number, on: boolean) => setSelected((s) => {
      const next = new Set(s);
      if (on) next.add(id);
      else next.delete(id);
      return next;
    }),
    selectAll: (on: boolean) => setSelected(on ? new Set(pending.map((p) => p.id)) : new Set()),
    approveOne: (id: number) => approve.mutate(id),
    rejectOne: (id: number) => reject.mutate(id),
    approveChosen: () => {
      setSentFrom(pending);
      many.mutate(chosen, { onSuccess: () => setSelected(new Set()) });
    },
  };
}
