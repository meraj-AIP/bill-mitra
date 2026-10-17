import AddRoundedIcon from '@mui/icons-material/AddRounded';
import BadgeOutlinedIcon from '@mui/icons-material/BadgeOutlined';
import {
  Box, Button, Container, Paper, Skeleton, Stack, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography,
} from '@mui/material';
import { useState } from 'react';

import { PageHeader } from '@/shared/components/PageHeader';
import { EmptyState, ErrorState } from '@/shared/components/States';
import { formatCount } from '@/shared/lib/format';

import { useRoles, type Role } from '../api/rolesApi';
import { DeleteRoleDialog } from '../components/DeleteRoleDialog';
import { RoleDialog } from '../components/RoleDialog';

type Open = { kind: 'edit'; role: Role | null } | { kind: 'delete'; role: Role } | null;

function Kind({ builtin, customised }: { builtin: boolean; customised: boolean }) {
  if (customised) {
    return (
      <Box component="span" sx={{ display: 'inline-block', px: 0.75, py: 0.125, borderRadius: 0.5, fontSize: '0.6875rem', fontWeight: 600,
        bgcolor: 'warning.light', color: 'warning.dark' }}>
        Built in, changed
      </Box>
    );
  }
  return (
    <Box component="span" sx={{ display: 'inline-block', px: 0.75, py: 0.125, borderRadius: 0.5, fontSize: '0.6875rem', fontWeight: 600,
      bgcolor: builtin ? 'info.light' : 'success.light', color: builtin ? 'primary.main' : 'success.dark' }}>
      {builtin ? 'Built in' : 'Custom'}
    </Box>
  );
}

function RoleRow({ role, onOpen }: { role: Role; onOpen: (open: Open) => void }) {
  return (
    <TableRow hover>
      <TableCell sx={{ minWidth: 240 }}>
        <Stack direction="row" sx={{ gap: 1, alignItems: 'center' }}>
          <Typography variant="subtitle2" component="p">{role.name}</Typography>
          <Kind builtin={role.builtin} customised={role.customised} />
        </Stack>
        <Typography variant="caption" component="p" sx={{ color: 'text.secondary', maxWidth: '60ch' }}>{role.description}</Typography>
      </TableCell>
      <TableCell align="right">{formatCount(role.permissions.length)}</TableCell>
      <TableCell align="right">{formatCount(role.accounts)}</TableCell>
      <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>
        <Button size="small" onClick={() => onOpen({ kind: 'edit', role })}>{role.locked ? 'View' : 'Edit'}</Button>
        {!role.builtin && (
          <Button size="small" color="error" onClick={() => onOpen({ kind: 'delete', role })} aria-label={`Delete ${role.name}`}>Delete</Button>
        )}
      </TableCell>
    </TableRow>
  );
}

function RolesTable({ result, onOpen }: { result: ReturnType<typeof useRoles>; onOpen: (open: Open) => void }) {
  const rows = result.data;
  if (result.isError) return <Box sx={{ p: 2 }}><ErrorState message="Could not load the roles." onRetry={() => void result.refetch()} /></Box>;
  if (rows?.length === 0) return <EmptyState icon={<BadgeOutlinedIcon />} title="No roles yet" hint="The built-in roles are created when the server starts." />;
  return (
    <TableContainer>
      <Table aria-label="Roles">
        <TableHead>
          <TableRow>
            <TableCell>Role</TableCell>
            <TableCell align="right">Permissions</TableCell>
            <TableCell align="right">Accounts</TableCell>
            <TableCell align="right" aria-label="Actions" />
          </TableRow>
        </TableHead>
        <TableBody>
          {!rows && Array.from({ length: 5 }, (_, i) => <TableRow key={i}><TableCell colSpan={4}><Skeleton /></TableCell></TableRow>)}
          {rows?.map((r) => <RoleRow key={r.slug} role={r} onOpen={onOpen} />)}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

/** Roles are few (a handful built in, a few custom), so the list comes whole rather than in pages. */
export function RolesPage() {
  const roles = useRoles();
  const [open, setOpen] = useState<Open>(null);
  const close = () => setOpen(null);

  return (
    <Container maxWidth="lg" sx={{ py: { xs: 3, md: 5 } }}>
      <Stack sx={{ gap: 3 }}>
        <PageHeader eyebrow="Administration" title="Roles"
          lead="A role is a named set of permissions. Built-in roles cover the usual jobs and can be adjusted or reset; add a custom role when a team needs a different mix."
          actions={<Button variant="contained" startIcon={<AddRoundedIcon />} onClick={() => setOpen({ kind: 'edit', role: null })}>Create role</Button>} />
        <Paper variant="outlined" sx={{ overflow: 'hidden' }}>
          <RolesTable result={roles} onOpen={setOpen} />
        </Paper>
        <Typography variant="caption" sx={{ color: 'text.secondary', maxWidth: '75ch' }}>
          Whatever the role, nobody approves or marks applied their own decision, and a role that manages roles cannot also move money.
        </Typography>
      </Stack>
      {open?.kind === 'edit' && <RoleDialog key={open.role?.slug ?? 'new'} role={open.role} onClose={close} />}
      {open?.kind === 'delete' && <DeleteRoleDialog key={open.role.slug} role={open.role} onClose={close} />}
    </Container>
  );
}
