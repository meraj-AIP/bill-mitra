import { useQuery } from '@tanstack/react-query';

import { getJson } from '@/shared/api/http';
import { queryKeys } from '@/shared/api/queryKeys';

export interface Modes {
  vision: 'live' | 'off';
  language_model: 'live' | 'template';
  voice: 'live' | 'off';
  listening: 'live' | 'off';
  whatsapp: string;
}

export interface QueueCount {
  queued: number;
  failed: number;
}

/** Durable queue sizes. Optional until every server sends them. */
export interface Queues {
  inbox: QueueCount;
  outbox: QueueCount;
  extract: QueueCount;
  /** Age in seconds of the oldest job still waiting, or null when nothing waits. */
  oldest_queued_s: number | null;
}

export interface Health {
  status: string;
  modes: Modes;
  /** The public Bill Mitra WhatsApp number, digits only, when one is set. */
  whatsapp_number: string | null;
  queues?: Queues;
}

/** Pass refreshMs on a page that watches the queues; elsewhere the cached copy is fine for a minute. */
export function useHealth(refreshMs: number | false = false) {
  return useQuery({
    queryKey: queryKeys.health,
    queryFn: ({ signal }) => getJson<Health>('/api/health', signal),
    staleTime: 60_000,
    refetchInterval: refreshMs,
  });
}
