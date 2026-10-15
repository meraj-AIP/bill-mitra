import { useQuery } from '@tanstack/react-query';

import { getJson } from '@/shared/api/http';
import type { Modes } from '@/shared/api/health';

export interface SystemHealth {
  modes: Modes;
  explanations: { llm_pass: number; llm_fallback: number; template: number };
  reads: { total: number; retake: number; not_a_bill: number; failed: number; median_ms: number | null };
  failed_deliveries_7d: number;
  failed_deliveries_open: number;
  complaints_overdue: number;
  reply_days: number;
}

export function useSystemHealth() {
  return useQuery({
    queryKey: ['admin', 'health'],
    queryFn: ({ signal }) => getJson<SystemHealth>('/api/admin/health', signal),
    refetchInterval: 60_000,
  });
}
