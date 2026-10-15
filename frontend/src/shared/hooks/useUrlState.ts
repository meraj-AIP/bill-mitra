import { useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';

export const PAGE_SIZES = [10, 25, 50];

/**
 * Page, filters and sort live in the URL so a view survives a reload and can be shared.
 * Setting any value other than the page sends the list back to page one.
 */
export function useUrlState() {
  const [params, setParams] = useSearchParams();

  const update = useCallback(
    (changes: Record<string, string | null>) => {
      setParams((current) => {
        const next = new URLSearchParams(current);
        for (const [key, value] of Object.entries(changes)) {
          if (value === null || value === '') next.delete(key);
          else next.set(key, value);
        }
        if (!('page' in changes)) next.delete('page');
        return next;
      }, { replace: true });
    },
    [setParams],
  );

  const page = Math.max(1, Number(params.get('page')) || 1);
  const sizeParam = Number(params.get('size'));
  const pageSize = PAGE_SIZES.includes(sizeParam) ? sizeParam : 10;

  /** A URL value, or '' when it is missing or not one of the allowed values. */
  const pick = <T extends string>(key: string, allowed: readonly T[]): T | '' => {
    const value = params.get(key) ?? '';
    return (allowed as readonly string[]).includes(value) ? (value as T) : '';
  };

  return {
    page,
    pageSize,
    pick,
    text: (key: string) => params.get(key) ?? '',
    update,
    setPage: (p: number) => update({ page: p > 1 ? String(p) : null }),
    setPageSize: (s: number) => update({ size: s === 10 ? null : String(s) }),
  };
}
