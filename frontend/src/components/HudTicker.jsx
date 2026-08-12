/**
 * Scrolling log strip. The item list is rendered twice so the -50% translate
 * loop reads as a continuous marquee with no visible seam.
 */
function HudTicker({ items }) {
  return (
    <div className="hud-ticker" aria-hidden="true">
      <div className="hud-ticker__track">
        {[...items, ...items].map((item, index) => (
          <span key={`${item}-${index}`}>{item}</span>
        ))}
      </div>
    </div>
  );
}

export default HudTicker;
