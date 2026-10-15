import { Box } from '@mui/material';

import { mediaUrl } from '../api/assistantApi';
import type { Outbound, ReplyButton } from '../api/types';
import { isRtl, UI } from '../model/strings';
import { Bubble } from './Bubble';
import { MessageImage } from './MessageImage';
import { ListReply, ReplyButtons } from './ReplyOptions';
import { VoiceNote } from './VoiceNote';
import { WaText } from './WaText';

interface BotMessageProps {
  message: Outbound;
  at: Date;
  first: boolean;
  live: boolean;
  autoPlay: boolean;
  disabled: boolean;
  onReply: (button: ReplyButton) => void;
}

function footerFor({ message, disabled, onReply }: BotMessageProps) {
  const rtl = isRtl(message.language);
  if (message.type === 'buttons') return <ReplyButtons buttons={message.buttons} rtl={rtl} disabled={disabled} onReply={onReply} />;
  if (message.type === 'list') {
    return <ListReply label={message.button_label} rows={message.rows} rtl={rtl} disabled={disabled} onReply={onReply} />;
  }
  return undefined;
}

/** Renders only what the WhatsApp Cloud API can deliver: text, image, audio, buttons and list. */
export function BotMessage(props: BotMessageProps) {
  const { message, at, first, live, autoPlay } = props;
  const rtl = isRtl(message.language);
  const shared = { side: 'in' as const, at, first, animate: live };

  // lang lets screen readers pick the right voice; dir is set on the text so the bubble stays on the left.
  return (
    <Box lang={message.language}>
      {message.type === 'audio' && (
        <Bubble {...shared}>
          <VoiceNote sources={message.media_ids.map(mediaUrl)} durationS={message.duration_s} autoPlay={autoPlay}
            transcript={{ text: message.transcript, label: UI[message.language].transcript, rtl }} />
        </Bubble>
      )}
      {message.type === 'image' && (
        <Bubble {...shared} flush>
          <MessageImage src={mediaUrl(message.media_id)} alt={message.caption ?? 'Chart from Bill Mitra'} width={280} />
          {message.caption && (
            <Box sx={{ px: 0.75, pt: 0.5 }}>
              <WaText text={message.caption} rtl={rtl} />
            </Box>
          )}
        </Bubble>
      )}
      {message.type !== 'audio' && message.type !== 'image' && (
        <Bubble {...shared} footer={footerFor(props)}>
          <WaText text={message.body} rtl={rtl} />
        </Bubble>
      )}
    </Box>
  );
}
