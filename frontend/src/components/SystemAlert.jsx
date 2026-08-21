import { TriangleAlert } from 'lucide-react';

/**
 * Critical-alert box modelled on the reference "SYSTEM FAILURE" dialog: hazard
 * title bar, blinking warning glyph and an uppercase log body.
 */
function SystemAlert({ code, title, children }) {
  return (
    <div className="hud-alert" role="note">
      <div className="hud-alert__bar">
        <span>{code}</span>
        <span className="hud-alert__glyphs" aria-hidden="true">
          <span>_</span>
          <span>□</span>
          <span>✕</span>
        </span>
      </div>

      <div className="hud-alert__body">
        <TriangleAlert size={30} className="hud-alert__icon" aria-hidden="true" />
        <div>
          <p className="hud-alert__title">{title}</p>
          <p className="hud-alert__text">{children}</p>
        </div>
      </div>

      <div className="hazard-bar" aria-hidden="true" />
    </div>
  );
}

export default SystemAlert;
