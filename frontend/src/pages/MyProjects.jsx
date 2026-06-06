function MyProjects() {
  // ️ Replace the URLs with your actual GitHub repo links
  const intro = `
    Here are some of the projects I've been working on. Check out the
    repositories below on GitHub to explore the code.
  `;

  const projects = [
    {
      name: 'SmartOneText',
      url: 'https://github.com/mali01001110/smartonetext',
      description: 'An anonymous message web app',
    },
    {
      name: 'SmartOneNote',
      url: 'https://github.com/mali01001110/SmartOneNote',
      description: 'A standalone text editor',
    },
    {
      name: 'My Personal Website',
      url: 'https://github.com/mali01001110/yzwebsite',
      description: 'Professional portfolio website',
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
