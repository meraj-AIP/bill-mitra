import PauseIcon from '@mui/icons-material/Pause';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import { Box, Button, Collapse, IconButton, Stack, Typography } from '@mui/material';
import { useEffect, useMemo, useRef, useState } from 'react';

import { WaText } from './WaText';

interface VoiceNoteProps {
  sources: string[];
  /** Bill Mitra's notes carry their text behind a toggle; the consumer's own notes do not. */
  transcript?: { text: string; label: string; rtl: boolean } | undefined;
  durationS?: number | null | undefined;
  autoPlay?: boolean;
}

const BARS = 32;

function bars(seed: string): number[] {
  let h = 7;
  for (const c of seed) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return Array.from({ length: BARS }, (_, i) => 0.22 + (((h >> (i % 24)) ^ (i * 7919)) % 78) / 100);
}

function clock(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

/** Plays the clips one after another, the way WhatsApp plays consecutive voice notes. */
export function VoiceNote({ sources, transcript, durationS, autoPlay = false }: VoiceNoteProps) {
  const audio = useRef<HTMLAudioElement | null>(null);
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [loaded, setLoaded] = useState<number | null>(null);
  const [showText, setShowText] = useState(false);
  const shape = useMemo(() => bars(sources.join('|')), [sources]);

  useEffect(() => {
    if (!autoPlay || !audio.current) return;
    audio.current.play().then(() => setPlaying(true)).catch(() => setPlaying(false));
  }, [autoPlay]);

  const play = () => audio.current?.play().then(() => setPlaying(true)).catch(() => setPlaying(false));
  const toggle = () => {
    if (audio.current?.paused) void play();
    else {
      audio.current?.pause();
      setPlaying(false);
    }
  };

  const onEnded = () => {
    if (index + 1 < sources.length) {
      setIndex(index + 1);
      window.setTimeout(() => void play(), 0);
      return;
    }
    setPlaying(false);
    setProgress(0);
    setElapsed(0);
    setIndex(0);
  };

  const onTime = () => {
    const el = audio.current;
    if (!el?.duration || !Number.isFinite(el.duration)) return;
    setProgress((index + el.currentTime / el.duration) / sources.length);
    setElapsed(el.currentTime);
  };

  const onMeta = () => {
    const d = audio.current?.duration;
    if (d && Number.isFinite(d) && sources.length === 1) setLoaded(d);
  };

  const total = durationS ?? loaded;
  return (
    <Box sx={{ minWidth: 236 }}>
      <Stack direction="row" sx={{ alignItems: 'center', gap: 1.25 }}>
        <IconButton onClick={toggle} size="small" aria-label={playing ? 'Pause voice note' : 'Play voice note'}
          sx={(theme) => ({ width: 36, height: 36, bgcolor: theme.palette.chat.accent, color: theme.palette.chat.onHeader,
            '&:hover': { bgcolor: theme.palette.chat.accentDark } })}>
          {playing ? <PauseIcon fontSize="small" /> : <PlayArrowIcon fontSize="small" />}
        </IconButton>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Stack direction="row" sx={{ alignItems: 'center', gap: '2px', height: 26 }} aria-hidden>
            {shape.map((h, i) => (
              <Box key={i} sx={(theme) => ({ flex: 1, maxWidth: 3, borderRadius: 2, height: `${Math.round(h * 24)}px`,
                transition: 'background-color 160ms', bgcolor: i / BARS <= progress ? theme.palette.chat.accent : 'grey.400' })} />
            ))}
          </Stack>
          <Typography variant="caption" sx={(theme) => ({ color: theme.palette.chat.meta, fontVariantNumeric: 'tabular-nums', fontSize: '0.6875rem' })}>
            {playing || elapsed > 0 ? clock(elapsed) : total != null ? clock(total) : 'Voice note'}
          </Typography>
        </Box>
      </Stack>
      <audio ref={audio} src={sources[index] ?? ''} preload="metadata" onEnded={onEnded} onTimeUpdate={onTime} onLoadedMetadata={onMeta} />
      {transcript && (
        <>
          <Button size="small" onClick={() => setShowText((v) => !v)} aria-expanded={showText}
            sx={(theme) => ({ mt: 0.25, px: 0.5, minWidth: 0, fontSize: '0.75rem', color: theme.palette.chat.quickReply })}>
            {transcript.label}
          </Button>
          <Collapse in={showText}>
            <Typography component="div" variant="body2" sx={{ color: 'text.secondary', pb: 0.25 }}>
              <WaText text={transcript.text} rtl={transcript.rtl} />
            </Typography>
          </Collapse>
        </>
      )}
    </Box>
  );
}
