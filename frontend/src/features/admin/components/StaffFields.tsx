import { ListItemText, MenuItem, Stack, TextField } from '@mui/material';

import { useAuth } from '@/features/auth';
import type { UnitRef } from '@/shared/api/types';
import { UnitPicker } from '@/shared/components/UnitPicker';

import { useRoles, type Role } from '../api/rolesApi';

// Only someone who manages roles may hand out a role that carries any of these.
const SETUP = ['roles.manage', 'units.manage', 'policy.manage'];

interface StaffFieldsProps {
  role: string;
  scopes: UnitRef[];
  onRole: (role: string) => void;
  onScopes: (scopes: UnitRef[]) => void;
  /** Shown under the units once the form has been submitted. */
  scopeError: string | null;
}

function lockedFor(role: Role, canManageRoles: boolean): boolean {
  return !canManageRoles && role.permissions.some((p) => SETUP.includes(p));
}

/** A staff account has one role and one or more units. A unit covers itself and everything under it. */
export function StaffFields({ role, scopes, onRole, onScopes, scopeError }: StaffFieldsProps) {
  const { can } = useAuth();
  const roles = useRoles();
  const staffRoles = (roles.data ?? []).filter((r) => r.slug !== 'consumer');
  const picked = staffRoles.find((r) => r.slug === role);
  const manageRoles = can('roles.manage');
  return (
    <Stack sx={{ gap: 2 }}>
      <TextField select label="Role" value={picked ? role : ''} fullWidth onChange={(e) => onRole(e.target.value)}
        disabled={roles.isPending}
        error={roles.isError}
        helperText={roles.isError ? 'Could not load the roles. Close this and try again.' : (picked?.description ?? 'What this person is allowed to do.')}
        slotProps={{ select: { renderValue: () => picked?.name ?? '' } }}>
        {staffRoles.map((r) => {
          const locked = lockedFor(r, manageRoles);
          return (
            <MenuItem key={r.slug} value={r.slug} disabled={locked} sx={{ whiteSpace: 'normal' }}>
              <ListItemText primary={r.name}
                secondary={locked ? 'Only someone who manages roles can give this role.' : r.description}
                slotProps={{ primary: { variant: 'subtitle2' }, secondary: { variant: 'caption' } }} />
            </MenuItem>
          );
        })}
      </TextField>
      <UnitPicker multiple label="Units" value={scopes} onChange={onScopes} error={Boolean(scopeError)}
        helperText={scopeError ?? 'Search by name. A DISCOM, circle or division covers everything under it; an ERO covers its sections.'} />
    </Stack>
  );
}
