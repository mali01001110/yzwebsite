import { MessageSquareLock, NotebookPen, Globe2, ArrowUpRight } from 'lucide-react';
import Section from '../components/Section';

const INTRO = `Here are some of the projects I've been working on. Check out the repositories below on GitHub to explore the code.`;

const PROJECTS = [
  {
    name: 'SmartOneText',
    url: 'https://github.com/mali01001110/smartonetext',
    description: 'An anonymous message web app',
    stack: 'Django // React',
    Icon: MessageSquareLock,
  },
  {
    name: 'SmartOneNote',
    url: 'https://github.com/mali01001110/SmartOneNote',
    description: 'A standalone text editor',
    stack: 'Python // Desktop',
    Icon: NotebookPen,
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

      <div className="projects-grid">
        {PROJECTS.map(({ name, url, description, stack, Icon }, index) => (
          <article key={name} className="hud-panel hud-panel--cut hud-brackets project-card">
            <header className="project-card__head">
              <span>Deploy_{String(index + 1).padStart(3, '0')}</span>
              <span>{stack}</span>
            </header>

            <div className="project-card__screen">
              <Icon size={46} strokeWidth={1.2} className="project-card__glyph" aria-hidden="true" />
            </div>

            <div>
              <h3 className="project-card__name">{name}</h3>
              <p className="project-card__description">{description}</p>
            </div>

            <a
              href={url}
              className="project-card__link"
              target="_blank"
              rel="noopener noreferrer"
            >
              View deployment
              <ArrowUpRight size={14} aria-hidden="true" />
            </a>

            <div className="project-card__meter" aria-hidden="true">
              <div className="project-card__meter-label">
                <span>Loading</span>
                <span>95%</span>
              </div>
              <div className="hud-meter">
                <div className="hud-meter__fill hud-meter__fill--cycle" />
              </div>
            </div>
          </article>
        ))}
      </div>
    </Section>
  );
}

export default MyProjects;
