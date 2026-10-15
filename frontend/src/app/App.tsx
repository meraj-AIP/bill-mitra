import { Button, Container, CssBaseline, LinearProgress, ThemeProvider } from '@mui/material';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { lazy, Suspense, type ReactNode } from 'react';
import { createBrowserRouter, Link, Navigate, RouterProvider } from 'react-router-dom';

import { landingFor, LoginPage, PrivacyPage, PublicOnly, RegisterPage, RequireRole, useAuth } from '@/features/auth';
import { BillPage, DashboardPage } from '@/features/dashboard';
import { ApiError, onUnauthorized } from '@/shared/api/http';
import { queryKeys } from '@/shared/api/queryKeys';
import { EmptyState } from '@/shared/components/States';
import { theme } from '@/theme';

import { AppShell } from './AppShell';
import { ADMIN, ASSISTANT, CONSUMER, EVERYONE, STAFF } from './nav';

const AssistantPage = lazy(() => import('@/features/assistant').then((m) => ({ default: m.AssistantPage })));
const ConsolePage = lazy(() => import('@/features/console').then((m) => ({ default: m.ConsolePage })));
const ComplaintsInboxPage = lazy(() => import('@/features/console').then((m) => ({ default: m.ComplaintsInboxPage })));
const ComplaintDetailPage = lazy(() => import('@/features/console').then((m) => ({ default: m.ComplaintDetailPage })));
const AccountsPage = lazy(() => import('@/features/admin').then((m) => ({ default: m.AccountsPage })));
const AuditPage = lazy(() => import('@/features/admin').then((m) => ({ default: m.AuditPage })));
const HealthPage = lazy(() => import('@/features/admin').then((m) => ({ default: m.HealthPage })));
const HowItWorksPage = lazy(() => import('@/features/explorer').then((m) => ({ default: m.HowItWorksPage })));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // A 4xx will not change on retry; only server and network failures get a second try.
      retry: (count, error) => count < 1 && !(error instanceof ApiError && error.status < 500),
      refetchOnWindowFocus: false,
    },
  },
});

// Any 401 outside /api/auth means the session ended. Clearing the cached account lets RequireRole
// send the person to /login with the page they were on as next.
onUnauthorized(() => queryClient.setQueryData(queryKeys.me, null));

function Lazy({ children }: { children: ReactNode }) {
  return <Suspense fallback={<LinearProgress aria-label="Loading page" sx={{ borderRadius: 0 }} />}>{children}</Suspense>;
}

function NotFound() {
  const { role } = useAuth();
  return (
    <Container maxWidth="lg" sx={{ py: { xs: 3, md: 5 } }}>
      <EmptyState title="Page not found" hint="The link may be old or mistyped."
        action={<Button variant="contained" component={Link} to={role ? landingFor(role) : '/login'}>Go to the start page</Button>} />
    </Container>
  );
}

const lazyRoute = (path: string, page: ReactNode) => ({ path, element: <Lazy>{page}</Lazy> });

const router = createBrowserRouter([
  { path: 'privacy', element: <PrivacyPage /> },
  {
    element: <PublicOnly />,
    children: [
      { path: 'login', element: <LoginPage /> },
      { path: 'register', element: <RegisterPage /> },
    ],
  },
  {
    element: <RequireRole roles={EVERYONE} />,
    children: [{
      element: <AppShell />,
      children: [
        {
          element: <RequireRole roles={CONSUMER} />,
          children: [
            { index: true, element: <DashboardPage /> },
            { path: 'bills/:id', element: <BillPage /> },
          ],
        },
        {
          element: <RequireRole roles={ASSISTANT} />,
          children: [lazyRoute('assistant', <AssistantPage />)],
        },
        {
          element: <RequireRole roles={STAFF} />,
          children: [
            lazyRoute('console', <ConsolePage />),
            lazyRoute('console/complaints', <ComplaintsInboxPage />),
            lazyRoute('console/complaints/:ticket', <ComplaintDetailPage />),
          ],
        },
        {
          element: <RequireRole roles={ADMIN} />,
          children: [
            { path: 'admin', element: <Navigate to="/admin/accounts" replace /> },
            lazyRoute('admin/accounts', <AccountsPage />),
            lazyRoute('admin/audit', <AuditPage />),
            lazyRoute('admin/health', <HealthPage />),
          ],
        },
        lazyRoute('how-it-works', <HowItWorksPage />),
        { path: '*', element: <NotFound /> },
      ],
    }],
  },
]);

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <RouterProvider router={router} />
      </ThemeProvider>
    </QueryClientProvider>
  );
}
