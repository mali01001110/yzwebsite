import { useEffect, useState } from 'react';

/** A section owns the menu once its top edge passes this far down the viewport. */
const READING_LINE_RATIO = 0.3;

/** Sub-pixel scroll positions mean the page bottom is never exactly equal. */
const BOTTOM_TOLERANCE_PX = 2;

/**
 * Scroll-spy: reports which section currently owns the viewport.
 * `sectionIds` must be a stable reference (module constant) so the listeners are
 * not torn down on every render.
 *
 * Ownership is the last section whose top edge has crossed the reading line,
 * which is independent of section height — comparing how much of each section
 * is visible would let a short section outscore a tall one such as the
 * full-viewport hero, and would skip sections shorter than the measuring band.
 */
export function useActiveSection(sectionIds) {
  const [activeSection, setActiveSection] = useState(sectionIds[0]);

  useEffect(() => {
    const elements = sectionIds
      .map((id) => document.getElementById(id))
      .filter(Boolean);

    if (elements.length === 0) return undefined;

    const isScrolledToBottom = () =>
      window.innerHeight + window.scrollY >=
      document.documentElement.scrollHeight - BOTTOM_TOLERANCE_PX;

    const resolveActiveSection = () => {
      // The closing section sits above the footer and can stop short of the
      // reading line, so the page bottom awards it the highlight outright.
      if (isScrolledToBottom()) {
        setActiveSection(elements[elements.length - 1].id);
        return;
      }

      const readingLine = window.innerHeight * READING_LINE_RATIO;
      const owner = elements.reduce(
        (current, element) =>
          element.getBoundingClientRect().top <= readingLine ? element : current,
        elements[0]
      );

      setActiveSection(owner.id);
    };

    // Scroll events outpace paints, so collapse bursts into one measurement.
    let frameId = null;
    const scheduleResolve = () => {
      if (frameId !== null) return;
      frameId = window.requestAnimationFrame(() => {
        frameId = null;
        resolveActiveSection();
      });
    };

    resolveActiveSection();
    window.addEventListener('scroll', scheduleResolve, { passive: true });
    window.addEventListener('resize', scheduleResolve);

    return () => {
      if (frameId !== null) window.cancelAnimationFrame(frameId);
      window.removeEventListener('scroll', scheduleResolve);
      window.removeEventListener('resize', scheduleResolve);
    };
  }, [sectionIds]);

  return activeSection;
}
