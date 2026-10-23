import { Alert, Button, CircularProgress, Dialog, DialogActions, DialogContent, DialogContentText, DialogTitle } from '@mui/material';

import { isStatus } from '@/shared/api/http';
import { ErrorNotice } from '@/shared/feedback';
import { formatCount } from '@/shared/lib/format';

import { useDeleteRole, type Role } from '../api/rolesApi';

function inUse(role: Role): string {
  return role.accounts === 1 ? '1 account still holds this role.' : `${formatCount(role.accounts)} accounts still hold this role.`;
}

/** The server refuses (409) while any account holds the role, so that case is explained before anyone clicks. */
export function DeleteRoleDialog({ role, onClose }: { role: Role; onClose: () => void }) {
  const remove = useDeleteRole();
  const held = role.accounts > 0;
  return (
    <Dialog open onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>Delete {role.name}?</DialogTitle>
      <DialogContent>
        {held ? (
          <Alert severity="warning">
            {inUse(role)} Give those people another role on the Accounts page first, then delete this one.
          </Alert>
        ) : (
          <DialogContentText>Nobody holds this role now. Deleting it cannot be undone; the audit log keeps a record.</DialogContentText>
        )}
        {isStatus(remove.error, 409)
          ? <Alert severity="error" sx={{ mt: 2 }}>This role cannot be deleted while accounts hold it. Move them to another role first.</Alert>
          : <ErrorNotice error={remove.error} action="Deleting the role" sx={{ mt: 2 }} />}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} autoFocus>{held ? 'Close' : 'Cancel'}</Button>
        {!held && (
          <Button variant="contained" color="error" disabled={remove.isPending} onClick={() => remove.mutate(role.slug, { onSuccess: onClose })}
            startIcon={remove.isPending ? <CircularProgress size={14} color="inherit" aria-hidden /> : null}>
            Delete role
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
}
