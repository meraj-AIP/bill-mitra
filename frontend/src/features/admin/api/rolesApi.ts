import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { getJson, sendJson } from '@/shared/api/http';
import { queryKeys } from '@/shared/api/queryKeys';
import { IDEMPOTENT } from '@/shared/api/retry';

export interface Role {
  slug: string;
  name: string;
  description: string;
  permissions: string[];
  builtin: boolean;
  /** A built-in role whose permissions no longer match what ships. */
  customised: boolean;
  /** Fixed for everyone: the consumer role. */
  locked: boolean;
  /** Accounts that hold this role now. */
  accounts: number;
}

export interface PermissionInfo { code: string; label: string; group: string }

export interface RoleDraft { name: string; description: string; permissions: string[] }

export function useRoles(enabled = true) {
  return useQuery({
    queryKey: queryKeys.roles,
    queryFn: ({ signal }) => getJson<Role[]>('/api/admin/roles', signal),
    staleTime: 60_000,
    enabled,
  });
}

/** Fixed in code on the server, so it never changes while the page is open. */
export function usePermissionCatalog(enabled = true) {
  return useQuery({
    queryKey: queryKeys.permissions,
    queryFn: ({ signal }) => getJson<PermissionInfo[]>('/api/admin/permissions', signal),
    staleTime: Infinity,
    enabled,
  });
}

function useRefreshRoles() {
  const client = useQueryClient();
  return () => {
    void client.invalidateQueries({ queryKey: queryKeys.roles });
    void client.invalidateQueries({ queryKey: ['admin', 'audit'] });
  };
}

export function useCreateRole() {
  const onSuccess = useRefreshRoles();
  return useMutation({ mutationFn: (body: RoleDraft) => sendJson<Role>('/api/admin/roles', body), onSuccess });
}

export function useUpdateRole() {
  const onSuccess = useRefreshRoles();
  return useMutation({
    ...IDEMPOTENT,
    mutationFn: ({ slug, changes }: { slug: string; changes: Partial<RoleDraft> }) =>
      sendJson<Role>(`/api/admin/roles/${encodeURIComponent(slug)}`, changes, 'PATCH'),
    onSuccess,
  });
}

export function useDeleteRole() {
  const onSuccess = useRefreshRoles();
  return useMutation({
    mutationFn: (slug: string) => sendJson<void>(`/api/admin/roles/${encodeURIComponent(slug)}`, undefined, 'DELETE'),
    onSuccess,
  });
}

/** Puts a built-in role back to the name, description and permissions it ships with. */
export function useResetRole() {
  const onSuccess = useRefreshRoles();
  return useMutation({
    ...IDEMPOTENT,
    mutationFn: (slug: string) => sendJson<Role>(`/api/admin/roles/${encodeURIComponent(slug)}/reset`, undefined, 'POST'),
    onSuccess,
  });
}
