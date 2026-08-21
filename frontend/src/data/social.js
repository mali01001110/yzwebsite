/**
 * Single source of truth for the external profiles and contact channels the
 * site links to.
 *
 * The footer and the Social section both link to several of these, but they
 * present them differently — the footer is a row of unlabelled icon buttons,
 * the section is a described list — so each keeps its own icons and copy.
 * Neither owns the address, which is what kept drifting: the LinkedIn and
 * Facebook URLs were previously written out in both files.
 */
export const SOCIAL_URLS = {
  linkedin: 'https://www.linkedin.com/in/mali01001110/',
  github: 'https://github.com/mali01001110',
  facebook: 'https://www.facebook.com/profile.php?id=61586600751798',
  // Stripped of `?is_from_webapp=1&sender_device=pc`. Those are TikTok's own
  // share-tracking parameters, recorded when the link was copied out of a
  // desktop browser; they describe that copy, not the profile.
  tiktok: 'https://www.tiktok.com/@sometaware',
  email: 'mailto:yannzakpa@gmail.com',
};
