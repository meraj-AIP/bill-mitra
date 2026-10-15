import { Box } from '@mui/material';
import type { ReactNode } from 'react';

const TOKEN = /(\*[^*\n]+\*|_[^_\n]+_|~[^~\n]+~)/g;

function renderLine(line: string, key: number): ReactNode[] {
  return line.split(TOKEN).map((part, i) => {
    if (!part) return null;
    const inner = part.slice(1, -1);
    if (part.startsWith('*') && part.endsWith('*') && part.length > 2) return <b key={`${key}-${i}`}>{inner}</b>;
    if (part.startsWith('_') && part.endsWith('_') && part.length > 2) return <i key={`${key}-${i}`}>{inner}</i>;
    if (part.startsWith('~') && part.endsWith('~') && part.length > 2) return <s key={`${key}-${i}`}>{inner}</s>;
    return part;
  });
}

interface WaTextProps {
  text: string;
  rtl?: boolean;
}

/** WhatsApp message formatting (*bold*, _italic_, ~strike~, line breaks), rendered without HTML injection. */
export function WaText({ text, rtl = false }: WaTextProps) {
  const lines = text.split('\n');
  return (
    <Box component="span" dir={rtl ? 'rtl' : 'auto'} sx={{ display: 'block', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
      {lines.map((line, i) => (
        <span key={i}>
          {renderLine(line, i)}
          {i < lines.length - 1 && <br />}
        </span>
      ))}
    </Box>
  );
}
