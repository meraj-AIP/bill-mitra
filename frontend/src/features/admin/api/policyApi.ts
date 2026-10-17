import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type { Policy } from '@/features/review';
import { getJson, sendJson } from '@/shared/api/http';
import { queryKeys } from '@/shared/api/queryKeys';
import { IDEMPOTENT } from '@/shared/api/retry';

export function usePolicies() {
  return useQuery({ queryKey: queryKeys.policies, queryFn: ({ signal }) => getJson<Policy[]>('/api/admin/policy', signal) });
}

export function useSavePolicy() {
  const client = useQueryClient();
  return useMutation({
    ...IDEMPOTENT,
    mutationFn: (policy: Policy) => sendJson<Policy>(`/api/admin/policy/${policy.discom}`, policy, 'PUT'),
    onSuccess: (saved) => {
      client.setQueryData<Policy[]>(queryKeys.policies, (all) => all?.map((p) => (p.discom === saved.discom ? saved : p)));
      void client.invalidateQueries({ queryKey: ['admin', 'audit'] });
    },
  });
}
