import Section from '../components/Section';
import HudWindow from '../components/HudWindow';
import LogBox from '../components/LogBox';
import InfoPanel from '../components/InfoPanel';
import TickBar from '../components/TickBar';

const ABOUT_LINES = [
  'Trained IT professional and software developer.',
  'Computer scientist and IT technician profile — certified in computer science, python programming and cybersecurity.',
  'Full-stack software developer.',
  'Also holds an undergraduate degree in Law.',
  'Bilingual French / English with strong computer literacy.',
  'Passionate about technology, aiming to make a meaningful contribution to society.',
  'An IT person by vocation, seeking a position to grow and fulfil myself socially.',
];

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
        <HudWindow title="PROFILE.LOG" tag="READ-ONLY" className="about__log">
          <LogBox label="Dump" lines={ABOUT_LINES} />
        </HudWindow>

        <aside className="about__side">
          <InfoPanel title="Information" rows={PROFILE_ROWS} />
          <div className="about__meter">
            <TickBar value={100} label="Record integrity" />
          </div>
        </aside>
      </div>
    </Section>
  );
}

export default AboutMe;
