import { useEffect, useMemo, useState } from 'react';
import { prefersReducedMotion } from '../utils/motion';

const SCRAMBLE_GLYPHS = '!<>-_\\/[]{}=+*^?#%01';
const FRAME_MS = 28;
const FRAMES_PER_CHAR = 2;

function randomGlyph() {
  return SCRAMBLE_GLYPHS[Math.floor(Math.random() * SCRAMBLE_GLYPHS.length)];
}

/** Replaces every non-space character with a random glyph. */
function scrambleAll(text) {
  return text
    .split('')
    .map((char) => (char === ' ' ? char : randomGlyph()))
    .join('');
}

/**
 * Decrypt-on-reveal effect: the string reads as noise until `isActive` flips,
 * then resolves left to right. Returns the plain text untouched when the
 * visitor prefers reduced motion, so the heading is never left unreadable.
 */
export function useScrambleText(text, isActive) {
  const isStatic = prefersReducedMotion();
  const placeholder = useMemo(() => scrambleAll(text), [text]);
  const [revealed, setRevealed] = useState(null);

  useEffect(() => {
    if (isStatic || !isActive) return undefined;

    let frame = 0;
    const timerId = window.setInterval(() => {
      frame += 1;
      const revealedCount = Math.floor(frame / FRAMES_PER_CHAR);

      if (revealedCount >= text.length) {
        setRevealed(text);
        window.clearInterval(timerId);
        return;
      }

      setRevealed(
        text
          .split('')
          .map((char, index) => {
            if (index < revealedCount || char === ' ') return char;
            return randomGlyph();
          })
          .join('')
      );
    }, FRAME_MS);

    return () => window.clearInterval(timerId);
  }, [text, isActive, isStatic]);

  if (isStatic) return text;
  return revealed ?? placeholder;
}
