import { Button, Container, CssBaseline, LinearProgress, ThemeProvider } from '@mui/material';
import { MutationCache, QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { lazy, Suspense, type ReactNode } from 'react';
import { createBrowserRouter, Link, Navigate, RouterProvider, type RouteObject } from 'react-router-dom';

import { AlertsPage } from '@/features/alerts';
import { landingFor, LoginPage, PrivacyPage, PublicOnly, RegisterPage, RequirePermission, useAuth, type Permission } from '@/features/auth';
import { BillPage, DashboardPage } from '@/features/dashboard';
import { NetworkError, onUnauthorized } from '@/shared/api/http';
import { queryKeys } from '@/shared/api/queryKeys';
import { retryDelay, retryQuery, retryUnsent } from '@/shared/api/retry';
import { EmptyState } from '@/shared/components/States';
import { theme } from '@/theme';

import { AppShell } from './AppShell';
import { ASSISTANT, COMPLAINTS, CONSOLE, CONSUMER, HEALTH, navFor, OPERATIONS, REVIEW, STAFF } from './nav';

const AssistantPage = lazy(() => import('@/features/assistant').then((m) => ({ default: m.AssistantPage })));
const ConsolePage = lazy(() => import('@/features/console').then((m) => ({ default: m.ConsolePage })));
const ComplaintsInboxPage = lazy(() => import('@/features/console').then((m) => ({ default: m.ComplaintsInboxPage })));
const ComplaintDetailPage = lazy(() => import('@/features/console').then((m) => ({ default: m.ComplaintDetailPage })));
const AccountsPage = lazy(() => import('@/features/admin').then((m) => ({ default: m.AccountsPage })));
const AuditPage = lazy(() => import('@/features/admin').then((m) => ({ default: m.AuditPage })));
const HealthPage = lazy(() => import('@/features/admin').then((m) => ({ default: m.HealthPage })));
const OperationsPage = lazy(() => import('@/features/admin').then((m) => ({ default: m.OperationsPage })));
const RolesPage = lazy(() => import('@/features/admin').then((m) => ({ default: m.RolesPage })));
const UnitsPage = lazy(() => import('@/features/admin').then((m) => ({ default: m.UnitsPage })));
const PolicyPage = lazy(() => import('@/features/admin').then((m) => ({ default: m.PolicyPage })));
const ReviewQueuePage = lazy(() => import('@/features/review').then((m) => ({ default: m.ReviewQueuePage })));
const CasePage = lazy(() => import('@/features/review').then((m) => ({ default: m.CasePage })));
const MyComplaintsPage = lazy(() => import('@/features/my-complaints').then((m) => ({ default: m.MyComplaintsPage })));
const MyComplaintPage = lazy(() => import('@/features/my-complaints').then((m) => ({ default: m.MyComplaintPage })));
const RaiseComplaintPage = lazy(() => import('@/features/my-complaints').then((m) => ({ default: m.RaiseComplaintPage })));
const HowItWorksPage = lazy(() => import('@/features/explorer').then((m) => ({ default: m.HowItWorksPage })));

const queryClient: QueryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: retryQuery, retryDelay, refetchOnWindowFocus: true, refetchOnReconnect: true },
    // Mutations retry only a request that never left the browser. Routes safe to repeat opt in with IDEMPOTENT.
    mutations: { retry: retryUnsent, retryDelay },
  },
  mutationCache: new MutationCache({
    // A lost answer means the action may have happened, so reload what is on screen before anyone sends it again.
    onError: (error) => {
      if (error instanceof NetworkError && error.sent) void queryClient.invalidateQueries();
    },
  }),
});

// Any 401 outside /api/auth means the session ended. Clearing the cached account lets RequireRole
// send the person to /login with the page they were on as next.
onUnauthorized(() => queryClient.setQueryData(queryKeys.me, null));

function Lazy({ children }: { children: ReactNode }) {
  return <Suspense fallback={<LinearProgress aria-label="Loading page" sx={{ borderRadius: 0 }} />}>{children}</Suspense>;
}

function NotFound() {
  const { account } = useAuth();
  return (
    <Container maxWidth="lg" sx={{ py: { xs: 3, md: 5 } }}>
      <EmptyState title="Page not found" hint="The link may be old or mistyped."
        action={<Button variant="contained" component={Link} to={landingFor(account)}>Go to the start page</Button>} />
    </Container>
  );
}

const lazyRoute = (path: string, page: ReactNode): RouteObject => ({ path, element: <Lazy>{page}</Lazy> });
const gated = (any: readonly Permission[], children: RouteObject[]): RouteObject => ({ element: <RequirePermission any={any} />, children });

/** /admin opens the first admin page this account may use. */
function AdminHome() {
  const { account } = useAuth();
  const first = account ? navFor(account).manage[0]?.to : undefined;
  return <Navigate to={first ?? landingFor(account)} replace />;
}

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
    element: <RequirePermission />,
    children: [{
      element: <AppShell />,
      children: [
        {
          element: <RequirePermission any={CONSUMER} />,
          children: [
            { index: true, element: <DashboardPage /> },
            { path: 'bills/:id', element: <BillPage /> },
            lazyRoute('complaints', <MyComplaintsPage />),
            lazyRoute('complaints/new', <RaiseComplaintPage />),
            lazyRoute('complaints/:ticket', <MyComplaintPage />),
          ],
        },
        gated(ASSISTANT, [lazyRoute('assistant', <AssistantPage />)]),
        gated(CONSOLE, [lazyRoute('console', <ConsolePage />)]),
        gated(COMPLAINTS, [
          lazyRoute('console/complaints', <ComplaintsInboxPage />),
          lazyRoute('console/complaints/:ticket', <ComplaintDetailPage />),
        ]),
        gated(REVIEW, [lazyRoute('review', <ReviewQueuePage />), lazyRoute('review/:ticket', <CasePage />)]),
        gated(STAFF, [{ path: 'alerts', element: <AlertsPage /> }]),
        { path: 'admin', element: <AdminHome /> },
        gated(['accounts.manage'], [lazyRoute('admin/accounts', <AccountsPage />)]),
        gated(['roles.manage'], [lazyRoute('admin/roles', <RolesPage />)]),
        gated(['units.manage'], [lazyRoute('admin/units', <UnitsPage />)]),
        gated(['policy.manage'], [lazyRoute('admin/policy', <PolicyPage />)]),
        gated(['audit.view'], [lazyRoute('admin/audit', <AuditPage />)]),
        gated(HEALTH, [lazyRoute('admin/health', <HealthPage />)]),
        gated(OPERATIONS, [lazyRoute('admin/operations', <OperationsPage />)]),
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
