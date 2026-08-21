import BrandIcon from './BrandIcon';

/**
 * The "LIMITS FOUND" row from the reference: index, label, optional meta, a
 * bracketed action tag and a trailing glyph. Renders as a link when `href` is
 * supplied, otherwise as a static record.
 *
 * The leading slot takes either a platform mark (`brand`) or a generic UI
 * glyph (`Icon`), never both — a row that names a platform should carry that
 * platform's logo, and everything else gets the house icon set.
 */
function DataRow({ index, label, meta, actionLabel, glyph = '✓', href, Icon, brand }) {
  const body = (
    <>
      {index && (
        <span className="data-row__index" aria-hidden="true">
          {index}
        </span>
      )}

      {(brand || Icon) && (
        <span className="data-row__icon" aria-hidden="true">
          {brand ? <BrandIcon name={brand} size={16} /> : <Icon size={16} />}
        </span>
      )}

      <span className="data-row__main">
        <span className="data-row__label">{label}</span>
        {meta && <span className="data-row__meta">{meta}</span>}
      </span>

      {actionLabel && <span className="data-row__action">{actionLabel}</span>}

      <span className="data-row__glyph" aria-hidden="true">
        {glyph}
      </span>
    </>
  );

  if (!href) {
    return <div className="data-row">{body}</div>;
  }

  const isExternal = href.startsWith('http');

  return (
    <a
      className="data-row data-row--link"
      href={href}
      {...(isExternal ? { target: '_blank', rel: 'noopener noreferrer' } : {})}
    >
      {body}
    </a>
  );
}

export default DataRow;
