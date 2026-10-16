import LockOutlinedIcon from '@mui/icons-material/LockOutlined';
import {
  Alert, Box, Button, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, Stack, TextField, Typography,
} from '@mui/material';
import { useState, type FormEvent } from 'react';

import { useCreateRole, useUpdateRole, type Role, type RoleDraft } from '../api/rolesApi';
import { separationProblem } from '../model/permissionText';
import { PermissionGroups } from './PermissionGroups';

interface RoleDialogProps {
  /** Null to create a new role. */
  role: Role | null;
  onClose: () => void;
}

const draftOf = (role: Role | null): RoleDraft =>
  (role ? { name: role.name, description: role.description, permissions: role.permissions } : { name: '', description: '', permissions: [] });

function problemsOf(d: RoleDraft) {
  return {
    name: d.name.trim() ? null : 'Give the role a name.',
    permissions: d.permissions.length > 0 ? null : 'Tick at least one permission.',
    separation: separationProblem(d.permissions),
  };
}

function titleOf(role: Role | null): string {
  if (!role) return 'Create a role';
  return role.builtin ? role.name : `Edit ${role.name}`;
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

function BuiltinNote({ description }: { description: string }) {
  return (
    <>
      <Alert severity="info" icon={<LockOutlinedIcon />}>
        A built-in role. Its permissions are fixed so every DISCOM works the same way. Create a custom role if you need a different mix.
      </Alert>
      <Typography variant="body1" sx={{ color: 'text.secondary', maxWidth: '65ch' }}>{description}</Typography>
    </>
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
      <PermissionGroups value={draft.permissions} onChange={(permissions) => patch({ permissions })} />
    </>
  );
}

function Actions({ readOnly, editing, pending, onClose }: { readOnly: boolean; editing: boolean; pending: boolean; onClose: () => void }) {
  return (
    <DialogActions sx={{ px: 3, py: 2 }}>
      <Button onClick={onClose}>{readOnly ? 'Close' : 'Cancel'}</Button>
      {!readOnly && (
        <Button type="submit" variant="contained" disabled={pending}
          startIcon={pending ? <CircularProgress size={16} color="inherit" aria-hidden /> : null}>
          {editing ? 'Save changes' : 'Create role'}
        </Button>
      )}
    </DialogActions>
  );
}

/** Built-in roles open read-only: their permissions are fixed in code. Mount with a key per role. */
export function RoleDialog({ role, onClose }: RoleDialogProps) {
  const create = useCreateRole();
  const update = useUpdateRole();
  const save = role ? update : create;
  const readOnly = Boolean(role?.builtin);
  const [draft, setDraft] = useState<RoleDraft>(() => draftOf(role));
  const [checked, setChecked] = useState(false);
  const problems = problemsOf(draft);
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
            {save.error && <Alert severity="error">{save.error.message}</Alert>}
            {role?.builtin ? (
              <>
                <BuiltinNote description={role.description} />
                <PermissionGroups value={draft.permissions} />
              </>
            ) : (
              <Editor draft={draft} patch={patch} problems={problems} checked={checked} />
            )}
          </Stack>
        </DialogContent>
        <Actions readOnly={readOnly} editing={role !== null} pending={save.isPending} onClose={onClose} />
      </Box>
    </Dialog>
  );
}
