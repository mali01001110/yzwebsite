import { useEffect, useState } from 'react';

const TICK_INTERVAL_MS = 1000;

/**
 * Single ticking clock shared by every live readout in the HUD (system rail,
 * countdown). Returns a fresh `Date` once per second.
 */
export function useSystemClock() {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const timerId = window.setInterval(() => setNow(new Date()), TICK_INTERVAL_MS);
    return () => window.clearInterval(timerId);
  }, []);

  return now;
}
