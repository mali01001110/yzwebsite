import { useEffect, useState } from 'react';

/**
 * Fires once when the referenced element first enters the viewport, then stops
 * observing. Drives the decode-on-scroll text effects.
 */
export function useInViewOnce(elementRef, threshold = 0.35) {
  const [isInView, setIsInView] = useState(false);

  useEffect(() => {
    const element = elementRef.current;
    if (!element) return undefined;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return;
        setIsInView(true);
        observer.disconnect();
      },
      { threshold }
    );

    observer.observe(element);
    return () => observer.disconnect();
  }, [elementRef, threshold]);

  return isInView;
}
