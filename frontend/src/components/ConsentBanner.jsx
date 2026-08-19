import { useState } from 'react';

const COOKIE_NAME = 'analytics.consent';
const MAX_AGE_SECONDS = 60 * 60 * 24 * 180;

/**
 * Deliberately unstyled beyond layout primitives. The site has a strong visual
 * identity and this component is expected to be restyled; shipping it with
 * opinionated colours would mean fighting them.
 */
const STYLES = {
  wrapper: {
    position: 'fixed',
    insetInline: 0,
    bottom: 0,
    zIndex: 9999,
    display: 'flex',
    flexWrap: 'wrap',
    gap: '1rem',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '1rem',
    background: 'rgba(0, 0, 0, 0.92)',
    borderTop: '1px solid rgba(255, 255, 255, 0.2)',
  },
  text: { margin: 0, fontSize: '0.85rem', lineHeight: 1.5, maxWidth: '60ch' },
  actions: { display: 'flex', gap: '0.5rem' },
  // Both buttons share one style on purpose. Making "reject" quieter than
  // "accept" is the standard dark pattern, and the point of this component is
  // that the two choices cost the visitor exactly the same effort.
  button: {
    padding: '0.5rem 1rem',
    fontSize: '0.85rem',
    fontFamily: 'inherit',
    cursor: 'pointer',
    border: '1px solid currentColor',
    background: 'transparent',
    color: 'inherit',
  },
};

function readConsentCookie() {
  const match = document.cookie.match(/(?:^|;\s*)analytics\.consent=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : null;
}

function writeConsentCookie(analyticsGranted) {
  const value = `essential:1,analytics:${analyticsGranted ? '1' : '0'}`;
  const secure = window.location.protocol === 'https:' ? '; Secure' : '';
  document.cookie =
    `${COOKIE_NAME}=${encodeURIComponent(value)}; path=/; max-age=${MAX_AGE_SECONDS}` +
    `; SameSite=Lax${secure}`;
}

function hasBrowserOptOut() {
  return (
    navigator.doNotTrack === '1' ||
    window.doNotTrack === '1' ||
    navigator.globalPrivacyControl === true
  );
}

/**
 * Minimal consent banner for the analytics category.
 *
 * Renders nothing when a decision has already been recorded, or when the
 * browser already sent Do Not Track or Global Privacy Control — those are an
 * answer, and asking again after someone has answered is the behaviour this
 * component exists to avoid.
 *
 * `enabled` must track the server's ANALYTICS['REQUIRE_CONSENT'] setting.
 * Showing a banner while the server is not gating on consent would ask a
 * question whose answer changes nothing, which is its own kind of dark
 * pattern.
 *
 * Reject is exactly as prominent and exactly as many clicks as accept.
 */
function ConsentBanner({ enabled = true, onDecision }) {
  // Read once on mount via a lazy initialiser rather than in an effect: the
  // cookie and the browser signals cannot change between renders, so an effect
  // would only add a second render pass.
  const [hasDecided, setHasDecided] = useState(
    () => hasBrowserOptOut() || readConsentCookie() !== null
  );

  const isVisible = enabled && !hasDecided;

  const decide = (granted) => () => {
    writeConsentCookie(granted);
    setHasDecided(true);
    onDecision?.(granted);
    // The beacon reads the cookie once, at load. A page that was loaded before
    // consent was granted needs a reload for collection to begin.
    if (granted && !window.analytics) window.location.reload();
  };

  if (!isVisible) return null;

  return (
    <div style={STYLES.wrapper} role="region" aria-label="Analytics consent">
      <p style={STYLES.text}>
        This site keeps its own anonymous visit statistics. No third-party
        trackers, no advertising, and no data leaves this server. Nothing that
        identifies you personally is stored.
      </p>
      <div style={STYLES.actions}>
        <button type="button" style={STYLES.button} onClick={decide(false)}>
          Reject
        </button>
        <button type="button" style={STYLES.button} onClick={decide(true)}>
          Accept
        </button>
      </div>
    </div>
  );
}

export default ConsentBanner;
