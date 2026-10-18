/* static/js/speak.js — record yourself, listen back, compare by ear.
 *
 * LICENCE: project code, Apache-2.0.
 *
 * Session 22 D1 / C3.
 *
 * There is no scoring here and there will not be. Coptic has no validated
 * speech recogniser, so any "accuracy %" would be a number borrowed from a
 * different language's model and dressed up as feedback. The whole loop is:
 * hear the transliteration in your head, say the word, play yourself back,
 * decide with your own ear. The banner on the page says so in those words.
 *
 * Privacy is structural, not a policy sentence:
 *   - the recording lives in MediaRecorder chunks in this page's memory
 *   - it is never POSTed, never stored in localStorage/IndexedDB, never
 *     cached by the service worker (a blob: URL is same-session only)
 *   - navigation destroys it; returning to /speak/ starts clean
 * The only network traffic this page makes is one GET of the word list,
 * same as every other page on the site.
 *
 * Shape: classic IIFE like write.js. FetchJson and translitDisplay are
 * load-bearing globals from fetch_json.js and translit.js (defer order in
 * the layout).
 */
(function (root) {
  "use strict";

  var WORDS_URL = "/data/dist/speak/speak.json.gz";
  var words = [];
  var scheme = "bohairic";
  var recorder = null;
  var chunks = [];
  var playbackUrl = null;
  var audio = null;

  function $(id) { return document.getElementById(id); }

  function currentWord() {
    var i = $("speak-word").selectedIndex;
    return words[i] || null;
  }

  function renderWord() {
    var w = currentWord();
    var coptic = $("speak-coptic");
    var translitEl = $("speak-translit");
    var link = $("speak-dict-link");
    if (!w) {
      coptic.textContent = "";
      translitEl.textContent = "";
      return;
    }
    coptic.textContent = w.lemma;
    translitEl.textContent = translitDisplay(w, scheme) || "(no transliteration)";
    link.href = "/dict/?q=" + encodeURIComponent(w.norm_key);
  }

  function fillSelect() {
    var sel = $("speak-word");
    var frag = document.createDocumentFragment();
    for (var i = 0; i < words.length; i += 1) {
      var w = words[i];
      var opt = document.createElement("option");
      opt.value = String(i);
      opt.textContent = w.lemma + " — " + (w.gloss || "(no gloss)");
      frag.appendChild(opt);
    }
    sel.appendChild(frag);
  }

  function discardRecording() {
    if (audio) { try { audio.pause(); } catch (e) { /* already stopped */ } audio = null; }
    if (playbackUrl) { URL.revokeObjectURL(playbackUrl); playbackUrl = null; }
    chunks = [];
    $("speak-play").disabled = true;
    $("speak-feedback").textContent = "";
  }

  function pickMime() {
    // Any of these works; none is assumed. An empty string means the
    // browser picks its default (usually webm/opus).
    var candidates = [
      "audio/webm;codecs=opus",
      "audio/webm",
      "audio/ogg;codecs=opus",
      ""
    ];
    for (var i = 0; i < candidates.length; i += 1) {
      if (candidates[i] === "" ||
          (root.MediaRecorder && MediaRecorder.isTypeSupported(candidates[i]))) {
        return candidates[i];
      }
    }
    return "";
  }

  function startRecording() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      $("speak-status").textContent =
        "This browser does not expose microphone access (getUserMedia).";
      return;
    }
    discardRecording();
    $("speak-status").textContent = "Requesting the microphone…";
    navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
      var mime = pickMime();
      recorder = new MediaRecorder(mime ? { mimeType: mime } : undefined);
      recorder.ondataavailable = function (e) {
        if (e.data && e.data.size) chunks.push(e.data);
      };
      recorder.onstop = function () {
        // Release the microphone the moment recording ends — holding it
        // open after the user is done is a bug, not a feature.
        stream.getTracks().forEach(function (t) { t.stop(); });
        if (!chunks.length) {
          $("speak-status").textContent = "Nothing was captured. Try again.";
          return;
        }
        playbackUrl = URL.createObjectURL(new Blob(chunks));
        audio = new Audio(playbackUrl);
        $("speak-play").disabled = false;
        $("speak-status").textContent =
          "Recorded. Play it back and listen against the transliteration.";
      };
      recorder.onerror = function () {
        stream.getTracks().forEach(function (t) { t.stop(); });
        $("speak-status").textContent = "Recording failed in this browser.";
      };
      recorder.start();
      $("speak-record").textContent = "Stop";
      $("speak-status").textContent = "Recording — say the word, then stop.";
    }, function () {
      $("speak-status").textContent =
        "Microphone permission was declined. Nothing was recorded.";
    });
  }

  function stopRecording() {
    if (recorder && recorder.state === "recording") recorder.stop();
    recorder = null;
    $("speak-record").textContent = "Record";
  }

  function playRecording() {
    if (!audio) return;
    audio.currentTime = 0;
    var p = audio.play();
    if (p && p.catch) {
      p.catch(function () {
        $("speak-feedback").textContent = "This browser blocked playback.";
      });
    }
    $("speak-feedback").textContent =
      "Listen back, then read the transliteration while it plays.";
  }

  function init() {
    if (!root.FetchJson || !root.translitDisplay) {
      $("speak-status").textContent =
        "Scripts did not load (FetchJson/translitDisplay missing).";
      return;
    }
    FetchJson.json(WORDS_URL).then(function (data) {
      words = (data && data.words) || [];
      if (!words.length) throw new Error("word list is empty");
      fillSelect();
      renderWord();
      $("speak-status").textContent =
        "Choose a word, then record. " + words.length + " word(s) loaded.";
    }).catch(function (e) {
      $("speak-status").textContent = "Could not load the word list: " +
        ((e && e.message) || e);
    });

    $("speak-word").addEventListener("change", function () {
      discardRecording();
      renderWord();
    });
    $("speak-scheme").addEventListener("change", function () {
      scheme = this.value || "bohairic";
      renderWord();
    });
    $("speak-record").addEventListener("click", function () {
      if (recorder && recorder.state === "recording") stopRecording();
      else startRecording();
    });
    $("speak-play").addEventListener("click", playRecording);

    // Navigation away: the page dies, blob URLs die with it. Nothing to
    // flush, nothing stored, nothing to opt out of.
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})(typeof globalThis !== "undefined" ? globalThis : this);
