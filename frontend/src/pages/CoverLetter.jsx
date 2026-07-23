function CoverLetter() {
  // ️ Replace this with your own cover letter text
  const coverLetterText = `Dear Hiring Manager,

I have a year of experience in the field of commerce plus a professional certification in cybersecurity and also certified in computer science and python programming. 

Therefore, i am hereby applying for a job in the field of software development.

I have received a fairly complete training and i am indeed a trained computer scientist and IT technician.

I am skilled in computer programming especially full-stack software development.

In addition to my training in IT and proficiency in computer science, i also hold an undergraduate degree in law with a good computer literacy in addition to being bilingual French/English.

I am attaching my resume with a hyperlink to my LinkedIn profile for more details.

I am able to help your company achieve its goals, so please consider my job application. Rest assured that I am competent, willing to work, and to help others.

Thank You !`;

  return (
    <section id="cover-letter" className="page">
      <h1>Cover Letter</h1>
      <pre className="letter-text">{coverLetterText}</pre>
    </section>
  );
}

export default CoverLetter;
