import { Box, Stack, Typography } from '@mui/material';
import type { ReactNode } from 'react';

interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  lead?: ReactNode;
  actions?: ReactNode;
}

export function PageHeader({ eyebrow, title, lead, actions }: PageHeaderProps) {
  return (
    <Stack direction={{ xs: 'column', md: 'row' }} component="header" sx={{ gap: 2, alignItems: { md: 'flex-end' } }}>
      <Box sx={{ flex: 1, minWidth: 0 }}>
        {eyebrow && (
          <Typography variant="overline" component="p" sx={{ color: 'primary.light', mb: 0.75 }}>
            {eyebrow}
          </Typography>
        )}
        <Typography variant="h1">{title}</Typography>
        {lead && (
          <Typography variant="body1" sx={{ color: 'text.secondary', maxWidth: '65ch', mt: 1 }}>
            {lead}
          </Typography>
        )}
      </Box>
      {actions}
    </Stack>
  );
}
