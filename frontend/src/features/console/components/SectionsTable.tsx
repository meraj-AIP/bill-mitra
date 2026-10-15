import { Paper, Skeleton, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography } from '@mui/material';

import { formatCount } from '@/shared/lib/format';

import type { Summary } from '../api/consoleApi';

export function SectionsTable({ rows }: { rows: Summary['sections'] | undefined }) {
  return (
    <Paper variant="outlined" sx={{ height: '100%' }}>
      <Typography variant="h3" component="h2" sx={{ px: 2, pt: 2 }}>
        By section
      </Typography>
      <Typography variant="caption" component="p" sx={{ color: 'text.secondary', px: 2, pb: 1 }}>
        Where mismatches cluster points to a billing machine or meter reader to check
      </Typography>
      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Section</TableCell>
              <TableCell align="right">Bills</TableCell>
              <TableCell align="right">Mismatches</TableCell>
              <TableCell align="right">Avg units</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {!rows &&
              [0, 1, 2, 3].map((i) => (
                <TableRow key={i}>
                  <TableCell colSpan={4}>
                    <Skeleton />
                  </TableCell>
                </TableRow>
              ))}
            {rows?.length === 0 && (
              <TableRow>
                <TableCell colSpan={4} sx={{ color: 'text.secondary' }}>No bills with a section yet.</TableCell>
              </TableRow>
            )}
            {rows?.map((r) => (
              <TableRow key={r.section}>
                <TableCell>{r.section}</TableCell>
                <TableCell align="right">{formatCount(r.bills)}</TableCell>
                <TableCell align="right" sx={{ color: r.mismatches ? 'warning.main' : 'text.primary' }}>
                  {formatCount(r.mismatches)}
                </TableCell>
                <TableCell align="right">{formatCount(r.avg_units)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Paper>
  );
}
