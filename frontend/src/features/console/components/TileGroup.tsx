import { Box, Grid, Typography } from '@mui/material';

import { StatTile } from '@/shared/components/StatTile';

export interface Tile {
  label: string;
  value: string | undefined;
  note?: string | undefined;
  emphasis?: 'default' | 'alert';
}

interface TileGroupProps {
  title: string;
  tiles: Tile[];
  /** Shown as one line instead of the tiles, so an empty window is not a wall of zeros. */
  empty?: string | null;
  /** Tiles per row on wide screens. */
  columns: 3 | 4 | 6;
}

export function TileGroup({ title, tiles, empty = null, columns }: TileGroupProps) {
  return (
    <Box component="section" aria-label={title}>
      <Typography variant="overline" component="h2" sx={{ color: 'text.secondary', display: 'block', mb: 1 }}>{title}</Typography>
      {empty ? (
        <Typography variant="body2" sx={{ color: 'text.secondary', py: 1.5, px: 2, border: 1, borderColor: 'divider', borderRadius: 1 }}>
          {empty}
        </Typography>
      ) : (
        <Grid container spacing={2}>
          {tiles.map((t) => (
            <Grid key={t.label} size={{ xs: 6, md: columns === 6 ? 4 : 12 / columns, lg: 12 / columns }}>
              <StatTile label={t.label} value={t.value} note={t.note} emphasis={t.emphasis} />
            </Grid>
          ))}
        </Grid>
      )}
    </Box>
  );
}
