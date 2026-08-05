import { useEffect, useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Hexagon, Menu, X, BriefcaseBusiness, Users, GitBranch, Mail } from 'lucide-react';
import BackgroundFx from './BackgroundFx';
import { NAV_ITEMS, SECTION_IDS } from '../data/navigation';
import { useActiveSection } from '../hooks/useActiveSection';

const FOOTER_LINKS = [
  {
    href: 'https://www.linkedin.com/in/mali01001110/',
    label: 'LinkedIn',
    Icon: BriefcaseBusiness,
  },
  { href: 'https://github.com/mali01001110', label: 'GitHub', Icon: GitBranch },
  {
    href: 'https://www.facebook.com/profile.php?id=61586600751798',
    label: 'Facebook',
    Icon: Users,
  },
  { href: 'mailto:yannzakpa@gmail.com', label: 'Email', Icon: Mail },
];

function Layout() {
  const [isNavOpen, setIsNavOpen] = useState(false);
  const activeSection = useActiveSection(SECTION_IDS);

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
      <BackgroundFx />

      <div className="layout">
        <header className="header">
          <div className="header__inner">
            <a href="#home" className="brand" onClick={() => setIsNavOpen(false)}>
              <span className="brand__mark" aria-hidden="true">
                <Hexagon size={16} strokeWidth={1.5} />
              </span>
              <span className="brand__text">
                <span className="brand__name">YANN ZAKPA</span>
                <span className="brand__role">Dev // IT Systems</span>
              </span>
            </a>

            <button
              type="button"
              className="nav-toggle"
              onClick={() => setIsNavOpen((open) => !open)}
              aria-expanded={isNavOpen}
              aria-controls="primary-navigation"
              aria-label={isNavOpen ? 'Close navigation' : 'Open navigation'}
            >
              {isNavOpen ? <X size={18} /> : <Menu size={18} />}
            </button>

            <nav
              id="primary-navigation"
              className={`nav ${isNavOpen ? 'is-open' : ''}`.trim()}
              aria-label="Main navigation"
            >
              {NAV_ITEMS.map((item) => (
                <a
                  key={item.id}
                  href={`#${item.id}`}
                  className={`nav__link ${activeSection === item.id ? 'is-active' : ''}`.trim()}
                  aria-current={activeSection === item.id ? 'true' : undefined}
                  onClick={() => setIsNavOpen(false)}
                >
                  {item.label}
                </a>
              ))}
            </nav>
          </div>
        </header>

        <main className="main-content">
          <Outlet />
        </main>

        <footer className="footer">
          <div className="footer__inner">
            <span className="footer__note">
              © {new Date().getFullYear()} — Smartone Metaware
            </span>

            <div className="footer__socials">
              {FOOTER_LINKS.map(({ href, label, Icon }) => (
                <a
                  key={label}
                  href={href}
                  className="footer__social"
                  aria-label={label}
                  {...(href.startsWith('http')
                    ? { target: '_blank', rel: 'noopener noreferrer' }
                    : {})}
                >
                  <Icon size={16} />
                </a>
              ))}
            </div>

            <span className="footer__note">
              <span className="hud-status-dot" aria-hidden="true" /> System online
            </span>
          </div>
        </footer>
      </div>
    </>
  );
}

export default Layout;
