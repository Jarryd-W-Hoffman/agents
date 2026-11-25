# Writer brief

The lead fills this in once per chapter and passes it as the manual-writer's prompt. Replace every `{{…}}`.

````markdown
Write one chapter of {{PROJECT}}'s user manual.

## Your chapter

- **File:** `docs/manual/{{NN-slug}}.md` ({{new | rewrite the existing one, keeping every true fact}})
- **Title:** {{Title}}
- **What's in it** (from the contents table; your `##` headings should cover these): {{topics}}
- **Start reading here:** {{source files, one per line, with a word on what each holds}}

## Screenshots you can use

These exist. Use each one at least once, with this alt text (adjust it only to be more exact). Do not reference any other image.

| Path from the chapter | What it shows | Alt text |
| --- | --- | --- |
| `images/{{name}}.png` | {{what is on screen, in detail}} | {{sentence}} |

## The whole manual

So your See also links and cross-references point at real chapters:

{{the contents table: emoji, linked title, what's in it}}

## Conventions

{{the Conventions section from the index, verbatim}}

## The template and the style

Follow the chapter template and the house style below exactly.

{{the "Chapter" section of manual-template.md, verbatim}}

{{style.md, verbatim}}
````
