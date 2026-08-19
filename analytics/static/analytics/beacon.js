/**
 * First-party analytics beacon. No dependencies, no cookies, no third party.
 *
 * Batches events in memory and flushes them with navigator.sendBeacon() when
 * the page is hidden, or every 10 seconds, whichever comes first. sendBeacon
 * is the only transport the browser guarantees to complete after a page starts
 * unloading; fetch(keepalive) is the fallback where it is unavailable.
 *
 * Engaged time is measured, not assumed: the timer accumulates only while the
 * document is visible AND the visitor has interacted within the last 30
 * seconds. A tab left open in the background for an hour reports zero, which
 * is the honest answer.
 *
 * Opts out entirely on DNT: 1, Sec-GPC (navigator.globalPrivacyControl), or a
 * consent cookie that withholds the analytics category.
 *
 * Exposes window.analytics: track(name, props), trackPageview(path),
 * identify(userId).
 */
(function (window, document) {
  'use strict';

  var ENDPOINT = '/api/analytics/events/';
  var FLUSH_INTERVAL_MS = 10000;
  var MAX_BATCH = 50;
  var INTERACTION_TIMEOUT_MS = 30000;
  var SCROLL_MILESTONES = [25, 50, 75, 100];
  var RAGE_RADIUS_PX = 40;
  var RAGE_WINDOW_MS = 1000;
  var RAGE_THRESHOLD = 3;
  var DEAD_CLICK_MS = 500;
  var CONSENT_COOKIE = 'analytics.consent';
  var DOWNLOAD_EXTENSIONS = /\.(pdf|zip|docx?|xlsx?|pptx?|csv|txt|png|jpe?g|svg|mp4|mp3)$/i;

  // ---------------------------------------------------------------- opt-out

  function hasOptedOut() {
    if (navigator.doNotTrack === '1' || window.doNotTrack === '1') return true;
    if (navigator.globalPrivacyControl === true) return true;
    return false;
  }

  function consentAllows() {
    // Absent cookie means the server is not gating on consent; the server
    // enforces the real decision either way, this only avoids pointless sends.
    var match = document.cookie.match(/(?:^|;\s*)analytics\.consent=([^;]*)/);
    if (!match) return true;
    var value = decodeURIComponent(match[1]);
    if (value.indexOf('analytics') === -1) return true;
    return /analytics\s*:\s*(1|true|yes)/i.test(value) || /(^|,)\s*analytics\s*(,|$)/i.test(value);
  }

  if (hasOptedOut() || !consentAllows()) {
    window.analytics = { track: noop, trackPageview: noop, identify: noop, flush: noop };
    return;
  }

  function noop() {}

  // ----------------------------------------------------------------- state

  var queue = [];
  var flushTimer = null;
  var userId = null;
  var currentPath = location.pathname + location.hash;
  var lastInteractionAt = Date.now();
  var engagedMs = 0;
  var engagedTickAt = Date.now();
  var maxScroll = 0;
  var firedMilestones = {};
  var recentClicks = [];
  var vitals = {};

  // ------------------------------------------------------------- transport

  function context() {
    var connection = navigator.connection || {};
    return {
      screen_width: screen.width,
      screen_height: screen.height,
      viewport_width: window.innerWidth,
      viewport_height: window.innerHeight,
      pixel_ratio: window.devicePixelRatio || 1,
      timezone: resolvedTimezone(),
      connection: connection.effectiveType || ''
    };
  }

  function resolvedTimezone() {
    try {
      return Intl.DateTimeFormat().resolvedOptions().timeZone || '';
    } catch (error) {
      return '';
    }
  }

  function send(isUnloading) {
    if (!queue.length) return;

    var batch = queue.splice(0, MAX_BATCH);
    var payload = context();
    payload.events = batch;

    var body = JSON.stringify(payload);
    var sent = false;

    if (navigator.sendBeacon) {
      // Blob with an explicit type: without it sendBeacon sends
      // text/plain;charset=UTF-8 and DRF refuses to parse the body as JSON.
      try {
        sent = navigator.sendBeacon(ENDPOINT, new Blob([body], { type: 'application/json' }));
      } catch (error) {
        sent = false;
      }
    }

    if (!sent) {
      try {
        fetch(ENDPOINT, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: body,
          keepalive: true,
          credentials: 'same-origin'
        }).catch(noop);
      } catch (error) {
        // Requeue only when the page is not going away; on unload there is no
        // later flush to retry into and holding the events achieves nothing.
        if (!isUnloading) queue = batch.concat(queue);
      }
    }
  }

  function enqueue(name, fields) {
    var event = fields || {};
    event.name = name;
    event.t = Date.now() / 1000;
    if (!event.path) event.path = currentPath;
    queue.push(event);
    if (queue.length >= MAX_BATCH) send(false);
  }

  function scheduleFlush() {
    if (flushTimer) clearInterval(flushTimer);
    flushTimer = setInterval(function () { send(false); }, FLUSH_INTERVAL_MS);
  }

  // ------------------------------------------------------- engagement time

  function tickEngagement() {
    var now = Date.now();
    var isEngaged =
      document.visibilityState === 'visible' &&
      now - lastInteractionAt < INTERACTION_TIMEOUT_MS;
    if (isEngaged) engagedMs += now - engagedTickAt;
    engagedTickAt = now;
  }

  function engagedSeconds() {
    tickEngagement();
    return Math.round(engagedMs / 1000);
  }

  function markInteraction() {
    tickEngagement();
    lastInteractionAt = Date.now();
  }

  ['pointerdown', 'keydown', 'scroll', 'touchstart'].forEach(function (type) {
    window.addEventListener(type, markInteraction, { passive: true, capture: true });
  });

  // ------------------------------------------------------------ scroll depth

  function onScroll() {
    var scrollable = document.documentElement.scrollHeight - window.innerHeight;
    if (scrollable <= 0) return;
    var depth = Math.min(100, Math.round(((window.scrollY || 0) / scrollable) * 100));
    if (depth > maxScroll) maxScroll = depth;

    for (var i = 0; i < SCROLL_MILESTONES.length; i++) {
      var milestone = SCROLL_MILESTONES[i];
      if (maxScroll >= milestone && !firedMilestones[milestone]) {
        firedMilestones[milestone] = true;
        enqueue('scroll_depth', { props: { depth: milestone } });
      }
    }
  }

  window.addEventListener('scroll', throttle(onScroll, 250), { passive: true });

  // -------------------------------------------------------- section views

  // The site is one route with anchored sections, so a section entering the
  // viewport is this app's equivalent of a page navigation.
  function observeSections() {
    if (!window.IntersectionObserver) return;
    var seen = {};
    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting || seen[entry.target.id]) return;
          seen[entry.target.id] = true;
          enqueue('section_view', {
            path: '/#' + entry.target.id,
            title: sectionTitle(entry.target),
            is_spa_navigation: true
          });
        });
      },
      { threshold: 0.5 }
    );

    document.querySelectorAll('section[id]').forEach(function (section) {
      observer.observe(section);
    });
  }

  function sectionTitle(element) {
    var heading = element.querySelector('h1, h2, h3');
    return heading ? heading.textContent.trim().slice(0, 200) : '';
  }

  // ---------------------------------------------------- clicks and outbound

  document.addEventListener(
    'click',
    function (event) {
      var target = event.target;
      if (!target || !target.closest) return;

      detectRageClick(event);

      var link = target.closest('a[href]');
      if (link) {
        handleLinkClick(link);
        return;
      }
      detectDeadClick(target);
    },
    true
  );

  function handleLinkClick(link) {
    var href = link.getAttribute('href') || '';
    if (!href || href.charAt(0) === '#') return;

    var isExternal = link.hostname && link.hostname !== location.hostname;
    if (DOWNLOAD_EXTENSIONS.test(link.pathname || '') || link.hasAttribute('download')) {
      enqueue('file_download', { props: { file: (link.pathname || '').slice(-100) } });
    } else if (isExternal) {
      enqueue('outbound_click', { props: { host: link.hostname, href: href.slice(0, 200) } });
    }
  }

  function detectRageClick(event) {
    var now = Date.now();
    recentClicks = recentClicks.filter(function (click) {
      return now - click.t < RAGE_WINDOW_MS;
    });
    recentClicks.push({ x: event.clientX, y: event.clientY, t: now });

    var nearby = recentClicks.filter(function (click) {
      return (
        Math.abs(click.x - event.clientX) < RAGE_RADIUS_PX &&
        Math.abs(click.y - event.clientY) < RAGE_RADIUS_PX
      );
    });

    if (nearby.length >= RAGE_THRESHOLD) {
      recentClicks = [];
      enqueue('rage_click', { props: { count: nearby.length, target: describe(event.target) } });
    }
  }

  function detectDeadClick(target) {
    if (target.closest('a, button, input, select, textarea, [role="button"], [onclick]')) return;

    var mutated = false;
    if (window.MutationObserver) {
      var observer = new MutationObserver(function () { mutated = true; });
      observer.observe(document.body, { childList: true, subtree: true, attributes: true });
      setTimeout(function () {
        observer.disconnect();
        if (!mutated) enqueue('dead_click', { props: { target: describe(target) } });
      }, DEAD_CLICK_MS);
    }
  }

  function describe(element) {
    if (!element || !element.tagName) return '';
    var name = element.tagName.toLowerCase();
    if (element.id) name += '#' + element.id;
    else if (element.className && typeof element.className === 'string') {
      name += '.' + element.className.trim().split(/\s+/)[0];
    }
    return name.slice(0, 80);
  }

  // ------------------------------------------------------ form abandonment

  // Opt-in only, by attribute, and field *names* only. Values are never read.
  var lastFocusedField = null;
  var startedForms = {};

  document.addEventListener(
    'focusin',
    function (event) {
      var field = event.target;
      var form = field.closest && field.closest('form[data-analytics-form]');
      if (!form) return;

      var formName = form.getAttribute('data-analytics-form');
      lastFocusedField = { form: formName, field: field.name || field.id || '' };

      if (!startedForms[formName]) {
        startedForms[formName] = true;
        enqueue('form_start', { props: { form: formName } });
      }
    },
    true
  );

  document.addEventListener(
    'submit',
    function (event) {
      var form = event.target;
      if (!form.hasAttribute || !form.hasAttribute('data-analytics-form')) return;
      var formName = form.getAttribute('data-analytics-form');
      lastFocusedField = null;
      startedForms[formName] = false;
      enqueue('form_submit', { props: { form: formName } });
    },
    true
  );

  // --------------------------------------------------------------- errors

  window.addEventListener('error', function (event) {
    enqueue('js_error', {
      props: {
        message: String(event.message || '').slice(0, 300),
        source: String(event.filename || '').slice(0, 200),
        line: event.lineno || 0,
        column: event.colno || 0,
        stack: event.error && event.error.stack ? String(event.error.stack).slice(0, 800) : ''
      }
    });
  });

  window.addEventListener('unhandledrejection', function (event) {
    var reason = event.reason;
    enqueue('js_error', {
      props: {
        message: String((reason && reason.message) || reason || 'unhandled rejection').slice(0, 300),
        stack: reason && reason.stack ? String(reason.stack).slice(0, 800) : '',
        kind: 'unhandledrejection'
      }
    });
  });

  // ---------------------------------------------------- core web vitals

  // Computed from raw PerformanceObserver entries rather than the web-vitals
  // package, to keep this file dependency-free. CLS uses the standard session
  // window; INP is approximated by the worst interaction latency, which tracks
  // the real metric closely enough for per-page comparison.
  function observeVitals() {
    if (!window.PerformanceObserver) return;

    observeEntry('largest-contentful-paint', function (entries) {
      var last = entries[entries.length - 1];
      if (last) vitals.LCP = Math.round(last.startTime);
    });

    observeEntry('paint', function (entries) {
      entries.forEach(function (entry) {
        if (entry.name === 'first-contentful-paint') vitals.FCP = Math.round(entry.startTime);
      });
    });

    var clsValue = 0;
    var sessionValue = 0;
    var sessionEntries = [];
    observeEntry('layout-shift', function (entries) {
      entries.forEach(function (entry) {
        if (entry.hadRecentInput) return;
        var first = sessionEntries[0];
        var last = sessionEntries[sessionEntries.length - 1];
        if (
          sessionEntries.length &&
          entry.startTime - last.startTime < 1000 &&
          entry.startTime - first.startTime < 5000
        ) {
          sessionValue += entry.value;
          sessionEntries.push(entry);
        } else {
          sessionValue = entry.value;
          sessionEntries = [entry];
        }
        if (sessionValue > clsValue) {
          clsValue = sessionValue;
          vitals.CLS = Math.round(clsValue * 1000) / 1000;
        }
      });
    });

    observeEntry('event', function (entries) {
      entries.forEach(function (entry) {
        var latency = Math.round(entry.duration);
        if (!vitals.INP || latency > vitals.INP) vitals.INP = latency;
      });
    }, { durationThreshold: 40 });

    var navigation = performance.getEntriesByType && performance.getEntriesByType('navigation')[0];
    if (navigation) vitals.TTFB = Math.round(navigation.responseStart);
  }

  function observeEntry(type, callback, extra) {
    try {
      var options = { type: type, buffered: true };
      if (extra) for (var key in extra) options[key] = extra[key];
      new PerformanceObserver(function (list) { callback(list.getEntries()); }).observe(options);
    } catch (error) {
      // An unsupported entry type throws; that metric is simply unavailable.
    }
  }

  function reportVitals() {
    Object.keys(vitals).forEach(function (metric) {
      enqueue('web_vital', { props: { metric: metric }, value: vitals[metric] });
    });
    vitals = {};
  }

  // --------------------------------------------------------- SPA routing

  // react-router uses history.pushState, so wrapping it catches every
  // client-side navigation without the app having to call anything.
  function wrapHistory(method) {
    var original = history[method];
    if (typeof original !== 'function') return;
    history[method] = function () {
      var result = original.apply(this, arguments);
      onRouteChange();
      return result;
    };
  }

  function onRouteChange() {
    var next = location.pathname + location.hash;
    if (next === currentPath) return;
    flushPageview();
    currentPath = next;
    maxScroll = 0;
    firedMilestones = {};
    engagedMs = 0;
    engagedTickAt = Date.now();
    enqueue('pageview', { path: currentPath, title: document.title, is_spa_navigation: true });
  }

  function flushPageview() {
    enqueue('engagement', {
      path: currentPath,
      engaged_seconds: engagedSeconds(),
      max_scroll_depth: maxScroll
    });
  }

  wrapHistory('pushState');
  wrapHistory('replaceState');
  window.addEventListener('popstate', onRouteChange);
  window.addEventListener('hashchange', onRouteChange);

  // ------------------------------------------------------------- lifecycle

  document.addEventListener('visibilitychange', function () {
    tickEngagement();
    if (document.visibilityState === 'hidden') {
      if (lastFocusedField) {
        // Recorded on hide rather than on unload: pagehide is not guaranteed
        // to run on mobile, where the tab is frozen instead of unloaded.
        enqueue('form_abandon', {
          props: { form: lastFocusedField.form, last_field: lastFocusedField.field }
        });
        lastFocusedField = null;
      }
      reportVitals();
      flushPageview();
      send(true);
    } else {
      engagedTickAt = Date.now();
    }
  });

  window.addEventListener('pagehide', function () {
    reportVitals();
    flushPageview();
    send(true);
  });

  function throttle(fn, wait) {
    var last = 0;
    var timer = null;
    return function () {
      var now = Date.now();
      var remaining = wait - (now - last);
      if (remaining <= 0) {
        last = now;
        fn();
      } else if (!timer) {
        timer = setTimeout(function () {
          timer = null;
          last = Date.now();
          fn();
        }, remaining);
      }
    };
  }

  // ------------------------------------------------------------- public API

  window.analytics = {
    /** Record a named event. Name must be on the server's allowlist. */
    track: function (name, props) {
      enqueue(name, { props: props || {} });
    },
    /** Record a pageview, for routers this script cannot observe. */
    trackPageview: function (path) {
      if (path && path !== currentPath) {
        flushPageview();
        currentPath = path;
      }
      enqueue('pageview', { path: currentPath, title: document.title, is_spa_navigation: true });
    },
    /** Associate subsequent events with an application user id. */
    identify: function (id) {
      userId = id;
      enqueue('login', { props: { user_id: String(id).slice(0, 64) } });
    },
    /** Force an immediate flush. */
    flush: function () {
      send(false);
    }
  };

  // ----------------------------------------------------------------- start

  function start() {
    observeVitals();
    observeSections();
    scheduleFlush();
    enqueue('pageview', { path: currentPath, title: document.title });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})(window, document);
