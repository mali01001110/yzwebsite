/**
 * True when the visitor has asked the OS to minimise animation.
 *
 * Scroll reveals themselves are CSS (`.reveal` / `.stagger` in base.css); this
 * guards the JS-driven effects — text scrambling, the typewriter log and the
 * drifting gauges — which CSS cannot switch off.
 */
export function prefersReducedMotion() {
  return (
    typeof window !== 'undefined' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  );
}
