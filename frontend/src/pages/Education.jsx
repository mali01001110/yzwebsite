import { useState } from 'react';
import ImageLightbox from '../components/ImageLightbox';
import edu1 from '../assets/education1.jpg';
import edu2 from '../assets/education2.jpg';

function Education() {
  const [activeImage, setActiveImage] = useState(null);

  // ️ Replace with your real education entries
  const educationEntries = [
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
      title: 'Undergraduate Deegree',
      institution: 'University Of The Atlantic — 2010',
      description: 'Degree in Law',
    },
  ];

  return (
    <section className="page">
      <h1>Education</h1>
      <div className="card-list">
        {educationEntries.map((entry, idx) => (
          <article key={idx} className="card">
            <button
              type="button"
              className="image-button"
              onClick={() => setActiveImage({ src: entry.image, alt: entry.alt })}
              aria-label={`View full image: ${entry.alt}`}
            >
              <img src={entry.image} alt={entry.alt} className="card-image" />
              <span className="image-hint">Click to view full image</span>
            </button>
            <h2>{entry.title}</h2>
            <h3>{entry.institution}</h3>
            <p>{entry.description}</p>
          </article>
        ))}
      </div>

      {activeImage && (
        <ImageLightbox
          src={activeImage.src}
          alt={activeImage.alt}
          onClose={() => setActiveImage(null)}
        />
      )}
    </section>
  );
}

export default Education;
