import { motion } from 'framer-motion';
import { SECTION_IDS } from '../data/navigation';

const REVEAL = {
  initial: { opacity: 0, y: 28 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, amount: 0.12 },
  transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1] },
};

/**
 * Standard section shell: scroll anchor, HUD heading block and a scroll-reveal
 * animation. The index badge is derived from the navigation order so numbering
 * cannot drift out of sync with the menu.
 */
function Section({ id, title, subtitle, className = '', children }) {
  const position = SECTION_IDS.indexOf(id);
  const index = String(position >= 0 ? position : 0).padStart(2, '0');

  return (
    <motion.section id={id} className={`section ${className}`.trim()} {...REVEAL}>
      <header className="section__head">
        <span className="section__index">
          sec.{index} // {title}
        </span>
        <h2 className="section__title">{title}</h2>
        <div className="section__rule" />
        {subtitle && <p className="section__subtitle">{subtitle}</p>}
      </header>

      <div className="section__body">{children}</div>
    </motion.section>
  );
}

export default Section;
