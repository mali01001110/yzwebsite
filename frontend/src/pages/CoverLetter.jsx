import Section from '../components/Section';

const COVER_LETTER_TEXT = `Dear Hiring Manager,

I have a year of experience in the field of commerce plus a professional certification in cybersecurity and also certified in computer science and python programming.

Therefore, i am hereby applying for a job in the field of software development.

I have received a fairly complete training and i am indeed a trained computer scientist and IT technician.

I am skilled in computer programming especially full-stack software development.

In addition to my training in IT and proficiency in computer science, i also hold an undergraduate degree in law with a good computer literacy in addition to being bilingual French/English.

I am attaching my resume with a hyperlink to my LinkedIn profile for more details.

I am able to help your company achieve its goals, so please consider my job application. Rest assured that I am competent, willing to work, and to help others.

Thank You !`;

function CoverLetter() {
  return (
    <Section id="cover-letter" title="Letter" subtitle="Transmission // cover letter">
      <div className="terminal">
        <div className="terminal__bar">
          <span className="terminal__dots" aria-hidden="true">
            <span className="terminal__dot" />
            <span className="terminal__dot" />
            <span className="terminal__dot" />
          </span>
          <span>~/yz/cover-letter.txt</span>
        </div>
        <pre className="terminal__body">{COVER_LETTER_TEXT}</pre>
      </div>
    </Section>
  );
}

export default CoverLetter;
