import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { getJson, sendJson } from '@/shared/api/http';
import { queryKeys } from '@/shared/api/queryKeys';

import type { AlertPage, AlertQuery } from './types';

export const LATEST_COUNT = 5;

async function fetchAlerts(query: AlertQuery, signal: AbortSignal): Promise<AlertPage> {
  const params = new URLSearchParams({ page: String(query.page), page_size: String(query.pageSize) });
  if (query.unread) params.set('unread', 'true');
  const body = await getJson<Omit<AlertPage, 'page' | 'page_size'>>(`/api/alerts?${params.toString()}`, signal);
  // The server sends items, total and unread; the pager fields are the ones asked for.
  return { ...body, page: query.page, page_size: query.pageSize };
}

export function useAlerts(query: AlertQuery) {
  return useQuery({
    queryKey: queryKeys.alertList(query),
    queryFn: ({ signal }) => fetchAlerts(query, signal),
    placeholderData: keepPreviousData,
  });
}

/**
 * The bell's one request: the latest few plus the unread count. It polls every minute and, by TanStack's
 * default, pauses while the tab is hidden.
 */
export function useLatestAlerts(enabled: boolean) {
  const query: AlertQuery = { page: 1, pageSize: LATEST_COUNT, unread: false };
  return useQuery({
    queryKey: queryKeys.alertList(query),
    queryFn: ({ signal }) => fetchAlerts(query, signal),
    enabled,
    refetchInterval: 60_000,
  });
}

function useRefresh() {
  const client = useQueryClient();
  return () => void client.invalidateQueries({ queryKey: queryKeys.alerts });
}

export function useMarkRead() {
  const onSuccess = useRefresh();
  return useMutation({ mutationFn: (id: number) => sendJson<void>(`/api/alerts/${id}/read`), onSuccess });
}

export function useMarkAllRead() {
  const onSuccess = useRefresh();
  return useMutation({ mutationFn: () => sendJson<void>('/api/alerts/read-all'), onSuccess });
}
