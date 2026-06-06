// src/components/Layout.jsx
import React from 'react';
import { Outlet, Link, useLocation } from 'react-router-dom';
import bgImage from '../assets/site-background.jpg';

function Layout() {
  const location = useLocation();
  const isHome = location.pathname === '/';

  const layoutStyle = {
    position: 'relative',
    minHeight: '100vh',
    width: '100%',
    overflow: 'hidden',
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

  const foregroundStyle = { position: 'relative', zIndex: 2 };

  return (
    <div className="layout" style={layoutStyle}>
      <div className="layout-overlay" style={overlayStyle} aria-hidden="true" />

      <header className="header" style={foregroundStyle}>
        <Link to="/" className="header-title">Yann Zakpa</Link>
      </header>

      <main className="main-content" style={foregroundStyle}>
        {!isHome && (
          <Link
            to="/"
            className="back-button"
            style={{ display: 'inline-block', marginBottom: '1rem' }}
          >
            ← Back to Home
          </Link>
        )}
        <Outlet />
      </main>

      <footer className="footer" style={{ ...foregroundStyle, marginTop: '2rem' }}>
        <p>© {new Date().getFullYear()} — Personal Website</p>
      </footer>
    </div>
  );
}

export default Layout;
