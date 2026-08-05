import { Code2, Globe, Wrench, ShieldCheck, Brain } from 'lucide-react';
import Section from '../components/Section';

const SKILL_GROUPS = [
  {
    category: 'Programming Languages',
    Icon: Code2,
    items: ['Python', 'JavaScript', 'C'],
  },
  {
    category: 'Web Technologies',
    Icon: Globe,
    items: [
      'React',
      'Django Web Framework',
      'Django Rest Framework',
      'HTML',
      'CSS',
      'Node.js',
      'PostgreSQL',
    ],
  },
  {
    category: 'Tools & Platforms',
    Icon: Wrench,
    items: [
      'Git',
      'GitHub',
      'Linux',
      'Claude Code',
      'Codex',
      'GitHub Copilot',
      'VS Code',
      'PyCharm',
    ],
  },
  {
    category: 'IT Support Skills',
    Icon: ShieldCheck,
    items: [
      'Computer Maintenance',
      'Windows 11 Hardening',
      'Blue Team Specialist',
      'Computer Networking',
    ],
  },
  {
    category: 'Soft Skills',
    Icon: Brain,
    items: ['Resilience', 'Critical thinking', 'Problem-solving', 'Solo work'],
  },
];

function Skills() {
  return (
    <Section id="skills" title="Skills" subtitle="Capability matrix // modules loaded">
      <div className="skills-grid">
        {SKILL_GROUPS.map(({ category, Icon, items }) => (
          <article key={category} className="hud-panel hud-panel--cut hud-brackets skill-card">
            <header className="skill-card__head">
              <span className="skill-card__hex" aria-hidden="true">
                <Icon size={20} strokeWidth={1.5} />
              </span>
              <div>
                <h3 className="skill-card__title">{category}</h3>
                <span className="skill-card__count">
                  {String(items.length).padStart(2, '0')} entries
                </span>
              </div>
            </header>

            <ul className="skill-card__list">
              {items.map((skill) => (
                <li key={skill} className="hud-tag">
                  {skill}
                </li>
              ))}
            </ul>
          </article>
        ))}
      </div>
    </Section>
  );
}

export default Skills;
