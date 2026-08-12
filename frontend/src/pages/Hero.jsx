import { motion } from 'framer-motion';
import { ChevronsDown, Send, Terminal } from 'lucide-react';
import HudButton from '../components/HudButton';
import SystemAlert from '../components/SystemAlert';
import Countdown from '../components/Countdown';
import HudGauge from '../components/HudGauge';
import BootLog from '../components/BootLog';

const SUMMARY = `Hello, World! I'm Yann Zakpa, and I am passionate about computing with a solid foundation in IT support and software development for web and desktop apps.`;

const BOOT_LOG = [
  'BOOT SEQUENCE COMPLETE',
  'MOUNTING OPERATOR PROFILE // YZ',
  'MODULES ONLINE: DEV / SUPPORT / SECURITY',
  'AWAITING INPUT',
];

const STATS = [
  { value: '03', label: 'Public repos' },
  { value: '02', label: 'Harvard CS50 certs' },
  { value: 'FR / EN', label: 'Bilingual' },
  { value: 'Law Degree', label: 'Bac +2' },
];

// Decorative terminal telemetry — machine readouts, not skill ratings.
const GAUGES = [
  { value: 98, label: 'Signal' },
  { value: 87, label: 'Integrity' },
  { value: 76, label: 'Load' },
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
        <span className="hero__numeral" aria-hidden="true">
          00
        </span>

        <motion.div className="hero__window" {...RISE}>
          <div className="hero__window-bar">
            <span className="hero__window-title">&gt;&gt; YANN_ZAKPA.EXE</span>
            <span className="hero__window-tag">SEC.00 :: HOME</span>
            <span className="hero__window-glyphs" aria-hidden="true">
              <span>_</span>
              <span>□</span>
              <span>✕</span>
            </span>
          </div>

          <div className="hero__grid">
            <div className="hero__main">
              <motion.span
                className="hero__eyebrow"
                {...RISE}
                transition={{ ...RISE.transition, delay: 0.08 }}
              >
                <span className="hud-status-dot" aria-hidden="true" />
                Open to opportunities // Abidjan, CI
              </motion.span>

              <motion.h1
                className="glitch"
                data-text="YANN ZAKPA"
                {...RISE}
                transition={{ ...RISE.transition, delay: 0.14 }}
              >
                YANN ZAKPA
              </motion.h1>

              <motion.p
                className="hero__subtitle"
                {...RISE}
                transition={{ ...RISE.transition, delay: 0.2 }}
              >
                Full-Stack Developer // IT Technician
              </motion.p>

              <motion.p
                className="hero__summary"
                {...RISE}
                transition={{ ...RISE.transition, delay: 0.26 }}
              >
                {SUMMARY}
              </motion.p>

              <motion.div {...RISE} transition={{ ...RISE.transition, delay: 0.32 }}>
                <BootLog lines={BOOT_LOG} />
              </motion.div>

              <motion.div
                className="hero__actions"
                {...RISE}
                transition={{ ...RISE.transition, delay: 0.38 }}
              >
                <HudButton href="#projects">
                  <Terminal size={15} aria-hidden="true" />
                  Execute // view projects
                </HudButton>
                <HudButton href="#contact" variant="ghost">
                  <Send size={15} aria-hidden="true" />
                  Initiate contact
                </HudButton>
              </motion.div>

              <motion.div
                className="hero__stats"
                {...RISE}
                transition={{ ...RISE.transition, delay: 0.44 }}
              >
                {STATS.map((stat) => (
                  <div key={stat.label} className="hero__stat">
                    <div className="hero__stat-value">{stat.value}</div>
                    <div className="hero__stat-label">{stat.label}</div>
                  </div>
                ))}
              </motion.div>
            </div>

            <motion.aside
              className="hero__side"
              {...RISE}
              transition={{ ...RISE.transition, delay: 0.5 }}
            >
              <SystemAlert code="001_ALERT" title="System limits detected">
                Comfort zone flagged as critical. Override protocol engaged — recruiting
                channel is open.
              </SystemAlert>

              <div className="hero__module">
                <Countdown label="Next sync cycle" />
              </div>

              <div className="hero__module">
                <span className="hud-label">Diagnostics</span>
                <div className="hero__gauges">
                  {GAUGES.map((gauge) => (
                    <HudGauge key={gauge.label} value={gauge.value} label={gauge.label} drifts />
                  ))}
                </div>
              </div>
            </motion.aside>
          </div>

          <div className="hazard-bar" aria-hidden="true" />
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
