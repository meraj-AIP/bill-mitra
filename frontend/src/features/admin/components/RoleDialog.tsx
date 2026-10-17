import LockOutlinedIcon from '@mui/icons-material/LockOutlined';
import {
  Alert, Box, Button, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, Stack, TextField,
} from '@mui/material';
import { useState, type FormEvent } from 'react';

import { useCreateRole, useResetRole, useUpdateRole, type Role, type RoleDraft } from '../api/rolesApi';
import { separationProblem } from '../model/permissionText';
import { PermissionGroups } from './PermissionGroups';

interface RoleDialogProps {
  /** Null to create a new role. */
  role: Role | null;
  onClose: () => void;
}

const draftOf = (role: Role | null): RoleDraft =>
  (role ? { name: role.name, description: role.description, permissions: role.permissions } : { name: '', description: '', permissions: [] });

const SUPER_ADMIN = 'super_admin';

function problemsOf(d: RoleDraft, slug: string | undefined) {
  return {
    name: d.name.trim() ? null : 'Give the role a name.',
    permissions: d.permissions.length > 0 ? null : 'Tick at least one permission.',
    separation: separationProblem(d.permissions),
    // Without this nobody could ever change a role again.
    lockout: slug === SUPER_ADMIN && !d.permissions.includes('roles.manage') ? 'Super admin must keep Manage roles.' : null,
  };
}

function titleOf(role: Role | null): string {
  if (!role) return 'Create a role';
  return role.locked ? role.name : `Edit ${role.name}`;
}

function NameFields({ draft, onChange, nameProblem }: { draft: RoleDraft; onChange: (d: Partial<RoleDraft>) => void; nameProblem: string | null }) {
  return (
    <Stack direction={{ xs: 'column', sm: 'row' }} sx={{ gap: 2 }}>
      <TextField label="Role name" value={draft.name} autoFocus sx={{ flex: 1 }} onChange={(e) => onChange({ name: e.target.value })}
        error={Boolean(nameProblem)} helperText={nameProblem ?? 'For example: Circle billing reviewer'} />
      <TextField label="What this role is for" value={draft.description} sx={{ flex: 2 }}
        onChange={(e) => onChange({ description: e.target.value })} helperText="One line people see when they pick a role." />
    </Stack>
  );
}

function BuiltinNote({ role }: { role: Role }) {
  if (role.locked) {
    return (
      <Alert severity="info" icon={<LockOutlinedIcon />}>
        The consumer role is fixed. Consumers only ever see their own bills and chats, so nothing here can be changed.
      </Alert>
    );
  }
  return (
    <Alert severity={role.customised ? 'warning' : 'info'}>
      {role.customised
        ? 'This built-in role has been changed from what ships. Reset it to go back to the default permissions.'
        : 'A built-in role. Changes apply to every account that holds it, from their next request.'}
      {role.slug === SUPER_ADMIN && ' Super admin always keeps Manage roles, so someone can always fix access.'}
    </Alert>
  );
}

function Editor({ draft, patch, problems, checked }: {
  draft: RoleDraft; patch: (d: Partial<RoleDraft>) => void; problems: ReturnType<typeof problemsOf>; checked: boolean;
}) {
  return (
    <>
      <NameFields draft={draft} onChange={patch} nameProblem={checked ? problems.name : null} />
      {checked && problems.permissions && <Alert severity="warning">{problems.permissions}</Alert>}
      {problems.separation && <Alert severity="warning">{problems.separation}</Alert>}
      {problems.lockout && <Alert severity="warning">{problems.lockout}</Alert>}
      <PermissionGroups value={draft.permissions} onChange={(permissions) => patch({ permissions })} />
    </>
  );
}

function Actions({ role, readOnly, pending, onReset, onClose }: {
  role: Role | null; readOnly: boolean; pending: boolean; onReset: () => void; onClose: () => void;
}) {
  return (
    <DialogActions sx={{ px: 3, py: 2 }}>
      {role?.customised && !readOnly && (
        <Button color="warning" onClick={onReset} disabled={pending} sx={{ mr: 'auto' }}>Reset to default</Button>
      )}
      <Button onClick={onClose}>{readOnly ? 'Close' : 'Cancel'}</Button>
      {!readOnly && (
        <Button type="submit" variant="contained" disabled={pending}
          startIcon={pending ? <CircularProgress size={16} color="inherit" aria-hidden /> : null}>
          {role ? 'Save changes' : 'Create role'}
        </Button>
      )}
    </DialogActions>
  );
}

/** Every role is editable except the consumer role. The server re-checks every rule shown here. Mount with a key per role. */
export function RoleDialog({ role, onClose }: RoleDialogProps) {
  const create = useCreateRole();
  const update = useUpdateRole();
  const reset = useResetRole();
  const save = role ? update : create;
  const readOnly = Boolean(role?.locked);
  const [draft, setDraft] = useState<RoleDraft>(() => draftOf(role));
  const [checked, setChecked] = useState(false);
  const problems = problemsOf(draft, role?.slug);
  const error = save.error ?? reset.error;
  const patch = (changes: Partial<RoleDraft>) => setDraft((d) => ({ ...d, ...changes }));

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setChecked(true);
    if (readOnly || Object.values(problems).some(Boolean)) return;
    const body = { ...draft, name: draft.name.trim(), description: draft.description.trim() };
    if (role) update.mutate({ slug: role.slug, changes: body }, { onSuccess: onClose });
    else create.mutate(body, { onSuccess: onClose });
  };

  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="md" scroll="paper">
      <Box component="form" noValidate onSubmit={submit} sx={{ display: 'contents' }}>
        <DialogTitle>{titleOf(role)}</DialogTitle>
        <DialogContent dividers>
          <Stack sx={{ gap: 2.5 }}>
            {error && <Alert severity="error">{error.message}</Alert>}
            {role?.builtin && <BuiltinNote role={role} />}
            {readOnly ? (
              <PermissionGroups value={draft.permissions} />
            ) : (
              <Editor draft={draft} patch={patch} problems={problems} checked={checked} />
            )}
          </Stack>
        </DialogContent>
        <Actions role={role} readOnly={readOnly} pending={save.isPending || reset.isPending} onClose={onClose}
          onReset={() => role && reset.mutate(role.slug, { onSuccess: onClose })} />
      </Box>
    </Dialog>
  );
}
