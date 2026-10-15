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

export interface Health {
  status: string;
  modes: Modes;
  /** The public Bill Mitra WhatsApp number, digits only, when one is set. */
  whatsapp_number: string | null;
}

export function useHealth() {
  return useQuery({
    queryKey: queryKeys.health,
    queryFn: ({ signal }) => getJson<Health>('/api/health', signal),
    staleTime: 60_000,
  });
}
