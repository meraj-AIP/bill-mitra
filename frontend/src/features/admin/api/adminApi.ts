import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type { Account } from '@/features/auth';
import { getJson, sendJson } from '@/shared/api/http';
import { queryKeys } from '@/shared/api/queryKeys';
import type { Page } from '@/shared/api/types';

export interface AccountQuery {
  page: number;
  pageSize: number;
  /** A role slug, or '' for every role. */
  role: string;
  active: 'true' | 'false' | '';
  q: string;
}

export interface NewAccount {
  /** Any role slug except consumer. */
  role: string;
  login: string;
  name: string;
  /** Unit ids. The server refuses a unit outside the creator's own scope. */
  scopes: string[];
  password: string;
}

export type AccountChanges = Partial<{ name: string; role: string; scopes: string[]; active: boolean }>;

export interface AuditEntry {
  id: number;
  ts: string;
  actor_id: string | null;
  actor_name: string | null;
  action: string;
  target: string | null;
  /** The account's name, or the ticket, as the server resolved it. */
  target_label: string | null;
  detail: string | null;
}

export function useAccounts(query: AccountQuery) {
  const params = new URLSearchParams({ page: String(query.page), page_size: String(query.pageSize) });
  if (query.role) params.set('role', query.role);
  if (query.active) params.set('active', query.active);
  if (query.q) params.set('q', query.q);
  return useQuery({
    queryKey: queryKeys.accountList(query),
    queryFn: ({ signal }) => getJson<Page<Account>>(`/api/admin/accounts?${params.toString()}`, signal),
    placeholderData: keepPreviousData,
  });
}

function useRefreshAccounts() {
  const client = useQueryClient();
  return () => {
    void client.invalidateQueries({ queryKey: queryKeys.accounts });
    void client.invalidateQueries({ queryKey: ['admin', 'audit'] });
  };
}

export function useCreateAccount() {
  const onSuccess = useRefreshAccounts();
  return useMutation({ mutationFn: (body: NewAccount) => sendJson<Account>('/api/admin/accounts', body), onSuccess });
}

export function useUpdateAccount() {
  const onSuccess = useRefreshAccounts();
  return useMutation({
    mutationFn: ({ id, changes }: { id: string; changes: AccountChanges }) =>
      sendJson<Account>(`/api/admin/accounts/${encodeURIComponent(id)}`, changes, 'PATCH'),
    onSuccess,
  });
}

export function useResetPassword() {
  const onSuccess = useRefreshAccounts();
  return useMutation({
    mutationFn: ({ id, password }: { id: string; password: string }) =>
      sendJson<void>(`/api/admin/accounts/${encodeURIComponent(id)}/reset-password`, { password }),
    onSuccess,
  });
}

export function useAuditLog(page: number, pageSize: number, action: string) {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (action) params.set('action', action);
  return useQuery({
    queryKey: queryKeys.auditLog({ page, pageSize, action }),
    queryFn: ({ signal }) => getJson<Page<AuditEntry>>(`/api/admin/audit?${params.toString()}`, signal),
    placeholderData: keepPreviousData,
  });
}
