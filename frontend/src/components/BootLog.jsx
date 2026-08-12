import { useEffect, useState } from 'react';
import { prefersReducedMotion } from '../utils/motion';

const TYPE_INTERVAL_MS = 18;

/**
 * Types a sequence of log lines out character by character. Lines that have not
 * started yet are not rendered, so the caret on the last visible line always
 * sits where the terminal is currently writing.
 */
function BootLog({ lines }) {
  const totalCharacters = lines.reduce((sum, line) => sum + line.length, 0);
  const isStatic = prefersReducedMotion();
  const [typedCount, setTypedCount] = useState(() => (isStatic ? totalCharacters : 0));

  useEffect(() => {
    if (isStatic || typedCount >= totalCharacters) return undefined;

    const timerId = window.setTimeout(
      () => setTypedCount((count) => count + 1),
      TYPE_INTERVAL_MS
    );

    return () => window.clearTimeout(timerId);
  }, [typedCount, totalCharacters, isStatic]);

  let remaining = typedCount;
  const visibleLines = [];

  for (const line of lines) {
    if (remaining <= 0) break;
    visibleLines.push(line.slice(0, Math.min(remaining, line.length)));
    remaining -= line.length;
  }

  return (
    <div className="hero__log" aria-hidden="true">
      {visibleLines.map((line, index) => (
        <div key={lines[index]} className="hero__log-line">
          {line}
        </div>
      ))}
    </div>
  );
}

export default BootLog;
