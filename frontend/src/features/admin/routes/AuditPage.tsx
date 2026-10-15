import HistoryOutlinedIcon from '@mui/icons-material/HistoryOutlined';
import {
  Container, MenuItem, Skeleton, Stack, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TextField,
} from '@mui/material';

import { ListPanel } from '@/shared/components/ListPanel';
import { PageHeader } from '@/shared/components/PageHeader';
import { EmptyState } from '@/shared/components/States';
import { dateTime } from '@/shared/lib/format';

import { useAuditLog, type AuditEntry } from '../api/adminApi';
import { useAuditParams } from '../hooks/useAdminParams';
import { auditDetail, auditTarget } from '../model/auditText';
import { AUDIT_ACTIONS, AUDIT_ACTION_KEYS } from '../model/labels';

function Row({ e }: { e: AuditEntry }) {
  return (
    <TableRow hover>
      <TableCell sx={{ whiteSpace: 'nowrap' }}>{dateTime(e.ts)}</TableCell>
      <TableCell>{e.actor_name ?? (e.actor_id ? 'Removed account' : 'System')}</TableCell>
      <TableCell>{AUDIT_ACTIONS[e.action] ?? e.action}</TableCell>
      <TableCell sx={{ overflowWrap: 'anywhere' }}>{auditTarget(e)}</TableCell>
      <TableCell sx={{ color: 'text.secondary' }}>{auditDetail(e)}</TableCell>
    </TableRow>
  );
}

function AuditTable({ rows, loadingRows, dimmed }: { rows: AuditEntry[] | undefined; loadingRows: number; dimmed: boolean }) {
  return (
    <TableContainer sx={{ opacity: dimmed ? 0.6 : 1 }}>
      <Table size="small" aria-label="Audit log">
        <TableHead>
          <TableRow>
            <TableCell>When</TableCell>
            <TableCell>Who</TableCell>
            <TableCell>Action</TableCell>
            <TableCell>About</TableCell>
            <TableCell>Detail</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {!rows && Array.from({ length: loadingRows }, (_, i) => (
            <TableRow key={i}><TableCell colSpan={5}><Skeleton /></TableCell></TableRow>
          ))}
          {rows?.map((e) => <Row key={e.id} e={e} />)}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

export function AuditPage() {
  const params = useAuditParams();
  const result = useAuditLog(params.page, params.pageSize, params.action);

  return (
    <Container maxWidth="lg" sx={{ py: { xs: 3, md: 5 } }}>
      <Stack sx={{ gap: 3 }}>
        <PageHeader eyebrow="Administration" title="Audit log"
          lead="Every sign in, account change and complaint action, newest first. Entries cannot be edited." />
        <TextField select size="small" label="Action" value={params.action} onChange={(e) => params.setAction(e.target.value)}
          sx={{ maxWidth: 300 }}>
          <MenuItem value="">All actions</MenuItem>
          {AUDIT_ACTION_KEYS.map((k) => <MenuItem key={k} value={k}>{AUDIT_ACTIONS[k]}</MenuItem>)}
        </TextField>
        <ListPanel result={result} page={params.page} pageSize={params.pageSize} onPage={params.setPage} onPageSize={params.setPageSize}
          empty={<EmptyState icon={<HistoryOutlinedIcon />} title="Nothing logged yet"
            hint={params.action ? 'No entries for this action. Pick another, or All actions.' : 'Entries appear as people sign in and staff make changes.'} />}>
          {(rows, dimmed) => <AuditTable rows={rows} loadingRows={params.pageSize} dimmed={dimmed} />}
        </ListPanel>
      </Stack>
    </Container>
  );
}
