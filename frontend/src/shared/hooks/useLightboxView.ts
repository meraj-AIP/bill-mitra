import { useCallback, useRef, useState, type PointerEvent } from 'react';

export const MIN_ZOOM = 1;
export const MAX_ZOOM = 4;
const STEP = 0.5;
const SWIPE_PX = 60;
const TAP_MOVE_PX = 8;
const DOUBLE_TAP_MS = 300;

export interface View { zoom: number; rotation: number; x: number; y: number }
const FIT: View = { zoom: 1, rotation: 0, x: 0, y: 0 };

const clamp = (z: number) => Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, z));
const withZoom = (v: View, zoom: number): View => {
  const z = clamp(zoom);
  // Back at fit size there is nothing to pan, so the photo recentres.
  return z === MIN_ZOOM ? { ...v, zoom: z, x: 0, y: 0 } : { ...v, zoom: z };
};

interface Gesture {
  pointers: Map<number, { x: number; y: number }>;
  start: { x: number; y: number; view: View } | null;
  pinch: { distance: number; zoom: number } | null;
  moved: boolean;
  lastTap: number;
}

function distance(points: Map<number, { x: number; y: number }>): number {
  const [a, b] = [...points.values()];
  return a && b ? Math.hypot(a.x - b.x, a.y - b.y) : 0;
}

/**
 * Zoom, rotate and pan for one photo, by buttons, keys, mouse or touch.
 * One finger swipes to the next photo at fit size and pans when zoomed; two fingers pinch; a double tap toggles zoom.
 */
export function useLightboxView(onSwipe: (direction: 1 | -1) => void) {
  const [view, setView] = useState<View>(FIT);
  const [dragging, setDragging] = useState(false);
  const g = useRef<Gesture>({ pointers: new Map(), start: null, pinch: null, moved: false, lastTap: 0 });

  const zoomBy = useCallback((delta: number) => setView((v) => withZoom(v, v.zoom + delta)), []);
  const zoomIn = useCallback(() => zoomBy(STEP), [zoomBy]);
  const zoomOut = useCallback(() => zoomBy(-STEP), [zoomBy]);
  const rotate = useCallback(() => setView((v) => ({ ...v, rotation: (v.rotation + 90) % 360 })), []);
  const reset = useCallback(() => setView(FIT), []);

  const onPointerDown = (e: PointerEvent<HTMLElement>) => {
    // Capturing a press on the previous or next button would swallow its click.
    if (e.target instanceof Element && e.target.closest('button, a')) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    g.current.pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (g.current.pointers.size === 2) {
      g.current.pinch = { distance: distance(g.current.pointers), zoom: view.zoom };
      g.current.start = null;
      return;
    }
    g.current.start = { x: e.clientX, y: e.clientY, view };
    g.current.moved = false;
    setDragging(true);
  };

  const onPointerMove = (e: PointerEvent<HTMLElement>) => {
    if (!g.current.pointers.has(e.pointerId)) return;
    g.current.pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    const { pinch, start } = g.current;
    if (pinch && g.current.pointers.size === 2) {
      g.current.moved = true;
      const now = distance(g.current.pointers);
      if (pinch.distance > 0) setView((v) => withZoom(v, pinch.zoom * (now / pinch.distance)));
      return;
    }
    if (!start) return;
    const dx = e.clientX - start.x;
    const dy = e.clientY - start.y;
    if (Math.hypot(dx, dy) > TAP_MOVE_PX) g.current.moved = true;
    if (start.view.zoom > MIN_ZOOM) setView((v) => ({ ...v, x: start.view.x + dx, y: start.view.y + dy }));
  };

  const finishTap = (time: number) => {
    if (time - g.current.lastTap < DOUBLE_TAP_MS) {
      g.current.lastTap = 0;
      setView((v) => withZoom(v, v.zoom > MIN_ZOOM ? MIN_ZOOM : 2));
    } else {
      g.current.lastTap = time;
    }
  };

  const onPointerUp = (e: PointerEvent<HTMLElement>) => {
    const { start, moved } = g.current;
    g.current.pointers.delete(e.pointerId);
    if (g.current.pointers.size > 0) return;
    g.current.pinch = null;
    g.current.start = null;
    setDragging(false);
    if (!start) return;
    const dx = e.clientX - start.x;
    if (!moved) finishTap(e.timeStamp);
    else if (start.view.zoom === MIN_ZOOM && Math.abs(dx) > SWIPE_PX) onSwipe(dx < 0 ? 1 : -1);
  };

  return {
    view, dragging, zoomIn, zoomOut, rotate, reset,
    handlers: { onPointerDown, onPointerMove, onPointerUp, onPointerCancel: onPointerUp },
  };
}
