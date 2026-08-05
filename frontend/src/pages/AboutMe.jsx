import Section from '../components/Section';

const ABOUT_TEXT = `I am a trained IT professional and software developer.
I have a computer scientist and IT technician profile, certified in computer science, python programming, cybersecurity and a full-stack software developer.
In addition to my background in IT and Computer Science, i also hold an undergraduate degree in Law.
I am bilingual French/English with a strong computer literacy.
I am passionate about technology especially computing and aim to make a meaningful contribution to society.
I am an IT person by vocation, and with that in mind, i am seeking a position that will allow me to grow and fulfill myself socially.`;

const PROFILE_ROWS = [
  { key: 'Role', value: 'Full-stack developer' },
  { key: 'Discipline', value: 'IT Support / Programming' },
  { key: 'Languages', value: 'French / English' },
  { key: 'Education', value: 'CS + Python Certified' },
  { key: 'Location', value: 'Abidjan, Côte d’Ivoire' },
  { key: 'Status', value: 'Open to opportunities' },
];

function AboutMe() {
  return (
    <Section id="about-me" title="About" subtitle="Operator profile // background dump">
      <div className="about">
        <article className="hud-panel hud-panel--cut hud-brackets">
          <span className="hud-label">Profile.log</span>
          <p className="about__text">{ABOUT_TEXT}</p>
        </article>

        <aside className="hud-panel hud-panel--cut hud-brackets about__aside">
          <span className="hud-label">Registry</span>
          <div>
            {PROFILE_ROWS.map((row) => (
              <div key={row.key} className="about__row">
                <span className="about__row-key">{row.key}</span>
                <span className="about__row-value">{row.value}</span>
              </div>
            ))}
          </div>
        </aside>
      </div>
    </Section>
  );
}

export default AboutMe;
