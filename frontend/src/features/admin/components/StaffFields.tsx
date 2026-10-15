import { FormControlLabel, FormLabel, MenuItem, Radio, RadioGroup, Stack, TextField } from '@mui/material';
import { useId } from 'react';

import { DISCOMS, type Discom } from '@/shared/api/types';

import type { StaffRole } from '../api/adminApi';

interface StaffFieldsProps {
  role: StaffRole;
  discom: Discom | null;
  onRole: (role: StaffRole) => void;
  onDiscom: (discom: Discom | null) => void;
}

/** Role and DISCOM scope. Admins always see every DISCOM, so the scope only applies to officers. */
export function StaffFields({ role, discom, onRole, onDiscom }: StaffFieldsProps) {
  const labelId = useId();
  return (
    <Stack sx={{ gap: 2 }}>
      <Stack>
        <FormLabel id={labelId} sx={{ fontSize: '0.8125rem', fontWeight: 600 }}>Role</FormLabel>
        <RadioGroup row aria-labelledby={labelId} value={role} onChange={(e) => onRole(e.target.value === 'admin' ? 'admin' : 'officer')}>
          <FormControlLabel value="officer" control={<Radio />} label="DISCOM officer" />
          <FormControlLabel value="admin" control={<Radio />} label="Administrator" />
        </RadioGroup>
      </Stack>
      {role === 'officer' && (
        <TextField select label="DISCOM" value={discom ?? 'all'} fullWidth
          helperText="An officer limited to one DISCOM only sees its complaints."
          onChange={(e) => onDiscom(DISCOMS.find((d) => d === e.target.value) ?? null)}>
          <MenuItem value="all">All DISCOMs</MenuItem>
          {DISCOMS.map((d) => <MenuItem key={d} value={d}>{d}</MenuItem>)}
        </TextField>
      )}
    </Stack>
  );
}
