import { useCallback, useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';

/**
 * Served by Django from the analytics app's static directory. Loaded at
 * runtime rather than bundled so the beacon ships independently of the app
 * build — the compiled bundle in `dist` is committed, and a tracking change
 * should not require rebuilding and recommitting it.
 */
const BEACON_SRC = '/static/analytics/beacon.js';

/**
 * Calls made before the beacon script finishes loading are held here and
 * replayed once it does, so a `track()` fired from a mount effect on a cold
 * cache is not silently dropped.
 */
const pendingCalls = [];

let loadPromise = null;

function loadBeacon() {
  if (loadPromise) return loadPromise;

  loadPromise = new Promise((resolve) => {
    if (window.analytics) {
      resolve(window.analytics);
      return;
    }

    const script = document.createElement('script');
    script.src = BEACON_SRC;
    script.async = true;
    script.addEventListener('load', () => {
      // The beacon opts itself out on DNT/GPC by installing a no-op API, so
      // window.analytics is always defined after a successful load.
      pendingCalls.splice(0).forEach(([method, args]) => {
        window.analytics?.[method]?.(...args);
      });
      resolve(window.analytics);
    });
    // A blocked or failed script must not leave callers hanging on a promise
    // that never settles; resolving with null makes every call a no-op.
    script.addEventListener('error', () => resolve(null));
    document.head.appendChild(script);
  });

  return loadPromise;
}

function call(method, ...args) {
  if (window.analytics?.[method]) {
    window.analytics[method](...args);
    return;
  }
  pendingCalls.push([method, args]);
}

/**
 * Loads the analytics beacon and returns its API.
 *
 * Route changes are reported automatically: the beacon wraps `history`, but
 * react-router's own navigations are reported from here too so a router that
 * bypasses `pushState` is still covered. The beacon deduplicates by path, so
 * the overlap costs nothing.
 *
 * Every returned function is safe to call before the script has loaded, and
 * safe to call when the visitor has opted out — in that case the beacon
 * installs a no-op API and nothing leaves the browser.
 */
export function useAnalytics({ trackRouteChanges = true } = {}) {
  const location = useLocation();
  const lastPathRef = useRef(null);

  useEffect(() => {
    loadBeacon();
  }, []);

  useEffect(() => {
    if (!trackRouteChanges) return;

    const path = `${location.pathname}${location.hash}`;
    if (lastPathRef.current === path) return;

    // Skipped on the first render: the beacon records the initial pageview
    // itself on load, and reporting it here as well would double-count it.
    if (lastPathRef.current !== null) {
      call('trackPageview', path);
    }
    lastPathRef.current = path;
  }, [location.pathname, location.hash, trackRouteChanges]);

  const track = useCallback((name, props) => call('track', name, props), []);
  const trackPageview = useCallback((path) => call('trackPageview', path), []);
  const identify = useCallback((userId) => call('identify', userId), []);

  return { track, trackPageview, identify };
}
