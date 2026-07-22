// src/components/Layout.jsx
import { useState, useEffect } from 'react';
import { Outlet, Link } from 'react-router-dom';
import bgImage from '../assets/site-background.jpg';

const navItems = [
  { label: 'Home', id: 'home' },
  { label: 'About Me', id: 'about-me' },
  { label: 'Resume', id: 'resume' },
  { label: 'Cover Letter', id: 'cover-letter' },
  { label: 'Education', id: 'education' },
  { label: 'Certifications', id: 'certifications' },
  { label: 'Skills', id: 'skills' },
  { label: 'Social Media Profiles', id: 'social-media-profiles' },
  { label: 'My Projects', id: 'my-projects' },
];

function Layout() {
  const [activeSection, setActiveSection] = useState('home');

  const layoutStyle = {
    position: 'relative',
    minHeight: '100vh',
    width: '100%',
    backgroundImage: `url(${bgImage})`,
    backgroundSize: 'cover',
    backgroundPosition: 'center center',
    backgroundRepeat: 'no-repeat',
    backgroundAttachment: 'fixed',
  };

  const overlayStyle = {
    position: 'absolute',
    inset: 0,
    background: 'rgba(0,0,0,0.35)',
    zIndex: 0,
    pointerEvents: 'none',
  };

  const foregroundStyle = { position: 'relative', zIndex: 1 };
  const headerStyle = { position: 'fixed', top: 0, left: 0, right: 0, zIndex: 2000 };

  useEffect(() => {
    const sectionIds = navItems.map(item => item.id);
    const sections = sectionIds
      .map(id => document.getElementById(id))
      .filter(Boolean);

    if (!sections.length) {
      return undefined;
    }

    const observer = new IntersectionObserver(
      entries => {
        const visibleEntries = entries
          .filter(entry => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio);

        if (visibleEntries.length > 0) {
          setActiveSection(visibleEntries[0].target.id);
        }
      },
      {
        root: null,
        rootMargin: '0px 0px -55% 0px',
        threshold: [0.25, 0.5, 0.75],
      }
    );

    sections.forEach(section => observer.observe(section));

    return () => observer.disconnect();
  }, []);

  return (
    <div className="layout" style={layoutStyle}>
      <div className="layout-overlay" style={overlayStyle} aria-hidden="true" />

      <header className="header" style={headerStyle}>
        <div className="header-top">
          <Link to="/" className="header-title">Yann Zakpa</Link>
        </div>

        <nav className="top-nav" aria-label="Main navigation">
          {navItems.map(item => (
            <a
              key={item.id}
              href={`/#${item.id}`}
              className={`top-nav-link ${activeSection === item.id ? 'active' : ''}`}
            >
              {item.label}
            </a>
          ))}
        </nav>
      </header>

      <main className="main-content" style={foregroundStyle}>
        <Outlet />
      </main>

      <footer className="footer" style={{ ...foregroundStyle, marginTop: '2rem' }}>
        <p>© {new Date().getFullYear()} — Smartone Metaware</p>
      </footer>
    </div>
  );
}

export default Layout;
