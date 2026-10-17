import { Alert, Box, Link as MuiLink, Paper, Stack, Typography } from '@mui/material';
import type { ReactNode } from 'react';

import { BrandPanel, CompactBrand, rise } from './BrandPanel';

interface AuthFrameProps {
  title: string;
  lead: string;
  children: ReactNode;
  footer?: ReactNode;
  /** A small control on the title row, such as the sample logins button. */
  titleAction?: ReactNode;
}

function BuiltBy() {
  return (
    <Stack direction="row" sx={{ gap: 1, alignItems: 'center', justifyContent: 'center', mt: 5 }}>
      <Typography variant="caption" sx={{ color: 'text.secondary' }}>Built by</Typography>
      <MuiLink href="https://aiplanet.com" target="_blank" rel="noopener noreferrer" sx={{ display: 'flex', borderRadius: 0.5 }}>
        <Box component="img" src="/aiplanet.png" width={1280} height={439} alt="AI Planet" sx={{ height: 18, width: 'auto' }} />
      </MuiLink>
    </Stack>
  );
}

/** The shared frame for sign in and register: brand panel on the left, the form on the right. */
export function AuthFrame({ title, lead, children, footer, titleAction }: AuthFrameProps) {
  return (
    <Box sx={{ minHeight: '100dvh', display: 'grid', bgcolor: 'background.default',
      gridTemplateColumns: { xs: '1fr', md: 'minmax(0, 5fr) minmax(0, 6fr)' } }}>
      <BrandPanel />
      <Stack component="main" sx={{ px: { xs: 2, sm: 4 }, py: { xs: 4, md: 6 }, alignItems: 'center', justifyContent: 'center' }}>
        <Box sx={{ width: '100%', maxWidth: 420 }}>
          <CompactBrand />
          <Paper variant="outlined" sx={{ p: { xs: 3, sm: 4 }, ...rise(120),
            boxShadow: (t) => `0 1px 2px ${t.palette.action.selected}, 0 24px 48px -32px ${t.palette.action.focus}` }}>
            <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between', gap: 1 }}>
              <Typography variant="h2" component="h2">{title}</Typography>
              {titleAction}
            </Stack>
            <Typography variant="body2" sx={{ color: 'text.secondary', mt: 0.75, mb: 3 }}>{lead}</Typography>
            {children}
          </Paper>
          {footer && <Box sx={{ mt: 2.5, ...rise(200) }}>{footer}</Box>}
          <BuiltBy />
        </Box>
      </Stack>
    </Box>
  );
}

export function FormError({ message, children }: { message: string | null; children?: ReactNode }) {
  if (!message) return null;
  return (
    <Alert severity="error" variant="outlined" sx={{ mb: 2, bgcolor: 'error.light' }}>
      {message} {children}
    </Alert>
  );
}
