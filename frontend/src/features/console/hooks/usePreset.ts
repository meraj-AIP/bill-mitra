import { useState } from 'react';

import type { Focus, FocusTarget } from '../model/focus';

/**
 * Applies a suggestion from AI assist once per press, as soon as the section is ready for it.
 * It runs during render, React's way to adjust state from a prop without an extra effect pass.
 */
export function usePreset(preset: Focus | null, target: FocusTarget, ready: boolean, apply: (key: string) => void): void {
  const [seen, setSeen] = useState(0);
  const fresh = preset !== null && preset.target === target && preset.n !== seen;
  if (fresh && ready) {
    setSeen(preset.n);
    apply(preset.key);
  }
}
