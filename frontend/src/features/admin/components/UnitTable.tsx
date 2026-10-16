import ChevronRightRoundedIcon from '@mui/icons-material/ChevronRightRounded';
import {
  Box, Button, Chip, Link, Skeleton, Stack, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography,
} from '@mui/material';

import { UNIT_KIND_LABEL, type Unit } from '@/shared/api/types';
import { formatCount } from '@/shared/lib/format';

interface UnitTableProps {
  label: string;
  rows: Unit[] | undefined;
  /** EROs of the division above, to name the ERO a section points at. */
  eros: Unit[];
  onOpen: (unit: Unit) => void;
  onEdit?: ((unit: Unit) => void) | undefined;
}

function Name({ unit, onOpen }: { unit: Unit; onOpen: (unit: Unit) => void }) {
  const leaf = unit.kind === 'section' || unit.kind === 'ero';
  return (
    <Stack direction="row" sx={{ gap: 1, alignItems: 'center' }}>
      {leaf ? (
        <Typography variant="subtitle2" component="p">{unit.name}</Typography>
      ) : (
        <Link component="button" type="button" onClick={() => onOpen(unit)} underline="hover"
          sx={{ fontWeight: 600, fontSize: '0.875rem', display: 'inline-flex', alignItems: 'center', gap: 0.25, textAlign: 'left' }}>
          {unit.name}
          <ChevronRightRoundedIcon fontSize="small" aria-hidden />
        </Link>
      )}
      {!unit.active && <Chip size="small" variant="outlined" label="Inactive" />}
    </Stack>
  );
}

/** One level of the tree. Names open the level below; sections and EROs are the leaves. */
export function UnitTable({ label, rows, eros, onOpen, onEdit }: UnitTableProps) {
  const eroName = new Map(eros.map((e) => [e.id, e.name]));
  const showEro = rows?.some((u) => u.kind === 'section') ?? false;
  const columns = 4 + (showEro ? 1 : 0) + (onEdit ? 1 : 0);
  return (
    <TableContainer>
      <Table size="small" aria-label={label}>
        <TableHead>
          <TableRow>
            <TableCell>Name</TableCell>
            <TableCell>Code</TableCell>
            <TableCell>Other spellings</TableCell>
            {showEro && <TableCell>ERO</TableCell>}
            <TableCell align="right">Units under it</TableCell>
            {onEdit && <TableCell align="right" aria-label="Actions" />}
          </TableRow>
        </TableHead>
        <TableBody>
          {!rows && Array.from({ length: 4 }, (_, i) => <TableRow key={i}><TableCell colSpan={columns}><Skeleton /></TableCell></TableRow>)}
          {rows?.map((u) => (
            <TableRow key={u.id} hover sx={{ opacity: u.active ? 1 : 0.7 }}>
              <TableCell sx={{ minWidth: 200 }}>
                <Name unit={u} onOpen={onOpen} />
                <Typography variant="caption" sx={{ color: 'text.secondary' }}>{UNIT_KIND_LABEL[u.kind]}</Typography>
              </TableCell>
              <TableCell sx={{ fontFamily: 'monospace' }}>{u.code ?? ''}</TableCell>
              <TableCell sx={{ maxWidth: 280 }}>
                <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                  {u.aliases.map((a) => <Chip key={a} size="small" variant="outlined" label={a} />)}
                </Box>
              </TableCell>
              {showEro && <TableCell>{u.ero_id ? (eroName.get(u.ero_id) ?? 'Linked') : ''}</TableCell>}
              <TableCell align="right">{u.kind === 'section' || u.kind === 'ero' ? '' : formatCount(u.children_count)}</TableCell>
              {onEdit && (
                <TableCell align="right">
                  <Button size="small" onClick={() => onEdit(u)} aria-label={`Edit ${u.name}`}>Edit</Button>
                </TableCell>
              )}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
