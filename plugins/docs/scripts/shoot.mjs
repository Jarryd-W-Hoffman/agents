#!/usr/bin/env node
// Take the screenshots a README and user manual use, from a plan kept in the repository.
//
//   node shoot.mjs <plan.json> [--root <dir>] [--only a,b] [--check]
//
// The plan (docs/screenshots.json by convention) lists every image and how to get it, so the
// pictures can be retaken whenever the app changes, the way Kite's Manual test suite does:
//
//   {
//     "baseUrl": "http://localhost:8000",
//     "viewport": { "width": 1440, "height": 900 },
//     "scale": 1,
//     "colorScheme": "light",
//     "setup": [ { "goto": "/login" }, { "fill": ["#email", "test@example.com"] },
//                { "fill": ["#password", "password"] }, { "click": "button[type=submit]" },
//                { "waitForURL": "**/dashboard" } ],
//     "shots": [
//       { "name": "workspace", "out": ".github/screenshots/workspace.png", "path": "/notes/1",
//         "waitFor": "[data-test=editor]", "alt": "A note open in the editor." },
//       { "name": "palette", "out": "docs/manual/images/palette.png", "path": "/notes/1",
//         "actions": [ { "press": "Control+K" }, { "type": "kite" }, { "wait": 500 } ],
//         "element": "[role=dialog]", "padding": 16 },
//       { "name": "dark", "out": ".github/screenshots/dark.png", "path": "/", "colorScheme": "dark" },
//       { "name": "help", "out": "docs/manual/images/help.png",
//         "terminal": { "command": "go run ./cmd/rill --help", "title": "rill --help" } }
//     ]
//   }
//
// A web shot visits baseUrl + path (or url), runs its actions, and captures the page, one
// element of it, or the full page. A terminal shot runs a command in the repository, and draws
// its output, colours included, in a terminal window; with "render": "markdown" the output is
// drawn as Markdown (headings, tables, code), the way Claude Code shows a report. `setup` runs once, before the first web
// shot, in the same browser context, so a login carries over.
//
// --check validates the plan and prints what would be taken, without a browser.
// --cached redraws terminal shots from the output their last run saved (in the OS temp dir),
// without running the command again: for restyling a shot whose command is slow or costs money.
//
// Playwright is looked up in the repository first (playwright, @playwright/test or
// playwright-core), then in $DOCS_PLAYWRIGHT_DIR. The browser is $CHROME_PATH, else an installed
// Google Chrome or Chromium, else Playwright's own.
//
// Node 18 or later; no dependencies of its own.

import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { createRequire } from "node:module";
import { dirname, isAbsolute, join, relative, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const ACTIONS = ["goto", "click", "dblclick", "hover", "fill", "type", "press", "select", "check",
  "uncheck", "wait", "waitFor", "waitForURL", "scroll", "eval", "drag", "setInput"];
const IMAGE = /\.(png|jpe?g)$/i;

function usage(message) {
  if (message) console.error(`shoot: ${message}`);
  console.error("usage: node shoot.mjs <plan.json> [--root <dir>] [--only a,b] [--check] [--cached]");
  process.exit(2);
}

function parseArgs(argv) {
  const args = { plan: null, root: null, only: null, check: false, cached: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--root") args.root = argv[++i];
    else if (a === "--only") args.only = new Set((argv[++i] ?? "").split(",").filter(Boolean));
    else if (a === "--check") args.check = true;
    else if (a === "--cached") args.cached = true;
    else if (a.startsWith("-")) usage(`unknown option ${a}`);
    else if (!args.plan) args.plan = a;
    else usage(`unexpected argument ${a}`);
  }
  if (!args.plan) usage("no plan given");
  return args;
}

// ---------------------------------------------------------------------------
// The plan
// ---------------------------------------------------------------------------

export function validate(plan, root) {
  const errors = [];
  if (typeof plan !== "object" || plan === null || Array.isArray(plan)) return ["the plan is not an object"];
  if (!Array.isArray(plan.shots) || plan.shots.length === 0) errors.push("'shots' is missing or empty");
  const names = new Set();
  const outs = new Set();
  for (const [i, shot] of (plan.shots ?? []).entries()) {
    const where = `shot ${i}${shot?.name ? ` (${shot.name})` : ""}`;
    if (typeof shot !== "object" || shot === null) { errors.push(`${where} is not an object`); continue; }
    if (!shot.name || !/^[a-z0-9][a-z0-9-]*$/.test(shot.name)) errors.push(`${where}: 'name' must be kebab-case`);
    if (names.has(shot.name)) errors.push(`${where}: name used twice`);
    names.add(shot.name);
    if (!shot.out || !IMAGE.test(shot.out)) errors.push(`${where}: 'out' must be a .png or .jpg path`);
    else if (isAbsolute(shot.out) || relative(root, resolve(root, shot.out)).startsWith("..")) errors.push(`${where}: 'out' must stay inside the repository`);
    if (outs.has(shot.out)) errors.push(`${where}: 'out' used twice`);
    outs.add(shot.out);
    if (!shot.alt) errors.push(`${where}: 'alt' is required, it is the image's alt text in the docs`);
    const web = shot.path !== undefined || shot.url !== undefined;
    if (shot.terminal && web) errors.push(`${where}: a shot is a terminal or a page, not both`);
    if (!shot.terminal && !web) errors.push(`${where}: needs 'path', 'url' or 'terminal'`);
    if (shot.terminal && typeof shot.terminal.command !== "string") errors.push(`${where}: terminal.command must be a string`);
    if (shot.terminal?.render && !["ansi", "markdown"].includes(shot.terminal.render)) errors.push(`${where}: terminal.render must be "ansi" or "markdown"`);
    if (web && shot.path !== undefined && !plan.baseUrl) errors.push(`${where}: 'path' needs a top-level 'baseUrl'`);
    for (const action of shot.actions ?? []) errors.push(...checkAction(action, where));
  }
  for (const action of plan.setup ?? []) errors.push(...checkAction(action, "setup"));
  return errors;
}

function checkAction(action, where) {
  if (typeof action !== "object" || action === null) return [`${where}: an action is not an object`];
  const keys = Object.keys(action).filter((k) => k !== "optional");
  if (keys.length !== 1 || !ACTIONS.includes(keys[0])) return [`${where}: unknown action ${JSON.stringify(action)}; use one of ${ACTIONS.join(", ")}`];
  return [];
}

// ---------------------------------------------------------------------------
// Terminal shots
// ---------------------------------------------------------------------------

const ANSI_COLOURS = ["#1e1e2e", "#f38ba8", "#a6e3a1", "#f9e2af", "#89b4fa", "#cba6f7", "#94e2d5", "#cdd6f4"];
const ANSI_BRIGHT = ["#585b70", "#f38ba8", "#a6e3a1", "#f9e2af", "#89b4fa", "#f5c2e7", "#94e2d5", "#ffffff"];

function escapeHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

export function ansiToHtml(text) {
  let out = "";
  let open = false;
  let state = {};
  const style = () => {
    const css = [];
    if (state.fg) css.push(`color:${state.fg}`);
    if (state.bg) css.push(`background:${state.bg}`);
    if (state.bold) css.push("font-weight:700");
    if (state.dim) css.push("opacity:.7");
    if (state.italic) css.push("font-style:italic");
    if (state.underline) css.push("text-decoration:underline");
    return css.join(";");
  };
  // eslint-disable-next-line no-control-regex
  const parts = text.replace(/\r\n/g, "\n").replace(/\x1b\][^\x07]*\x07/g, "").split(/(\x1b\[[0-9;]*[A-Za-z])/);
  for (const part of parts) {
    // eslint-disable-next-line no-control-regex
    const m = /^\x1b\[([0-9;]*)([A-Za-z])$/.exec(part);
    if (!m) { out += escapeHtml(part); continue; }
    if (m[2] !== "m") continue;
    const codes = m[1] === "" ? [0] : m[1].split(";").map(Number);
    for (let i = 0; i < codes.length; i++) {
      const c = codes[i];
      if (c === 0) state = {};
      else if (c === 1) state.bold = true;
      else if (c === 2) state.dim = true;
      else if (c === 3) state.italic = true;
      else if (c === 4) state.underline = true;
      else if (c === 22) { state.bold = false; state.dim = false; }
      else if (c === 39) state.fg = null;
      else if (c === 49) state.bg = null;
      else if (c >= 30 && c <= 37) state.fg = ANSI_COLOURS[c - 30];
      else if (c >= 90 && c <= 97) state.fg = ANSI_BRIGHT[c - 90];
      else if (c >= 40 && c <= 47) state.bg = ANSI_COLOURS[c - 40];
      else if ((c === 38 || c === 48) && codes[i + 1] === 2) {
        const rgb = `rgb(${codes[i + 2]},${codes[i + 3]},${codes[i + 4]})`;
        if (c === 38) state.fg = rgb; else state.bg = rgb;
        i += 4;
      } else if ((c === 38 || c === 48) && codes[i + 1] === 5) {
        const n = codes[i + 2];
        const colour = n < 8 ? ANSI_COLOURS[n] : n < 16 ? ANSI_BRIGHT[n - 8] : `hsl(${(n * 37) % 360} 60% 70%)`;
        if (c === 38) state.fg = colour; else state.bg = colour;
        i += 2;
      }
    }
    if (open) out += "</span>";
    const css = style();
    open = css !== "";
    if (open) out += `<span style="${css}">`;
  }
  if (open) out += "</span>";
  return out;
}

// Markdown output (a CLI or an agent that prints a report) drawn the way a terminal that renders
// Markdown shows it: headings, bold, code, lists, tables and rules. Small on purpose: no HTML
// passthrough, no nesting beyond one list level.
function inline(text) {
  return escapeHtml(text)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
    .replace(/(^|[^*])\*([^*\s][^*]*)\*/g, "$1<i>$2</i>")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '<u>$1</u>');
}

export function markdownToHtml(text) {
  const lines = text.replace(/\r\n/g, "\n").split("\n");
  const out = [];
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const fence = /^```(\w*)/.exec(line);
    if (fence) {
      const body = [];
      while (++i < lines.length && !lines[i].startsWith("```")) body.push(lines[i]);
      out.push(`<pre class="code">${escapeHtml(body.join("\n"))}</pre>`);
      continue;
    }
    if (/^\|.*\|\s*$/.test(line) && /^\|[\s:|-]+\|\s*$/.test(lines[i + 1] ?? "")) {
      const cells = (row) => row.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
      const head = cells(line);
      i++;
      const rows = [];
      while (i + 1 < lines.length && /^\|.*\|\s*$/.test(lines[i + 1])) rows.push(cells(lines[++i]));
      out.push(`<table><tr>${head.map((c) => `<th>${inline(c)}</th>`).join("")}</tr>${rows
        .map((r) => `<tr>${r.map((c) => `<td>${inline(c)}</td>`).join("")}</tr>`).join("")}</table>`);
      continue;
    }
    const h = /^(#{1,6})\s+(.*)$/.exec(line);
    if (h) { out.push(`<div class="h h${h[1].length}">${inline(h[2])}</div>`); continue; }
    if (/^(-{3,}|\*{3,})\s*$/.test(line)) { out.push('<hr>'); continue; }
    const li = /^(\s*)([-*]|\d+\.)\s+(.*)$/.exec(line);
    if (li) {
      const mark = /\d/.test(li[2]) ? li[2] : "•";
      out.push(`<div class="li" style="padding-left:${li[1].length >= 2 ? 24 : 4}px"><span class="m">${mark}</span><span>${inline(li[3])}</span></div>`);
      continue;
    }
    if (/^>\s?/.test(line)) { out.push(`<div class="q">${inline(line.replace(/^>\s?/, ""))}</div>`); continue; }
    out.push(line.trim() === "" ? '<div class="gap"></div>' : `<div class="para">${inline(line)}</div>`);
  }
  return out.join("");
}

function terminalPage(title, prompt, command, output, width, render = "ansi") {
  const body = render === "markdown"
    ? `<div class="md">${markdownToHtml(output)}</div>`
    : ansiToHtml(output);
  return `<!doctype html><meta charset="utf-8"><style>
  body{margin:0;padding:32px;background:transparent;font:14px/1.5 "JetBrains Mono","Fira Code",ui-monospace,Menlo,Consolas,monospace}
  .win{width:${width}px;border-radius:10px;overflow:hidden;background:#1e1e2e;color:#cdd6f4;box-shadow:0 12px 40px rgba(0,0,0,.35)}
  .bar{display:flex;align-items:center;gap:8px;padding:10px 14px;background:#181825;color:#a6adc8;font-size:12px}
  .dot{width:12px;height:12px;border-radius:50%}.t{flex:1;text-align:center;margin-right:52px}
  pre{margin:0;padding:16px 18px 20px;white-space:pre-wrap;word-break:break-word;font:inherit}
  .p{color:#a6e3a1}.c{color:#f9e2af}
  .md{white-space:normal}.md .h{font-weight:700;color:#89b4fa;margin:6px 0 2px}.md .h1{color:#cba6f7;font-size:15px}
  .md .h2{color:#89b4fa}.md .h3,.md .h4{color:#94e2d5}.md b{color:#fff}.md i{color:#f5c2e7;font-style:italic}
  .md code{color:#fab387}.md u{color:#89dceb}.md .gap{height:10px}.md .li{display:flex;gap:8px;margin:1px 0}
  .md .li .m{flex:none;min-width:12px;color:#6c7086}.md .q{border-left:3px solid #45475a;padding-left:10px;color:#a6adc8}
  .md hr{border:0;border-top:1px solid #45475a;margin:10px 0}
  .md pre.code{padding:8px 12px;margin:4px 0;background:#181825;border-radius:6px;white-space:pre-wrap;color:#cdd6f4}
  .md table{border-collapse:collapse;margin:6px 0;font-size:13px}.md th,.md td{border:1px solid #45475a;padding:3px 8px;text-align:left;vertical-align:top;word-break:normal;overflow-wrap:normal}
  .md td:not(:last-child):not(:nth-last-child(2)),.md th{white-space:nowrap}
  .md th{color:#f9e2af;font-weight:700}</style>
  <div class="win" id="win"><div class="bar"><span class="dot" style="background:#f38ba8"></span><span class="dot" style="background:#f9e2af"></span><span class="dot" style="background:#a6e3a1"></span><span class="t">${escapeHtml(title)}</span></div>
  <pre>${command ? `<span class="p">${escapeHtml(prompt)}</span> <span class="c">${escapeHtml(command)}</span>\n` : ""}${body}</pre></div>`;
}

function cachePath(shot, root) {
  const key = createHash("sha1").update(`${root}\0${JSON.stringify(shot.terminal)}`).digest("hex").slice(0, 16);
  return join(tmpdir(), "docs-shoot-cache", `${shot.name}-${key}.txt`);
}

function runCommand(shot, root, cached) {
  const cache = cachePath(shot, root);
  if (cached && existsSync(cache)) return readFileSync(cache, "utf8");
  const output = execute(shot, root);
  mkdirSync(dirname(cache), { recursive: true });
  writeFileSync(cache, output);
  return output;
}

function execute(shot, root) {
  const t = shot.terminal;
  const result = spawnSync(t.shell ?? "bash", ["-lc", t.command], {
    cwd: t.cwd ? resolve(root, t.cwd) : root,
    env: { ...process.env, FORCE_COLOR: "1", CLICOLOR_FORCE: "1", COLUMNS: String(t.columns ?? 100), TERM: "xterm-256color", ...(t.env ?? {}) },
    input: t.stdin ?? "",
    encoding: "utf8",
    timeout: (t.timeout ?? 60) * 1000,
    maxBuffer: 8 * 1024 * 1024,
  });
  if (result.error) throw new Error(`${shot.name}: ${result.error.message}`);
  if (result.status !== 0 && !t.allowFailure) {
    throw new Error(`${shot.name}: '${t.command}' exited ${result.status}; set terminal.allowFailure to show an error on purpose\n${result.stderr}`);
  }
  let output = (result.stdout ?? "") + (t.stderr === false ? "" : result.stderr ?? "");
  const lines = output.replace(/\s+$/, "").split("\n");
  if (t.maxLines && lines.length > t.maxLines) output = [...lines.slice(0, t.maxLines), "…"].join("\n");
  else output = lines.join("\n");
  return output;
}

// ---------------------------------------------------------------------------
// Browser
// ---------------------------------------------------------------------------

async function loadPlaywright(root) {
  const tried = [];
  const bases = [join(root, "package.json"), process.env.DOCS_PLAYWRIGHT_DIR && join(process.env.DOCS_PLAYWRIGHT_DIR, "package.json")].filter(Boolean);
  for (const base of bases) {
    const require = createRequire(base);
    for (const name of ["playwright", "@playwright/test", "playwright-core"]) {
      try {
        const resolved = require.resolve(name);
        const mod = await import(pathToFileURL(resolved).href);
        const chromium = mod.chromium ?? mod.default?.chromium;
        if (chromium) return chromium;
      } catch {
        tried.push(`${name} from ${dirname(base)}`);
      }
    }
  }
  throw new Error(`Playwright not found (tried ${tried.join(", ")}).\n` +
    "Install it outside the repository and point DOCS_PLAYWRIGHT_DIR at it:\n" +
    "  npm install --prefix <dir> playwright-core && DOCS_PLAYWRIGHT_DIR=<dir> node shoot.mjs …");
}

function browserPath() {
  if (process.env.CHROME_PATH) return process.env.CHROME_PATH;
  const candidates = process.platform === "darwin"
    ? ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/Applications/Chromium.app/Contents/MacOS/Chromium"]
    : process.platform === "win32"
      ? ["C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe", "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe"]
      : ["/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/usr/bin/chromium", "/usr/bin/chromium-browser", "/snap/bin/chromium"];
  return candidates.find((p) => existsSync(p));
}

async function act(page, action, baseUrl) {
  const [kind] = Object.keys(action).filter((k) => k !== "optional");
  const v = action[kind];
  const run = async () => {
    switch (kind) {
      case "goto": return page.goto(/^https?:/.test(v) ? v : baseUrl + v, { waitUntil: "networkidle" });
      case "click": return page.click(v);
      case "dblclick": return page.dblclick(v);
      case "hover": return page.hover(v);
      case "fill": return page.fill(v[0], v[1]);
      case "type": return page.keyboard.type(v, { delay: 15 });
      case "press": return page.keyboard.press(v);
      case "select": return page.selectOption(v[0], v[1]);
      case "check": return page.check(v);
      case "uncheck": return page.uncheck(v);
      case "wait": return page.waitForTimeout(v);
      case "waitFor": return page.waitForSelector(v, { state: "visible", timeout: 15000 });
      case "waitForURL": return page.waitForURL(v, { timeout: 15000 });
      case "scroll": return page.evaluate(([sel, y]) => (sel ? document.querySelector(sel) : window)?.scrollTo(0, y), Array.isArray(v) ? v : [null, v]);
      case "eval": return page.evaluate(v);
      case "drag": return page.dragAndDrop(v[0], v[1]);
      case "setInput": return page.setInputFiles(v[0], v[1]);
      default: throw new Error(`unknown action ${kind}`);
    }
  };
  try {
    await run();
  } catch (err) {
    if (!action.optional) throw err;
  }
}

async function shootWeb(context, plan, shot, root) {
  const page = await context.newPage();
  const viewport = { ...(plan.viewport ?? { width: 1440, height: 900 }), ...(shot.viewport ?? {}) };
  await page.setViewportSize(viewport);
  await page.emulateMedia({ colorScheme: shot.colorScheme ?? plan.colorScheme ?? "light", reducedMotion: "reduce" });
  for (const [key, value] of Object.entries({ ...(plan.localStorage ?? {}), ...(shot.localStorage ?? {}) })) {
    await page.addInitScript(([k, val]) => localStorage.setItem(k, val), [key, String(value)]);
  }
  const url = shot.url ?? plan.baseUrl + shot.path;
  await page.goto(url, { waitUntil: "networkidle", timeout: 30000 });
  if (shot.waitFor) await page.waitForSelector(shot.waitFor, { state: "visible", timeout: 15000 });
  for (const action of shot.actions ?? []) await act(page, action, plan.baseUrl ?? "");
  await page.waitForTimeout(shot.settle ?? plan.settle ?? 600);
  const out = resolve(root, shot.out);
  mkdirSync(dirname(out), { recursive: true });
  if (shot.element) {
    const box = await page.locator(shot.element).first().boundingBox();
    if (!box) throw new Error(`${shot.name}: element ${shot.element} is not visible`);
    const pad = shot.padding ?? 0;
    await page.screenshot({ path: out, clip: { x: Math.max(0, box.x - pad), y: Math.max(0, box.y - pad), width: box.width + pad * 2, height: box.height + pad * 2 } });
  } else {
    await page.screenshot({ path: out, fullPage: Boolean(shot.fullPage) });
  }
  await page.close();
}

async function shootTerminal(browser, shot, root, cached) {
  const output = runCommand(shot, root, cached);
  const t = shot.terminal;
  const width = t.width ?? 900;
  const page = await browser.newPage({ viewport: { width: width + 64, height: 400 }, deviceScaleFactor: t.scale ?? 2 });
  await page.setContent(terminalPage(t.title ?? t.command, t.prompt ?? "$", t.showCommand === false ? "" : (t.display ?? t.command), output, width, t.render));
  const out = resolve(root, shot.out);
  mkdirSync(dirname(out), { recursive: true });
  await page.locator("#win").screenshot({ path: out, omitBackground: true });
  await page.close();
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const root = resolve(args.root ?? process.cwd());
  let plan;
  try {
    plan = JSON.parse(readFileSync(resolve(root, args.plan), "utf8"));
  } catch (err) {
    usage(`cannot read ${args.plan}: ${err.message}`);
  }
  const errors = validate(plan, root);
  if (errors.length) {
    for (const e of errors) console.error(`shoot: ${e}`);
    process.exit(1);
  }
  const shots = plan.shots.filter((s) => !args.only || args.only.has(s.name));
  if (args.only) for (const n of args.only) if (!plan.shots.some((s) => s.name === n)) usage(`no shot named ${n}`);
  if (args.check) {
    for (const s of shots) console.log(`${s.name}\t${s.terminal ? "terminal" : "page"}\t${s.out}`);
    console.log(`shoot: plan ok, ${shots.length} shot(s)`);
    return;
  }

  const chromium = await loadPlaywright(root);
  const executablePath = browserPath();
  const browser = await chromium.launch({ headless: true, ...(executablePath ? { executablePath } : {}) });
  const failed = [];
  try {
    const context = await browser.newContext({ deviceScaleFactor: plan.scale ?? 1, ignoreHTTPSErrors: true });
    let ready = false;
    for (const shot of shots) {
      try {
        if (shot.terminal) {
          await shootTerminal(browser, shot, root, args.cached);
        } else {
          if (!ready && plan.setup?.length) {
            const page = await context.newPage();
            for (const action of plan.setup) await act(page, action, plan.baseUrl ?? "");
            await page.close();
          }
          ready = true;
          await shootWeb(context, plan, shot, root);
        }
        const size = statSync(resolve(root, shot.out)).size;
        console.log(`shot ${shot.name} -> ${shot.out} (${Math.round(size / 1024)} KB)`);
      } catch (err) {
        failed.push(shot.name);
        console.error(`shoot: ${shot.name} failed: ${err.message.split("\n")[0]}`);
      }
    }
  } finally {
    await browser.close();
  }
  if (failed.length) {
    console.error(`shoot: ${failed.length} of ${shots.length} failed: ${failed.join(", ")}`);
    process.exit(1);
  }
  console.log(`shoot: ${shots.length} screenshot(s) taken`);
}

const invoked = process.argv[1] && resolve(process.argv[1]) === resolve(new URL(import.meta.url).pathname);
if (invoked) {
  main().catch((err) => {
    console.error(`shoot: ${err.message}`);
    process.exit(1);
  });
}
