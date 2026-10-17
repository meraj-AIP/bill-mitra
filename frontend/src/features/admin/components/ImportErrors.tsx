import { Table, TableBody, TableCell, TableContainer, TableHead, TableRow } from '@mui/material';

/** Lines of an uploaded CSV that the server skipped, with its reason for each. */
export function ImportErrors({ errors }: { errors: Array<{ line: number; detail: string }> }) {
  return (
    <TableContainer sx={{ maxHeight: 280, border: 1, borderColor: 'divider', borderRadius: 1 }}>
      <Table size="small" stickyHeader aria-label="Lines that were skipped">
        <TableHead>
          <TableRow><TableCell sx={{ width: 72 }}>Line</TableCell><TableCell>Problem</TableCell></TableRow>
        </TableHead>
        <TableBody>
          {errors.map((e) => (
            <TableRow key={`${e.line}-${e.detail}`}>
              <TableCell sx={{ fontFamily: 'monospace' }}>{e.line}</TableCell>
              <TableCell>{e.detail}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
