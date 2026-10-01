import {
  DownloadCloud,
  NotebookPen,
  Globe2,
  Gamepad2,
  Monitor,
  ArrowUpRight,
} from 'lucide-react';
import Section from '../components/Section';
import HudWindow from '../components/HudWindow';
import StaggerGrid from '../components/StaggerGrid';
import TickBar from '../components/TickBar';

const INTRO = `Here are some of the projects I've been working on. Check out the repositories below on GitHub to explore the code.`;

const PROJECTS = [
  {
    name: 'SmartOneDL',
    url: 'https://github.com/mali01001110/SmartOneDL',
    description: 'A basic download manager',
    stack: 'Python // Desktop',
    Icon: DownloadCloud,
  },
  {
    name: 'SmartOneNote',
    url: 'https://github.com/mali01001110/SmartOneNote',
    description: 'A standalone text editor',
    stack: 'Python // Desktop',
    Icon: NotebookPen,
  },
  {
    name: 'Servo Jeu Web',
    url: 'https://github.com/mali01001110/servo-jeu-web',
    description: 'A browser-based servo game built with PixiJS',
    stack: 'JavaScript // PixiJS',
    Icon: Gamepad2,
  },
  {
    name: 'Portfolio Windows Desktop Y2K',
    url: 'https://github.com/mali01001110/Portfolio-Windows-Desktop-Y2K',
    description: 'A portfolio design inspired by retro Windows and Y2K',
    stack: 'React // TypeScript',
    Icon: Monitor,
  },
  {
    name: 'My Personal Website',
    url: 'https://github.com/mali01001110/yzwebsite',
    description: 'Professional portfolio website',
    stack: 'React // Django',
    Icon: Globe2,
  },
];

function MyProjects() {
  return (
    <Section id="projects" title="Projects" subtitle="System deployments // source available">
      <p className="prose">{INTRO}</p>

      <HudWindow
        title="DEPLOYMENTS.EXE"
        tag={`${String(PROJECTS.length).padStart(2, '0')} FOUND`}
      >
        <StaggerGrid className="deploys">
          {PROJECTS.map(({ name, url, description, stack, Icon }, index) => (
            <article key={name} className="deploy">
              <span className="deploy__glyph" aria-hidden="true">
                <Icon size={26} />
              </span>

              <div className="deploy__body">
                <span className="deploy__id">
                  DEPLOY_{String(index + 1).padStart(3, '0')} // {stack}
                </span>
                <h3 className="deploy__name">&gt; {name}</h3>
                <p className="deploy__description">{description}</p>
                <TickBar value={95} label="Build" />
              </div>

              <a
                className="deploy__action"
                href={url}
                target="_blank"
                rel="noopener noreferrer"
              >
                <ArrowUpRight size={22} aria-hidden="true" />
                <span>OPEN</span>
              </a>
            </article>
          ))}
        </StaggerGrid>
      </HudWindow>
    </Section>
  );
}

export default MyProjects;
