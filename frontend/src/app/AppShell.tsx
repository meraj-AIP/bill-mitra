import HelpOutlineRoundedIcon from '@mui/icons-material/HelpOutlineRounded';
import { AppBar, Box, Button, Container, Link as MuiLink, Stack, Tab, Tabs, Typography } from '@mui/material';
import { Link, Outlet, useLocation } from 'react-router-dom';

import { AccountMenu, isConsumer, landingFor, useAuth } from '@/features/auth';
import { ModeStatus } from '@/shared/components/ModeStatus';

import { ManageMenu } from './ManageMenu';
import { currentTab, navFor, type Nav } from './nav';

function Brand({ home }: { home: string }) {
  return (
    <Stack direction="row" component={Link} to={home} aria-label="Bill Mitra home"
      sx={{ gap: { xs: 1.5, sm: 2.5 }, alignItems: 'center', minWidth: 0, color: 'inherit', textDecoration: 'none', borderRadius: 1 }}>
      <Box component="img" src="/partners.png" width={720} height={193} decoding="async"
        alt="Government of Telangana, Telangana Rising and AIKAM"
        sx={{ height: { xs: 40, sm: 48, md: 56 }, width: 'auto', flexShrink: 0, display: 'block' }} />
      <Box aria-hidden sx={{ width: '1px', height: { xs: 28, md: 36 }, bgcolor: 'divider', flexShrink: 0 }} />
      <Typography component="p" noWrap
        sx={{ fontFamily: (t) => t.typography.h1.fontFamily, fontWeight: 600, fontSize: { xs: '1.125rem', sm: '1.375rem' }, lineHeight: 1 }}>
        Bill Mitra
      </Typography>
    </Stack>
  );
}

function Footer({ hiddenOnPhone }: { hiddenOnPhone: boolean }) {
  return (
    <Box component="footer" sx={{ borderTop: 1, borderColor: 'divider', bgcolor: 'background.paper', display: { xs: hiddenOnPhone ? 'none' : 'block', md: 'block' },
      '@media print': { display: 'none' } }}>
      <Container maxWidth="lg">
        <Stack direction="row" sx={{ py: 2, gap: 2, alignItems: 'center', justifyContent: 'space-between' }}>
          <Stack direction="row" sx={{ gap: 1, alignItems: 'center' }}>
            <Typography variant="caption" sx={{ color: 'text.secondary' }}>Built by</Typography>
            <MuiLink href="https://aiplanet.com" target="_blank" rel="noopener noreferrer" sx={{ display: 'flex', borderRadius: 0.5 }}>
              <Box component="img" src="/aiplanet.png" width={1280} height={439} alt="AI Planet" sx={{ height: 20, width: 'auto' }} />
            </MuiLink>
          </Stack>
          <MuiLink component={Link} to="/privacy" variant="caption" sx={{ color: 'text.secondary' }}>Privacy notice</MuiLink>
        </Stack>
      </Container>
    </Box>
  );
}

function Sections({ nav, pathname }: { nav: Nav; pathname: string }) {
  const all = [...nav.main, ...nav.manage, nav.help];
  const active = currentTab(all, pathname);
  const inMain = nav.main.some((n) => n.to === active);
  const inManage = nav.manage.some((n) => n.to === active);
  const onHelp = active === nav.help.to;
  return (
    <Stack component="nav" aria-label="Sections" direction="row" sx={{ alignItems: 'center', mx: { xs: -1, sm: -2 } }}>
      <Tabs value={inMain ? active : false} variant="scrollable" scrollButtons={false}
        sx={{ minHeight: 44, '& .MuiTab-root': { minHeight: 44, px: { xs: 1.25, sm: 2 }, whiteSpace: 'nowrap' } }}>
        {nav.main.map((n) => <Tab key={n.to} value={n.to} label={n.label} component={Link} to={n.to} />)}
      </Tabs>
      {nav.manage.length > 0 && <ManageMenu items={nav.manage} active={inManage ? active : false} />}
      <Button component={Link} to={nav.help.to} startIcon={<HelpOutlineRoundedIcon />} aria-current={onHelp ? 'page' : undefined}
        sx={{ ml: 'auto', minHeight: 44, borderRadius: 0, fontWeight: 500, whiteSpace: 'nowrap', px: { xs: 1, sm: 2 },
          color: onHelp ? 'primary.main' : 'text.secondary', '&:hover': { color: 'text.primary', bgcolor: 'transparent' },
          '& .label': { display: { xs: 'none', sm: 'inline' } } }}>
        <span className="label">{nav.help.label}</span>
      </Button>
    </Stack>
  );
}

export function AppShell() {
  const { pathname } = useLocation();
  const { account } = useAuth();
  // RequirePermission wraps the shell, so an account is always present here.
  const nav = account ? navFor(account) : null;
  const home = landingFor(account);
  const staff = Boolean(account) && !isConsumer(account);
  return (
    <Box sx={{ minHeight: '100dvh', display: 'flex', flexDirection: 'column', bgcolor: 'background.default', '@media print': { bgcolor: 'background.paper' } }}>
      <MuiLink href="#main" sx={{ position: 'absolute', left: 8, top: -48, zIndex: 'tooltip', bgcolor: 'background.paper', px: 2, py: 1,
        borderRadius: 1, '&:focus': { top: 8 }, '@media print': { display: 'none' } }}>
        Skip to content
      </MuiLink>
      <AppBar position="sticky" color="inherit" elevation={0}
        sx={{ borderBottom: 1, borderColor: 'divider', bgcolor: 'background.paper', '@media print': { display: 'none' } }}>
        <Box sx={{ height: 3, bgcolor: 'primary.main' }} />
        <Container maxWidth="lg">
          <Stack direction="row" sx={{ pt: { xs: 1.5, md: 2 }, pb: 1, gap: 2, alignItems: 'center', justifyContent: 'space-between' }}>
            <Brand home={home} />
            <Stack direction="row" sx={{ gap: 2, alignItems: 'center' }}>
              {staff && (
                <Box sx={{ display: { xs: 'none', md: 'block' } }}>
                  <ModeStatus />
                </Box>
              )}
              <AccountMenu />
            </Stack>
          </Stack>
          {nav && <Sections nav={nav} pathname={pathname} />}
        </Container>
      </AppBar>
      <Box component="main" id="main" tabIndex={-1} sx={{ flex: 1, outline: 'none' }}>
        <Outlet />
      </Box>
      <Footer hiddenOnPhone={pathname.startsWith('/assistant')} />
    </Box>
  );
}
