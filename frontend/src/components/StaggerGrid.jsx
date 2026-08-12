import { useRef } from 'react';
import { useInViewOnce } from '../hooks/useInViewOnce';

/**
 * Grid wrapper that deals its children in one after another once it scrolls
 * into view. The per-child delay is CSS (`.stagger > *:nth-child`), so the
 * children stay plain elements.
 */
function StaggerGrid({ className = '', threshold = 0.1, children }) {
  const gridRef = useRef(null);
  const isInView = useInViewOnce(gridRef, threshold);

  return (
    <div
      ref={gridRef}
      className={`stagger ${isInView ? 'is-revealed' : ''} ${className}`
        .replace(/\s+/g, ' ')
        .trim()}
    >
      {children}
    </div>
  );
}

export default StaggerGrid;
