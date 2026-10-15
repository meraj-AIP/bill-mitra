import { useEffect, useState } from 'react';

/** Whole seconds since the calling component mounted. Mount it only while the work runs. */
export function useElapsed(): number {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const started = performance.now();
    const id = window.setInterval(() => setSeconds(Math.floor((performance.now() - started) / 1000)), 500);
    return () => window.clearInterval(id);
  }, []);
  return seconds;
}
