import { useSystemClock } from '../hooks/useSystemClock';
import { useScrollProgress } from '../hooks/useScrollProgress';
import { formatClock } from '../utils/time';

const BUILD_ID = 'SYS.OVERRIDE_V.02';

/**
 * Always-on telemetry strip pinned above the header: build tag, standing
 * breach alert, live scroll depth and a live clock. The progress bar along the
 * bottom edge doubles as the page's scroll indicator.
 */
function SystemRail() {
  const now = useSystemClock();
  const scrollProgress = useScrollProgress();
  const isComplete = scrollProgress >= 100;

  return (
    <div className="system-rail" aria-hidden="true">
      <span className="system-rail__group">
        <span className="hud-status-dot" />
        {BUILD_ID}
      </span>

      <span className="system-rail__group system-rail__group--secondary">
        <span className="system-rail__alert">⚠ BREACH DETECTED</span>
        <span className="system-rail__hide-sm">NODE // ABIDJAN.CI</span>
        <span className="system-rail__scan">
          {isComplete ? 'LOAD COMPLETE' : `LOAD ${String(Math.round(scrollProgress)).padStart(3, '0')}%`}
        </span>
        <span className="system-rail__clock">{formatClock(now)}</span>
      </span>

      <span className={`rail-loader ${isComplete ? 'is-complete' : ''}`.trim()}>
        <span className="rail-loader__fill" style={{ width: `${scrollProgress}%` }} />
      </span>
    </div>
  );
}

export default SystemRail;
