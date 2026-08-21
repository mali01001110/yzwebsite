import Reveal from './Reveal';
import ScrambleText from './ScrambleText';
import { SECTION_IDS } from '../data/navigation';

/**
 * Standard section shell: scroll anchor, HUD heading block and a scroll-reveal
 * animation. The index badge is derived from the navigation order so numbering
 * cannot drift out of sync with the menu.
 */
function Section({ id, title, subtitle, className = '', children }) {
  const position = SECTION_IDS.indexOf(id);
  const index = String(position >= 0 ? position : 0).padStart(2, '0');
  // The hero occupies slot 00 and is not a Section, so the run of numbered
  // sections is one shorter than the navigation.
  const total = String(SECTION_IDS.length - 1).padStart(2, '0');

  return (
    <Reveal as="section" id={id} className={`section ${className}`.trim()}>
      <header className="section__head">
        <span className="section__numeral" aria-hidden="true">
          {index}
        </span>
        <span className="section__index">
          SEC.{index} :: {title}
        </span>
        <ScrambleText as="h2" className="section__title" text={title} />
        <div className="section__rule" />
        <div className="section__meta">
          {subtitle && <p className="section__subtitle">{subtitle}</p>}
          <span className="section__progress" aria-hidden="true">
            {index} / {total}
          </span>
        </div>
      </header>

      <div className="section__body">{children}</div>
    </Reveal>
  );
}

export default Section;
