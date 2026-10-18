#!/usr/bin/env node
/* tools/validate/js_object_scan.mjs — AST scan of JS for rendered-object leaks.
 *
 * LICENCE: project code, Apache-2.0.
 *
 * Session 22 D0 / C1. Companion to tools/validate/no_object_object_guard.py,
 * which keeps the byte-level text scan for HTML and JSON and delegates every
 * published .js file to this scanner.
 *
 * Why AST, not grep (E34). Session 21 wrote a comment in pos_labels.js that
 * MENTIONED the needle string in order to explain what the guard prevents, and
 * the text scan failed the build for it. A comment cannot render. Comments
 * are not in the AST, so they cannot be flagged. The scan now asks the only
 * question that matters: can this literal reach a page?
 *
 * What is flagged (all three, per the Session 22 spec):
 *   1. a string literal containing the needle used in a `+` concatenation
 *   2. a template literal whose cooked/raw text contains the needle
 *   3. a literal (or template) assigned to innerHTML / textContent, or
 *      passed to document.write(...)
 *
 * What is deliberately NOT flagged:
 *   - comments (absent from the AST)
 *   - a bare `const s = "[object Object]"` with no sink — dead data, not a
 *     rendering path; the Session 22 spec says only concatenations, template
 *     literals, and innerHTML/textContent/document.write sinks count
 *   - equality comparisons (`x !== "[object Object]"`), which is exactly how
 *     upstream pagefind-highlight.js uses the string as a type check. The
 *     old THIRD_PARTY_EXCEPTIONS carve-out exists no longer.
 *
 * Usage: node tools/validate/js_object_scan.mjs <file.js> [more.js ...]
 * Exit 0 = clean, 1 = findings, 2 = parse failure (fail closed: a file this
 * scanner cannot parse cannot be certified clean).
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { parse } from "acorn";

const NEEDLE = "[object Object]";
const SINK_PROPS = new Set(["innerHTML", "textContent"]);
const SKIP_KEYS = new Set(["loc", "range", "start", "end", "comments", "tokens"]);

/** Depth-first walk of every node with a .type. No cycles in acorn output
 *  beyond the skipped location keys. */
function walk(node, visit) {
  if (!node || typeof node !== "object" || typeof node.type !== "string") return;
  visit(node);
  for (const key of Object.keys(node)) {
    if (SKIP_KEYS.has(key)) continue;
    const value = node[key];
    if (Array.isArray(value)) {
      for (const child of value) walk(child, visit);
    } else if (value && typeof value === "object" && typeof value.type === "string") {
      walk(value, visit);
    }
  }
}

function literalHasNeedle(node) {
  return node.type === "Literal" && typeof node.value === "string"
    && node.value.includes(NEEDLE);
}

function templateHasNeedle(node) {
  if (node.type !== "TemplateLiteral") return false;
  return node.quasis.some((q) =>
    (q.value && (q.value.cooked || q.value.raw) || "").includes(NEEDLE));
}

function subtreeHasNeedle(node) {
  let found = "";
  walk(node, (n) => {
    if (found) return;
    if (literalHasNeedle(n) || templateHasNeedle(n)) found = n.type;
  });
  return found;
}

function describeSink(node) {
  // AssignmentExpression to obj.innerHTML / obj.textContent, or a call to
  // obj.document.write / document.write.
  if (node.type === "AssignmentExpression") {
    const left = node.left;
    if (left && left.type === "MemberExpression" && left.computed === false
        && left.property && SINK_PROPS.has(left.property.name)) {
      return `assignment to .${left.property.name}`;
    }
    return "";
  }
  if (node.type === "CallExpression") {
    const callee = node.callee;
    if (callee && callee.type === "MemberExpression" && callee.computed === false
        && callee.property && callee.property.name === "write") {
      const obj = callee.object;
      if (obj && obj.type === "Identifier" && obj.name === "document") {
        return "document.write()";
      }
    }
  }
  return "";
}

function scanSource(source, file) {
  const findings = [];
  let ast;
  const opts = { ecmaVersion: "latest", locations: true, allowHashBang: true };
  try {
    ast = parse(source, { ...opts, sourceType: "module" });
  } catch {
    try {
      ast = parse(source, { ...opts, sourceType: "script" });
    } catch (e) {
      return { parseError: `${file}: cannot parse (${e.message})` };
    }
  }

  // Sink map: for a given node object, remember that it sits under a sink
  // assignment/call so nested literals are attributed to the sink.
  const underSink = new WeakSet();

  walk(ast, (node) => {
    const sink = describeSink(node);
    if (sink) {
      if (node.type === "AssignmentExpression") {
        const hit = subtreeHasNeedle(node.right);
        if (hit) findings.push({ line: node.loc.start.line, reason: sink });
      } else if (node.type === "CallExpression") {
        for (const arg of node.arguments) {
          if (subtreeHasNeedle(arg)) {
            findings.push({ line: node.loc.start.line, reason: sink });
            break;
          }
        }
      }
      // Mark descendants so a plain walk pass can skip double-reporting them
      // as bare concatenations already reported here.
      walk(node, (inner) => underSink.add(inner));
      return;
    }
    if (underSink.has(node)) return;

    if (node.type === "BinaryExpression" && node.operator === "+") {
      if (literalHasNeedle(node.left) || literalHasNeedle(node.right)) {
        findings.push({ line: node.loc.start.line, reason: "string concatenation" });
      }
      return;
    }
    if (templateHasNeedle(node)) {
      // Only report the outermost template literal, not each quasi.
      findings.push({ line: node.loc.start.line, reason: "template literal" });
    }
  });

  return { findings };
}

function main(argv) {
  if (argv.length === 0) {
    process.stderr.write("usage: js_object_scan.mjs <file.js> [...]\n");
    return 2;
  }
  let anyFindings = false;
  let anyParseError = false;
  for (const file of argv) {
    let source;
    try {
      source = readFileSync(file, "utf8");
    } catch (e) {
      process.stderr.write(`${file}: cannot read (${e.message})\n`);
      anyParseError = true;
      continue;
    }
    const result = scanSource(source, file);
    if (result.parseError) {
      process.stderr.write(`${result.parseError}\n`);
      anyParseError = true;
      continue;
    }
    for (const f of result.findings) {
      process.stdout.write(`${file}:${f.line}: ${f.reason}\n`);
      anyFindings = true;
    }
  }
  if (anyParseError) return 2;
  return anyFindings ? 1 : 0;
}

// Run when invoked directly (the guard spawns this); stay importable for tests.
const invokedDirectly =
  process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (invokedDirectly) process.exit(main(process.argv.slice(2)));

export { scanSource, NEEDLE };
