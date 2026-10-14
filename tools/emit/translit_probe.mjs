#!/usr/bin/env node
/*
 * tools/emit/translit_probe.mjs — call the shipped transliteration renderer.
 *
 * Session 16 D1. Python must not reimplement translitDisplay(): a second
 * implementation is how two renderers drift apart and how one of them becomes
 * wrong. This tiny harness loads static/js/translit.js and returns its answers.
 *
 * Input is one JSON object per line on stdin:
 *   {"translit": {...}, "forms": [...], "scheme": "romanization"}
 * Output is one JSON string per line, in the same order.
 *
 * LICENCE: project code, Apache-2.0.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const HELPER = path.join(ROOT, "static", "js", "translit.js");
const source = fs.readFileSync(HELPER, "utf8");
const module = { exports: {} };
new Function("module", "globalThis", source)(module, globalThis);
const display = module.exports && Object.keys(module.exports).length
  ? module.exports
  : globalThis.translitDisplay;
if (typeof display !== "function") {
  console.error("[translit_probe] translit.js did not export translitDisplay");
  process.exit(1);
}

const lines = fs.readFileSync(0, "utf8").split("\n").filter((line) => line !== "");
const out = lines.map((line, index) => {
  let task;
  try {
    task = JSON.parse(line);
  } catch (e) {
    console.error(`[translit_probe] line ${index + 1} is not JSON: ${e.message}`);
    process.exit(1);
  }
  const rendered = display(task, task.scheme || "bohairic");
  if (typeof rendered !== "string") {
    console.error(`[translit_probe] line ${index + 1} did not return a string`);
    process.exit(1);
  }
  return JSON.stringify(rendered);
});
process.stdout.write(out.join("\n") + (out.length ? "\n" : ""));
