import { useEffect, useState } from 'react';
import { prefersReducedMotion } from '../utils/motion';

const DIAL_SIZE = 76;
const STROKE_WIDTH = 3;
const ARC_RADIUS = (DIAL_SIZE - STROKE_WIDTH) / 2 - 1;
const TICK_RADIUS = ARC_RADIUS - 7;
const ARC_LENGTH = 2 * Math.PI * ARC_RADIUS;

const DRIFT_INTERVAL_MS = 2200;
const DRIFT_RANGE = 5;

function clampPercentage(value) {
  return Math.min(Math.max(value, 0), 100);
}

/**
 * Circular technical gauge. The arc animates up from zero on mount so the dials
 * read as instruments spinning up; `drifts` then keeps the needle wandering
 * inside a small band so the readout never looks frozen.
 */
function HudGauge({ value, label, suffix = '%', drifts = false }) {
  const [renderedValue, setRenderedValue] = useState(0);

  useEffect(() => {
    const frameId = window.requestAnimationFrame(() => setRenderedValue(value));
    return () => window.cancelAnimationFrame(frameId);
  }, [value]);

  useEffect(() => {
    if (!drifts || prefersReducedMotion()) return undefined;

    const timerId = window.setInterval(() => {
      const offset = (Math.random() * 2 - 1) * DRIFT_RANGE;
      setRenderedValue(clampPercentage(value + offset));
    }, DRIFT_INTERVAL_MS);

    return () => window.clearInterval(timerId);
  }, [drifts, value]);

  const clamped = clampPercentage(renderedValue);
  const center = DIAL_SIZE / 2;

  return (
    <div className="hud-gauge">
      <div className="hud-gauge__dial">
        <svg
          className="hud-gauge__svg"
          width={DIAL_SIZE}
          height={DIAL_SIZE}
          viewBox={`0 0 ${DIAL_SIZE} ${DIAL_SIZE}`}
          role="img"
          aria-label={`${label}: ${value}${suffix}`}
        >
          <circle className="hud-gauge__ticks" cx={center} cy={center} r={TICK_RADIUS} />
          <circle className="hud-gauge__track" cx={center} cy={center} r={ARC_RADIUS} />
          <circle
            className="hud-gauge__arc"
            cx={center}
            cy={center}
            r={ARC_RADIUS}
            strokeDasharray={ARC_LENGTH}
            strokeDashoffset={ARC_LENGTH * (1 - clamped / 100)}
          />
        </svg>
        <span className="hud-gauge__value">
          {Math.round(clamped)}
          {suffix}
        </span>
      </div>
      <span className="hud-gauge__label">{label}</span>
    </div>
  );
}

export default HudGauge;
