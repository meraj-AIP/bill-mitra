import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type { ReviewSummary } from '@/features/review';
import { getJson, isStatus, postForm, sendJson } from '@/shared/api/http';
import { queryKeys } from '@/shared/api/queryKeys';
import { shrinkImage } from '@/shared/lib/image';
import type { Language } from '@/shared/lib/languages';

import type { BillListQuery, BillReport, BillSummary, Page } from './types';

export const MAX_MB = 12;
const MAX_BYTES = MAX_MB * 1024 * 1024;
export const ACCEPTED_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif', 'application/pdf'];
// Some browsers give iPhone photos no type at all, so the extension is checked too.
const HEIC_NAME = /\.hei[cf]$/i;

/** Same limits the server enforces, checked first so the user is not kept waiting for a 413 or 415. */
export function validateFile(file: File): string | null {
  if (!ACCEPTED_TYPES.includes(file.type) && !HEIC_NAME.test(file.name)) return 'Please choose a JPG, PNG, WEBP, HEIC or PDF file.';
  if (file.size > MAX_BYTES) return `This file is over ${MAX_MB} MB. Please choose a smaller one.`;
  return null;
}

export async function uploadBill(file: File, language: Language): Promise<BillReport> {
  const problem = validateFile(file);
  if (problem) throw new Error(problem);
  const body = await shrinkImage(file);
  const form = new FormData();
  form.append('file', body, file.name);
  form.append('language', language);
  return postForm<BillReport>('/api/bills', form);
}

export function useUploadBill() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ file, language }: { file: File; language: Language }) => uploadBill(file, language),
    onSuccess: (report, { language }) => {
      if (!report.id) return;
      client.setQueryData(queryKeys.bill(report.id, language), report);
      void client.invalidateQueries({ queryKey: [...queryKeys.bills, 'list'] });
      // A new upload can answer a request for earlier bills on another report, so other reports are fetched again.
      void client.invalidateQueries({ queryKey: [...queryKeys.bills, 'one'], predicate: (q) => q.queryKey[2] !== report.id });
    },
  });
}

/** The Gruha Jyothi unit limit of the tariff a bill was checked against, from the tariff tables. */
export function useSubsidyLimit(tariffId: string) {
  return useQuery({
    queryKey: queryKeys.tariffs,
    queryFn: ({ signal }) => getJson<Array<{ id: string; gruha_jyothi_limit: number }>>('/api/tariffs', signal),
    select: (versions) => versions.find((v) => v.id === tariffId)?.gruha_jyothi_limit ?? null,
    staleTime: Infinity,
  });
}

export function useBills({ page, pageSize, status, sort }: BillListQuery) {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize), sort });
  if (status) params.set('audit_status', status);
  return useQuery({
    queryKey: queryKeys.billList(page, pageSize, status, sort),
    queryFn: ({ signal }) => getJson<Page<BillSummary>>(`/api/bills?${params.toString()}`, signal),
    placeholderData: keepPreviousData,
  });
}

export function useBill(id: string, language: Language) {
  return useQuery({
    queryKey: queryKeys.bill(id, language),
    queryFn: ({ signal }) =>
      getJson<BillReport>(`/api/bills/${encodeURIComponent(id)}?language=${language}`, signal),
    // Keep the old report on screen while the explanation reloads in another language, never across bills.
    placeholderData: (previous, previousQuery) => (previousQuery?.queryKey[2] === id ? previous : undefined),
    staleTime: Infinity,
    retry: (count, error) => count < 1 && !('status' in error && error.status === 404),
  });
}

const billKey = (billId: string) => [...queryKeys.bills, 'one', billId];
const reportPath = (billId: string) => `/api/bills/${encodeURIComponent(billId)}/review-request`;

/** Report a problem with this bill. A 409 means it is already reported; the bill is reloaded to show where it stands. */
export function useReviewRequest(billId: string, language: Language) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (note: string) => sendJson<ReviewSummary>(`${reportPath(billId)}?language=${language}`, note ? { note } : {}),
    onSuccess: (review) => {
      client.setQueriesData<BillReport>({ queryKey: billKey(billId) }, (old) => (old ? { ...old, review } : old));
      void client.invalidateQueries({ queryKey: [...queryKeys.bills, 'list'] });
    },
    onError: (error) => {
      if (isStatus(error, 409)) void client.invalidateQueries({ queryKey: billKey(billId) });
    },
  });
}

/** The consumer has no copies of the requested bills. The bill is reloaded so the report shows the new state. */
export function useNoBills(billId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => sendJson<unknown>(`${reportPath(billId)}/no-bills`, {}),
    onSettled: () => client.invalidateQueries({ queryKey: billKey(billId) }),
  });
}

