import RuleFolderOutlinedIcon from '@mui/icons-material/RuleFolderOutlined';
import {
  Alert, Box, Button, CircularProgress, Paper, Skeleton, Stack, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography,
} from '@mui/material';
import { useState } from 'react';

import type { UnitRef } from '@/shared/api/types';
import { EmptyState, ErrorState } from '@/shared/components/States';
import { UnitPicker } from '@/shared/components/UnitPicker';
import { dateTime, formatCount } from '@/shared/lib/format';

import { useMapUnmapped, useUnmapped, type Unmapped } from '../api/unitsApi';

function MapRow({ item }: { item: Unmapped }) {
  const map = useMapUnmapped();
  const [section, setSection] = useState<UnitRef | null>(null);
  const mapTo = (sectionId: string) => map.mutate({ name: item.name, discom: item.discom, section_id: sectionId });
  const suggestions = item.suggestions ?? [];
  return (
    <TableRow>
      <TableCell sx={{ minWidth: 180 }}>
        <Typography variant="subtitle2" component="p" sx={{ fontFamily: 'monospace' }}>{item.name}</Typography>
        <Typography variant="caption" sx={{ color: 'text.secondary' }}>{item.discom}</Typography>
      </TableCell>
      <TableCell align="right">{formatCount(item.count)}</TableCell>
      <TableCell sx={{ whiteSpace: 'nowrap' }}>{dateTime(item.last_seen)}</TableCell>
      <TableCell sx={{ minWidth: 300 }}>
        {suggestions.length > 0 && (
          <Stack direction="row" sx={{ gap: 1, flexWrap: 'wrap', mb: 1 }}>
            {suggestions.map((s) => (
              <Button key={s.section_id} size="small" variant="outlined" disabled={map.isPending} onClick={() => mapTo(s.section_id)}
                title={`${Math.round(s.score * 100)}% name match`}>
                Map to {s.name}
              </Button>
            ))}
          </Stack>
        )}
        <Stack direction="row" sx={{ gap: 1, alignItems: 'flex-start' }}>
          <Box sx={{ flex: 1 }}>
            <UnitPicker label={`Section in ${item.discom}`} kind="section" size="small" value={section} onChange={setSection} />
          </Box>
          <Button variant="contained" size="small" sx={{ mt: 0.5 }} disabled={!section || map.isPending}
            onClick={() => section && mapTo(section.unit_id)}
            startIcon={map.isPending ? <CircularProgress size={14} color="inherit" aria-hidden /> : null}>
            Map
          </Button>
        </Stack>
        {map.error && <Alert severity="error" sx={{ mt: 1 }}>{map.error.message}</Alert>}
      </TableCell>
    </TableRow>
  );
}

/** Section names printed on bills that match no section. Mapping one adds it as an alias and re-routes its open cases. */
export function UnmappedQueue() {
  const unmapped = useUnmapped();
  const rows = unmapped.data;
  return (
    <Paper variant="outlined" sx={{ overflow: 'hidden' }}>
      <Box sx={{ px: 2.5, pt: 2, pb: 1.5 }}>
        <Typography variant="h3" component="h2">Unmapped sections</Typography>
        <Typography variant="body2" sx={{ color: 'text.secondary', mt: 0.25, maxWidth: '70ch' }}>
          Bills printed these names after Sec: and no section matched. Until a name is mapped, its cases wait at the division.
        </Typography>
      </Box>
      {unmapped.isError && <Box sx={{ p: 2 }}><ErrorState message="Could not load unmapped sections." onRetry={() => void unmapped.refetch()} /></Box>}
      {rows?.length === 0 && (
        <EmptyState icon={<RuleFolderOutlinedIcon />} title="Every printed section name is mapped" hint="New names appear here as bills come in." />
      )}
      {!unmapped.isError && rows?.length !== 0 && (
        <TableContainer>
          <Table size="small" aria-label="Unmapped sections">
            <TableHead>
              <TableRow>
                <TableCell>Printed name</TableCell>
                <TableCell align="right">Bills</TableCell>
                <TableCell>Last seen</TableCell>
                <TableCell>Map to</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {!rows && Array.from({ length: 3 }, (_, i) => <TableRow key={i}><TableCell colSpan={4}><Skeleton /></TableCell></TableRow>)}
              {rows?.map((u) => <MapRow key={`${u.discom}-${u.name}`} item={u} />)}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Paper>
  );
}
