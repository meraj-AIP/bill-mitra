import { Alert, Divider, Link as MuiLink, Stack, Tab, Tabs, Typography } from '@mui/material';
import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import { AuthFrame } from '../components/AuthFrame';
import { ConsumerSignIn } from '../components/ConsumerSignIn';
import { DemoLogins } from '../components/DemoLogins';
import { StaffSignIn } from '../components/StaffSignIn';
import { WhatsAppOnly } from '../components/WhatsAppOnly';
import { usePhone } from '../hooks/usePhone';
import { normaliseLogin, MOBILE_PATTERN } from '../model/roles';

type Who = 'consumer' | 'staff';

export function LoginPage() {
  const [params, setParams] = useSearchParams();
  const deleted = params.get('deleted') === '1';
  const who: Who = params.get('as') === 'staff' ? 'staff' : 'consumer';
  const phone = usePhone();
  const [mobile, setMobile] = useState('');
  const [staffLogin, setStaffLogin] = useState('');
  const show = (next: Who) => setParams((p) => { p.set('as', next); return p; }, { replace: true });
  // A sample mobile is a consumer, anything else is staff.
  const pick = (sample: string) => {
    const login = normaliseLogin(sample);
    if (MOBILE_PATTERN.test(login)) { setMobile(login); show('consumer'); } else { setStaffLogin(login); show('staff'); }
  };

  return (
    <AuthFrame title="Sign in" lead="Consumers sign in with their mobile number and a one-time code. Staff use their work email."
      titleAction={<DemoLogins onPick={pick} />}
      footer={
        <Stack sx={{ gap: 1.5, alignItems: 'center', textAlign: 'center' }}>
          <Typography variant="caption" component="p" sx={{ color: 'text.secondary', maxWidth: '44ch' }}>
            DISCOM and department staff: your account is created by the Bill Mitra administrator. Ask them if you cannot sign in.
          </Typography>
          <MuiLink component={Link} to="/privacy" variant="caption" sx={{ fontWeight: 600 }}>Privacy notice</MuiLink>
        </Stack>
      }>
      {deleted && (
        <Alert severity="success" variant="outlined" sx={{ bgcolor: 'success.light', mb: 2 }}>
          Your account and its data have been deleted.
        </Alert>
      )}
      <Tabs value={who} onChange={(_e, v: Who) => show(v)} variant="fullWidth" sx={{ mb: 3, borderBottom: 1, borderColor: 'divider' }}>
        <Tab value="consumer" label="Consumer" />
        <Tab value="staff" label="Staff" />
      </Tabs>
      {who === 'staff' && <StaffSignIn key={staffLogin} login={staffLogin} />}
      {who === 'consumer' && (phone ? <WhatsAppOnly /> : <ConsumerSignIn mobile={mobile} onMobile={setMobile} />)}
      {who === 'consumer' && !phone && (
        <>
          <Divider sx={{ my: 3 }} />
          <Typography variant="body2" sx={{ textAlign: 'center' }}>
            New here?{' '}
            <MuiLink component={Link} to="/register" sx={{ fontWeight: 600 }}>Create an account</MuiLink>
          </Typography>
        </>
      )}
    </AuthFrame>
  );
}
