import { Box, Container, Drawer, useMediaQuery } from '@mui/material';
import { useTheme } from '@mui/material/styles';
import { useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import { isConsumer, useAuth } from '@/features/auth';

import { AsideRail } from '../components/AsideRail';
import { AssistantHeader } from '../components/AssistantHeader';
import { ChatHeader } from '../components/ChatHeader';
import { ChatThread } from '../components/ChatThread';
import { Composer } from '../components/Composer';
import { Device } from '../components/Device';
import { NewChatDialog } from '../components/NewChatDialog';
import { TracePanel } from '../components/TracePanel';
import { useConversation } from '../hooks/useConversation';
import { BILL_ACCEPT } from '@/shared/lib/billFile';

import { useHistory } from '../hooks/useHistory';
import { FAILURE_TEXT } from '../model/failures';
import { UI } from '../model/strings';

export function AssistantPage() {
  const theme = useTheme();
  const wide = useMediaQuery(theme.breakpoints.up('lg'));
  // The step trace is for staff checking how a reply was built; consumers only need the chat.
  const { account } = useAuth();
  const staff = Boolean(account) && !isConsumer(account);
  const [traceOpen, setTraceOpen] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const fileInput = useRef<HTMLInputElement | null>(null);
  // Sent here from a bill that would not read: show how to type the units instead.
  const typeUnits = useSearchParams()[0].get('hint') === 'units';

  const history = useHistory();
  const chat = useConversation(history.clear);
  const { state, language } = chat;
  const items = useMemo(() => [...history.items, ...state.items], [history.items, state.items]);

  const attach = () => fileInput.current?.click();
  const sendText = (text: string) => void chat.sendText(text);
  const trace = <TracePanel turns={state.turns} hasHistory={history.items.length > 0} />;

  return (
    <Container maxWidth="xl" sx={{ py: { xs: 2, md: 4 }, px: { xs: 0, sm: 3 } }}>
      <Box sx={{ px: { xs: 2, sm: 0 }, mb: { xs: 2, md: 4 } }}>
        <AssistantHeader staff={staff} language={language} onLanguage={chat.setLanguage} onNewChat={() => setConfirmOpen(true)}
          onTrace={staff && !wide ? () => setTraceOpen(true) : undefined} />
      </Box>
      <Box
        sx={{
          display: 'grid', alignItems: 'start', gap: 6,
          gridTemplateColumns: { xs: '1fr', md: 'auto', lg: 'minmax(0, 1fr) auto minmax(0, 1fr)' },
          justifyContent: 'center',
        }}
      >
        {wide && (
          <Box sx={{ justifySelf: 'end', width: '100%', maxWidth: 300, pt: 2 }}>
            <AsideRail staff={staff} busy={state.busy} onText={sendText} />
          </Box>
        )}
        <Device>
          <ChatHeader language={language} busy={state.busy} />
          <ChatThread items={items} history={history} busy={state.busy} error={state.error} language={language}
            onReply={(b) => void chat.reply(b)} onRetry={chat.retry} onAttach={attach} onText={sendText} />
          <Composer placeholder={typeUnits ? FAILURE_TEXT[language].unitsHint : UI[language].placeholder} busy={state.busy} autoFocus={typeUnits}
            onText={sendText} onAttach={attach} onVoice={(b) => void chat.sendVoice(b)} />
        </Device>
        {wide && staff && <Box sx={{ justifySelf: 'start', width: '100%', maxWidth: 360, pt: 2 }}>{trace}</Box>}
      </Box>
      <Box component="input" type="file" accept={BILL_ACCEPT} ref={fileInput} sx={{ display: 'none' }} aria-hidden tabIndex={-1}
        onChange={(e) => {
          const file = e.currentTarget.files?.[0];
          if (file) void chat.sendFile(file);
          e.currentTarget.value = '';
        }} />
      <NewChatDialog open={confirmOpen} onClose={() => setConfirmOpen(false)} onConfirm={chat.reset} />
      {staff && !wide && (
        <Drawer anchor="bottom" open={traceOpen} onClose={() => setTraceOpen(false)}
          slotProps={{ paper: { sx: { maxHeight: '80dvh', p: 2.5, borderTopLeftRadius: 16, borderTopRightRadius: 16, bgcolor: 'background.default' } } }}>
          {trace}
        </Drawer>
      )}
    </Container>
  );
}
