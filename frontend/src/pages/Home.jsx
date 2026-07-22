import AboutMe from './AboutMe';
import Resume from './Resume';
import CoverLetter from './CoverLetter';
import Education from './Education';
import Certifications from './Certifications';
import Skills from './Skills';
import SocialMediaProfiles from './SocialMediaProfiles';
import MyProjects from './MyProjects';

function Home() {
  // ️ Replace the text below with your own short bio
  const summary = `
    Hello, World! I'm Yann Zakpa, and i am passionate about computing with a strong background in IT support and software development web/desktop apps.
  `;

  return (
    <section id="home" className="home">
      <div className="hero hero-no-image">
        <h1>Welcome</h1>
        <p>{summary}</p>
      </div>

      <div className="spa-content">
        <AboutMe />
        <Resume />
        <CoverLetter />
        <Education />
        <Certifications />
        <Skills />
        <SocialMediaProfiles />
        <MyProjects />
      </div>
    </section>
  );
}

export default Home;
