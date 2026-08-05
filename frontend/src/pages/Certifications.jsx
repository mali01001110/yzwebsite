import Section from '../components/Section';
import CredentialTimeline from '../components/CredentialTimeline';
import cert1 from '../assets/cert1.jpg';
import cert2 from '../assets/cert2.jpg';

const CERTIFICATIONS = [
  {
    image: cert1,
    alt: 'Certificate Of Completion For CS50x',
    title: 'CS50’s Introduction to Computer Science',
    institution: 'Harvard Online — 2026',
    description: 'Certificate Of Completion For CS50x - I Took CS50x',
  },
  {
    image: cert2,
    alt: 'Certificate Of Completion For CS50P',
    title: 'CS50’s Introduction to Programming with Python',
    institution: 'Harvard Online — 2026',
    description: 'Certificate Of Completion For CS50P - I Took CS50P',
  },
];

function Certifications() {
  return (
    <Section
      id="certifications"
      title="Certs"
      subtitle="Verified credentials // integrity confirmed"
    >
      <CredentialTimeline entries={CERTIFICATIONS} />
    </Section>
  );
}

export default Certifications;
