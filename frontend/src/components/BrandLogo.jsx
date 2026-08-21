/**
 * Full-colour company logos, in their official geometry and palette.
 *
 * These are the real marks — Orange's square and wordmark, WhatsApp's glyph,
 * the five-segment Gmail envelope — not house redraws. Path data is copied
 * verbatim from the vendors' published vectors, so the shapes and the hex
 * values are theirs rather than an approximation of them. Only whitespace has
 * been normalised: SVG treats newlines and tabs inside `d` as separators, so
 * collapsing them changes nothing but lets each shape sit on one line.
 *
 * Used only where a channel has to be identified by its provider, which today
 * means the CHANNELS.SYS panel. Everywhere else — the footer, CHANNELS.NET —
 * platforms are drawn as monochrome silhouettes that take the protocol hue;
 * see BrandIcon. Two components rather than a colour flag on one, because the
 * two carry different data: a silhouette is one path, a logo is a palette.
 *
 * A viewBox is kept per logo instead of normalising to a 24 grid — Gmail's is
 * 4:3 and Orange's is square, and rescaling them to a common box would either
 * distort the marks or crop them.
 */
const BRAND_LOGOS = {
  orange: {
    viewBox: '0 0 283.5 283.5',
    shapes: [
      { fill: '#FF7900', d: 'M0 0h283.5v283.5H0z' },
      { fill: '#FFFFFF', d: 'M111.2,256c-4,2.6-8.4,3.9-13,3.9c-7.4,0-11.7-4.9-11.7-11.5c0-8.8,8.1-13.5,24.8-15.4v-2.2 c0-2.9-2.2-4.5-6.2-4.5c-4,0-7.3,1.6-9.6,4.5l-7-4c3.7-5.1,9.3-7.7,16.8-7.7c10.3,0,16.1,4.5,16.1,11.7c0,0,0,28.5,0,28.6h-9.2 L111.2,256z M96.6,247.7c0,2.6,1.7,5.1,4.7,5.1c3.3,0,6.4-1.4,9.6-4.2v-9.3C101.2,240.6,96.6,243,96.6,247.7z' },
      { fill: '#FFFFFF', d: 'M129.5,221.1l8.6-1.2l0.9,4.7c4.9-3.5,8.7-5.4,13.6-5.4c8.1,0,12.3,4.3,12.3,12.8v27.5h-10.4v-25.7 c0-4.8-1.3-7-5-7c-3.1,0-6.2,1.4-9.7,4.4v28.3h-10.3V221.1z' },
      { fill: '#FFFFFF', d: 'M233.7,260.2c-11.6,0-18.6-7.5-18.6-20.5c0-13.1,7-20.6,18.4-20.6c11.4,0,18.2,7.2,18.2,20.1 c0,0.7-0.1,1.4-0.1,2h-26.3c0.1,7.5,3.2,11.2,9.3,11.2c3.9,0,6.5-1.6,8.9-5.1l7.6,4.2C247.8,257.2,241.8,260.2,233.7,260.2z M241.5,234.5c0-5.3-3-8.4-7.9-8.4c-4.7,0-7.6,3-8,8.4H241.5z' },
      { fill: '#FFFFFF', d: 'M34.9,260.6c-10.3,0-19.5-6.5-19.5-20.8c0-14.3,9.3-20.8,19.5-20.8c10.3,0,19.5,6.5,19.5,20.8 C54.4,254.1,45.2,260.6,34.9,260.6z M34.9,227.7c-7.7,0-9.2,7-9.2,12c0,5.1,1.4,12,9.2,12c7.8,0,9.2-7,9.2-12 C44.1,234.7,42.6,227.7,34.9,227.7z' },
      { fill: '#FFFFFF', d: 'M61.5,220h9.9v4.6c1.9-2.5,6.5-5.5,10.9-5.5c0.4,0,0.9,0,1.3,0.1v9.7c-0.2,0-0.3,0-0.5,0 c-4.5,0-9.5,0.7-11,4.2v26.2H61.5V220z' },
      { fill: '#FFFFFF', d: 'M190.3,251c7.9-0.1,8.5-8.1,8.5-13.3c0-6.2-3-11.2-8.6-11.2c-3.7,0-7.9,2.7-7.9,11.6 C182.4,243,182.7,251,190.3,251z M208.9,219.9v37.4c0,6.6-0.5,17.4-19.3,17.6c-7.8,0-14.9-3.1-16.4-9.8l10.2-1.6 c0.4,1.9,1.6,3.9,7.4,3.9c5.4,0,8-2.6,8-8.7v-4.6l-0.1-0.1c-1.6,2.9-4.2,5.7-10.2,5.7c-9.2,0-16.4-6.4-16.4-19.7 c0-13.2,7.5-20.6,15.9-20.6c7.9,0,10.8,3.6,11.5,5.5l-0.1,0l0.9-4.7H208.9z' },
      { fill: '#FFFFFF', d: 'M255.7,206.8h-4.1v11.3h-2.2v-11.3h-4.1v-1.7h10.3V206.8z M272.7,218.1h-2.2v-10.9h-0.1l-4.3,10.9h-1.4 l-4.3-10.9h-0.1v10.9h-2.2v-13h3.3l3.9,9.9l3.8-9.9h3.3V218.1z' },
    ],
  },
  whatsapp: {
    viewBox: '0 0 24 24',
    shapes: [
      { fill: '#25D366', d: 'M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413Z' },
    ],
  },
  gmail: {
    viewBox: '52 42 88 66',
    shapes: [
      { fill: '#4285F4', d: 'M58 108h14V74L52 59v43c0 3.32 2.69 6 6 6' },
      { fill: '#34A853', d: 'M120 108h14c3.32 0 6-2.69 6-6V59l-20 15' },
      { fill: '#FBBC04', d: 'M120 48v26l20-15v-8c0-7.42-8.47-11.65-14.4-7.2' },
      { fill: '#EA4335', d: 'M72 74V48l24 18 24-18v26L96 92' },
      { fill: '#C5221F', d: 'M52 51v8l20 15V48l-5.6-4.2c-5.94-4.45-14.4-.22-14.4 7.2' },
    ],
  },
};

function BrandLogo({ name, size = 22, className = '' }) {
  const logo = BRAND_LOGOS[name];
  if (!logo) return null;

  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox={logo.viewBox}
      aria-hidden="true"
      focusable="false"
    >
      {logo.shapes.map((shape) => (
        <path key={shape.d} fill={shape.fill} d={shape.d} />
      ))}
    </svg>
  );
}

export default BrandLogo;
