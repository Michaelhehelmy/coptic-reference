/* static/js/quiz.js — the client-side quiz renderer. Session 16 D2.
 *
 * LICENCE: project code, Apache-2.0.
 *
 * No framework, no build step, no server, no accounts (invariants 1–4). One
 * bank file is fetched per session, ten items are rendered, and progress stays
 * in the reader's own browser.
 *
 * Rule 11 applies to what this file does NOT do: quiz prompts arrive as plain
 * strings from data/dist/quiz, already rendered by the one transliteration
 * renderer at generation time. This UI never interpolates e.translit,
 * entry.translit, or any other structured schema field. A prompt that is not a
  * string cannot make this renderer print the raw-object marker because it refuses
  * to render it at all.
 */
(function (root) {
  "use strict";

  var BANK_ROOT = "/data/quiz/";
  var SESSION_SIZE = 10;
  var STORAGE_KEY = "coptic-quiz-progress-v1";
  var QUIZ_TYPES = [
    "coptic_to_english",
    "english_to_coptic",
    "transliteration_to_coptic",
    "lemma_identification",
    "pos_identification",
    "dialect_identification",
    "verse_matching"
  ];

  function $(id) { return document.getElementById(id); }

  function esc(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (c) {
      return {
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
      }[c];
    });
  }

  function plainText(value) {
    return typeof value === "string" ? value : "";
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

  function defaultProgress() {
    return {
      version: 1,
      sessionsCompleted: 0,
      answered: 0,
      correct: 0,
      items: {}
    };
  }

  function loadProgress() {
    var stored = null;
    try {
      if (storageAvailable()) stored = window.localStorage.getItem(STORAGE_KEY);
    } catch (e) {
      stored = null;
    }
    if (!stored) return defaultProgress();
    try {
      var parsed = JSON.parse(stored);
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        return defaultProgress();
      }
      return {
        version: 1,
        sessionsCompleted: Number(parsed.sessionsCompleted) || 0,
        answered: Number(parsed.answered) || 0,
        correct: Number(parsed.correct) || 0,
        items: (parsed.items && typeof parsed.items === "object") ? parsed.items : {}
      };
    } catch (e) {
      return defaultProgress();
    }
  }

  function saveProgress(progress) {
    if (!storageAvailable()) return false;
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(progress));
      return true;
    } catch (e) {
      return false;
    }
  }

  function itemState(progress, id) {
    var state = progress.items[id];
    if (!state || typeof state !== "object") {
      state = { seen: 0, correct: 0, wrong: 0, streak: 0, nextDueSession: 0 };
      progress.items[id] = state;
    }
    return state;
  }

  /* Wrong answers reappear sooner: a miss is due in the next session, while a
   * hit waits longer with every consecutive success. New items are due now.
   */
  function chooseSession(items, progress) {
    var upcoming = progress.sessionsCompleted + 1;
    var scored = items.map(function (item, index) {
      var state = itemState(progress, item.id);
      var due = typeof state.nextDueSession === "number" ? state.nextDueSession : 0;
      var unseen = !state.seen ? 0 : 1;
      return { item: item, due: due, unseen: unseen, wrong: state.wrong || 0, index: index };
    });
    scored.sort(function (a, b) {
      if (a.due !== b.due) return a.due - b.due;
      if (a.unseen !== b.unseen) return a.unseen - b.unseen;
      if (a.wrong !== b.wrong) return b.wrong - a.wrong;
      return a.index - b.index;
    });
    var selected = scored.filter(function (entry) {
      return entry.due <= upcoming || entry.unseen === 0;
    }).slice(0, SESSION_SIZE).map(function (entry) { return entry.item; });
    if (selected.length < Math.min(SESSION_SIZE, items.length)) {
      var have = {};
      selected.forEach(function (item) { have[item.id] = true; });
      scored.forEach(function (entry) {
        if (selected.length >= Math.min(SESSION_SIZE, items.length)) return;
        if (!have[entry.item.id]) {
          have[entry.item.id] = true;
          selected.push(entry.item);
        }
      });
    }
    return { upcoming: upcoming, items: selected };
  }

  function bankURL(type, band) {
    if (type === "verse_matching") return BANK_ROOT + "verse_matching.json.gz";
    return BANK_ROOT + type + "-" + band + ".json.gz";
  }

  function validateBank(payload, type, band) {
    if (!Array.isArray(payload) || !payload.length) {
      throw new Error("quiz bank is empty");
    }
    payload.forEach(function (item, index) {
      if (!item || typeof item !== "object" || Array.isArray(item)) {
        throw new Error("quiz item " + index + " is not an object");
      }
      if (typeof item.prompt !== "string" || !item.prompt.trim()) {
        throw new Error("quiz item " + (item.id || index) + " has no prompt");
      }
      if (!Array.isArray(item.choices) || item.choices.length < 2 ||
          item.choices.some(function (choice) { return typeof choice !== "string"; })) {
        throw new Error("quiz item " + (item.id || index) + " has no usable choices");
      }
      if (typeof item.correct !== "number" || item.correct < 0 ||
          item.correct >= item.choices.length) {
        throw new Error("quiz item " + (item.id || index) + " has no valid answer");
      }
      if (item.type !== type) {
        throw new Error("quiz item " + (item.id || index) + " is the wrong type");
      }
      if (type !== "verse_matching" && item.difficulty !== band) {
        throw new Error("quiz item " + (item.id || index) + " is the wrong band");
      }
    });
    return payload;
  }

  /* Rule 11: even though the bank carries a precomputed prompt string, a
   * transliteration question is displayed only through translitDisplay(). The
   * source object travels with the item for exactly this call, and a mismatch
   * fails loudly rather than silently showing a stale string. */
  function displayPrompt(item) {
    if (item.type === "transliteration_to_coptic") {
      if (typeof translitDisplay !== "function") {
        throw new Error("translit.js did not load before quiz.js");
      }
      var source = item.source || {};
      var rendered = translitDisplay({
        translit: source.translit_snapshot || {},
        forms: source.romanization_forms || []
      }, source.translit_scheme || "romanization");
      if (rendered !== item.prompt) {
        throw new Error("quiz prompt does not match translitDisplay()");
      }
      return rendered;
    }
    return item.prompt;
  }

  function sourceLink(item) {
    var source = item.source || {};
    if (item.type === "verse_matching" && source.work_slug != null &&
        source.verse_index != null) {
      return '<p class="quiz-source">Source: <a href="/corpus/' +
        esc(source.work_slug) + '/#v' + esc(source.verse_index) + '">verse ' +
        esc(source.ref || source.verse_index) + " in " + esc(source.work_slug) +
        "</a></p>";
    }
    if (source.entry_id && item.answer_kind !== "gloss") {
      var lemma = null;
      if (item.answer_kind === "lemma") {
        lemma = item.choices[item.correct];
      } else if (item.prompt_kind === "lemma" || item.prompt_kind === "inflected_form") {
        lemma = item.prompt;
      }
      if (lemma) {
        return '<p class="quiz-source">Source: <a href="/dict/?q=' +
          encodeURIComponent(lemma) + '">dictionary entry ' + esc(source.entry_id) +
          "</a></p>";
      }
      return '<p class="quiz-source">Source: dictionary entry ' +
        esc(source.entry_id) + "</p>";
    }
    return "";
  }

  function questionLabel(item) {
    switch (item.type) {
      case "coptic_to_english": return "Choose the English gloss";
      case "english_to_coptic": return "Choose the Coptic lemma";
      case "transliteration_to_coptic": return "Choose the Coptic lemma";
      case "lemma_identification": return "Choose the lemma for this form";
      case "pos_identification": return "Choose the part of speech";
      case "dialect_identification": return "Choose the dialect";
      case "verse_matching": return "Choose the English translation";
      default: return "Choose the answer";
    }
  }

  function renderScore(progress, current, total) {
    var overall = progress.answered
      ? Math.round((progress.correct / progress.answered) * 100)
      : 0;
    return "Session " + current + "/" + total +
      " · all sessions " + progress.correct + "/" + progress.answered +
      " (" + overall + "%)" +
      (storageAvailable() ? "" : " · progress is in memory only");
  }

  async function startSession() {
    var typeEl = $("quiz-type");
    var bandEl = $("quiz-band");
    var status = $("quiz-status");
    var promptEl = $("quiz-prompt");
    var choicesEl = $("quiz-choices");
    var feedbackEl = $("quiz-feedback");
    var scoreEl = $("quiz-score");
    var progressEl = $("quiz-progress");
    if (!typeEl || !bandEl || !promptEl || !choicesEl || !feedbackEl || !scoreEl) return;

    var type = typeEl.value;
    var band = type === "verse_matching" ? "all" : bandEl.value;
    var progress = loadProgress();
    status.textContent = "Loading " + type.replace(/_/g, " ") + " questions …";
    feedbackEl.textContent = "";
    promptEl.textContent = "";
    choicesEl.innerHTML = "";
    progressEl.textContent = "";

    var bank;
    try {
      if (typeof FetchJson === "undefined") {
        throw new Error("fetch_json.js did not load before quiz.js");
      }
      bank = validateBank(await FetchJson.json(bankURL(type, band)), type, band);
    } catch (e) {
      status.textContent = "Could not load this quiz: " + (e && e.message ? e.message : e);
      return;
    }

    var selection = chooseSession(bank, progress);
    var session = selection.items;
    var answered = 0;
    var right = 0;
    scoreEl.textContent = renderScore(progress, answered, session.length);

    function renderQuestion(position) {
      var item = session[position];
      var state = itemState(progress, item.id);
      promptEl.textContent = displayPrompt(item);
      progressEl.innerHTML = "<strong>" + questionLabel(item) + "</strong> · question " +
        (position + 1) + " of " + session.length +
        (item.translit_scheme ? " · " + esc(item.translit_scheme) + " romanization" : "") +
        sourceLink(item);
      scoreEl.textContent = renderScore(progress, answered, session.length);
      feedbackEl.textContent = "";
      choicesEl.innerHTML = "";
      item.choices.forEach(function (choice, index) {
        var button = document.createElement("button");
        button.type = "button";
        button.className = "hit";
        // The answer key stays in memory. Putting it in the DOM would make the
        // quiz solvable by inspection rather than by knowledge.
        button.innerHTML = '<span class="choice">' + esc(choice) + "</span>";
        button.addEventListener("click", function () {
          Array.prototype.forEach.call(choicesEl.querySelectorAll("button"), function (other) {
            other.disabled = true;
          });
          var isRight = index === item.correct;
          button.classList.add(isRight ? "right" : "wrong");
          if (!isRight && choicesEl.children[item.correct]) {
            choicesEl.children[item.correct].classList.add("right");
          }
          state.seen += 1;
          progress.answered += 1;
          answered += 1;
          if (isRight) {
            state.correct += 1;
            state.streak += 1;
            state.nextDueSession = selection.upcoming + Math.min(2 + state.streak, 8);
            right += 1;
            feedbackEl.textContent = "Correct.";
          } else {
            state.wrong += 1;
            state.streak = 0;
            state.nextDueSession = selection.upcoming + 1;
            feedbackEl.textContent = "Not quite — the answer is “" +
              item.choices[item.correct] + "”. It will come back sooner.";
          }
          saveProgress(progress);
          scoreEl.textContent = renderScore(progress, answered, session.length);
          var next = document.createElement("button");
          next.type = "button";
          next.className = "quiz-next";
          next.textContent = position + 1 < session.length ? "Next question" : "Finish session";
          next.addEventListener("click", function () {
            if (position + 1 < session.length) {
              renderQuestion(position + 1);
            } else {
              progress.sessionsCompleted += 1;
              saveProgress(progress);
              promptEl.textContent = "Session complete.";
              choicesEl.innerHTML = "";
              progressEl.innerHTML = "";
              feedbackEl.textContent = "You answered " + right + " of " +
                session.length + " correctly. Missed items are due again next session.";
              scoreEl.textContent = renderScore(progress, answered, session.length);
              status.textContent = "Finished " + type.replace(/_/g, " ") + ".";
            }
          });
          feedbackEl.appendChild(document.createElement("br"));
          feedbackEl.appendChild(next);
        });
        choicesEl.appendChild(button);
      });
    }

    status.textContent = "Loaded " + session.length + " questions.";
    renderQuestion(0);
  }

  function exportProgress() {
    var blob = new Blob([JSON.stringify(loadProgress(), null, 2)],
      { type: "application/json" });
    var link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "coptic-quiz-progress.json";
    document.body.appendChild(link);
    link.click();
    setTimeout(function () {
      URL.revokeObjectURL(link.href);
      link.remove();
    }, 0);
  }

  function importProgress(file, done) {
    var reader = new FileReader();
    reader.onload = function () {
      try {
        var parsed = JSON.parse(String(reader.result || ""));
        if (!parsed || typeof parsed !== "object" || Array.isArray(parsed) ||
            typeof parsed.items !== "object" || !parsed.items) {
          throw new Error("not a quiz progress file");
        }
        var progress = defaultProgress();
        progress.sessionsCompleted = Number(parsed.sessionsCompleted) || 0;
        progress.answered = Number(parsed.answered) || 0;
        progress.correct = Number(parsed.correct) || 0;
        progress.items = parsed.items;
        if (!saveProgress(progress) && storageAvailable()) {
          throw new Error("the browser refused to store progress");
        }
        done(null, progress);
      } catch (e) {
        done(e);
      }
    };
    reader.onerror = function () { done(new Error("could not read that file")); };
    reader.readAsText(file);
  }

  function init() {
    var typeEl = $("quiz-type");
    var bandEl = $("quiz-band");
    var start = $("quiz-start");
    if (!typeEl || !bandEl || !start) return;
    var score = $("quiz-score");
    if (score) score.textContent = renderScore(loadProgress(), 0, 0);
    var syncBand = function () {
      var isVerse = typeEl.value === "verse_matching";
      bandEl.disabled = isVerse;
      bandEl.setAttribute("aria-disabled", isVerse ? "true" : "false");
    };
    typeEl.addEventListener("change", syncBand);
    syncBand();
    start.addEventListener("click", startSession);

    var exportButton = $("quiz-export");
    if (exportButton) exportButton.addEventListener("click", exportProgress);
    var importInput = $("quiz-import-file");
    var importStatus = $("quiz-import-status");
    if (importInput) {
      importInput.addEventListener("change", function () {
        if (!importInput.files || !importInput.files.length) return;
        importProgress(importInput.files[0], function (error) {
          if (importStatus) {
            importStatus.textContent = error
              ? "Could not import progress: " + (error.message || error)
              : "Progress imported. Start a session to continue where it left off.";
          }
          importInput.value = "";
        });
      });
    }
    var reset = $("quiz-reset");
    if (reset) {
      reset.addEventListener("click", function () {
        try {
          if (storageAvailable()) window.localStorage.removeItem(STORAGE_KEY);
        } catch (e) {
          /* Resetting must work even when storage is unavailable. */
        }
        var score = $("quiz-score");
        if (score) score.textContent = renderScore(defaultProgress(), 0, 0);
        var status = $("quiz-status");
        if (status) status.textContent = "Progress cleared on this browser.";
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  root.Quiz = {
    chooseSession: chooseSession,
    loadProgress: loadProgress,
    bankURL: bankURL,
    STORAGE_KEY: STORAGE_KEY
  };
  if (typeof module !== "undefined" && module.exports) {
    module.exports = root.Quiz;
  }
})(typeof globalThis !== "undefined" ? globalThis : this);
