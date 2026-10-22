import { useState } from 'react';

import { useCodeChannels, useStartCode, type CodeChannel, type CodeSent } from '../api/authApi';

type StartBody = Parameters<ReturnType<typeof useStartCode>['mutate']>[0];

/** Asking for a code, and asking again. The sent code moves the form to its second step; round keys that step. */
export function useCodeFlow() {
  const channels = useCodeChannels().data?.channels ?? [];
  const start = useStartCode();
  const [picked, setPicked] = useState<CodeChannel | null>(null);
  const [sent, setSent] = useState<CodeSent | null>(null);
  const [round, setRound] = useState(0);
  const [last, setLast] = useState<StartBody | null>(null);
  const channel = picked && channels.includes(picked) ? picked : (channels[0] ?? 'sms');
  const sentNow = (found: CodeSent) => { setSent(found); setRound((r) => r + 1); };
  const send = (body: Omit<StartBody, 'channel'>) => {
    const full = { ...body, channel };
    setLast(full);
    start.mutate(full, { onSuccess: sentNow });
  };
  const resend = () => { if (last) start.mutate(last, { onSuccess: sentNow }); };
  const back = () => { setSent(null); start.reset(); };
  return { channels, channel, pick: setPicked, start, sent, round, send, resend, back };
}
