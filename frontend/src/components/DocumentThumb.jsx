import { Maximize2 } from 'lucide-react';
import { useLanguage } from '../hooks/useLanguage';

/**
 * Clickable scan preview shared by the credentials timeline and the resume
 * panel. Opening the full view is delegated to the parent via `onOpen`.
 */
function DocumentThumb({ src, alt, onOpen, hint = 'Expand scan' }) {
  const { translate: t } = useLanguage();
  return (
    <button
      type="button"
      className="thumb"
      onClick={onOpen}
      aria-label={`${t('View full image')}: ${t(alt)}`}
    >
      <img src={src} alt={t(alt)} className="thumb__img" loading="lazy" />
      <span className="thumb__veil" aria-hidden="true" />
      <span className="thumb__hint">
        <Maximize2 size={12} aria-hidden="true" /> {t(hint)}
      </span>
    </button>
  );
}

export default DocumentThumb;
