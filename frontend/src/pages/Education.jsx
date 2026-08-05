import Section from '../components/Section';
import CredentialTimeline from '../components/CredentialTimeline';
import edu1 from '../assets/education1.jpg';
import edu2 from '../assets/education2.jpg';

const EDUCATION_ENTRIES = [
  {
    image: edu1,
    alt: 'Ivorian Baccalaureate',
    title: 'Baccalaureate Diploma',
    institution: 'CSM Cocody — 2007',
    description: 'Baccalaureate In Litterature',
  },
  {
    image: edu2,
    alt: 'Ivorian Associate Degree In Law',
    title: 'Undergraduate Degree',
    institution: 'UA — 2010',
    description: 'Undergaduate Degree In Law',
  },
];

function Education() {
  return (
    <Section id="education" title="Education" subtitle="Academic record // archive access">
      <CredentialTimeline entries={EDUCATION_ENTRIES} />
    </Section>
  );
}

export default Education;
