import { useRef } from 'react';
import { useInViewOnce } from '../hooks/useInViewOnce';

/**
 * Reveals its content the first time it scrolls into view.
 *
 * Deliberately plain DOM + CSS rather than framer-motion: in framer-motion
 * 13.0.0 `whileInView` never fires, and refs attached to its motion components
 * are not reliably populated in time for an IntersectionObserver to bind. Both
 * failures left whole sections stuck invisible. A ref on a plain element and a
 * CSS transition cannot fail the same way.
 */
function Reveal({ as: Tag = 'div', className = '', threshold = 0.05, children, ...rest }) {
  const elementRef = useRef(null);
  const isInView = useInViewOnce(elementRef, threshold);

  return (
    <Tag
      ref={elementRef}
      className={`reveal ${isInView ? 'is-revealed' : ''} ${className}`.replace(/\s+/g, ' ').trim()}
      {...rest}
    >
      {children}
    </Tag>
  );
}

export default Reveal;
