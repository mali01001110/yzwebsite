import { useState } from 'react';
import ImageLightbox from '../components/ImageLightbox';
import cert1 from '../assets/cert1.jpg';
import cert2 from '../assets/cert2.jpg';

function Certifications() {
  const [activeImage, setActiveImage] = useState(null);

  // ️ Replace with your real certifications
  const certifications = [
    {
      image: cert1,
      alt: 'Certificate Of Completion - Information Security Training Program',
      title: 'Information Security',
      issuer: 'CNFDI — 2024',
      description: 'I Have Completed A Training Program In Information Security',
    },
    {
      image: cert2,
      alt: 'Certificate of completion for [CS50P]',
      title: 'CS50’s Introduction to Programming with Python',
      issuer: 'Harvard Online — 2026',
      description: 'Certificate of completion for [CS50P] - I Took CS50P',
    },
  ];

  return (
    <section className="page">
      <h1>Certifications</h1>
      <div className="card-list">
        {certifications.map((cert, idx) => (
          <article key={idx} className="card">
            <button
              type="button"
              className="image-button"
              onClick={() => setActiveImage({ src: cert.image, alt: cert.alt })}
              aria-label={`View full image: ${cert.alt}`}
            >
              <img src={cert.image} alt={cert.alt} className="card-image" />
              <span className="image-hint">Click to view full image</span>
            </button>
            <h2>{cert.title}</h2>
            <h3>{cert.issuer}</h3>
            <p>{cert.description}</p>
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

export default Certifications;
