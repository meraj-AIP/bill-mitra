import { Chip, Skeleton, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography } from '@mui/material';

import { isConsumer, scopeLabel, type Account } from '@/features/auth';
import { UNIT_KIND_LABEL } from '@/shared/api/types';
import { dateTime } from '@/shared/lib/format';

import { AccountRowActions } from './AccountRowActions';

interface AccountsTableProps {
  rows: Account[] | undefined;
  loadingRows: number;
  dimmed: boolean;
  selfId: string | undefined;
  onEdit: (account: Account) => void;
  onReset: (account: Account) => void;
}

function Units({ a }: { a: Account }) {
  if (isConsumer(a)) return <Typography variant="body2" sx={{ color: 'text.secondary' }}>Own bills only</Typography>;
  if (a.scopes.length === 0) return <Typography variant="body2" sx={{ color: 'warning.dark' }}>No units yet</Typography>;
  const first = a.scopes[0];
  const label = scopeLabel(a);
  return (
    <>
      <Typography variant="body2" sx={{ overflowWrap: 'anywhere' }}>{label}</Typography>
      {a.scopes.length === 1 && first && (
        <Typography variant="caption" component="p" sx={{ color: 'text.secondary' }}>{UNIT_KIND_LABEL[first.kind]}</Typography>
      )}
    </>
  );
}

export function AccountsTable({ rows, loadingRows, dimmed, selfId, onEdit, onReset }: AccountsTableProps) {
  return (
    <TableContainer sx={{ opacity: dimmed ? 0.6 : 1, transition: 'opacity 200ms' }}>
      <Table aria-label="Accounts" sx={{ '& td, & th': { py: 1.25 } }}>
        <TableHead>
          <TableRow>
            <TableCell>Name</TableCell>
            <TableCell>Role</TableCell>
            <TableCell>Units</TableCell>
            <TableCell>Status</TableCell>
            <TableCell>Last sign in</TableCell>
            <TableCell align="right" aria-label="Actions" />
          </TableRow>
        </TableHead>
        <TableBody>
          {!rows && Array.from({ length: loadingRows }, (_, i) => (
            <TableRow key={i}><TableCell colSpan={6}><Skeleton /></TableCell></TableRow>
          ))}
          {rows?.map((a) => (
            <TableRow key={a.id} hover>
              <TableCell sx={{ minWidth: 200 }}>
                <Typography variant="subtitle2" component="p">
                  {a.name}{a.id === selfId ? ' (you)' : ''}
                </Typography>
                <Typography variant="caption" component="p" sx={{ color: 'text.secondary', overflowWrap: 'anywhere' }}>{a.login}</Typography>
              </TableCell>
              <TableCell>
                <Chip size="small" variant="outlined" color={isConsumer(a) ? 'default' : 'primary'} label={a.role_name} />
              </TableCell>
              <TableCell sx={{ minWidth: 160, maxWidth: 260 }}><Units a={a} /></TableCell>
              <TableCell>
                <Chip size="small" variant={a.active ? 'filled' : 'outlined'} color={a.active ? 'success' : 'default'}
                  label={a.active ? 'Active' : 'Deactivated'} />
              </TableCell>
              <TableCell sx={{ whiteSpace: 'nowrap' }}>
                {a.last_login_at ? dateTime(a.last_login_at) : 'Never'}
                <Typography variant="caption" component="p" sx={{ color: 'text.secondary' }}>Created {dateTime(a.created_at)}</Typography>
              </TableCell>
              <TableCell align="right" sx={{ width: 56 }}>
                <AccountRowActions account={a} isSelf={a.id === selfId} onEdit={() => onEdit(a)} onReset={() => onReset(a)} />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
