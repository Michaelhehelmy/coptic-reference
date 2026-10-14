/* static/js/sw-register.js — registers the service worker. Nothing else.
 *
 * LICENCE: project code, Apache-2.0.
 *
 * Session 12 D2 / C3. This used to be an inline <script> block in the footer
 * partial. Inline meant one thing above all: it forced `'unsafe-inline'` into the
 * Content-Security-Policy, or it violated it. Session 11's DEPLOY.md shipped a
 * tight CSP and noted that the inline block would break it — i.e. the build and
 * its own security policy disagreed, and the documentation was carrying the
 * conflict instead of the code.
 *
 * Moving it to a file removes the disagreement: `script-src 'self'` permits this
 * file, because this file is served from the origin.
 *
 * The registration itself is unchanged from Session 10, when it was added after
 * Playwright proved sw.js existed, passed every guard, and was never installed.
 */

(function () {
  "use strict";

  if (!("serviceWorker" in navigator)) return;

  // On load, not immediately: registering during parse competes with the page's
  // own subresources for bandwidth, and on a cold first visit the page is the
  // thing the reader is waiting for.
  window.addEventListener("load", function () {
    navigator.serviceWorker.register("/sw.js").catch(function (e) {
      // A failed registration must never break the page. The site works fine
      // without a cache; it is just slower on a second visit.
      console.warn("[sw] registration failed:", e && e.message);
    });
  });

  // Offline indicator. Ask the browser, but do not depend on the answer:
  // navigator.onLine is a hint, and a reader on captive-portal wifi is "online"
  // and cannot fetch anything.
  var net = document.getElementById("net");
  if (!net) return;
  var online = function () { net.hidden = true; };
  var offline = function () { net.hidden = false; };
  window.addEventListener("online", online);
  window.addEventListener("offline", offline);
  net.hidden = navigator.onLine !== false;
})();
