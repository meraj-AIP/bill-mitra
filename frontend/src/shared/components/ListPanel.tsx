import { Box, Paper, TablePagination } from '@mui/material';
import type { ReactNode } from 'react';

import type { Page } from '@/shared/api/types';
import { ErrorState } from '@/shared/components/States';
import { PAGE_SIZES } from '@/shared/hooks/useUrlState';

interface ListResult<T> {
  data: Page<T> | undefined;
  error: Error | null;
  isPlaceholderData: boolean;
  refetch: () => unknown;
}

interface ListPanelProps<T> {
  result: ListResult<T>;
  page: number;
  pageSize: number;
  onPage: (page: number) => void;
  onPageSize: (size: number) => void;
  /** Shown when the server says there is nothing on this page. */
  empty: ReactNode;
  /** Rows are undefined while the first page loads, so the list can draw its skeleton. */
  children: (rows: T[] | undefined, dimmed: boolean) => ReactNode;
}

/** One frame for every server-paginated list: error, empty, rows and the pager. */
export function ListPanel<T>({ result, page, pageSize, onPage, onPageSize, empty, children }: ListPanelProps<T>) {
  const { data, error } = result;
  const hasRows = data !== undefined && data.total > 0;
  return (
    <Paper variant="outlined" sx={{ overflow: 'hidden' }}>
      {error && (
        <Box sx={{ p: 2 }}>
          <ErrorState message={error.message} onRetry={() => void result.refetch()} />
        </Box>
      )}
      {data?.total === 0 && empty}
      {!error && data?.total !== 0 && children(data?.items, result.isPlaceholderData)}
      {hasRows && (
        <TablePagination component="div" count={data.total} page={page - 1} rowsPerPage={pageSize}
          rowsPerPageOptions={PAGE_SIZES} onPageChange={(_e, p) => onPage(p + 1)}
          onRowsPerPageChange={(e) => onPageSize(Number(e.target.value))}
          sx={{ borderTop: 1, borderColor: 'divider' }} />
      )}
    </Paper>
  );
}
