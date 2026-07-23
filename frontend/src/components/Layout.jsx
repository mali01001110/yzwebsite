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
  { label: 'Social', id: 'social' },
  { label: 'Projects', id: 'projects' },
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

    // Track observed IDs so we don't observe the same element multiple times
    const observed = new Set();

    function updateSections() {
      const sections = sectionIds
        .map(id => document.getElementById(id))
        .filter(Boolean);

      sections.forEach(section => {
        if (!observed.has(section.id)) {
          observer.observe(section);
          observed.add(section.id);
        }
      });
    }

    // Initial attempt to observe any already-mounted sections
    updateSections();

    // Use a MutationObserver to detect when new section elements are mounted
    // (React may mount child routes/elements after this effect runs).
    const mo = new MutationObserver(() => {
      updateSections();
    });

    mo.observe(document.body, { childList: true, subtree: true });

    return () => {
      observer.disconnect();
      mo.disconnect();
    };
  }, []);

  // Navigation should not hide other sections. Keep all sections visible so the site behaves like a standard
  // single-page site where content is reachable by normal scrolling (not by toggling visibility).
  // The previous showOnlySection function was removed to allow natural scrolling between sections.

  function handleNavClick(e, id) {
    e.preventDefault();
    const section = document.getElementById(id);
    if (!section) return;

    // Do not hide other sections; just scroll to the requested section while keeping everything visible

    const header = document.querySelector('.header');
    const headerH = header ? header.getBoundingClientRect().height : 0;
    const viewportH = window.innerHeight;
    const availableH = Math.max(0, viewportH - headerH);

    // If the whole section fits within the available area, center the whole section
    const sectionH = section.offsetHeight;
    if (sectionH <= availableH) {
      // Apply a stronger upward bias for specific sections so the title/content sit higher
      const liftUpIds = new Set([
        'about-me',
        'resume',
        'cover-letter',
        'education',
        'certifications',
        'skills',
        'social',
        'projects',
      ]);
      const bias = liftUpIds.has(id) ? 0.35 : 0.45; // smaller bias => content appears higher

      const topOffset = Math.max(0, section.offsetTop - headerH - Math.round((availableH - sectionH) * bias));
      window.scrollTo({ top: topOffset, behavior: 'smooth' });
      setActiveSection(id);
      return;
    }

    // Otherwise prefer the section's title when present so we can center the title visually
    const title = section.querySelector('h1, h2, h3');
    let titleTopDoc = section.offsetTop;
    let titleH = 0;
    if (title) {
      const rect = title.getBoundingClientRect();
      titleTopDoc = window.scrollY + rect.top;
      titleH = rect.height || 0;
    }

    // Position the title a bit above strict center so it reads as visually centered (40% down)
    const desiredTitleCenter = headerH + Math.round(availableH * 0.4);
    const scrollTo = Math.max(0, titleTopDoc - desiredTitleCenter + Math.round(titleH / 2));

    window.scrollTo({ top: scrollTo, behavior: 'smooth' });
    setActiveSection(id);
  }

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
              onClick={(e) => handleNavClick(e, item.id)}
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
