import AboutMe from './AboutMe';
import Resume from './Resume';
import CoverLetter from './CoverLetter';
import Education from './Education';
import Certifications from './Certifications';
import Skills from './Skills';
import SocialMediaProfiles from './SocialMediaProfiles';
import MyProjects from './MyProjects';
import Contact from './Contact';

function Home() {
  // ️ Replace the text below with your own short bio
  const summary = `
    Hello, World! I'm Yann Zakpa, and I am passionate about computing with a solid foundation in IT support and software development for web and desktop apps.
  `;

  return (
    <>
      <section id="home" className="home">
        <div className="hero hero-no-image">
          <div className="hero-text">
            <h1>Welcome</h1>
            <p>{summary}</p>
          </div>
        </div>
      </section>

      <div className="spa-content">
        <AboutMe />
        <Resume />
        <CoverLetter />
        <Education />
        <Certifications />
        <Skills />
        <SocialMediaProfiles />
        <MyProjects />
        <Contact />
      </div>
    </>
  );
}

export default Home;
