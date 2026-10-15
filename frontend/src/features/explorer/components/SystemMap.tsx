import { Box, useTheme } from '@mui/material';
import type { KeyboardEvent } from 'react';

import { EDGES, edgePath, LANE_X, LANES, MAP_H, MAP_W, NODE_BY_ID, NODE_H, NODE_W, NODES, nodeX, type SystemNode } from '../model/systemMap';

interface SystemMapProps {
  hotEdges: string[];
  selected: string | null;
  onSelect: (id: string) => void;
  /** Scale to the box it sits in instead of keeping a readable minimum width (presentation mode). */
  fit?: boolean;
  /** Glide the camera towards the boxes the current step lights up. */
  focus?: boolean;
}

const FOCUS_PAD = 70;
const MAX_ZOOM = 1.7;

/** Zoom and pan that frame the lit boxes, so a presenter's audience sees where the step happens. */
function camera(hotEdges: string[]): string {
  const nodes = [...new Set(hotEdges.flatMap((e) => e.split('>')))].map((id) => NODE_BY_ID.get(id)).filter((n) => n !== undefined);
  if (nodes.length === 0) return 'translate(0px, 0px) scale(1)';
  const left = Math.min(...nodes.map(nodeX)) - FOCUS_PAD;
  const right = Math.max(...nodes.map((n) => nodeX(n) + NODE_W)) + FOCUS_PAD;
  const top = Math.min(...nodes.map((n) => n.y)) - FOCUS_PAD;
  const bottom = Math.max(...nodes.map((n) => n.y + NODE_H)) + FOCUS_PAD;
  const scale = Math.max(1, Math.min(MAP_W / (right - left), MAP_H / (bottom - top), MAX_ZOOM));
  const x = MAP_W / 2 - scale * ((left + right) / 2);
  const y = MAP_H / 2 - scale * ((top + bottom) / 2);
  // Never pan past the drawing's edge, so no empty margin slides into view.
  const clampX = Math.min(0, Math.max(MAP_W * (1 - scale), x));
  const clampY = Math.min(0, Math.max(MAP_H * (1 - scale), y));
  return `translate(${clampX}px, ${clampY}px) scale(${scale})`;
}

/** The whole system as one drawing. Lit edges animate along the direction data moves. */
export function SystemMap({ hotEdges, selected, onSelect, fit = false, focus = false }: SystemMapProps) {
  const { palette: p } = useTheme();
  const hotNodes = new Set(hotEdges.flatMap((e) => e.split('>')));
  const stroke = (n: SystemNode) =>
    n.status === 'planned' ? p.secondary.main : n.status === 'external' ? p.warning.main : p.grey[400];
  const keyOpen = (id: string) => (e: KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(id); }
  };

  return (
    <Box component="svg" viewBox={`0 0 ${MAP_W} ${MAP_H}`} role="group" aria-label="Bill Mitra system map, from the consumer's phone to DISCOM systems"
      sx={{ display: 'block', width: '100%', height: fit ? '100%' : 'auto', minWidth: fit ? 0 : 960, overflow: 'hidden',
        '@keyframes flow': { to: { strokeDashoffset: -130 } },
        '@media (prefers-reduced-motion: reduce)': { '& *': { animation: 'none !important', transition: 'none !important' } } }}>
      <Box component="g" sx={{ transform: focus ? camera(hotEdges) : 'none', transformOrigin: '0 0',
        transition: 'transform 900ms cubic-bezier(0.22, 1, 0.36, 1)' }}>
        {LANES.map((lane, i) => (
          <text key={lane} x={LANE_X[i]} y={12} fill={p.text.secondary}
            style={{ fontSize: 10.5, letterSpacing: '0.08em', textTransform: 'uppercase', fontWeight: 600 }}>{lane}</text>
        ))}
        {EDGES.map((e) => <path key={e} d={edgePath(e)} fill="none" stroke={p.divider} strokeWidth={1.4} />)}
        {hotEdges.map((e, i) => (
          <Box component="path" key={`${e}-hot`} d={edgePath(e)} fill="none" stroke={p.secondary.main} strokeWidth={2.4} strokeLinecap="round"
            sx={{ strokeDasharray: '8 122', animation: 'flow 2.6s linear infinite', animationDelay: `${-i * 0.45}s` }} />
        ))}
        {NODES.map((n) => {
          const hot = hotNodes.has(n.id);
          const x = nodeX(n);
          return (
            <Box component="g" key={n.id} role="button" tabIndex={0} aria-label={`${n.title}, ${n.status}`} aria-pressed={selected === n.id}
              onClick={() => onSelect(n.id)} onKeyDown={keyOpen(n.id)}
              sx={{ cursor: 'pointer', opacity: hotEdges.length && !hot && selected !== n.id ? 0.45 : 1, transition: 'opacity 300ms',
                '&:hover rect, &:focus-visible rect': { stroke: p.primary.main }, outline: 'none' }}>
              <rect x={x} y={n.y} width={NODE_W} height={NODE_H} rx={6}
                fill={hot ? p.success.light : selected === n.id ? p.info.light : p.background.paper}
                stroke={selected === n.id ? p.primary.main : stroke(n)} strokeWidth={hot || selected === n.id ? 2 : 1.2}
                strokeDasharray={n.status === 'planned' ? '4 3' : undefined} style={{ transition: 'fill 300ms' }} />
              <text x={x + 12} y={n.y + 21} fill={p.text.primary} style={{ fontSize: 12.5, fontWeight: 600 }}>{n.title}</text>
              <text x={x + 12} y={n.y + 37} fill={p.text.secondary} style={{ fontSize: 10, fontFamily: 'monospace' }}>{n.code}</text>
            </Box>
          );
        })}
      </Box>
    </Box>
  );
}
