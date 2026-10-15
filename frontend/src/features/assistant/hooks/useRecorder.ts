import { useCallback, useEffect, useRef, useState } from 'react';

const MAX_SECONDS = 60;

export type RecorderState = 'idle' | 'recording' | 'unsupported' | 'denied';

/** Microphone capture for voice questions. Produces audio/webm (Opus), which Soniox accepts. */
export function useRecorder(onRecorded: (blob: Blob) => void) {
  const [state, setState] = useState<RecorderState>(
    typeof window !== 'undefined' && 'MediaRecorder' in window ? 'idle' : 'unsupported',
  );
  const [seconds, setSeconds] = useState(0);
  const recorder = useRef<MediaRecorder | null>(null);
  const timer = useRef<number | null>(null);

  const clearTimer = () => {
    if (timer.current !== null) window.clearInterval(timer.current);
    timer.current = null;
  };

  const stop = useCallback(() => {
    clearTimer();
    recorder.current?.stop();
  }, []);

  const start = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const chunks: Blob[] = [];
      const rec = new MediaRecorder(stream);
      rec.ondataavailable = (e) => chunks.push(e.data);
      rec.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        setState('idle');
        const blob = new Blob(chunks, { type: rec.mimeType || 'audio/webm' });
        if (blob.size > 2000) onRecorded(blob);
      };
      recorder.current = rec;
      rec.start();
      setSeconds(0);
      setState('recording');
      timer.current = window.setInterval(() => {
        setSeconds((s) => {
          if (s + 1 >= MAX_SECONDS) stop();
          return s + 1;
        });
      }, 1000);
    } catch {
      setState('denied');
    }
  }, [onRecorded, stop]);

  useEffect(() => clearTimer, []);

  return { state, seconds, start, stop };
}
