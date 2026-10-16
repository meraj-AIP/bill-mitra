import { Box, Button, Link as MuiLink, Skeleton, Stack, Typography } from '@mui/material';
import { Link } from 'react-router-dom';

import { ErrorState } from '@/shared/components/States';

import { usePrivacy } from '../api/authApi';
import { useAuth } from '../hooks/useAuth';
import { AuthFrame } from '../components/AuthFrame';
import { landingFor } from '../model/permissions';

/** Public on purpose: people read it before they register. */
export function PrivacyPage() {
  const notice = usePrivacy();
  const { account } = useAuth();
  const data = notice.data;
  const back = account ? { to: landingFor(account), label: 'Back to Bill Mitra' } : { to: '/register', label: 'Create an account' };

  return (
    <AuthFrame title="Privacy notice" lead="What Bill Mitra keeps about you, why, and for how long."
      footer={<Box sx={{ textAlign: 'center' }}><Button component={Link} to={back.to}>{back.label}</Button></Box>}>
      {notice.isPending && <Stack sx={{ gap: 1 }}><Skeleton /><Skeleton /><Skeleton width="60%" /></Stack>}
      {notice.isError && <ErrorState message="Could not load the privacy notice." onRetry={() => void notice.refetch()} />}
      {data && (
        <Stack sx={{ gap: 2.5 }}>
          <Box>
            <Typography variant="subtitle1" component="h3">We use your information to</Typography>
            <Box component="ul" sx={{ pl: 2.5, my: 1, '& li': { mb: 0.75 } }}>
              {data.purposes.map((p) => <Typography key={p} component="li" variant="body2">{p}</Typography>)}
            </Box>
          </Box>
          <Box>
            <Typography variant="subtitle1" component="h3">How long we keep it</Typography>
            <Typography variant="body2" sx={{ mt: 0.5 }}>
              Bills, chats and photos are removed after {data.retention_days} days, unless a complaint you raised still needs
              them. You can delete your account and its data at any time from the account menu.
            </Typography>
          </Box>
          {data.contact && (
            <Box>
              <Typography variant="subtitle1" component="h3">Questions</Typography>
              <Typography variant="body2" sx={{ mt: 0.5, overflowWrap: 'anywhere' }}>
                Contact{' '}
                {data.contact.includes('@') ? <MuiLink href={`mailto:${data.contact}`}>{data.contact}</MuiLink> : data.contact}
              </Typography>
            </Box>
          )}
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>Notice version {data.version}</Typography>
        </Stack>
      )}
    </AuthFrame>
  );
}
