import { useState } from 'react';
import { Paper, Stack, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography } from '@mui/material';

import { BillImage } from '@/shared/components/BillImage';
import { rupees } from '@/shared/lib/format';

import type { ComplaintDetail } from '../api/types';

const money = (v: number | null) => (v === null ? 'Not printed' : rupees(v));

function difference(v: number | null): string {
  if (v === null || v === 0) return v === 0 ? rupees(0) : '';
  return v > 0 ? `+ ${rupees(v)}` : `- ${rupees(Math.abs(v))}`;
}

function AuditLines({ lines }: { lines: ComplaintDetail['audit_lines'] }) {
  return (
    <Paper variant="outlined">
      <Stack sx={{ px: 2, pt: 1.75, pb: 1.25 }}>
        <Typography variant="h3" component="h2">Charges check</Typography>
        <Typography variant="caption" sx={{ color: 'text.secondary' }}>Printed on the bill, against the TGERC tariff for that month</Typography>
      </Stack>
      {lines.length === 0 ? (
        <Typography variant="body2" sx={{ px: 2, pb: 2, color: 'text.secondary' }}>No charge on this bill could be checked line by line.</Typography>
      ) : (
        <TableContainer>
          <Table size="small" aria-label="Printed and expected charges">
            <TableHead>
              <TableRow>
                <TableCell>Charge</TableCell>
                <TableCell align="right">Printed</TableCell>
                <TableCell align="right">Tariff says</TableCell>
                <TableCell align="right">Difference</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {lines.map((line) => {
                const over = line.status === 'over';
                return (
                  <TableRow key={line.code} sx={over ? { bgcolor: 'error.light' } : undefined}>
                    <TableCell>{line.label}</TableCell>
                    <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>{money(line.printed)}</TableCell>
                    <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>{line.expected === null ? 'Not checkable' : rupees(line.expected)}</TableCell>
                    <TableCell align="right" sx={{ whiteSpace: 'nowrap', fontWeight: over ? 700 : 400, color: over ? 'error.dark' : 'text.primary' }}>
                      {difference(line.difference)}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Paper>
  );
}

/** The bill and the line-by-line check the complaint rests on. */
export function ComplaintEvidence({ complaint, staff }: { complaint: ComplaintDetail; staff: boolean }) {
  // The contract does not say whether the file is a photo or a PDF, so a photo that fails to load is shown as a PDF.
  const [isPdf, setIsPdf] = useState(false);
  return (
    <Stack sx={{ gap: 2 }}>
      {complaint.media_url ? (
        <BillImage src={complaint.media_url} isPdf={isPdf} heading={staff ? 'Bill as uploaded' : 'Your bill'}
          onImageError={() => setIsPdf(true)} />
      ) : (
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>No bill photo is attached to this complaint.</Typography>
        </Paper>
      )}
      <AuditLines lines={complaint.audit_lines} />
    </Stack>
  );
}
