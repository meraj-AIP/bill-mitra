import { useMediaQuery } from '@mui/material';

import { PHONE_AGENT } from '../model/codes';

/** Consumers on a phone are sent to WhatsApp: it is where Bill Mitra lives for them. A narrow desktop window is
 * not a phone, so both the touch screen and the browser's own name have to say so. */
export function usePhone(): boolean {
  const touch = useMediaQuery('(pointer: coarse)');
  return touch && PHONE_AGENT.test(navigator.userAgent);
}
