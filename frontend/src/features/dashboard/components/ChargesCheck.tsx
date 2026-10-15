import { Box, Chip, Stack, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography } from '@mui/material';

import { rupees } from '@/shared/lib/format';

import type { Analysis } from '../api/types';
import { AUDIT_NOTE, auditStatus, LINE_STATUS } from '../model/labels';
import { ReportSection } from './ReportSection';

const money = (v: number | null) => (v === null ? 'Not printed' : rupees(v));

function difference(v: number | null): string {
  if (v === null) return '';
  if (v === 0) return rupees(0);
  return v > 0 ? `+ ${rupees(v)}` : `- ${rupees(Math.abs(v))}`;
}

/** Each printed charge next to what the TGERC tariff says it should be. */
export function ChargesCheck({ audit }: { audit: Analysis['audit'] }) {
  const status = auditStatus(audit.status);
  const mismatch = audit.status === 'mismatch';
  const notes = audit.notes.flatMap((code) => AUDIT_NOTE[code] ?? []);
  return (
    <ReportSection flush title="Charges check" caption="Printed on the bill, against the tariff in force that month"
      aside={<Chip size="small" label={status.label} color={status.tone} variant={mismatch ? 'filled' : 'outlined'} />}>
      {mismatch && audit.overcharge > 0 && (
        <Stack direction="row" sx={{ mx: { xs: 2, sm: 2.5 }, mb: 1.5, px: 2, py: 1.5, gap: 2, borderRadius: 1.5, bgcolor: 'error.light', alignItems: 'baseline', flexWrap: 'wrap' }}>
          <Typography variant="body2" sx={{ color: 'error.dark', flex: 1, minWidth: 180 }}>
            Charged more than the tariff allows
          </Typography>
          <Typography sx={{ color: 'error.dark', fontWeight: 700, fontSize: '1.5rem', fontVariantNumeric: 'tabular-nums' }}>
            {rupees(audit.overcharge)}
          </Typography>
        </Stack>
      )}
      {audit.lines.length === 0 && (
        <Typography variant="body2" sx={{ px: { xs: 2, sm: 2.5 }, pb: 1, color: 'text.secondary' }}>
          No charge on this bill could be checked line by line.
        </Typography>
      )}
      {audit.lines.length > 0 && (
        <TableContainer>
          <Table size="small" aria-label="Charges check">
            <TableHead>
              <TableRow>
                <TableCell>Charge</TableCell>
                <TableCell align="right">Printed</TableCell>
                <TableCell align="right">Tariff says</TableCell>
                <TableCell align="right">Difference</TableCell>
                <TableCell>Status</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {audit.lines.map((line) => {
                const s = LINE_STATUS[line.status];
                return (
                  <TableRow key={line.code} sx={line.status === 'over' ? { bgcolor: 'error.light' } : undefined}>
                    <TableCell sx={{ minWidth: 140 }}>{line.label}</TableCell>
                    <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>{money(line.printed)}</TableCell>
                    <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>{line.expected === null ? 'Not checkable' : rupees(line.expected)}</TableCell>
                    <TableCell align="right" sx={{ whiteSpace: 'nowrap', fontWeight: line.status === 'over' ? 700 : 400,
                      color: line.status === 'over' ? 'error.dark' : 'text.primary' }}>
                      {difference(line.difference)}
                    </TableCell>
                    <TableCell>
                      <Chip size="small" variant="outlined" label={s.label} color={s.tone} />
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
      )}
      {(notes.length > 0 || audit.undercharge > 0) && (
        <Box component="ul" sx={{ m: 0, px: { xs: 4, sm: 4.5 }, py: 1.5, color: 'text.secondary' }}>
          {audit.undercharge > 0 && (
            <Typography component="li" variant="body2">Charged less than the tariff on some lines: {rupees(audit.undercharge)} in total.</Typography>
          )}
          {notes.map((n) => <Typography component="li" variant="body2" key={n}>{n}</Typography>)}
        </Box>
      )}
    </ReportSection>
  );
}
