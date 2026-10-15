/* static/js/course.js — the structured course renderer. Session 19 D4.
 *
 * LICENCE: project code, Apache-2.0.
 *
 * No framework, no build step, no server, no accounts, no telemetry. The
 * course file (data/dist/course/course.json.gz) chains the banks the site
 * already ships: quiz banks by band, drill banks by work. Checkpoints are
 * real ten-question sessions drawn from the lesson band's vocabulary banks,
 * preferring items whose answer is one of the lesson's own vocabulary
 * lemmas; scoring ≥ threshold unlocks the next lesson. Progress — passes
 * and attempts — stays in this browser.
 *
 * Same shape as quiz.js and drill.js: FetchJson fetches, localStorage
 * persists, and bank strings are rendered as-is, never interpolated as
 * objects (there is no structured schema field here that could print the
 * raw-object marker, and the Playwright suite asserts it).
 */
(function (root) {
  "use strict";

  var COURSE_URL = "/data/course/course.json.gz";
  var QUIZ_ROOT = "/data/quiz/";
  var SESSION_SIZE = 10;
  var STORAGE_KEY = "coptic-course-progress-v1";

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

  function defaultProgress() {
    return { version: 1, passed: {}, attempts: {} };
  }

  function loadProgress() {
    var progress = defaultProgress();
    if (!storageAvailable()) return progress;
    try {
      var parsed = JSON.parse(window.localStorage.getItem(STORAGE_KEY));
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        if (parsed.passed && typeof parsed.passed === "object") progress.passed = parsed.passed;
        if (parsed.attempts && typeof parsed.attempts === "object") progress.attempts = parsed.attempts;
      }
    } catch (e) {
      /* Corrupt progress is reset silently; nothing leaves the browser. */
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

  function isUnlocked(progress, number) {
    if (number <= 1) return true;
    return !!progress.passed[String(number - 1)];
  }

  function validateCourse(course) {
    if (!course || typeof course !== "object" || !Array.isArray(course.lessons)) {
      throw new Error("course file is not a course");
    }
    if (course.lessons.length !== 15) throw new Error("course has no 15 lessons");
    course.lessons.forEach(function (lesson, index) {
      if (!lesson || lesson.number !== index + 1) {
        throw new Error("lesson order is broken at position " + index);
      }
      ["title", "reading", "vocabulary", "quiz", "drill",
        "corpus", "checkpoint"].forEach(function (field) {
        if (lesson[field] == null) throw new Error("lesson " + lesson.number + " has no " + field);
      });
      var wantPrereq = lesson.number <= 1 ? null : lesson.number - 1;
      if (lesson.prerequisite !== wantPrereq) {
        throw new Error("lesson " + lesson.number + " has the wrong prerequisite");
      }
    });
    return course;
  }

  function quizBankURL(band, type) {
    return QUIZ_ROOT + type + "-" + band + ".json.gz";
  }

  function vocabSet(lesson) {
    var set = {};
    ((lesson.vocabulary || {}).lemmas || []).forEach(function (lemma) {
      set[lemma] = true;
    });
    return set;
  }

  function checkpointPool(c2e, t2c, lesson) {
    var vocab = vocabSet(lesson);
    var preferred = [];
    var rest = [];
    // Quiz banks ship as bare lists, not {items} objects.
    var c2eItems = Array.isArray(c2e) ? c2e : (c2e.items || []);
    var t2cItems = Array.isArray(t2c) ? t2c : (t2c.items || []);
    c2eItems.forEach(function (item) {
      if (!item || item.type !== "coptic_to_english") return;
      (vocab[item.prompt] ? preferred : rest).push(item);
    });
    t2cItems.forEach(function (item) {
      if (!item || item.type !== "transliteration_to_coptic") return;
      var answer = item.choices && item.choices[item.correct];
      (vocab[answer] ? preferred : rest).push(item);
    });
    return preferred.concat(rest);
  }

  function renderLessonList(course, progress, host) {
    host.innerHTML = "";
    course.lessons.forEach(function (lesson) {
      var unlocked = isUnlocked(progress, lesson.number);
      var passed = !!progress.passed[String(lesson.number)];
      var wrap = document.createElement("article");
      wrap.className = "course-lesson" + (passed ? " done" : unlocked ? " open" : " locked");
      var head = document.createElement("h2");
      head.textContent = lesson.number + ". " + lesson.title +
        (passed ? " — passed" : unlocked ? "" : " — locked");
      wrap.appendChild(head);
      var detail = document.createElement("p");
      detail.className = "note";
      detail.textContent = "Quiz: " + lesson.quiz.band + " · Drill: " +
        lesson.drill.work.replace(/_/g, " ") + " · Reading: lesson " + lesson.number;
      wrap.appendChild(detail);
      if (!unlocked) {
        var lock = document.createElement("p");
        lock.textContent = "Pass lesson " + (lesson.number - 1) + " first — or unlock everything below.";
        wrap.appendChild(lock);
        host.appendChild(wrap);
        return;
      }
      var start = document.createElement("button");
      start.type = "button";
      start.className = "hit";
      start.textContent = passed ? "Retake checkpoint" : "Start checkpoint";
      start.addEventListener("click", function () {
        startCheckpoint(lesson, progress);
      });
      wrap.appendChild(start);
      var links = document.createElement("p");
      links.innerHTML = "Study first: " +
        '<a href="/lessons/' + String(lesson.number).padStart(2, "0") + '/">reading</a> · ' +
        '<a href="/quiz/">quiz (' + esc(lesson.quiz.band) + ")</a> · " +
        '<a href="/drill/">drills (' + esc(lesson.drill.work.replace(/_/g, " ")) + ")</a> · " +
        '<a href="/corpus/' + esc(lesson.corpus.work) + "/#v" + lesson.corpus.verse_start + '">passage</a>';
      wrap.appendChild(links);
      host.appendChild(wrap);
    });
  }

  function startCheckpoint(lesson, progress) {
    var status = $("course-status");
    var area = $("course-checkpoint");
    if (!status || !area) return;
    status.textContent = "Loading checkpoint for lesson " + lesson.number + " …";
    area.innerHTML = "";
    var band = lesson.quiz.band;
    Promise.all([
      FetchJson.json(quizBankURL(band, "coptic_to_english")),
      FetchJson.json(quizBankURL(band, "transliteration_to_coptic"))
    ]).then(function (banks) {
      var pool = checkpointPool(banks[0], banks[1], lesson);
      if (pool.length === 0) throw new Error("no checkpoint questions for this lesson");
      var attempts = Number(progress.attempts[String(lesson.number)] || 0);
      var offset = pool.length ? (attempts * SESSION_SIZE) % pool.length : 0;
      var session = [];
      for (var k = 0; k < SESSION_SIZE && k < pool.length; k += 1) {
        session.push(pool[(offset + k) % pool.length]);
      }
      runSession(lesson, session, progress);
    }).catch(function (e) {
      status.textContent = "Could not load this checkpoint: " + (e && e.message ? e.message : e);
    });
  }

  function runSession(lesson, session, progress) {
    var status = $("course-status");
    var area = $("course-checkpoint");
    var right = 0;
    var threshold = Number((lesson.checkpoint || {}).threshold || 70);

    function render(position) {
      var item = session[position];
      area.innerHTML = "";
      var prompt = document.createElement("h3");
      prompt.textContent = item.prompt;
      area.appendChild(prompt);
      var meta = document.createElement("p");
      meta.className = "note";
      meta.textContent = "Checkpoint question " + (position + 1) + " of " + session.length;
      area.appendChild(meta);
      var list = document.createElement("ul");
      list.className = "hits";
      area.appendChild(list);
      var feedback = document.createElement("p");
      feedback.className = "note";
      area.appendChild(feedback);
      item.choices.forEach(function (choice, index) {
        var button = document.createElement("button");
        button.type = "button";
        button.className = "hit";
        button.textContent = choice;
        button.addEventListener("click", function () {
          Array.prototype.forEach.call(list.querySelectorAll("button"), function (other) {
            other.disabled = true;
          });
          var isRight = index === item.correct;
          button.classList.add(isRight ? "right" : "wrong");
          if (!isRight && list.children[item.correct]) {
            list.children[item.correct].classList.add("right");
          }
          if (isRight) right += 1;
          var next = document.createElement("button");
          next.type = "button";
          next.className = "course-next";
          next.textContent = position + 1 < session.length ? "Next" : "Finish checkpoint";
          next.addEventListener("click", function () {
            if (position + 1 < session.length) {
              render(position + 1);
            } else {
              finish(right);
            }
          });
          feedback.textContent = isRight ? "Correct."
            : "Not quite — the answer is “" + item.choices[item.correct] + "”.";
          feedback.appendChild(document.createElement("br"));
          feedback.appendChild(next);
        });
        list.appendChild(button);
      });
    }

    function finish(score) {
      var need = Math.ceil((threshold / 100) * session.length);
      var passed = score >= need;
      progress.attempts[String(lesson.number)] =
        Number(progress.attempts[String(lesson.number)] || 0) + 1;
      if (passed) progress.passed[String(lesson.number)] = true;
      saveProgress(progress);
      status.textContent = passed
        ? "Lesson " + lesson.number + " passed (" + score + "/" + session.length +
          "). Lesson " + (lesson.number + 1) + " is unlocked."
        : "Scored " + score + "/" + session.length + " — need " + need +
          ". Study and retry; the next attempt rotates questions.";
      init();
    }

    status.textContent = "Checkpoint: " + session.length + " questions, " +
      threshold + "% to pass.";
    render(0);
  }

  function init() {
    var host = $("course-lessons");
    var status = $("course-status");
    if (!host) return;
    var progress = loadProgress();
    if (typeof FetchJson === "undefined") {
      if (status) status.textContent = "fetch_json.js did not load before course.js";
      return;
    }
    FetchJson.json(COURSE_URL).then(function (course) {
      validateCourse(course);
      renderLessonList(course, progress, host);
      if (status) status.textContent = "Fifteen lessons. Pass each checkpoint to unlock the next.";
      var all = $("course-unlock-all");
      if (all && !all.dataset.wired) {
        all.dataset.wired = "1";
        all.addEventListener("click", function () {
          var next = loadProgress();
          for (var n = 1; n <= 15; n += 1) next.passed[String(n)] = true;
          saveProgress(next);
          init();
        });
      }
    }).catch(function (e) {
      if (status) status.textContent = "Could not load the course: " + (e && e.message ? e.message : e);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  root.Course = {
    validateCourse: validateCourse,
    isUnlocked: isUnlocked,
    STORAGE_KEY: STORAGE_KEY
  };
  if (typeof module !== "undefined" && module.exports) {
    module.exports = root.Course;
  }
})(typeof globalThis !== "undefined" ? globalThis : this);
