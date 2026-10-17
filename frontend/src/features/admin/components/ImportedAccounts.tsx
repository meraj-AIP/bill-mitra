import ContentCopyOutlinedIcon from '@mui/icons-material/ContentCopyOutlined';
import FileDownloadOutlinedIcon from '@mui/icons-material/FileDownloadOutlined';
import {
  Alert, AlertTitle, Button, IconButton, Stack, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Tooltip, Typography,
} from '@mui/material';
import { useState } from 'react';

import type { ImportedAccount } from '../api/adminApi';
import { csvCell, downloadCsv } from '../model/csv';

type CopyState = { key: string; ok: boolean } | null;

function toCsv(rows: ImportedAccount[]): string[] {
  return [
    'name,login,role,unit,password',
    ...rows.map((r) => [csvCell(r.name), csvCell(r.login), csvCell(r.role), csvCell(r.unit), csvCell(r.password, false)].join(',')),
  ];
}

function PasswordCell({ row, copied, onCopy }: { row: ImportedAccount; copied: CopyState; onCopy: (key: string, text: string) => void }) {
  const state = copied?.key === row.login ? copied : null;
  return (
    <TableCell sx={{ whiteSpace: 'nowrap' }}>
      <Stack direction="row" sx={{ alignItems: 'center', gap: 0.5 }}>
        <Typography component="span" variant="body2" sx={{ fontFamily: 'monospace' }}>{row.password}</Typography>
        <Tooltip title={state ? (state.ok ? 'Copied' : 'Could not copy') : 'Copy password'}>
          <IconButton size="small" aria-label={`Copy password for ${row.login}`} onClick={() => onCopy(row.login, row.password)}>
            <ContentCopyOutlinedIcon fontSize="inherit" />
          </IconButton>
        </Tooltip>
      </Stack>
    </TableCell>
  );
}

/** Shown in clear text on purpose: the admin passes each password on. It lives only in this component's props. */
export function ImportedAccounts({ rows }: { rows: ImportedAccount[] }) {
  const [copied, setCopied] = useState<CopyState>(null);
  const copy = async (key: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied({ key, ok: true });
    } catch {
      setCopied({ key, ok: false });
    }
  };
  const allText = rows.map((r) => `${r.login}\t${r.password}`).join('\n');
  return (
    <Stack sx={{ gap: 1.5 }}>
      <Alert severity="warning">
        <AlertTitle sx={{ fontWeight: 600 }}>Save these passwords now</AlertTitle>
        They will not be shown again. Copy them or download the file before you close this window, and share each one with its
        person directly. Each person should change it after signing in.
      </Alert>
      <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 1 }}>
        <Button variant="contained" startIcon={<FileDownloadOutlinedIcon />} onClick={() => downloadCsv('bill-mitra-new-staff.csv', toCsv(rows))}>
          Download as CSV
        </Button>
        <Button variant="outlined" startIcon={<ContentCopyOutlinedIcon />} onClick={() => void copy('*', allText)}>
          {copied?.key === '*' ? (copied.ok ? 'Copied' : 'Could not copy') : 'Copy all'}
        </Button>
      </Stack>
      <TableContainer sx={{ maxHeight: 320, border: 1, borderColor: 'divider', borderRadius: 1 }}>
        <Table size="small" stickyHeader aria-label="Accounts created">
          <TableHead>
            <TableRow>
              <TableCell sx={{ width: 64 }}>Line</TableCell>
              <TableCell>Name</TableCell>
              <TableCell>Login</TableCell>
              <TableCell>Role</TableCell>
              <TableCell>Unit</TableCell>
              <TableCell>Password</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.map((r) => (
              <TableRow key={r.login}>
                <TableCell sx={{ fontFamily: 'monospace' }}>{r.line}</TableCell>
                <TableCell>{r.name}</TableCell>
                <TableCell>{r.login}</TableCell>
                <TableCell>{r.role}</TableCell>
                <TableCell>{r.unit}</TableCell>
                <PasswordCell row={r} copied={copied} onCopy={(key, text) => void copy(key, text)} />
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Stack>
  );
}
