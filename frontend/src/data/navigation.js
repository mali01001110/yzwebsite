/**
 * Single source of truth for the site's section anchors.
 * Consumed by the header navigation and the scroll-spy hook so the two can
 * never drift apart.
 */
export const NAV_ITEMS = [
  { id: 'home', label: 'Home' },
  { id: 'about-me', label: 'About' },
  { id: 'skills', label: 'Skills' },
  { id: 'projects', label: 'Projects' },
  { id: 'education', label: 'Education' },
  { id: 'certifications', label: 'Certs' },
  { id: 'resume', label: 'Resume' },
  { id: 'cover-letter', label: 'Letter' },
  { id: 'social', label: 'Social' },
  { id: 'contact', label: 'Contact' },
];

export const SECTION_IDS = NAV_ITEMS.map((item) => item.id);
