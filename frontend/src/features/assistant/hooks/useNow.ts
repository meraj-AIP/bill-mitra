import { useEffect, useState } from 'react';

/** The current time, refreshed often enough for a clock showing minutes. */
export function useNow(everyMs = 15_000): Date {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), everyMs);
    return () => window.clearInterval(timer);
  }, [everyMs]);
  return now;
}
