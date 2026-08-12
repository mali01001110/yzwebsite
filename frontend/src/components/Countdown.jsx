import { useSystemClock } from '../hooks/useSystemClock';
import { padTimePart } from '../utils/time';

const MS_PER_SECOND = 1000;
const SECONDS_PER_HOUR = 3600;

/**
 * Live countdown to the next full hour. Self-resetting, so the readout is
 * always genuinely ticking instead of frozen at an invented deadline.
 */
function Countdown({ label = 'Next sync cycle' }) {
  const now = useSystemClock();

  const nextHour = new Date(now);
  nextHour.setHours(now.getHours() + 1, 0, 0, 0);

  const remainingSeconds = Math.max(
    Math.floor((nextHour.getTime() - now.getTime()) / MS_PER_SECOND),
    0
  );

  const hours = Math.floor(remainingSeconds / SECONDS_PER_HOUR);
  const minutes = Math.floor((remainingSeconds % SECONDS_PER_HOUR) / 60);
  const seconds = remainingSeconds % 60;

  const elapsedRatio = 1 - remainingSeconds / SECONDS_PER_HOUR;

  return (
    <div className="hud-countdown">
      <span className="hud-countdown__label">{label}</span>
      <div className="hud-countdown__value" role="timer" aria-live="off">
        {padTimePart(hours)}:{padTimePart(minutes)}:{padTimePart(seconds)}
      </div>
      <div className="hud-meter" aria-hidden="true">
        <div
          className="hud-meter__fill"
          style={{ width: `${(elapsedRatio * 100).toFixed(1)}%` }}
        />
      </div>
    </div>
  );
}

export default Countdown;
