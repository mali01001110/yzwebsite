import { Code2, Globe, Wrench, ShieldCheck, Brain } from 'lucide-react';
import Section from '../components/Section';
import HudWindow from '../components/HudWindow';
import DataRow from '../components/DataRow';
import StaggerGrid from '../components/StaggerGrid';

const SKILL_GROUPS = [
  {
    category: 'Programming Languages',
    file: 'LANG.SYS',
    Icon: Code2,
    items: ['Python', 'JavaScript', 'C'],
  },
  {
    category: 'Web Technologies',
    file: 'WEB.SYS',
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
    file: 'TOOLS.SYS',
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
    file: 'SUPPORT.SYS',
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
    file: 'HUMAN.SYS',
    Icon: Brain,
    items: ['Resilience', 'Critical thinking', 'Problem-solving', 'Solo work'],
  },
];

function Skills() {
  return (
    <Section id="skills" title="Skills" subtitle="Capability matrix // modules loaded">
      <div className="skills">
        {SKILL_GROUPS.map(({ category, file, Icon, items }) => (
          <HudWindow
            key={category}
            title={file}
            tag={`${String(items.length).padStart(2, '0')} MODULES`}
          >
            <header className="skills__head">
              <span className="skills__glyph" aria-hidden="true">
                <Icon size={18} />
              </span>
              <h3 className="skills__title">{category}</h3>
            </header>

            <StaggerGrid className="skills__rows" threshold={0.05}>
              {items.map((skill, index) => (
                <DataRow
                  key={skill}
                  index={String(index + 1).padStart(2, '0')}
                  label={skill}
                  actionLabel="LOADED"
                  glyph="✓"
                />
              ))}
            </StaggerGrid>
          </HudWindow>
        ))}
      </div>
    </Section>
  );
}

export default Skills;
