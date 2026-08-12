/**
 * Segmented tick meter from the poster's footer bar. `value` fills the ticks
 * left to right.
 */
function TickBar({ value = 100, label, showValue = true }) {
  const clamped = Math.min(Math.max(value, 0), 100);

  return (
    <div className="tick-bar">
      {label && (
        <div className="tick-bar__label">
          <span>{label}</span>
          {showValue && <span>{clamped}%</span>}
        </div>
      )}
      <div className="tick-bar__track" aria-hidden="true">
        <div className="tick-bar__fill" style={{ width: `${clamped}%` }} />
      </div>
    </div>
  );
}

export default TickBar;
