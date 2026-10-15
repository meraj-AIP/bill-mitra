import { Box, Paper, Stack, Typography } from '@mui/material';
import type { ReactNode } from 'react';

interface ReportSectionProps {
  title: string;
  caption?: ReactNode;
  aside?: ReactNode;
  children: ReactNode;
  flush?: boolean;
}

export function ReportSection({ title, caption, aside, children, flush = false }: ReportSectionProps) {
  return (
    <Paper component="section" variant="outlined" sx={{ overflow: 'hidden' }}>
      <Stack direction="row" sx={{ px: { xs: 2, sm: 2.5 }, pt: 2, pb: flush ? 1.5 : 0, gap: 1.5, alignItems: 'flex-start' }}>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography variant="h3" component="h2">{title}</Typography>
          {caption && (
            <Typography variant="body2" sx={{ color: 'text.secondary', mt: 0.25 }}>
              {caption}
            </Typography>
          )}
        </Box>
        {aside}
      </Stack>
      <Box sx={flush ? undefined : { px: { xs: 2, sm: 2.5 }, pt: 1.5, pb: 2.5 }}>{children}</Box>
    </Paper>
  );
}
