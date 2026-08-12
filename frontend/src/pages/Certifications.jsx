import { useState } from 'react';
import Section from '../components/Section';
import CredentialCard from '../components/CredentialCard';
import ImageLightbox from '../components/ImageLightbox';
import StaggerGrid from '../components/StaggerGrid';
import cert1 from '../assets/cert1.jpg';
import cert2 from '../assets/cert2.jpg';

const CERTIFICATIONS = [
  {
    image: cert1,
    alt: 'Certificate Of Completion For CS50x',
    code: 'CS50X',
    title: 'CS50’s Introduction to Computer Science',
    description: 'Certificate Of Completion For CS50x',
    facts: [
      { key: 'Issuer', value: 'Harvard Online' },
      { key: 'Issued', value: '2026' },
    ],
  },
  {
    image: cert2,
    alt: 'Certificate Of Completion For CS50P',
    code: 'CS50P',
    title: 'CS50’s Introduction to Programming with Python',
    description: 'Certificate Of Completion For CS50P',
    facts: [
      { key: 'Issuer', value: 'Harvard Online' },
      { key: 'Issued', value: '2026' },
    ],
  },
];

function Certifications() {
  const [activeImage, setActiveImage] = useState(null);

  return (
    <Section
      id="certifications"
      title="Certs"
      subtitle="Verified credentials // integrity confirmed"
    >
      <StaggerGrid className="credentials">
        {CERTIFICATIONS.map((cert) => (
          <CredentialCard
            key={cert.code}
            code={cert.code}
            title={cert.title}
            description={cert.description}
            image={cert.image}
            alt={cert.alt}
            facts={cert.facts}
            hint="Open certificate"
            onOpen={() => setActiveImage({ src: cert.image, alt: cert.alt })}
          />
        ))}
      </StaggerGrid>

      {activeImage && (
        <ImageLightbox
          src={activeImage.src}
          alt={activeImage.alt}
          onClose={() => setActiveImage(null)}
        />
      )}
    </Section>
  );
}

export default Certifications;
