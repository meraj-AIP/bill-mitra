import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { getJson, isStatus, postForm, sendJson } from '@/shared/api/http';
import { shrinkImage } from '@/shared/lib/image';
import { queryKeys } from '@/shared/api/queryKeys';
import type { Page } from '@/shared/api/types';

import type { MyComplaintDetail, MyComplaintRow, MyListQuery, NewMyComplaint } from './types';

// The server defaults to Telugu; this page is in English, so labels are asked for in English.
const LANG = 'language=en';
const path = (ticket: string) => `/api/complaints/${encodeURIComponent(ticket)}`;

export function useMyComplaints(query: MyListQuery) {
  const params = new URLSearchParams({ page: String(query.page), page_size: String(query.pageSize), language: 'en' });
  if (query.status) params.set('status', query.status);
  return useQuery({
    queryKey: queryKeys.myComplaintList(query),
    queryFn: ({ signal }) => getJson<Page<MyComplaintRow>>(`/api/complaints?${params.toString()}`, signal),
    placeholderData: keepPreviousData,
  });
}

export function useMyComplaint(ticket: string) {
  return useQuery({
    queryKey: queryKeys.myComplaint(ticket),
    queryFn: ({ signal }) => getJson<MyComplaintDetail>(`${path(ticket)}?${LANG}`, signal),
    // A reply from Bill Mitra should show without a reload.
    refetchInterval: 30_000,
    retry: (count, error) => count < 1 && !isStatus(error, 404),
  });
}

function useStore() {
  const client = useQueryClient();
  return (detail: MyComplaintDetail) => {
    client.setQueryData(queryKeys.myComplaint(detail.ticket), detail);
    void client.invalidateQueries({ queryKey: [...queryKeys.myComplaints, 'list'] });
  };
}

export function useRaiseComplaint() {
  const store = useStore();
  return useMutation({
    mutationFn: (body: NewMyComplaint) => sendJson<MyComplaintDetail>(`/api/complaints?${LANG}`, body),
    onSuccess: store,
  });
}

export function useReplyToComplaint(ticket: string) {
  const store = useStore();
  return useMutation({
    mutationFn: (body: string) => sendJson<MyComplaintDetail>(`${path(ticket)}/reply?${LANG}`, { body }),
    onSuccess: store,
  });
}

/** A photo answer, shrunk on the phone first. The optional line goes with it as its caption. */
export function useSendPhoto(ticket: string) {
  const store = useStore();
  return useMutation({
    mutationFn: async ({ file, body }: { file: File; body: string }) => {
      const form = new FormData();
      const image = await shrinkImage(file);
      form.append('file', image, file.name);
      if (body) form.append('caption', body);
      return postForm<MyComplaintDetail>(`${path(ticket)}/photo?${LANG}`, form);
    },
    onSuccess: store,
  });
}
