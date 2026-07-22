function AboutMe() {
  // ️ Replace this with your own "About Me" text
  const aboutMeText = `
I am a trained IT professional and software developer.
I have a computer scientist and IT technician profile, certified in computer science, python programming, cybersecurity and a full-stack software developer.
In addition to my background in IT and Computer Science, I also hold an undergraduate degree in Law.
I am bilingual French/English with a strong computer literacy.
I am passionate about technology especially computing and aim to make a meaningful contribution to society.
I am an IT person by vocation, and with that in mind, I am seeking a position that will allow me to grow and fulfill myself socially.
  `;

  return (
    <section id="about-me" className="page">
      <h1>About Me</h1>
      <p>{aboutMeText}</p>
    </section>
  );
}

export default AboutMe;