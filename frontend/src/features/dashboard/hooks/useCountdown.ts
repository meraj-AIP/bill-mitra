import { useEffect, useState } from 'react';

/** Seconds left until the deadline, ticking once a second. Null deadline means nothing to wait for. */
export function useCountdown(deadline: number | null): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (deadline === null) return undefined;
    const id = window.setInterval(() => {
      const t = Date.now();
      setNow(t);
      if (t >= deadline) window.clearInterval(id);
    }, 1000);
    return () => window.clearInterval(id);
  }, [deadline]);
  return deadline === null ? 0 : Math.max(0, Math.ceil((deadline - now) / 1000));
}
