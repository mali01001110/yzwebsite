import resumeImage from '../assets/resume.jpg';

function Resume() {
  return (
    <section className="page">
      <h1>Resume</h1>
      <img
        src={resumeImage}
        alt="Scanned image of [Your Name]'s resume showing work experience and skills"
        className="full-image"
      />
    </section>
  );
}

export default Resume;