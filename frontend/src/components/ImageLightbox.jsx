import { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';

/**
 * Full-view overlay for document scans. Rendered into <body> so it escapes the
 * sticky header's stacking context.
 */
function ImageLightbox({ src, alt, onClose }) {
  useEffect(() => {
    const closeOnEscape = (event) => {
      if (event.key === 'Escape') onClose();
    };

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    document.addEventListener('keydown', closeOnEscape);

    return () => {
      document.removeEventListener('keydown', closeOnEscape);
      document.body.style.overflow = previousOverflow;
    };
  }, [onClose]);

  const overlay = (
    <div
      className="lightbox"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={alt}
    >
      <div className="lightbox__frame" onClick={(event) => event.stopPropagation()}>
        <button
          type="button"
          className="lightbox__close"
          onClick={onClose}
          aria-label="Close full view"
        >
          <X size={18} />
        </button>
        <img src={src} alt={alt} className="lightbox__image" />
        <p className="lightbox__caption">{alt}</p>
      </div>
    </div>
  );

  return createPortal(overlay, document.body);
}

export default ImageLightbox;
