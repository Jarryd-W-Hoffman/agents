# House style

Distilled from Kite's README and user manual (github.com/Jarryd-W-Hoffman/kite). Every page this plugin writes follows it.

## Voice

- **Second person, present tense, plain words.** "Type `[[` to link to another note", not "Users can create links by typing…".
- **Say what it is for before how it works, and how it works before the steps.** A reader who stops after the first paragraph should still know why the feature exists.
- **Short sentences. One idea each.** Cut "simply", "just", "easily", "powerful", "seamless", "robust", "leverage", "utilise". No marketing.
- **British spelling** in prose (colour, organise, licence as a noun), unless the repository already writes American English consistently: match the repository.
- **Honest.** Say what it does not do and where it creaks. Kite's "Why this stack?" names its own trade-offs; do the same where a choice is debatable.
- **No emoji in body text.** Emoji go only where the template puts them: the title, feature group headings, the manual's contents table.

## Formatting

- **Bold** names a button, menu item, command or setting exactly as the app shows it: **Rename or move**, **Preferences → Quick capture**.
- `code` is for anything typed: file names, paths, commands, syntax, property names, values.
- <kbd>Key</kbd> for every key, joined with `+`: <kbd>Mod</kbd>+<kbd>K</kbd>. Define `Mod` once (⌘ on macOS, Ctrl elsewhere) in the manual's conventions and the README's shortcut section.
- Numbered lists for steps a reader follows in order; bullets for everything else. A step starts with a verb.
- Tables for anything with two or more parallel attributes: syntax and its result, a command and what it does, a setting and its default. Prefer a table to a list of "X: does Y" bullets once there are four or more.
- A bullet that is a definition starts with the term in bold and a colon: `- **Backlinks:** each note that links here…`.
- Links between manual chapters are relative (`04-links.md#link-to-a-block`). The README links into the manual with `docs/manual/…`.

## Diagrams

- **Mermaid**, fenced as ```` ```mermaid ````, so GitHub draws them. One idea per diagram, 4 to 12 nodes.
- Show the **real mechanism** with the project's own names: the files, tables, classes, events and commands that exist in the code, not "Frontend → Backend → Database".
- `flowchart LR` for a pipeline, `flowchart TD` for a decision, `sequenceDiagram` for who calls whom over time, `stateDiagram-v2` for lifecycles, `erDiagram` for data.
- Node labels in quotes when they hold punctuation: `A["Home<br/>'Start with [[Kite launch]]'"]`. Use `<br/>` for line breaks. Dotted arrows (`-.->`) for derived or indirect relations.
- Follow each diagram with two to four bullets that say what it shows in words, so a reader who cannot see it loses nothing.

## Pseudocode

The user wants plenty of it: wherever a feature has an algorithm, a rule or an order of steps a reader would want to predict, show it.

- Fence it as ```` ```text ````. Lowercase keywords (`for each`, `if`, `else`, `return`, `when`), indented by two spaces, one action per line.
- Use the domain's words, not the code's: `for each note that links here` beats `foreach ($backlinks as $b)`.
- Ten to twenty lines. It explains the behaviour a user sees (the order things are tried in, what wins a tie, when something is skipped), not every branch in the source.
- Check it against the code. Pseudocode that describes what the code does not do is worse than none.

```text
when a note is saved:
  parse its links, tags, headings and block ids
  replace this note's rows in the index
  for each note it links to that doesn't exist yet:
    record an unresolved link, shown faded
  for each open tab showing a note that links here:
    refresh its backlinks panel
```

## Screenshots

- Real screenshots of the running app, of demo data that reads like real use (named people, plausible projects, realistic dates), never "Lorem ipsum", "Test 1" or an empty state unless the empty state is the point.
- 1440×900 for whole-window shots; crop to the element when the point is one panel or dialog. A dark-theme variant of the hero if the app has one.
- Every image has alt text that says what the picture shows, as a sentence: "The command palette searching for “kite” filtered to the Projects folder." Not "screenshot".
- README images live in `.github/screenshots/`; manual images in `docs/manual/images/`. Both are taken from the one plan in `docs/screenshots.json`, so they can be retaken.
- CLI projects get terminal shots of real commands and their real output.

## Accuracy

Every claim, shortcut, default, path, command and limit in a page comes from the code, config or a command you ran. If you cannot confirm it, leave it out, or say what you could not confirm in your reply. Never invent a feature, a flag or a number.
