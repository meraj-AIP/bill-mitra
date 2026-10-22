import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { getJson, postForm, sendJson } from '@/shared/api/http';
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
    refetchInterval: 60_000,
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
  return useMutation({ meta: { action: 'Your complaint', success: 'Complaint sent' },
    mutationFn: (body: NewMyComplaint) => sendJson<MyComplaintDetail>(`/api/complaints?${LANG}`, body),
    onSuccess: store,
  });
}

export function useReplyToComplaint(ticket: string) {
  const store = useStore();
  return useMutation({ meta: { action: 'Your message', success: 'Message sent' },
    mutationFn: (body: string) => sendJson<MyComplaintDetail>(`${path(ticket)}/reply?${LANG}`, { body }),
    onSuccess: store,
  });
}

/**
 * A photo answer, shrunk on the phone first. The optional line goes with it as its caption. The client default
 * resends only a photo that never fully arrived, so a lost answer never posts the same photo twice.
 */
export function useSendPhoto(ticket: string, onProgress: (fraction: number) => void) {
  const store = useStore();
  return useMutation({ meta: { action: 'The photo', success: 'Photo sent' },
    mutationFn: async ({ file, body }: { file: File; body: string }) => {
      const form = new FormData();
      const image = await shrinkImage(file);
      form.append('file', image, file.name);
      if (body) form.append('caption', body);
      return postForm<MyComplaintDetail>(`${path(ticket)}/photo?${LANG}`, form, onProgress);
    },
    onSuccess: store,
  });
}
