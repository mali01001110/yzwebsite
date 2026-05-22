function CoverLetter() {
  // ️ Replace this with your own cover letter text
  const coverLetterText = `Dear Hiring Manager,

I have a year of experience in the field of commerce plus professional certifications in network administration and information security and Python programming language. Therefore, I am hereby applying for a job in the field of IT or software development.
I have received a fairly complete training and I am indeed a trained IT technician and also knowledgeable in the field of computer science.
I am also in continuing education to acquire skills in backend web development.
In addition to my Baccalaureate +2 level in IT, I also hold an undergraduate degree In law with a good computer literacy in addition to being bilingual French/English.
I am attaching my CV with a hyperlink to my LinkedIn profile for more details.
I am able to help your company achieve its goals, so please consider my job application. Rest assured that I am competent, willing to work, and to help others.

Sincerely,
Yann Zakpa`;

  return (
    <section className="page">
      <h1>Cover Letter</h1>
      <pre className="letter-text">{coverLetterText}</pre>
    </section>
  );
}

export default CoverLetter;