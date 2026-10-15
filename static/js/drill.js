/* static/js/drill.js — the client-side cloze drill renderer. Session 18 D4.
 *
 * LICENCE: project code, Apache-2.0.
 *
 * No framework, no build step, no server, no accounts. One bank file is
 * fetched per session, ten verses are rendered with one blank each, and
 * progress stays in the reader's own browser.
 *
 * Same shape as quiz.js: FetchJson fetches, localStorage persists, and the
 * bank carries precomputed strings the UI refuses to second-guess. Drill
 * items carry no structured schema fields, so there is nothing here that
 * could print the raw-object marker — and the Playwright suite asserts that.
 */
(function (root) {
  "use strict";

  var BANK_ROOT = "/data/drill/";
  var SESSION_SIZE = 10;
  var STORAGE_KEY = "coptic-drill-progress-v1";
  var WORKS = [
    "bohairic_1corinthians",
    "bohairic_mark",
    "lausiac_history",
    "life_of_isaac",
    "martyrdom_of_victor",
    "sahidic_ruth"
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
    var progress = defaultProgress();
    if (!storageAvailable()) return progress;
    try {
      var parsed = JSON.parse(window.localStorage.getItem(STORAGE_KEY));
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        if (typeof parsed.sessionsCompleted === "number") {
          progress.sessionsCompleted = parsed.sessionsCompleted;
        }
        if (typeof parsed.answered === "number") progress.answered = parsed.answered;
        if (typeof parsed.correct === "number") progress.correct = parsed.correct;
        if (parsed.items && typeof parsed.items === "object") progress.items = parsed.items;
      }
    } catch (e) {
      /* A corrupt progress blob is not the reader's problem to debug. */
    }
    return progress;
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

  var DRILL_TYPES = ["cloze", "pos", "lemma"];

  function bankURL(type, work) {
    if (type === "cloze") return BANK_ROOT + "cloze-" + work + ".json.gz";
    return BANK_ROOT + "parse-" + work + ".json.gz";
  }

  function drillType(item) {
    // Cloze banks shipped without the field before Session 20 D4; a missing
    // field has always meant cloze, so old banks keep working.
    return item.drill_type || "cloze";
  }

  function validateBank(bank, work) {
    if (!bank || typeof bank !== "object" || Array.isArray(bank)) {
      throw new Error("drill bank is not an object");
    }
    if (bank.work_slug !== work) {
      throw new Error("drill bank is for the wrong work");
    }
    var items = bank.items;
    if (!Array.isArray(items) || items.length === 0) {
      throw new Error("drill bank has no items");
    }
    items.forEach(function (item, index) {
      if (!item || typeof item !== "object") throw new Error("item " + index + " is not an object");
      ["id", "work_slug"].forEach(function (field) {
        if (typeof item[field] !== "string" || item[field] === "") {
          throw new Error("item " + index + " has no " + field);
        }
      });
      var kind = drillType(item);
      if (kind !== "cloze" && kind !== "pos" && kind !== "lemma") {
        throw new Error("item " + index + " has an unknown drill type");
      }
      if (!Array.isArray(item.tokens) || item.tokens.length === 0) {
        throw new Error("item " + index + " has no verse");
      }
      if (kind === "cloze") {
        if (typeof item.blank !== "number" ||
            item.blank < 0 || item.blank >= item.tokens.length) {
          throw new Error("item " + index + " has a blank outside its verse");
        }
      } else {
        if (typeof item.token_index !== "number" ||
            item.token_index < 0 || item.token_index >= item.tokens.length) {
          throw new Error("item " + index + " has a token outside its verse");
        }
      }
      if (!Array.isArray(item.choices) || item.choices.length !== 4 ||
          typeof item.correct !== "number" ||
          item.correct < 0 || item.correct > 3) {
        throw new Error("item " + index + " does not offer four choices");
      }
    });
    return bank;
  }

  function renderScore(progress, current, total) {
    var overall = progress.answered
      ? Math.round((progress.correct / progress.answered) * 100)
      : 0;
    return "Drill " + current + "/" + total +
      " · all sessions " + progress.correct + "/" + progress.answered +
      " (" + overall + "%)" +
      (storageAvailable() ? "" : " · progress is in memory only");
  }

  function verseHTML(item) {
    var kind = drillType(item);
    return item.tokens.map(function (token, index) {
      if (kind === "cloze" && index === item.blank) {
        return '<span class="drill-blank" aria-label="missing word">____</span>';
      }
      if (kind !== "cloze" && index === item.token_index) {
        return '<span class="drill-target" aria-label="questioned token"><strong>' +
          esc(token) + "</strong></span>";
      }
      return "<span>" + esc(token) + "</span>";
    }).join(" ");
  }

  function questionText(item) {
    var kind = drillType(item);
    if (kind === "pos") return "What part of speech is the marked word?";
    if (kind === "lemma") return "Which dictionary headword is the marked word?";
    return "Fill the gap";
  }

  function answerLink(item) {
    var source = item.source || {};
    var kind = drillType(item);
    if (kind === "lemma") {
      var lemma = item.choices[item.correct];
      return lemmaLink(plainText(lemma));
    }
    if (kind === "cloze") return lemmaLink(plainText(source.lemma));
    return "";
  }

  function lemmaLink(lemma) {
    return '<p class="quiz-source">Answer: <a href="/dict/?q=' +
      encodeURIComponent(lemma) + '">' + esc(lemma) + "</a></p>";
  }

  async function startSession() {
    var workEl = $("drill-work");
    var typeEl = $("drill-type");
    var status = $("drill-status");
    var promptEl = $("drill-prompt");
    var choicesEl = $("drill-choices");
    var feedbackEl = $("drill-feedback");
    var scoreEl = $("drill-score");
    var progressEl = $("drill-progress");
    if (!workEl || !promptEl || !choicesEl || !feedbackEl || !scoreEl) return;

    var work = workEl.value;
    var type = typeEl ? typeEl.value : "cloze";
    if (DRILL_TYPES.indexOf(type) === -1) type = "cloze";
    var progress = loadProgress();
    status.textContent = "Loading " + type + " drills for " + work.replace(/_/g, " ") + " …";
    feedbackEl.textContent = "";
    promptEl.textContent = "";
    choicesEl.innerHTML = "";
    progressEl.textContent = "";

    var bank;
    try {
      if (typeof FetchJson === "undefined") {
        throw new Error("fetch_json.js did not load before drill.js");
      }
      bank = validateBank(await FetchJson.json(bankURL(type, work)), work);
    } catch (e) {
      status.textContent = "Could not load these drills: " + (e && e.message ? e.message : e);
      return;
    }

    var pool = bank.items.filter(function (item) {
      return drillType(item) === type;
    });
    var offset = pool.length
      ? (progress.sessionsCompleted * SESSION_SIZE) % pool.length
      : 0;
    var session = [];
    for (var k = 0; k < SESSION_SIZE && k < pool.length; k += 1) {
      session.push(pool[(offset + k) % pool.length]);
    }
    var answered = 0;
    var right = 0;
    scoreEl.textContent = renderScore(progress, answered, session.length);

    function renderQuestion(position) {
      var item = session[position];
      promptEl.innerHTML = verseHTML(item);
      var context = item.context || {};
      var bits = [];
      if (context.prev != null) bits.push("before: “" + context.prev + "”");
      if (context.next != null) bits.push("after: “" + context.next + "”");
      progressEl.innerHTML = "<strong>" + esc(questionText(item)) + "</strong> · question " +
        (position + 1) + " of " + session.length +
        (bits.length ? " · " + esc(bits.join("; ")) : "") +
        (item.ref ? " · verse " + esc(item.ref) : "");
      scoreEl.textContent = renderScore(progress, answered, session.length);
      feedbackEl.textContent = "";
      choicesEl.innerHTML = "";
      item.choices.forEach(function (choice, index) {
        var button = document.createElement("button");
        button.type = "button";
        button.className = "hit";
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
          progress.answered += 1;
          answered += 1;
          var key = item.id;
          progress.items[key] = progress.items[key] || { seen: 0, correct: 0 };
          progress.items[key].seen += 1;
          if (isRight) {
            progress.items[key].correct += 1;
            right += 1;
            progress.correct += 1;
            feedbackEl.textContent = "Correct. ";
          } else {
            feedbackEl.textContent = "Not quite — the verse has “" +
              item.choices[item.correct] + "”. ";
          }
          saveProgress(progress);
          feedbackEl.innerHTML = esc(feedbackEl.textContent) + answerLink(item);
          scoreEl.textContent = renderScore(progress, answered, session.length);
          var next = document.createElement("button");
          next.type = "button";
          next.className = "drill-next";
          next.textContent = position + 1 < session.length ? "Next drill" : "Finish session";
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
                session.length + " correctly.";
              scoreEl.textContent = renderScore(progress, answered, session.length);
              status.textContent = "Finished drills for " + work.replace(/_/g, " ") + ".";
            }
          });
          feedbackEl.appendChild(document.createElement("br"));
          feedbackEl.appendChild(next);
        });
        choicesEl.appendChild(button);
      });
    }

    status.textContent = "Loaded " + session.length + " drills.";
    renderQuestion(0);
  }

  function init() {
    var workEl = $("drill-work");
    var start = $("drill-start");
    if (!workEl || !start) return;
    var score = $("drill-score");
    if (score) score.textContent = renderScore(loadProgress(), 0, 0);
    start.addEventListener("click", startSession);
    var reset = $("drill-reset");
    if (reset) {
      reset.addEventListener("click", function () {
        try {
          if (storageAvailable()) window.localStorage.removeItem(STORAGE_KEY);
        } catch (e) {
          /* Resetting must work even when storage is unavailable. */
        }
        var scoreEl = $("drill-score");
        if (scoreEl) scoreEl.textContent = renderScore(defaultProgress(), 0, 0);
        var status = $("drill-status");
        if (status) status.textContent = "Progress cleared on this browser.";
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  root.Drill = {
    bankURL: bankURL,
    validateBank: validateBank,
    STORAGE_KEY: STORAGE_KEY,
    WORKS: WORKS
  };
  if (typeof module !== "undefined" && module.exports) {
    module.exports = root.Drill;
  }
})(typeof globalThis !== "undefined" ? globalThis : this);
