function Skills() {
  // ️ Replace with your real skills
  const skillGroups = [
    {
      category: 'Programming Languages',
      items: ['Python', 'JavaScript'],
    },
    {
      category: 'Web Technologies',
      items: ['React', 'Django Web Framework','Django Rest Framework', 'HTML', 'CSS', 'Node.js', 'PostgreSQL'],
    },
    {
      category: 'Tools & Platforms',
      items: ['Git', 'GitHub', 'Linux', 'Claude Code', 'Codex', 'PyCharm'],
    },
    {
      category: 'IT Support Skills',
      items: ['Computer Maintenance', 'Windows 11 Hardening', 'Blue Team Specialist', 'Computer Networking'],
    },
    {
      category: 'Soft Skills',
      items: ['Teamwork', 'Communication', 'Problem-solving'],
    },
  ];

  return (
    <section className="page">
      <h1>Skills</h1>
      {skillGroups.map((group, idx) => (
        <div key={idx} className="skill-group">
          <h2>{group.category}</h2>
          <ul className="skill-list">
            {group.items.map((skill, i) => (
              <li key={i} className="skill-item">{skill}</li>
            ))}
          </ul>
        </div>
      ))}
    </section>
  );
}

export default Skills;
