import { useEffect, useRef } from 'react';

/** Formats a pixel coordinate as a fixed-width HUD readout. */
function formatCoordinate(value) {
  return String(Math.round(value)).padStart(4, '0');
}

/**
 * Targeting reticle that tracks the pointer: full-bleed crosshair hairlines, a
 * bracketed box and a live coordinate readout. Positions are written straight
 * to the DOM inside an animation frame rather than through React state, so
 * moving the mouse never triggers a re-render.
 */
function CursorReticle() {
  const rootRef = useRef(null);
  const horizontalRef = useRef(null);
  const verticalRef = useRef(null);
  const boxRef = useRef(null);
  const readoutRef = useRef(null);

  useEffect(() => {
    const isPointerCoarse = window.matchMedia('(hover: none)').matches;
    const isReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (isPointerCoarse || isReduced) return undefined;

    let frameId = 0;
    let pointerX = 0;
    let pointerY = 0;

    const paint = () => {
      frameId = 0;
      if (horizontalRef.current) {
        horizontalRef.current.style.transform = `translate3d(0, ${pointerY}px, 0)`;
      }
      if (verticalRef.current) {
        verticalRef.current.style.transform = `translate3d(${pointerX}px, 0, 0)`;
      }
      if (boxRef.current) {
        boxRef.current.style.transform = `translate3d(${pointerX}px, ${pointerY}px, 0)`;
      }
      if (readoutRef.current) {
        readoutRef.current.textContent = `X:${formatCoordinate(pointerX)} Y:${formatCoordinate(pointerY)}`;
      }
    };

    const handlePointerMove = (event) => {
      pointerX = event.clientX;
      pointerY = event.clientY;
      rootRef.current?.classList.add('is-live');
      if (!frameId) frameId = window.requestAnimationFrame(paint);
    };

    window.addEventListener('mousemove', handlePointerMove, { passive: true });

    return () => {
      window.removeEventListener('mousemove', handlePointerMove);
      if (frameId) window.cancelAnimationFrame(frameId);
    };
  }, []);

  return (
    <div className="reticle" ref={rootRef} aria-hidden="true">
      <div className="reticle__line reticle__line--h" ref={horizontalRef} />
      <div className="reticle__line reticle__line--v" ref={verticalRef} />
      <div className="reticle__box" ref={boxRef}>
        <span className="reticle__readout" ref={readoutRef} />
      </div>
    </div>
  );
}

export default CursorReticle;
