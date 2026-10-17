import { useState } from 'react';
import { Box, Paper, Stack, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography } from '@mui/material';

import { BillImage } from '@/shared/components/BillImage';
import { Figure, Panel } from '@/shared/components/Panel';
import { formatCount, monthLabel, rupees } from '@/shared/lib/format';

import type { ComplaintDetail } from '../api/types';

const money = (v: number | null) => (v === null ? 'Not printed' : rupees(v));

function difference(v: number | null): string {
  if (v === null || v === 0) return v === 0 ? rupees(0) : '';
  return v > 0 ? `+ ${rupees(v)}` : `- ${rupees(Math.abs(v))}`;
}

/** Printed charges against the tariff, line by line. Shared with the review case page. */
export function AuditLines({ lines }: { lines: ComplaintDetail['audit_lines'] }) {
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

function BillSummary({ bill }: { bill: NonNullable<ComplaintDetail['bill']> }) {
  return (
    <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: 'repeat(2, minmax(0, 1fr))', sm: 'repeat(4, minmax(0, 1fr))' } }}>
      <Figure label="Bill month" value={monthLabel(bill.bill_month)} />
      <Figure label="Units" value={bill.units === null ? 'Not printed' : formatCount(bill.units)} />
      <Figure label="Bill amount" value={money(bill.bill_amount)} />
      <Figure label="Total payable" value={money(bill.total_payable)} strong />
    </Box>
  );
}

/** The bill the complaint rests on: its figures, the photo and the line-by-line check. */
export function ComplaintEvidence({ complaint, staff }: { complaint: ComplaintDetail; staff: boolean }) {
  // The contract does not say whether the file is a photo or a PDF, so a photo that fails to load is shown as a PDF.
  const [isPdf, setIsPdf] = useState(false);
  const { bill } = complaint;
  if (!bill && !complaint.media_url) {
    return (
      <Panel title="Linked bill">
        <Typography variant="body2" sx={{ color: 'text.secondary' }}>
          No bill is linked to this complaint. Ask for a bill photo if the complaint needs one.
        </Typography>
      </Panel>
    );
  }
  return (
    <Stack sx={{ gap: 2 }}>
      {bill && (
        <Panel title="Linked bill" caption={`${bill.discom}${bill.service_masked ? `, service no. ${bill.service_masked}` : ''}`}>
          <BillSummary bill={bill} />
        </Panel>
      )}
      <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', md: complaint.media_url ? 'minmax(0, 5fr) minmax(0, 7fr)' : '1fr' }, alignItems: 'start' }}>
        {complaint.media_url && (
          <BillImage src={complaint.media_url} isPdf={isPdf} heading={staff ? 'Bill as uploaded' : 'Your bill'}
            onImageError={() => setIsPdf(true)} />
        )}
        {bill && <AuditLines lines={complaint.audit_lines} />}
      </Box>
    </Stack>
  );
}
