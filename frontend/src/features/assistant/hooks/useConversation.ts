import { useCallback, useReducer, useState } from 'react';

import { mediaUrl, resetConversation, sendMessage, upload } from '../api/assistantApi';
import type { Language, OutgoingMessage, ReplyButton, StreamEvent } from '../api/types';
import { initialState, reducer, type UserContent } from '../model/conversation';

const reason = (error: unknown, fallback: string) => (error instanceof Error ? error.message : fallback);

/** Messages sent in this visit, streamed replies and the step trace for each turn. */
export function useConversation(onCleared: () => void) {
  const [state, dispatch] = useReducer(reducer, initialState);
  const [language, setLanguage] = useState<Language>('te');

  const run = useCallback(
    async (content: UserContent, title: string, message: OutgoingMessage) => {
      dispatch({ type: 'user', content, title });
      const onEvent = (event: StreamEvent) => {
        if (event.kind === 'trace') dispatch({ type: 'trace', step: event.trace });
        else if (event.kind === 'message') dispatch({ type: 'bot', message: event.message });
        else if (event.kind === 'transcript') dispatch({ type: 'transcript', text: event.text });
      };
      try {
        await sendMessage(language, message, onEvent);
        dispatch({ type: 'done' });
      } catch (error) {
        dispatch({ type: 'failed', error: reason(error, 'Could not reach Bill Mitra') });
      }
    },
    [language],
  );

  const sendText = useCallback(
    (text: string) => run({ kind: 'text', text }, `Text: "${text.slice(0, 48)}"`, { kind: 'text', text }),
    [run],
  );

  const sendFile = useCallback(
    async (file: File) => {
      try {
        const uploaded = await upload(file, file.name);
        const isPdf = uploaded.mime_type === 'application/pdf';
        const src = mediaUrl(uploaded.media_id);
        const content: UserContent = isPdf ? { kind: 'document', name: file.name, href: src } : { kind: 'image', src };
        await run(content, `${isPdf ? 'PDF' : 'Photo'}: ${file.name}`, {
          kind: isPdf ? 'document' : 'image',
          media_id: uploaded.media_id,
          mime_type: uploaded.mime_type,
        });
      } catch (error) {
        dispatch({ type: 'failed', error: reason(error, 'Upload failed') });
      }
    },
    [run],
  );

  const sendVoice = useCallback(
    async (blob: Blob) => {
      try {
        const uploaded = await upload(blob, 'voice-note.webm');
        await run({ kind: 'audio', src: mediaUrl(uploaded.media_id) }, 'Voice note', {
          kind: 'audio',
          media_id: uploaded.media_id,
          mime_type: uploaded.mime_type,
        });
      } catch (error) {
        dispatch({ type: 'failed', error: reason(error, 'Voice note failed') });
      }
    },
    [run],
  );

  const reply = useCallback(
    (button: ReplyButton) =>
      run({ kind: 'reply', title: button.title }, `Tapped: ${button.title}`, { kind: 'button_reply', reply_id: button.id }),
    [run],
  );

  /** Throws on failure so the confirm dialog can stay open and say why. */
  const reset = useCallback(async () => {
    await resetConversation();
    onCleared();
    dispatch({ type: 'reset' });
  }, [onCleared]);

  return { state, language, setLanguage, sendText, sendFile, sendVoice, reply, reset };
}

export type Conversation = ReturnType<typeof useConversation>;
