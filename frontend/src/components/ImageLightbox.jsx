import { useEffect } from 'react';
import { createPortal } from 'react-dom';

function ImageLightbox({ src, alt, onClose, size = 'default' }) {
  // Close the lightbox when the user presses the Escape key
  useEffect(() => {
    const handleKey = (e) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKey);
    // Prevent the page behind from scrolling while the lightbox is open
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    return () => {
      document.removeEventListener('keydown', handleKey);
      document.body.style.overflow = previousOverflow || '';
    };
  }, [onClose]);

  const imageClass = `lightbox-image${size === 'resume' ? ' lightbox-image--resume' : ''}`;

  const lightbox = (
    <div
      className="lightbox-overlay"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Image full view"
    >
      <button
        type="button"
        className="lightbox-close"
        onClick={onClose}
        aria-label="Close full view"
      >
        ×
      </button>
      <img
        src={src}
        alt={alt}
        className={imageClass}
        onClick={(e) => e.stopPropagation()}
      />
    </div>
  );

  // Render the lightbox at the document body root so it sits above fixed headers and other stacking contexts
  return createPortal(lightbox, document.body);
}

export default ImageLightbox;
