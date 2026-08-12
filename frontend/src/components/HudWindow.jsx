/**
 * Application-window chrome from the reference posters: a `>> NAME.EXE` title
 * bar with minimise/maximise/close glyphs, an optional right-hand tag, and a
 * hazard strip closing the frame.
 */
function HudWindow({ title, tag, className = '', children }) {
  return (
    <div className={`hud-window ${className}`.trim()}>
      <div className="hud-window__bar">
        <span className="hud-window__title">&gt;&gt; {title}</span>
        {tag && <span className="hud-window__tag">{tag}</span>}
        <span className="hud-window__glyphs" aria-hidden="true">
          <span>_</span>
          <span>□</span>
          <span>✕</span>
        </span>
      </div>

      <div className="hud-window__body">{children}</div>

      <div className="hazard-bar hazard-bar--tight" aria-hidden="true" />
    </div>
  );
}

export default HudWindow;
