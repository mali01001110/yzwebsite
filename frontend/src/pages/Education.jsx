import { useState } from 'react';
import Section from '../components/Section';
import CredentialCard from '../components/CredentialCard';
import ImageLightbox from '../components/ImageLightbox';
import StaggerGrid from '../components/StaggerGrid';
import edu1 from '../assets/education1.jpg';
import edu2 from '../assets/education2.jpg';

const EDUCATION_ENTRIES = [
  {
    image: edu1,
    alt: 'Ivorian Baccalaureate',
    code: 'BAC',
    title: 'Baccalaureate Diploma',
    description: 'Baccalaureate In Litterature',
    facts: [
      { key: 'Institution', value: 'CSM Cocody' },
      { key: 'Year', value: '2007' },
    ],
  },
  {
    image: edu2,
    alt: 'Ivorian Associate Degree In Law',
    code: 'LAW',
    title: 'Undergraduate Degree',
    description: 'Undergaduate Degree In Law',
    facts: [
      { key: 'Institution', value: 'UA' },
      { key: 'Year', value: '2010' },
    ],
  },
];

function Education() {
  const [activeImage, setActiveImage] = useState(null);

  return (
    <Section id="education" title="Education" subtitle="Academic record // archive access">
      <StaggerGrid className="credentials">
        {EDUCATION_ENTRIES.map((entry) => (
          <CredentialCard
            key={entry.code}
            code={entry.code}
            title={entry.title}
            description={entry.description}
            image={entry.image}
            alt={entry.alt}
            facts={entry.facts}
            hint="Open diploma"
            onOpen={() => setActiveImage({ src: entry.image, alt: entry.alt })}
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

export default Education;
