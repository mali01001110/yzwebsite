import { useEffect, useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Menu, X, ArrowUp } from 'lucide-react';
import BackgroundFx from './BackgroundFx';
import CursorReticle from './CursorReticle';
import SystemRail from './SystemRail';
import HudTicker from './HudTicker';
import ProtocolSwitch from './ProtocolSwitch';
import ProtocolLoader from './ProtocolLoader';
import BrandIcon from './BrandIcon';
import { NAV_ITEMS, SECTION_IDS } from '../data/navigation';
import { SOCIAL_URLS } from '../data/social';
import { useActiveSection } from '../hooks/useActiveSection';
import { useTheme } from '../hooks/useTheme';
import { useLanguage } from '../hooks/useLanguage';

// Platform profiles only. Email is deliberately absent: it is a contact
// channel rather than a profile, and the Contact section already gives it a
// labelled row alongside phone and WhatsApp.
const FOOTER_LINKS = [
  { href: SOCIAL_URLS.linkedin, label: 'LinkedIn', brand: 'linkedin' },
  { href: SOCIAL_URLS.github, label: 'GitHub', brand: 'github' },
  { href: SOCIAL_URLS.facebook, label: 'Facebook', brand: 'facebook' },
  { href: SOCIAL_URLS.instagram, label: 'Instagram', brand: 'instagram' },
  { href: SOCIAL_URLS.youtube, label: 'YouTube', brand: 'youtube' },
  { href: SOCIAL_URLS.tiktok, label: 'TikTok', brand: 'tiktok' },
];

const TICKER_ITEMS = [
  'FULL-STACK DEVELOPER',
  '///',
  'IT TECHNICIAN',
  '///',
  'CS50X + CS50P CERTIFIED',
  '///',
  'PYTHON / JAVASCRIPT / C',
  '///',
  'DJANGO / REACT / POSTGRESQL',
  '///',
  'BLUE TEAM SPECIALIST',
  '///',
  'STATUS: OPEN TO OPPORTUNITIES',
  '///',
];

function Layout() {
  const [isNavOpen, setIsNavOpen] = useState(false);
  const [activeSection, setActiveSection] = useActiveSection(SECTION_IDS);
  const { isDay, isSwitching, switchingTo, toggle } = useTheme();
  const { language, toggleLanguage, translate: t } = useLanguage();

  useEffect(() => {
    if (!isNavOpen) return undefined;

    const closeOnEscape = (event) => {
      if (event.key === 'Escape') setIsNavOpen(false);
    };

    document.addEventListener('keydown', closeOnEscape);
    return () => document.removeEventListener('keydown', closeOnEscape);
  }, [isNavOpen]);

  return (
    <>
      {/* First element in the tab order. The site is a single scrolling page
          behind a ten-item menu, so without this a keyboard visitor tabs the
          whole navigation before reaching any content. */}
      <a className="skip-link" href="#main-content">
        {t('Skip to content')}
      </a>

      <BackgroundFx />
      <CursorReticle />
      <SystemRail />
      <ProtocolLoader isSwitching={isSwitching} target={switchingTo} />

      <div className="layout">
        <header className="header">
          <div className="header__inner">
            <a href="#home" className="brand" onClick={() => setIsNavOpen(false)}>
              {/* The favicon file itself, so the mark in the header and the
                  mark in the browser tab cannot drift apart. Decorative: the
                  operator's name sits right beside it. */}
              <img className="brand__mark" src="/favicon.svg" alt="" width="32" height="32" />
              <span className="brand__text">
                <span className="brand__name">YANN ZAKPA</span>
                <span className="brand__role">{t('Dev // IT Systems')}</span>
              </span>
            </a>

            <div className="header__controls">
              <ProtocolSwitch isDay={isDay} isSwitching={isSwitching} onToggle={toggle} />
              <button
                type="button"
                className="language-switch"
                onClick={toggleLanguage}
                aria-label={t(language === 'en' ? 'Switch language to French' : 'Switch language to English')}
                title={t(language === 'en' ? 'Switch language to French' : 'Switch language to English')}
              >
                <span className="language-switch__label" aria-hidden="true">{t('LANG')}</span>
                <span className="language-switch__value" aria-hidden="true">{language.toUpperCase()}</span>
              </button>
            </div>

            <button
              type="button"
              className="nav-toggle"
              onClick={() => setIsNavOpen((open) => !open)}
              aria-expanded={isNavOpen}
              aria-controls="primary-navigation"
              aria-label={t(isNavOpen ? 'Close navigation' : 'Open navigation')}
            >
              {isNavOpen ? <X size={18} /> : <Menu size={18} />}
            </button>

            <nav
              id="primary-navigation"
              className={`nav ${isNavOpen ? 'is-open' : ''}`.trim()}
              aria-label={t('Main navigation')}
            >
              {NAV_ITEMS.map((item) => (
                <a
                  key={item.id}
                  href={`#${item.id}`}
                  className={`nav__link ${activeSection === item.id ? 'is-active' : ''}`.trim()}
                  aria-current={activeSection === item.id ? 'true' : undefined}
                  onClick={() => {
                    setIsNavOpen(false);
                    setActiveSection(item.id);
                  }}
                >
                  {t(item.label)}
                </a>
              ))}
            </nav>
          </div>
        </header>

        <main className="main-content" id="main-content" tabIndex={-1}>
          <Outlet />
        </main>

        <div className="footer-ticker">
          <HudTicker items={TICKER_ITEMS.map(t)} />
        </div>

        <footer className="footer">
          <div className="footer__inner">
            <span className="footer__note">
              © {new Date().getFullYear()} — Smartone Metaware
            </span>

            <div className="footer__socials">
              {FOOTER_LINKS.map(({ href, label, brand }) => (
                <a
                  key={label}
                  href={href}
                  className="footer__social"
                  aria-label={label}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <BrandIcon name={brand} size={16} />
                </a>
              ))}
            </div>

            <div className="footer__end">
              <span className="footer__note">
                <span className="hud-status-dot" aria-hidden="true" /> {t('System online')}
              </span>

              <a className="back-to-top" href="#home">
                <ArrowUp size={13} aria-hidden="true" />
                {t('Top')}
              </a>
            </div>
          </div>
        </footer>
      </div>
    </>
  );
}

export default Layout;
