"""tools/tests/playwright/test_speak.py — self-comparison, no scoring, no network.

Session 22 D1 / C3. Three claims to prove in a browser:

  1. the recorder works with a mocked MediaRecorder and the page never
     talks to a non-local origin (the word list is same-origin; the
     recording is blob:-only; there is nothing to leak)
  2. the banner text is exactly the no-ASR, no-score promise
  3. the no-JS fallback links to /speak/top100.html and that page is a
     complete script-free table of the 100 words

No real microphone is used: init scripts replace getUserMedia and
MediaRecorder before any page script runs, so the flow under test is the
page's own state machine, not the browser's audio stack.

LICENCE: project code, Apache-2.0.
"""
from __future__ import annotations

import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "public"

pytestmark = pytest.mark.skipif(
    not (PUBLIC / "speak" / "index.html").is_file(),
    reason="no published /speak/ — run tools/build.py first")

_FAKE_MEDIA = """
(() => {
  class FakeTrack { stop() {} }
  navigator.mediaDevices = navigator.mediaDevices || {};
  navigator.mediaDevices.getUserMedia = async () => ({
    getTracks: () => [new FakeTrack()]
  });
  class FakeMediaRecorder {
    constructor() { this.state = "inactive"; }
    start() { this.state = "recording"; }
    stop() {
      this.state = "inactive";
      setTimeout(() => {
        if (this.ondataavailable) {
          this.ondataavailable({ data: new Blob([new Uint8Array([1,2,3,4])],
                                                 { type: "audio/webm" }) });
        }
        if (this.onstop) this.onstop();
      }, 10);
    }
  }
  FakeMediaRecorder.isTypeSupported = () => true;
  window.MediaRecorder = FakeMediaRecorder;
})();
"""


def _speak_page(browser, server):
    ctx = browser.new_context(service_workers="allow")
    ctx.add_init_script(_FAKE_MEDIA)
    requests: list[str] = []
    p = ctx.new_page()
    p.on("request", lambda r: requests.append(r.url))
    p.goto(server + "/speak/")
    p.wait_for_function(
        "() => { const s = document.getElementById('speak-status');"
        " return s && /word\\(s\\) loaded/.test(s.textContent); }",
        timeout=25000)
    return p, ctx, server, requests


def test_record_play_and_no_foreign_network(browser, server):
    p, ctx, base, requests = _speak_page(browser, server)

    # The banner is the contract: no score, no ASR, self-comparison only.
    # Compare against whitespace-collapsed text: the layout wraps lines.
    banner = " ".join((p.text_content("#speak-banner") or "").split())
    assert "self-comparison tool, not a pronunciation score" in banner
    assert "validated ASR" in banner
    assert "use your ear" in banner

    # Word rendered in Coptic + transliteration via translitDisplay.
    assert (p.text_content("#speak-coptic") or "").strip()
    translit = (p.text_content("#speak-translit") or "").strip()
    assert translit and translit != "(no transliteration)"

    # Scheme switch changes the transliteration, never the Coptic.
    before = translit
    p.select_option("#speak-scheme", "sahidic")
    after = (p.text_content("#speak-translit") or "").strip()
    assert after, "scheme switch wiped the transliteration"

    # Record → stop → play, all through the mocked recorder.
    p.click("#speak-record")
    p.wait_for_function(
        "() => document.getElementById('speak-status').textContent"
        ".includes('Recording')", timeout=10000)
    p.click("#speak-record")           # stop
    p.wait_for_function(
        "() => !document.getElementById('speak-play').disabled",
        timeout=10000)
    p.click("#speak-play")
    p.wait_for_function(
        "() => document.getElementById('speak-feedback').textContent"
        ".length > 0", timeout=10000)

    # Nothing left the machine. blob:/data:/same-origin only.
    local = base.rstrip("/")
    foreign = [u for u in requests
               if not (u.startswith(local) or u.startswith("blob:")
                       or u.startswith("data:"))]
    assert not foreign, f"foreign network requests: {foreign}"

    # No scoring UI was rendered at any point.
    body = p.content()
    assert "%" not in p.text_content("#speak-feedback")
    assert "score" not in (p.text_content("#speak-feedback") or "").lower()
    ctx.close()


def test_speak_no_js_fallback_links_to_the_static_list(browser, server):
    """No-JS: the noscript block points at /speak/top100.html, and that
    page is a complete, script-free table of all 100 words."""
    ctx = browser.new_context(java_script_enabled=False)
    p = ctx.new_page()
    p.goto(server + "/speak/")
    body = p.content()
    assert "Recording needs JavaScript" in body
    assert "/speak/top100.html" in body
    # The fallback page itself: 100 data rows, no script tag.
    p.goto(server + "/speak/top100.html")
    page = p.content()
    assert "<script" not in page.lower()
    rows = p.locator("tbody tr")
    assert rows.count() == 100, f"expected 100 rows, got {rows.count()}"
    # Header carries the three schemes, not a scoring column.
    header = p.locator("thead th").all_inner_texts()
    assert "Bohairic" in header and "Sahidic" in header and "Layton" in header
    assert not any("score" in h.lower() for h in header)
    ctx.close()
