import { motion } from 'framer-motion';
import { ChevronsDown, Send, Terminal } from 'lucide-react';
import HudButton from '../components/HudButton';

const SUMMARY = `Hello, World! I'm Yann Zakpa, and I am passionate about computing with a solid foundation in IT support and software development for web and desktop apps.`;

const STATS = [
  { value: '03', label: 'Public repos' },
  { value: '02', label: 'Harvard CS50 certs' },
  { value: 'FR / EN', label: 'Bilingual' },
  { value: 'Law Degree', label: 'Undergraduate (Bac +2)' },
];

const RISE = {
  initial: { opacity: 0, y: 24 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.7, ease: [0.16, 1, 0.3, 1] },
};

function Hero() {
  return (
    <section id="home" className="hero">
      <div className="hero__inner">
        <motion.span className="hero__eyebrow" {...RISE}>
          <span className="hud-status-dot" aria-hidden="true" />
          Open to opportunities // Abidjan, CI
        </motion.span>

        <motion.h1
          className="glitch"
          data-text="YANN ZAKPA"
          {...RISE}
          transition={{ ...RISE.transition, delay: 0.08 }}
        >
          YANN ZAKPA
        </motion.h1>

        <motion.p
          className="hero__subtitle"
          {...RISE}
          transition={{ ...RISE.transition, delay: 0.16 }}
        >
          Full-Stack Developer // IT Technician
        </motion.p>

        <motion.p
          className="hero__summary"
          {...RISE}
          transition={{ ...RISE.transition, delay: 0.24 }}
        >
          {SUMMARY}
        </motion.p>

        <motion.div
          className="hero__actions"
          {...RISE}
          transition={{ ...RISE.transition, delay: 0.32 }}
        >
          <HudButton href="#projects">
            <Terminal size={15} aria-hidden="true" />
            View projects
          </HudButton>
          <HudButton href="#contact" variant="ghost">
            <Send size={15} aria-hidden="true" />
            Initiate contact
          </HudButton>
        </motion.div>

        <motion.div
          className="hero__stats"
          {...RISE}
          transition={{ ...RISE.transition, delay: 0.4 }}
        >
          {STATS.map((stat) => (
            <div key={stat.label} className="hero__stat">
              <div className="hero__stat-value">{stat.value}</div>
              <div className="hero__stat-label">{stat.label}</div>
            </div>
          ))}
        </motion.div>
      </div>

      <a href="#about-me" className="hero__scroll" aria-label="Scroll to About">
        Scroll
        <ChevronsDown size={16} aria-hidden="true" />
      </a>
    </section>
  );
}

export default Hero;
