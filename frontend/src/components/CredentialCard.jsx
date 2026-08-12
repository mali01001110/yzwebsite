import HudGauge from './HudGauge';
import DocumentThumb from './DocumentThumb';
import TickBar from './TickBar';

/**
 * Verification card used by both Education and Certifications: code + title,
 * a 100% verification dial, a large document scan and the record's facts.
 * Shared so the two sections cannot drift apart visually.
 */
function CredentialCard({ code, title, description, image, alt, facts, hint, onOpen }) {
  return (
    <article className="credential">
      <header className="credential__head">
        <div className="credential__ident">
          <span className="credential__code">{code}</span>
          <h3 className="credential__title">{title}</h3>
        </div>
        <HudGauge value={100} label="Verified" />
      </header>

      <DocumentThumb src={image} alt={alt} onOpen={onOpen} hint={hint} />

      {description && <p className="credential__description">{description}</p>}

      <dl className="credential__facts">
        {facts.map(({ key, value }) => (
          <div key={key} className="credential__fact">
            <dt>{key}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>

      <TickBar value={100} label="Integrity" />
    </article>
  );
}

export default CredentialCard;
