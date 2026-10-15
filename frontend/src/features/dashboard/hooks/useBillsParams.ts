import { useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';

import type { AuditStatus, BillListQuery } from '../api/types';
import { AUDIT_STATUS } from '../model/labels';

const PAGE_SIZES = [10, 25, 50];

/** Page, filter and sort live in the URL so a view survives a reload and can be shared. */
export function useBillsParams() {
  const [params, setParams] = useSearchParams();

  const page = Math.max(1, Number(params.get('page')) || 1);
  const sizeParam = Number(params.get('size'));
  const pageSize = PAGE_SIZES.includes(sizeParam) ? sizeParam : 10;
  const statusParam = params.get('status') ?? '';
  const status = statusParam in AUDIT_STATUS ? (statusParam as AuditStatus) : '';
  const sort = params.get('sort') === 'oldest' ? 'oldest' : 'newest';

  const update = useCallback(
    (changes: Record<string, string | null>) => {
      setParams((current) => {
        const next = new URLSearchParams(current);
        for (const [key, value] of Object.entries(changes)) {
          if (value === null || value === '') next.delete(key);
          else next.set(key, value);
        }
        return next;
      }, { replace: true });
    },
    [setParams],
  );

  return {
    query: { page, pageSize, status, sort } satisfies BillListQuery,
    pageSizes: PAGE_SIZES,
    setPage: (p: number) => update({ page: p > 1 ? String(p) : null }),
    setPageSize: (s: number) => update({ size: s === 10 ? null : String(s), page: null }),
    setStatus: (s: BillListQuery['status']) => update({ status: s, page: null }),
    setSort: (s: BillListQuery['sort']) => update({ sort: s === 'newest' ? null : s, page: null }),
  };
}
