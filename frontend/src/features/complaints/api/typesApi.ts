import { useQuery } from '@tanstack/react-query';

import { getJson } from '@/shared/api/http';
import { queryKeys } from '@/shared/api/queryKeys';

import type { ComplaintType } from './types';

/** The complaint catalogue from the server. Public, so consumers and staff read the same list. */
export function useComplaintTypes(language = 'en') {
  return useQuery({
    queryKey: queryKeys.complaintTypes(language),
    queryFn: ({ signal }) => getJson<ComplaintType[]>(`/api/complaint-types?language=${encodeURIComponent(language)}`, signal),
    staleTime: Infinity,
  });
}
