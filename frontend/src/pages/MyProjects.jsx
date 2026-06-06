function MyProjects() {
  // ️ Replace the URLs with your actual GitHub repo links
  const intro = `
    Here are some of the projects I've been working on. Check out the
    repositories below on GitHub to explore the code.
  `;

  const projects = [
    {
      name: 'Project One',
      url: 'https://github.com/your-username/project-one',
      description: 'A short description of project one',
    },
    {
      name: 'Project Two',
      url: 'https://github.com/your-username/project-two',
      description: 'A short description of project two',
    },
    {
      name: 'Project Three',
      url: 'https://github.com/your-username/project-three',
      description: 'A short description of project three',
    },
  ];

  return (
    <section className="page">
      <h1>My Projects</h1>
      <p>{intro}</p>
      <ul className="social-list">
        {projects.map((project, idx) => (
          <li key={idx}>
            <a href={project.url} target="_blank" rel="noopener noreferrer">
              <strong>{project.name}</strong> — {project.description}
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default MyProjects;