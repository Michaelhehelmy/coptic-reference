/* static/js/write.js — handwriting tracing with lenient feedback. Session 21 D4.
 *
 * LICENCE: project code, Apache-2.0.
 *
 * No framework, no build step, no server, no accounts, no telemetry. The
 * learner picks a glyph, traces it on a canvas with mouse or touch, and gets
 * one of three verdicts: good, close, or try again. Never a numeric score —
 * a number would claim a precision this comparison does not have.
 *
 * WHAT IS COMPARED (and what is not). The reference glyph is drawn in the
 * site Coptic font to an offscreen canvas; its ink pixels and connected ink
 * regions (flood fill) are measured at session start. The learner's ink and
 * gesture count (pointer-down to pointer-up) are measured the same way.
 * Overlap = reference pixels the learner covered; count = gestures vs ink
 * regions within one. Stroke ORDER is deliberately not assessed: no verified
 * source for Coptic stroke order exists in this repository, and an invented
 * order would teach wrong handwriting with authority. See DECISIONS.md
 * Session 21 D4. The reference SVG files carry the shape as font text for
 * the no-JS list; all measurement happens here, at runtime, from the font.
 */
(function (root) {
  "use strict";

  var INDEX_URL = "/write/index.json";
  var SIZE = 200;
  var STORAGE_KEY = "coptic-write-progress-v1";

  function $(id) { return document.getElementById(id); }

  function esc(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (c) {
      return {
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
      }[c];
    });
  }

  function storageAvailable() {
    try {
      var key = STORAGE_KEY + ":probe";
      window.localStorage.setItem(key, "1");
      window.localStorage.removeItem(key);
      return true;
    } catch (e) {
      return false;
    }
  }

  var FONT_STACK = "Coptic, 'Segoe UI Historic', 'Noto Sans Coptic', serif";

  function fontStack() {
    // The reference must be measured in the same font the learner sees.
    var canvas = document.getElementById("write-canvas");
    if (canvas && typeof getComputedStyle === "function") {
      var family = getComputedStyle(canvas).fontFamily;
      if (family) return family + ", " + FONT_STACK;
    }
    return FONT_STACK;
  }

  // Reference ink: draw the glyph large in the site font, collect dark
  // pixels and count 4-connected ink regions (flood fill). Both numbers are
  // measured, never asserted; an empty reference fails loudly.
  function measureReference(glyph) {
    var canvas = document.createElement("canvas");
    canvas.width = SIZE;
    canvas.height = SIZE;
    var ctx = canvas.getContext("2d", { willReadFrequently: true });
    if (!ctx) throw new Error("canvas 2d is unavailable");
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, SIZE, SIZE);
    ctx.fillStyle = "#000000";
    ctx.font = "150px " + fontStack();
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(glyph, SIZE / 2, SIZE / 2 + 8);
    var data = ctx.getImageData(0, 0, SIZE, SIZE).data;
    var ink = new Uint8Array(SIZE * SIZE);
    var count = 0;
    var i, x;
    for (i = 0; i < SIZE * SIZE; i += 1) {
      if (data[i * 4] < 128) {
        ink[i] = 1;
        count += 1;
      }
    }
    if (count === 0) throw new Error("the reference did not render — check fonts");
    // Flood fill on a SEPARATE visited map: pixels keeps its 1s, because
    // the verdict below queries them. Consuming the map during counting
    // would make every overlap zero — caught in review, not in testing,
    // because an always-"Try again" tool still looks like it works.
    var seen = new Uint8Array(SIZE * SIZE);
    var regions = 0;
    var stack = [];
    for (i = 0; i < SIZE * SIZE; i += 1) {
      if (ink[i] !== 1 || seen[i]) continue;
      regions += 1;
      stack.push(i);
      while (stack.length) {
        x = stack.pop();
        if (ink[x] !== 1 || seen[x]) continue;
        seen[x] = 1;
        var px = x % SIZE;
        if (px > 0) stack.push(x - 1);
        if (px < SIZE - 1) stack.push(x + 1);
        if (x >= SIZE) stack.push(x - SIZE);
        if (x < SIZE * (SIZE - 1)) stack.push(x + SIZE);
      }
    }
    return { pixels: ink, count: count, regions: regions };
  }

  function learnerInk(canvas) {
    var ctx = canvas.getContext("2d", { willReadFrequently: true });
    var data = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
    var ink = [];
    var stepX = canvas.width / SIZE;
    var stepY = canvas.height / SIZE;
    var x, y, dx, dy, found;
    for (y = 0; y < SIZE; y += 1) {
      for (x = 0; x < SIZE; x += 1) {
        found = false;
        for (dx = 0; dx < stepX && !found; dx += 1) {
          for (dy = 0; dy < stepY && !found; dy += 1) {
            var px = Math.min(canvas.width - 1, Math.floor(x * stepX + dx));
            var py = Math.min(canvas.height - 1, Math.floor(y * stepY + dy));
            var at = (py * canvas.width + px) * 4;
            if (data[at] < 128) found = true;
          }
        }
        if (found) ink.push(y * SIZE + x);
      }
    }
    return ink;
  }

  // Lenient bands, documented in the module header. Overlap is the share of
  // reference ink the learner covered; gestures within one of the measured
  // region count. No numbers ever reach the learner.
  function verdict(overlap, gestures, regions) {
    var countOk = Math.abs(gestures - regions) <= 1;
    if (overlap >= 0.7 && countOk) return "Good.";
    if (overlap >= 0.4) return "Close — try again.";
    return "Try again.";
  }

  function saveProgress(glyph, ok) {
    if (!storageAvailable()) return;
    try {
      var progress = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "{}");
      if (!progress || typeof progress !== "object") progress = {};
      var entry = progress[glyph] || { tries: 0, good: 0 };
      entry.tries += 1;
      if (ok) entry.good += 1;
      progress[glyph] = entry;
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(progress));
    } catch (e) {
      /* Progress is a courtesy, not a contract. */
    }
  }

  function init() {
    var select = $("write-glyph");
    var canvas = $("write-canvas");
    var check = $("write-check");
    var clear = $("write-clear");
    var feedback = $("write-feedback");
    var status = $("write-status");
    if (!select || !canvas || !check) return;
    var strokes = 0;
    var drawing = false;
    var reference = null;

    function loadIndex() {
      return FetchJson.json(INDEX_URL).then(function (index) {
        if (!index || !Array.isArray(index.glyphs) || index.glyphs.length === 0) {
          throw new Error("the glyph index is empty");
        }
        select.innerHTML = "";
        index.glyphs.forEach(function (entry) {
          var option = document.createElement("option");
          option.value = entry.glyph;
          option.textContent = entry.glyph + "  (" + entry.codepoints.join(" ") + ")";
          select.appendChild(option);
        });
        return index;
      });
    }

    function setupCanvas() {
      var ratio = window.devicePixelRatio || 1;
      var side = 280;
      canvas.width = side * ratio;
      canvas.height = side * ratio;
      canvas.style.width = side + "px";
      canvas.style.height = side + "px";
      var ctx = canvas.getContext("2d");
      ctx.lineWidth = 6 * ratio;
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      ctx.strokeStyle = "#1a1a1a";
      clearInk();
    }

    function clearInk() {
      var ctx = canvas.getContext("2d");
      ctx.save();
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.restore();
      strokes = 0;
      drawing = false;
      if (feedback) feedback.textContent = "";
    }

    function canvasPoint(event) {
      var rect = canvas.getBoundingClientRect();
      var point = event.touches && event.touches.length
        ? event.touches[0]
        : event;
      return {
        x: (point.clientX - rect.left) * (canvas.width / rect.width),
        y: (point.clientY - rect.top) * (canvas.height / rect.height)
      };
    }

    var last = null;
    function down(event) {
      event.preventDefault();
      drawing = true;
      strokes += 1;
      last = canvasPoint(event);
      var ctx = canvas.getContext("2d");
      ctx.beginPath();
      ctx.arc(last.x, last.y, ctx.lineWidth / 2, 0, Math.PI * 2);
      ctx.fillStyle = "#1a1a1a";
      ctx.fill();
    }
    function move(event) {
      if (!drawing) return;
      event.preventDefault();
      var point = canvasPoint(event);
      var ctx = canvas.getContext("2d");
      ctx.beginPath();
      ctx.moveTo(last.x, last.y);
      ctx.lineTo(point.x, point.y);
      ctx.stroke();
      last = point;
    }
    function up() {
      drawing = false;
      last = null;
    }

    canvas.addEventListener("pointerdown", down);
    canvas.addEventListener("pointermove", move);
    canvas.addEventListener("pointerup", up);
    canvas.addEventListener("pointercancel", up);
    canvas.addEventListener("touchstart", down, { passive: false });
    canvas.addEventListener("touchmove", move, { passive: false });
    canvas.addEventListener("touchend", up);
    if (clear) clear.addEventListener("click", clearInk);

    check.addEventListener("click", function () {
      try {
        if (!reference) reference = measureReference(select.value);
      } catch (e) {
        if (status) status.textContent = "Could not measure this glyph: " + e.message;
        return;
      }
      var ink = learnerInk(canvas);
      if (ink.length === 0) {
        if (feedback) feedback.textContent = "Draw the letter first.";
        return;
      }
      var covered = 0;
      var i;
      for (i = 0; i < ink.length; i += 1) {
        if (reference.pixels[ink[i]] === 1) covered += 1;
      }
      var result = verdict(
        reference.count ? covered / reference.count : 0,
        strokes, reference.regions);
      if (feedback) feedback.textContent = result;
      saveProgress(select.value, result === "Good.");
      if (status) {
        status.textContent = "Checked “" + select.value + "”. " +
          (storageAvailable() ? "" : "Progress is in memory only.");
      }
    });

    function showReference() {
      // The reference is the letter itself in the site font (same shaping
      // the dictionary uses) plus its SVG image. Either may fail alone;
      // the session needs only one of them, the measurement needs the font.
      var big = $("write-reference-text");
      if (big) big.textContent = select.value;
      var img = $("write-reference-img");
      if (img) {
        var entry = null;
        (indexCache || []).forEach(function (candidate) {
          if (candidate.glyph === select.value) entry = candidate;
        });
        if (entry) {
          img.setAttribute("src", "/write/" + entry.file);
          img.setAttribute("alt", "Reference shape for " + entry.glyph);
        }
      }
    }

    var indexCache = null;
    select.addEventListener("change", function () {
      reference = null;
      clearInk();
      showReference();
      if (status) status.textContent = "Trace “" + select.value + "”, then check.";
    });

    if (typeof FetchJson === "undefined") {
      if (status) status.textContent = "fetch_json.js did not load before write.js";
      return;
    }
    setupCanvas();
    loadIndex().then(function (index) {
      indexCache = index.glyphs || [];
      showReference();
      if (status) status.textContent = "Trace the letter, then check.";
    }).catch(function (e) {
      if (status) status.textContent = "Could not load the glyphs: " + (e && e.message ? e.message : e);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  root.Write = {
    verdict: verdict,
    measureReference: measureReference,
    STORAGE_KEY: STORAGE_KEY
  };
  if (typeof module !== "undefined" && module.exports) {
    module.exports = root.Write;
  }
})(typeof globalThis !== "undefined" ? globalThis : this);
