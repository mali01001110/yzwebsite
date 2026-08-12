import { useEffect, useState } from 'react';

/**
 * `scrollHeight` is rounded to an integer while `scrollY` can be fractional, so
 * the last pixel of a page is often unreachable and the bar would stall at 99%.
 * Anything this close to the end counts as the bottom.
 */
const BOTTOM_TOLERANCE_PX = 2;

/**
 * Percentage of the document scrolled, 0–100, reaching exactly 100 at the
 * bottom. Reads are coalesced into an animation frame so the always-on rail
 * readout cannot thrash on scroll.
 */
export function useScrollProgress() {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    let frameId = 0;

    const measure = () => {
      frameId = 0;
      const scrollableDistance =
        document.documentElement.scrollHeight - window.innerHeight;

      // A page that cannot scroll is, by definition, already fully seen
      if (scrollableDistance <= 0) {
        setProgress(100);
        return;
      }

      const remaining = scrollableDistance - window.scrollY;
      if (remaining <= BOTTOM_TOLERANCE_PX) {
        setProgress(100);
        return;
      }

      const ratio = window.scrollY / scrollableDistance;
      setProgress(Math.min(Math.max(ratio, 0), 1) * 100);
    };

    const requestMeasure = () => {
      if (frameId) return;
      frameId = window.requestAnimationFrame(measure);
    };

    measure();
    window.addEventListener('scroll', requestMeasure, { passive: true });
    window.addEventListener('resize', requestMeasure);

    return () => {
      window.removeEventListener('scroll', requestMeasure);
      window.removeEventListener('resize', requestMeasure);
      if (frameId) window.cancelAnimationFrame(frameId);
    };
  }, []);

  return progress;
}
