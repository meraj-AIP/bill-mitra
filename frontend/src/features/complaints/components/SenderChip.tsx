import PhoneAndroidRoundedIcon from '@mui/icons-material/PhoneAndroidRounded';
import { Box, Chip, Tooltip, Typography } from '@mui/material';

import type { SenderCheck, SenderStatus } from '../api/types';

type Tone = 'success' | 'warning' | 'info' | 'default';

const STATUS: Record<SenderStatus | 'pending', { label: string; hint: string; tone: Tone }> = {
  verified: { label: 'Registered mobile', hint: 'Sent from the mobile the DISCOM holds for this connection.', tone: 'success' },
  other_connection: { label: 'Mobile of another connection', hint: 'The mobile is registered with the DISCOM, but not for the connection this complaint is about.', tone: 'warning' },
  registered: { label: 'Registered mobile, no connection named', hint: 'The mobile is registered with the DISCOM. The complaint does not say which connection yet.', tone: 'info' },
  not_registered: { label: 'Not a registered mobile', hint: 'The DISCOM holds no connection for this mobile.', tone: 'warning' },
  not_checked: { label: 'Mobile not checked', hint: 'The DISCOM lookup by mobile is not connected yet.', tone: 'default' },
  no_mobile: { label: 'No mobile to check', hint: 'Raised on the web from an account whose mobile the DISCOM has not confirmed.', tone: 'default' },
  pending: { label: 'Checking mobile', hint: 'The DISCOM lookup runs within a minute of the complaint.', tone: 'default' },
};

function Details({ check, hint, staffRaised }: { check: SenderCheck; hint: string; staffRaised: boolean }) {
  return (
    <Box sx={{ p: 0.5, maxWidth: 320 }}>
      <Typography variant="body2">{staffRaised ? `The caller's number, as typed by staff. ${hint}` : hint}</Typography>
      {check.connections.length > 0 && (
        <>
          <Typography variant="caption" component="p" sx={{ mt: 1, fontWeight: 600 }}>Connections on this mobile</Typography>
          {check.connections.map((c) => (
            <Typography key={`${c.discom}${c.service_masked}`} variant="caption" component="p" sx={{ fontFamily: 'monospace' }}>
              {`${c.service_masked}  ${[c.section, c.discom].filter(Boolean).join(', ')}${c.this_one ? '  (this complaint)' : ''}`}
            </Typography>
          ))}
        </>
      )}
      {check.source === 'dev' && (
        <Typography variant="caption" component="p" sx={{ mt: 1 }}>Development data: this consumer&apos;s own bills stand in for the DISCOM.</Typography>
      )}
    </Box>
  );
}

/** Whether the consumer wrote from the DISCOM's registered mobile; hover for the connections on that number. */
export function SenderChip({ check, staffRaised = false }: { check: SenderCheck | null | undefined; staffRaised?: boolean }) {
  if (!check) return null;
  const s = STATUS[check.status ?? 'pending'];
  const count = check.connections.length;
  const label = count > 1 ? `${s.label} · ${count} connections` : s.label;
  return (
    <Tooltip title={<Details check={check} hint={s.hint} staffRaised={staffRaised} />} arrow>
      <Chip size="small" variant="outlined" color={s.tone} icon={<PhoneAndroidRoundedIcon />} label={label} tabIndex={0} />
    </Tooltip>
  );
}
