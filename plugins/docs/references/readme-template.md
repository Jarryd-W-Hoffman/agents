# README template

The shape of Kite's README. Keep the sections in this order; leave out a section only when it has nothing true to say (a library has no **Download**; a CLI has no **Keyboard shortcuts**), and rename a section when the project's own word fits better ("Your vault on disk" becomes "Your data on disk", "Where things are kept", or "Project layout"). Placeholders are `{{LIKE_THIS}}`; comments in `<!-- -->` are instructions, not output.

````markdown
<h1 align="center">{{EMOJI}} {{NAME}}</h1>

<p align="center">
    <strong>{{ONE_LINE: what it is, for whom, in under 15 words.}}</strong><br>
    {{TWO_LINES: the promise and what makes it different. Plain words, no hype.}}
</p>

<p align="center">
    <!-- One badge per CI workflow that runs on push or PR (from the survey's `badge`), then
         platforms or runtimes, the main language version, and the licence. shields.io for static ones. -->
    <a href="https://github.com/{{SLUG}}/actions/workflows/{{WORKFLOW}}"><img src="https://github.com/{{SLUG}}/actions/workflows/{{WORKFLOW}}/badge.svg" alt="{{Tests}}"></a>
    <img src="https://img.shields.io/badge/{{LABEL}}-{{VALUE}}-{{COLOUR}}" alt="{{LABEL VALUE}}">
    <img src="https://img.shields.io/badge/license-{{SPDX}}-22c55e" alt="{{SPDX}} license">
</p>

<p align="center">
    <img src=".github/screenshots/{{HERO}}.png" alt="{{A sentence saying what the main screen shows, left to right.}}" width="900">
</p>

<p align="center">
    <!-- One link per ## section below, in order, separated by " ·". Anchors must match. -->
    <a href="#why-{{name}}">Why {{NAME}}?</a> ·
    <a href="#features">Features</a> ·
    <a href="#user-manual">User manual</a> ·
    …
    <a href="#license">License</a>
</p>

---

## Why {{NAME}}?

<!-- Three to five bullets. Each is a bold claim and one or two sentences of proof.
     The proof is a fact about the code (a format, a benchmark, a test, a design choice), with
     a link to where it is checked when there is one. -->
- **{{Claim}}.** {{Proof.}}

## Features

> 📖 **New to {{NAME}}?** The [user manual](docs/manual/README.md) covers every feature step by step, with diagrams of how each one works.

<!-- Group features under ### headings with one emoji each (✍️ Writing, 🔗 Connecting,
     🔎 Finding, 🕸️ Seeing, 🧠 Learning, 🛡️ Keeping safe, ♿ For everyone, or the project's own
     verbs). Each group: bold-term bullets, nested bullets for lists of options, a table where
     syntax maps to a result, a code block where the reader types something. After every group
     or two, a screenshot (or two side by side at width="49%"). A feature with a workflow of its
     own (Kite's Quick capture, Flashcards) gets a short paragraph and its own screenshot. -->

### {{EMOJI}} {{Group}}
- **{{Feature}}:** {{what it does, in the reader's words}}.

<p align="center">
    <img src=".github/screenshots/{{a}}.png" alt="{{…}}" width="49%">
    <img src=".github/screenshots/{{b}}.png" alt="{{…}}" width="49%">
</p>

## User manual

<!-- Only when docs/manual exists. A three-column table of every chapter, in order. -->
The features above are the short version. The **[user manual](docs/manual/README.md)** takes each one in turn: what it's for, a diagram of how it works, screenshots, and step-by-step instructions, with tips at the end.

| | | |
| --- | --- | --- |
| [{{Chapter}}](docs/manual/01-{{slug}}.md) | … | … |

## {{Your data on disk | How it works}}

<!-- What the project reads and writes, as an annotated tree (```text with ← comments), and
     a Mermaid diagram of the main flow: a request, a command, a pipeline, a compile. Use the
     project's real names. Add pseudocode (```text) for the one algorithm a user most needs to
     predict. -->

```mermaid
flowchart LR
    {{real components and the arrows between them}}
```

## {{Keyboard shortcuts | Commands | Usage}}

<!-- An app: a two-pair-per-row shortcut table, `Mod` defined first. A CLI: a table of
     commands, then a terminal screenshot of a real session. A library: the smallest useful
     example, then the API at a glance. -->

## Download

<!-- Only if releases exist. A table: platform, file, the one thing a first-time user trips on.
     Then how updates work. -->

## Getting started

These steps are for working on {{NAME}} itself. To use it, [download it](#download) instead.

### Requirements
<!-- Exact versions and extensions, from the manifests and CI. -->

### Install

```bash
git clone https://github.com/{{SLUG}}.git
cd {{name}}
{{the real setup command(s), with a trailing # comment saying what each does}}
```

### Run

```bash
{{the real dev command}}   # {{what it starts, and where}}
```

## How it's built

| Layer | Technology |
| --- | --- |
| {{Layer}} | {{Linked technology, with version}} |

<!-- One paragraph on the architecture pattern the code actually follows (Kite: "an actions
     pattern: business logic lives in single-purpose classes in app/Actions"), with a Mermaid
     diagram of the layers when there are more than three. -->

### Why this stack?

<!-- Honest. What you would normally reach for, the trade-offs of this choice as bullets with
     bold leads, why you chose it anyway as bullets, then one closing paragraph. Only write
     what the code and history support; ask the user for the reasons if they are not
     recorded anywhere, rather than inventing them. -->

## Development

```bash
{{the one command that runs everything CI runs}}
```

<!-- What that command runs, as bullets. A table of the other useful commands. A paragraph on
     CI: which workflows, which platforms, what fails a build. -->

| Command | What it does |
| --- | --- |
| `{{command}}` | {{…}} |

### Contributing

Pull requests are welcome.
<!-- The repository's real rules: branch naming, sign-off (DCO) if the repo checks it, tests. -->

## License

{{NAME}} is open-source software licensed under the [{{SPDX}} license](LICENSE).
<!-- Credit third-party assets (icons, fonts, data) with their licences. -->
````

## Checklist

- Every `<a href="#…">` in the link row matches a `##` heading's anchor.
- Every image exists, has alt text, and was taken from `docs/screenshots.json`.
- At least one Mermaid diagram, and pseudocode wherever an algorithm matters.
- Every command was run, or copied from a manifest or CI workflow.
- `docs_check.py --readme README.md` reports no errors.
