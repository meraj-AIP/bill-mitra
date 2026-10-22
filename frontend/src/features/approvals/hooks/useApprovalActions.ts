import { useState } from 'react';

import { notify, useConfirm } from '@/shared/feedback';

import { useApprove, useApproveMany, useReject, type Proposal } from '../api/approvalsApi';
import { KIND_ACTION, KIND_LABEL } from '../model/labels';

/** How many of each kind are in a selection, as lines for the confirmation. */
function tally(rows: Proposal[]): string[] {
  const counts = new Map<string, number>();
  rows.forEach((p) => counts.set(KIND_LABEL[p.kind], (counts.get(KIND_LABEL[p.kind]) ?? 0) + 1));
  return [...counts].map(([label, n]) => `${label}: ${n}`);
}

/** Selection, single and batch approval with a confirmation each time, and what to tell the officer afterwards. */
export function useApprovalActions(pending: Proposal[]) {
  const approve = useApprove();
  const reject = useReject();
  const many = useApproveMany();
  const confirm = useConfirm();
  const [selected, setSelected] = useState<ReadonlySet<number>>(new Set());
  // The rows a batch was sent from, so its skipped ids still have tickets after the list refreshes.
  const [sentFrom, setSentFrom] = useState<Proposal[]>([]);

  const chosen = pending.filter((p) => selected.has(p.id));
  const byId = (id: number) => pending.find((p) => p.id === id);
  const approveOne = async (id: number) => {
    const p = byId(id);
    if (!p || !(await confirm({ title: `${KIND_LABEL[p.kind]}?`, confirmLabel: 'Approve', body: KIND_ACTION[p.kind],
      points: [`Complaint ${p.ticket}`, 'It is checked again first; if the complaint has changed, nothing is done.'] }))) return;
    approve.mutate(id, { onSuccess: (done) => {
      if (done.state === 'approved') notify({ severity: 'success', title: 'Approved and carried out', message: `Complaint ${done.ticket}` });
      else notify({ severity: 'warning', title: 'Nothing was done', message: done.note ?? 'The complaint had changed since this was proposed.' });
    } });
  };
  const rejectOne = async (id: number) => {
    const p = byId(id);
    const said = p && await confirm({ title: 'Reject this proposal?', confirmLabel: 'Reject', tone: 'warning',
      body: `Nothing is sent or changed on complaint ${p.ticket}, and this is not proposed for it again.`,
      note: { label: 'Why (optional)', max: 300, helper: 'Helps tune the rules. Not shown to the consumer.' } });
    if (said) reject.mutate({ id, note: said.note });
  };
  const approveChosen = async () => {
    if (!chosen.length || !(await confirm({ title: `Approve ${chosen.length} ${chosen.length === 1 ? 'proposal' : 'proposals'}?`,
      confirmLabel: `Approve ${chosen.length}`, body: 'Each one is checked again and carried out on its own. Any that no longer fit are skipped and listed.',
      points: tally(chosen) }))) return;
    setSentFrom(pending);
    many.mutate(chosen.map((p) => p.id), { onSuccess: () => setSelected(new Set()) });
  };
  const running = approve.isPending ? approve.variables : reject.isPending ? reject.variables?.id : undefined;
  return {
    selected,
    chosen: chosen.map((p) => p.id),
    busyId: running ?? null,
    batchBusy: many.isPending,
    batch: many.data ? { ...many.data, rows: sentFrom } : null,
    toggle: (id: number, on: boolean) => setSelected((s) => {
      const next = new Set(s);
      if (on) next.add(id);
      else next.delete(id);
      return next;
    }),
    selectAll: (on: boolean) => setSelected(on ? new Set(pending.map((p) => p.id)) : new Set()),
    approveOne: (id: number) => void approveOne(id),
    rejectOne: (id: number) => void rejectOne(id),
    approveChosen: () => void approveChosen(),
  };
}
