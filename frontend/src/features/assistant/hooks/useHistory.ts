import { useInfiniteQuery, useQueryClient, type InfiniteData } from '@tanstack/react-query';
import { useCallback, useMemo } from 'react';

import { queryKeys } from '@/shared/api/queryKeys';

import { fetchHistory } from '../api/assistantApi';
import type { HistoryPage } from '../api/types';
import { fromHistory } from '../model/history';

const EMPTY: InfiniteData<HistoryPage, number | undefined> = { pages: [{ items: [], has_more: false }], pageParams: [undefined] };

/** Saved chat, newest page first in the cache; pages further on are older. */
export function useHistory() {
  const client = useQueryClient();
  const query = useInfiniteQuery({
    queryKey: queryKeys.assistantHistory,
    queryFn: ({ pageParam, signal }) => fetchHistory(pageParam, signal),
    initialPageParam: undefined as number | undefined,
    getNextPageParam: (last) => (last.has_more ? last.items[0]?.id : undefined),
    // Live messages are appended locally, so a refetch would duplicate them. Fetch fresh on each visit instead.
    staleTime: Infinity,
    gcTime: 0,
  });

  const items = useMemo(
    () => fromHistory([...(query.data?.pages ?? [])].reverse().flatMap((page) => page.items)),
    [query.data],
  );

  const clear = useCallback(() => client.setQueryData(queryKeys.assistantHistory, EMPTY), [client]);
  const { fetchNextPage, refetch } = query;

  return {
    items,
    loading: query.isPending,
    error: query.isError && !query.isFetchNextPageError ? query.error.message : null,
    retry: useCallback(() => void refetch(), [refetch]),
    hasEarlier: query.hasNextPage,
    loadingEarlier: query.isFetchingNextPage,
    earlierFailed: query.isFetchNextPageError,
    loadEarlier: useCallback(() => void fetchNextPage(), [fetchNextPage]),
    clear,
  };
}

export type History = ReturnType<typeof useHistory>;
