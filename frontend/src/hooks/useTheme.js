import { useCallback, useEffect, useState } from 'react';

const STORAGE_KEY = 'yz.theme';
export const NIGHT = 'night';
export const DAY = 'day';

/**
 * Duration of the switch sequence, in milliseconds.
 *
 * Kept in step with `--speed-switch` in tokens.css. The theme flips at the
 * halfway point so the reboot bar covers the repaint rather than following it.
 */
export const SWITCH_DURATION_MS = 900;

/**
 * Reads the theme the page booted with.
 *
 * The inline script in index.html has already resolved and applied it before
 * first paint, so this reads the DOM rather than recomputing — recomputing
 * risks disagreeing with what the user is currently looking at.
 */
function bootTheme() {
  const applied = document.documentElement.getAttribute('data-theme');
  return applied === DAY ? DAY : NIGHT;
}

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  // Drives the browser's own UI — form controls, scrollbars on some platforms
  // — so they do not stay dark under a white page.
  document.documentElement.style.colorScheme = theme === DAY ? 'light' : 'dark';
}

function persist(theme) {
  try {
    window.localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // Private browsing or a storage quota. The theme still applies for this
    // page load; it simply will not be remembered.
  }
}

/**
 * Day/night protocol switching, with the reboot sequence that accompanies it.
 *
 * Returns the current theme, whether a switch is in flight, and a `toggle`
 * that runs the sequence. `isSwitching` is what the reboot bar renders from.
 *
 * The theme is applied at the midpoint of the sequence, not at the start: the
 * bar is there to hide the repaint, and a swap on the first frame would happen
 * before the bar has covered anything.
 */
export function useTheme() {
  const [theme, setTheme] = useState(bootTheme);
  // Held separately from `theme` because the theme flips at the midpoint of
  // the sequence. Deriving the target from `theme` would make the readout
  // change halfway through the animation.
  const [switchingTo, setSwitchingTo] = useState(null);

  // Follow the OS preference until the visitor states one of their own. Once
  // they have chosen, their choice wins and the listener stops mattering.
  useEffect(() => {
    let stored;
    try {
      stored = window.localStorage.getItem(STORAGE_KEY);
    } catch {
      // Storage unavailable. Treated as "no stated preference", so the OS
      // setting keeps driving the theme for this session.
      stored = null;
    }
    if (stored) return undefined;

    const query = window.matchMedia('(prefers-color-scheme: light)');
    const follow = (event) => {
      const next = event.matches ? DAY : NIGHT;
      applyTheme(next);
      setTheme(next);
    };

    query.addEventListener('change', follow);
    return () => query.removeEventListener('change', follow);
  }, []);

  const toggle = useCallback(() => {
    setSwitchingTo((pending) => {
      // Ignore a second press while a sequence is running, rather than
      // queueing it — two overlapping sequences would leave the bar and the
      // applied theme out of step.
      if (pending) return pending;

      const next = theme === NIGHT ? DAY : NIGHT;

      window.setTimeout(() => {
        applyTheme(next);
        persist(next);
        setTheme(next);
      }, SWITCH_DURATION_MS / 2);

      window.setTimeout(() => setSwitchingTo(null), SWITCH_DURATION_MS);

      return next;
    });
  }, [theme]);

  return {
    theme,
    isDay: theme === DAY,
    isSwitching: switchingTo !== null,
    switchingTo,
    toggle,
  };
}
