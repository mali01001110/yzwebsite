import { useState } from 'react';
import DocumentThumb from './DocumentThumb';
import ImageLightbox from './ImageLightbox';

/**
 * Vertical HUD timeline of credential records with an expandable scan for each
 * entry. Shared by the Education and Certifications sections.
 */
function CredentialTimeline({ entries }) {
  const [activeImage, setActiveImage] = useState(null);

  return (
    <>
      <div className="timeline">
        {entries.map((entry) => (
          <article key={entry.title} className="timeline__entry">
            <DocumentThumb
              src={entry.image}
              alt={entry.alt}
              onOpen={() => setActiveImage({ src: entry.image, alt: entry.alt })}
            />

            <div className="hud-panel hud-panel--cut hud-brackets timeline__meta">
              <span className="hud-label">{entry.institution}</span>
              <h3 className="timeline__title">{entry.title}</h3>
              <p className="timeline__description">{entry.description}</p>
            </div>
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
    </>
  );
}

export default CredentialTimeline;
