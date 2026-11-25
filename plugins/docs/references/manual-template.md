# Manual template

The shape of Kite's user manual: an index page and one chapter per feature area, in `docs/manual/`, with images in `docs/manual/images/`.

## Planning the chapters

- **One chapter per thing a user sets out to do**, not per module in the code. Kite has Links, Graph, Flashcards, not `LinkParser`, `GraphController`.
- **Getting started is always 01**: installing or opening the app, a tour of the screen with a labelled screenshot, where data lives on disk. **Preferences and shortcuts** (or **Configuration and commands** for a CLI) is always last.
- Between them, order chapters the way a new user meets the features. Eight to sixteen chapters for an app; four to eight for a CLI or library.
- File names are `NN-slug.md`: two-digit number, lowercase, hyphens.
- Each chapter's plan names: title, emoji, a one-line "what's in it" for the index, the source files that implement it, the screenshots it needs, and the chapters it should link to.

## Index: `docs/manual/README.md`

````markdown
# {{NAME}} user manual

Everything {{NAME}} does, one feature at a time: what it's for, how it works, and how to use it, step by step. New to {{NAME}}? Start with **Getting started**, then dip into whatever you need.

![{{alt: the main screen, described left to right}}](images/{{hero}}.png)

## Contents

| | Page | What's in it |
| --- | --- | --- |
| {{EMOJI}} | [{{Title}}](01-{{slug}}.md) | {{Comma-separated topics, matching the chapter's ## headings}} |

## Conventions

- `Mod` means <kbd>⌘</kbd> on macOS and <kbd>Ctrl</kbd> on Windows and Linux.
- **Bold** names a button, menu item or command, as it appears in {{NAME}}.
- {{Any other convention the chapters rely on: a menu glyph, a prompt symbol for CLI examples.}}

## About the screenshots

The screenshots are taken of {{demo data: where it comes from}} by a script, so they can be brought up to date whenever the app changes:

```bash
{{how to start the app with its demo data}}
node <path-to>/shoot.mjs docs/screenshots.json   # or /docs:screenshots in Claude Code
```

That writes the images into [`images/`](images). The plan of what each shows is [`docs/screenshots.json`](../screenshots.json).
````

## Chapter: `docs/manual/NN-slug.md`

Sections in this order. The `## How it works` section, its diagram and the screenshot under the intro are required; the rest are there when they have something to say. Task sections take the reader's verb: "Make a link", "Preview a link", "Embed a note", not "Linking" or "Link creation".

````markdown
# {{Title}}

{{Intro: two or three sentences. What this is for, in the reader's terms, and the one idea that makes the rest make sense.}}

![{{alt}}](images/{{shot}}.png)

## How it works

```mermaid
{{The real mechanism, with the project's names. See the style guide.}}
```

- {{Two to four bullets: what the diagram shows, in words. The rules a user needs to predict what happens: what wins a tie, when it updates, what it never touches.}}

```text
{{Pseudocode of the rule or order of steps, when there is one. Plenty of these: see the style guide.}}
```

## {{Do the main task}}

1. {{Verb first. One action per step.}}
2. {{What the reader sees as a result, when it is not obvious.}}

| You write / You choose | It does / You get |
| --- | --- |
| `{{syntax}}` | {{result}} |

### {{A variation of the task}}

- {{…}}

## {{Do the next task}}

![{{alt}}](images/{{shot}}.png)

{{…}}

## Tips

- **{{Lead}}:** {{a non-obvious thing that saves time or avoids a mistake}}.

## See also

- [{{Chapter}}](NN-{{slug}}.md) · [{{Chapter}}](NN-{{slug}}.md)
````

## Checklist

- Every chapter is in the index, in order, and its "What's in it" matches its headings.
- Every chapter has a screenshot, a Mermaid diagram, and pseudocode wherever a rule or algorithm applies.
- Every shortcut, setting, default and limit was checked in the code.
- Links between chapters point at headings that exist.
- `docs_check.py --manual docs/manual` reports no errors.
