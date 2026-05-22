import { Link } from 'react-router-dom';

function Home() {
  // ️ Replace the text below with your own short bio
  const summary = `
    Hello! I'm Yann Zakpa, and i am passionate computing with a strong background in IT support and software development web/desktop apps.'
  `;

  const buttons = [
    { label: 'About Me', path: '/about-me' },
    { label: 'Resume', path: '/resume' },
    { label: 'Cover Letter', path: '/cover-letter' },
    { label: 'Education', path: '/education' },
    { label: 'Certifications', path: '/certifications' },
    { label: 'Skills', path: '/skills' },
    { label: 'Social Media Profiles', path: '/social-media-profiles' },
  ];

  return (
    <section className="home">
      <div className="hero hero-no-image">
        <h1>Welcome</h1>
        <p>{summary}</p>
      </div>

      <nav className="button-grid">
        {buttons.map(btn => (
          <Link key={btn.path} to={btn.path} className="nav-button">
            {btn.label}
          </Link>
        ))}
      </nav>
    </section>
  );
}

export default Home;