/**
 * The poster's LOG panel: dashed header, `>` prefixed entries and an optional
 * gutter of line numbers for longer transmissions.
 */
function LogBox({ label, lines, numbered = false, className = '' }) {
  return (
    <div className={`log-box ${className}`.trim()}>
      {label && <span className="log-box__label">{label}</span>}

      <div className="log-box__lines">
        {lines.map((line, index) => (
          <p key={line} className="log-box__line">
            {numbered && (
              <span className="log-box__num" aria-hidden="true">
                {String(index + 1).padStart(2, '0')}
              </span>
            )}
            <span className="log-box__text">{line}</span>
          </p>
        ))}
      </div>
    </div>
  );
}

export default LogBox;
