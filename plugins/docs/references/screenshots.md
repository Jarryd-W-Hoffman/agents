# Taking screenshots

Every image in the README and the manual comes from one plan, `docs/screenshots.json`, run by `scripts/shoot.mjs`. The plan stays in the repository so anyone can retake the pictures after the app changes. The script's header documents every field; this page covers how to get a good set.

## 1. Get the app running with demo data

Screenshots are only as good as the data in them. Kite builds a demo vault in its test suite; do the equivalent:

- **A web app with seeders** (Laravel: `database/seeders`): run the app on a spare port against a throwaway database, seeded. Prefer the project's own seeders. If they are thin (one user, "Test" records), write a demo seeder only if the user agrees, and never against their real database.

  ```bash
  # Laravel, in a scratch copy or with a throwaway sqlite file
  DB_CONNECTION=sqlite DB_DATABASE=<scratch>/docs.sqlite php artisan migrate:fresh --seed --force
  DB_CONNECTION=sqlite DB_DATABASE=<scratch>/docs.sqlite php artisan serve --port=8199
  ```

- **A front-end app**: `npm run build && npm run preview -- --port 8199`, or the dev server.
- **A desktop app** (Electron, NativePHP): screenshot the web view it serves, in a browser at the window's size. Kite's manual does exactly this.
- **A CLI, a library or a set of Claude Code plugins**: terminal shots of real commands (for plugins, `claude -p '/plugin:skill'` in a demo repository, with `"render": "markdown"`) on example input in the repository (`examples/`, `testdata/`). Write a small example file in the scratchpad if none fits, and run the command against it.
- **A game** (Godot): run the project's own export or headless capture if it has one; otherwise ask the user for screenshots rather than faking them.

Run the app in the background, wait until the port answers (`curl -sf <url>`), and stop it when the screenshots are done. Use a port the user's other projects do not hold.

## 2. Write the plan

```json
{
  "baseUrl": "http://127.0.0.1:8199",
  "viewport": { "width": 1440, "height": 900 },
  "scale": 1,
  "setup": [
    { "goto": "/login" },
    { "fill": ["input[name=email]", "test@example.com"] },
    { "fill": ["input[name=password]", "password"] },
    { "click": "button[type=submit]" },
    { "waitForURL": "**/dashboard" }
  ],
  "shots": [
    { "name": "dashboard", "out": ".github/screenshots/dashboard.png", "path": "/dashboard",
      "waitFor": "main", "alt": "The dashboard: this week's jobs on the left, the map on the right." },
    { "name": "dashboard-dark", "out": ".github/screenshots/dashboard-dark.png", "path": "/dashboard",
      "colorScheme": "dark", "alt": "The same dashboard in the dark theme." },
    { "name": "new-job-dialog", "out": "docs/manual/images/new-job-dialog.png", "path": "/jobs",
      "actions": [ { "click": "text=New job" }, { "waitFor": "[role=dialog]" } ],
      "element": "[role=dialog]", "padding": 24,
      "alt": "The New job dialog with the client, site address and due date filled in." },
    { "name": "cli-help", "out": "docs/manual/images/cli-help.png",
      "terminal": { "command": "go run ./cmd/rill --help", "title": "rill --help", "display": "rill --help" },
      "alt": "rill --help listing the run, check, fmt and repl commands." }
  ]
}
```

- **One shot per image**, named after what it shows. README images go to `.github/screenshots/`, manual images to `docs/manual/images/`. An image both use lives in one place and is referenced from both.
- **`alt` is required** and is the text you put in the page.
- **Selectors**: prefer what the app already exposes (`[data-test=…]`, roles, labels, `text=…`) over CSS classes that a restyle will change.
- **Actions**: `goto`, `click`, `dblclick`, `hover`, `fill`, `type`, `press`, `select`, `check`, `uncheck`, `wait` (ms), `waitFor`, `waitForURL`, `scroll`, `eval`, `drag`, `setInput`. Add `"optional": true` to one that may not apply (a cookie banner).
- **Theme**: `colorScheme: "dark"` works when the app follows the system theme. If it keeps its own setting, set it with `localStorage` (`{"localStorage": {"theme": "dark"}}`) or an `eval` action.
- **Terminal**: `command` runs in the repository through `bash -lc`; `display` is what the picture shows as the typed command. Set `allowFailure` to show an error message on purpose, `maxLines` to trim long output, `columns` to the width tools should wrap at.
- **Markdown output**: `"render": "markdown"` draws the output as Markdown (headings, tables, code, lists), the way Claude Code shows a report. Use it for a command that prints Markdown, such as `claude -p '/plugin:skill'`.
- **A slow or paid command**: the raw output of every terminal shot is cached in the OS temp dir. `--cached` redraws from that cache without running the command again, so restyling a shot of a two-minute agent run costs nothing.

## 3. Take them

```bash
node "${CLAUDE_PLUGIN_ROOT}/scripts/shoot.mjs" docs/screenshots.json --check      # validate, no browser
node "${CLAUDE_PLUGIN_ROOT}/scripts/shoot.mjs" docs/screenshots.json              # every shot
node "${CLAUDE_PLUGIN_ROOT}/scripts/shoot.mjs" docs/screenshots.json --only a,b   # some
node "${CLAUDE_PLUGIN_ROOT}/scripts/shoot.mjs" docs/screenshots.json --cached     # redraw terminal shots from their last output
```

Playwright is taken from the repository's `node_modules` if it has it. Otherwise install `playwright-core` once outside the repository and point at it:

```bash
npm install --prefix "<scratchpad>/pw" playwright-core
DOCS_PLAYWRIGHT_DIR="<scratchpad>/pw" node "${CLAUDE_PLUGIN_ROOT}/scripts/shoot.mjs" docs/screenshots.json
```

The browser is `$CHROME_PATH`, else an installed Chrome or Chromium, else Playwright's own (`npx playwright-core install chromium`).

A shot of a check that looks for every image, its own included (`docs_check.py --plan`), fails the first time because its own image is missing. Take it once with `allowFailure` set, then again without: the second take is the real, passing output.

## 4. Look at every image

Open each PNG with the Read tool before using it. Retake any that shows a spinner, an error page, a login screen, a half-drawn graph, an empty list, a toast, a dev-tools overlay or a cursor in the wrong place. Wait for something specific (`waitFor`) rather than adding `wait`s.
