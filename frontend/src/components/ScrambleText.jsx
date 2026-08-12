import { useRef } from 'react';
import { useInViewOnce } from '../hooks/useInViewOnce';
import { useScrambleText } from '../hooks/useScrambleText';

/**
 * Renders text that decrypts from noise the first time it scrolls into view.
 * `as` lets headings keep their real element so document outline is preserved.
 */
function ScrambleText({ text, as: Tag = 'span', className = '' }) {
  const elementRef = useRef(null);
  const isInView = useInViewOnce(elementRef);
  const display = useScrambleText(text, isInView);

  return (
    <Tag ref={elementRef} className={className} aria-label={text}>
      {display}
    </Tag>
  );
}

export default ScrambleText;
