import { Box, Container, LinearProgress } from '@mui/material';
import { Navigate, Outlet, useLocation, useSearchParams } from 'react-router-dom';

import { ErrorState } from '@/shared/components/States';

import type { Role } from '../api/authApi';
import { useAuth } from '../hooks/useAuth';
import { landingFor, safeNext } from '../model/roles';

function Checking() {
  return (
    <Box sx={{ minHeight: '100dvh' }}>
      <LinearProgress aria-label="Checking your sign in" sx={{ borderRadius: 0 }} />
    </Box>
  );
}

function Unreachable({ onRetry }: { onRetry: () => void }) {
  return (
    <Container maxWidth="sm" sx={{ py: 8 }}>
      <ErrorState message="Could not reach Bill Mitra. Check your connection and try again." onRetry={onRetry} />
    </Container>
  );
}

/**
 * Lets the page through only for the given roles. Signed-out people go to the login page with the path
 * they wanted; a signed-in person with the wrong role goes to their own landing page.
 */
export function RequireRole({ roles }: { roles: readonly Role[] }) {
  const { account, loading, error, retry } = useAuth();
  const location = useLocation();
  if (loading) return <Checking />;
  if (error) return <Unreachable onRetry={retry} />;
  if (!account) {
    const next = `${location.pathname}${location.search}`;
    return <Navigate to={next === '/' ? '/login' : `/login?next=${encodeURIComponent(next)}`} replace />;
  }
  if (!roles.includes(account.role)) return <Navigate to={landingFor(account.role)} replace />;
  return <Outlet />;
}

/** Login and register are for signed-out people; anyone signed in moves on to where they were going. */
export function PublicOnly() {
  const { account, loading, error, retry } = useAuth();
  const [params] = useSearchParams();
  if (loading) return <Checking />;
  if (error) return <Unreachable onRetry={retry} />;
  if (account) return <Navigate to={safeNext(params.get('next')) ?? landingFor(account.role)} replace />;
  return <Outlet />;
}
