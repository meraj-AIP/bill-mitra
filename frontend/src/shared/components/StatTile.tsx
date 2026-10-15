import { Paper, Skeleton, Typography } from '@mui/material';

interface StatTileProps {
  label: string;
  value: string | undefined;
  note?: string | undefined;
  emphasis?: 'default' | 'alert' | undefined;
}

export function StatTile({ label, value, note, emphasis = 'default' }: StatTileProps) {
  return (
    <Paper variant="outlined" sx={{ p: 2, height: '100%' }}>
      <Typography variant="body2" sx={{ color: 'text.secondary', fontWeight: 500 }}>
        {label}
      </Typography>
      {value === undefined ? (
        <Skeleton width="60%" height={44} />
      ) : (
        <Typography
          component="p"
          sx={{ mt: 0.5, fontSize: '1.75rem', fontWeight: 600, lineHeight: 1.25, letterSpacing: '-0.01em', fontVariantNumeric: 'tabular-nums',
            color: emphasis === 'alert' ? 'warning.main' : 'text.primary' }}
        >
          {value}
        </Typography>
      )}
      {note && (
        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
          {note}
        </Typography>
      )}
    </Paper>
  );
}
