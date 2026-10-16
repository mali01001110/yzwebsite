import { useLanguage } from '../hooks/useLanguage';

/**
 * The poster's INFORMATION readout: a compact titled frame of key/value pairs
 * with a hatched footer block.
 */
function InfoPanel({ title = 'Information', rows, className = '' }) {
  const { translate: t } = useLanguage();
  return (
    <div className={`info-panel ${className}`.trim()}>
      <div className="info-panel__bar">
        <span>{t(title)}</span>
        <span className="info-panel__glyphs" aria-hidden="true">
          <span>_</span>
          <span>✕</span>
        </span>
      </div>

      <dl className="info-panel__body">
        {rows.map(({ key, value }) => (
          <div key={key} className="info-panel__row">
            <dt className="info-panel__key">{t(key)}</dt>
            <dd className="info-panel__value">{t(value)}</dd>
          </div>
        ))}
      </dl>

      <div className="info-panel__hatch" aria-hidden="true" />
    </div>
  );
}

export default InfoPanel;
