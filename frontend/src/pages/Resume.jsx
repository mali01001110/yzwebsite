import { useState } from 'react';
import ImageLightbox from '../components/ImageLightbox';
import resumeImage from '../assets/resume.jpg';

function Resume() {
  const [activeImage, setActiveImage] = useState(null);

  return (
    <section id="resume" className="page">
      <h1>Resume</h1>
      <article className="card">
        <button
          type="button"
          className="image-button"
          onClick={() => setActiveImage({ src: resumeImage, alt: 'Scanned image of resume showing work experience and skills' })}
          aria-label="View full resume image"
        >
          <img
            src={resumeImage}
            alt="Scanned image of resume showing work experience and skills"
            className="card-image"
            loading="lazy"
          />
          <span className="image-hint">Click to view full image</span>
        </button>
        <h2>Professional and Educational Background</h2>
        <p>Open the resume image to view the complete education, certifications, and professional experience details.</p>
      </article>

      {activeImage && (
        <ImageLightbox
          src={activeImage.src}
          alt={activeImage.alt}
          size="resume"
          onClose={() => setActiveImage(null)}
        />
      )}
    </section>
  );
}

export default Resume;