import CheckRoundedIcon from '@mui/icons-material/CheckRounded';
import { Box, Checkbox, FormControl, FormControlLabel, FormGroup, FormLabel, Skeleton, Stack, Typography } from '@mui/material';

import { ErrorState } from '@/shared/components/States';

import { usePermissionCatalog, type PermissionInfo } from '../api/rolesApi';
import { groupCatalog, PERMISSION_HINT } from '../model/permissionText';

interface PermissionGroupsProps {
  value: string[];
  /** Leave out for a read-only list of what the role holds. */
  onChange?: (value: string[]) => void;
}

function Hint({ p }: { p: PermissionInfo }) {
  return (
    <Box sx={{ py: 0.5 }}>
      <Typography variant="body2" sx={{ fontWeight: 600 }}>{p.label}</Typography>
      <Typography variant="caption" component="p" sx={{ color: 'text.secondary' }}>{PERMISSION_HINT[p.code] ?? p.code}</Typography>
    </Box>
  );
}

function ReadOnly({ items, value }: { items: PermissionInfo[]; value: string[] }) {
  const held = items.filter((p) => value.includes(p.code));
  if (held.length === 0) return <Typography variant="body2" sx={{ color: 'text.secondary' }}>None from this group.</Typography>;
  return (
    <Stack component="ul" sx={{ listStyle: 'none', m: 0, p: 0, gap: 0.5 }}>
      {held.map((p) => (
        <Stack component="li" key={p.code} direction="row" sx={{ gap: 1, alignItems: 'flex-start' }}>
          <CheckRoundedIcon fontSize="small" sx={{ color: 'success.main', mt: 0.75 }} aria-hidden />
          <Hint p={p} />
        </Stack>
      ))}
    </Stack>
  );
}

/** The fixed catalogue, grouped as the server groups it, each permission said in plain words. */
export function PermissionGroups({ value, onChange }: PermissionGroupsProps) {
  const catalog = usePermissionCatalog();
  if (catalog.isPending) return <Stack sx={{ gap: 1 }}><Skeleton height={32} /><Skeleton height={32} /><Skeleton height={32} width="70%" /></Stack>;
  if (catalog.isError) return <ErrorState message="Could not load the list of permissions." onRetry={() => void catalog.refetch()} />;

  const toggle = (code: string, on: boolean) => onChange?.(on ? [...value, code] : value.filter((c) => c !== code));
  // Read-only shows only the groups the role draws on, consumer permission included.
  const groups = onChange ? groupCatalog(catalog.data)
    : groupCatalog(catalog.data, new Set()).filter((g) => g.items.some((p) => value.includes(p.code)));
  return (
    <Stack sx={{ gap: 2 }}>
      {groups.map(({ group, items }) => (
        <FormControl key={group} component="fieldset" variant="standard"
          sx={{ p: 2, borderRadius: 2, border: 1, borderColor: 'divider', bgcolor: 'grey.50' }}>
          <FormLabel component="legend" sx={{ px: 0.5, fontWeight: 600, fontSize: '0.8125rem', color: 'text.primary' }}>{group}</FormLabel>
          {onChange ? (
            <FormGroup sx={{ gap: 0.25 }}>
              {items.map((p) => (
                <FormControlLabel key={p.code} sx={{ alignItems: 'flex-start', mr: 0 }}
                  control={<Checkbox size="small" checked={value.includes(p.code)} onChange={(e) => toggle(p.code, e.target.checked)} sx={{ mt: 0.25 }} />}
                  label={<Hint p={p} />} />
              ))}
            </FormGroup>
          ) : (
            <ReadOnly items={items} value={value} />
          )}
        </FormControl>
      ))}
    </Stack>
  );
}
