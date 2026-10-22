import { Button, Container, LinearProgress, Stack } from '@mui/material';
import { useEffect, useState } from 'react';
import { isRouteErrorResponse, Link, useRouteError } from 'react-router-dom';

import { EmptyState } from '@/shared/components/States';
import { isChunkError, reloadedRecently, reloadOnce } from '@/shared/lib/reload';

/** Shown instead of React Router's default error screen. A page file missing after a deploy reloads once. */
export function RouteError() {
  const error = useRouteError();
  // Decided once, so the reload below cannot flip it and flash the error page while the new version loads.
  const [reloading] = useState(() => isChunkError(error) && !reloadedRecently());
  useEffect(() => {
    if (reloading) reloadOnce();
  }, [reloading]);
  if (reloading) return <LinearProgress aria-label="Loading the new version" sx={{ borderRadius: 0 }} />;
  const notFound = isRouteErrorResponse(error) && error.status === 404;
  return (
    <Container maxWidth="lg" sx={{ py: { xs: 3, md: 5 } }}>
      <EmptyState
        title={notFound ? 'Page not found' : 'This page could not open'}
        hint={notFound ? 'The link may be old or mistyped.' : 'Reload the page to try again.'}
        action={
          <Stack direction="row" sx={{ gap: 1, justifyContent: 'center' }}>
            <Button variant="contained" onClick={() => window.location.reload()}>Reload</Button>
            <Button variant="outlined" component={Link} to="/">Go to the start page</Button>
          </Stack>
        }
      />
    </Container>
  );
}
