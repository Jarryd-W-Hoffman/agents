# Report template

Render `impact.md` from the validated `impact.json` with this structure. Omit a section with nothing in it, except Limits.

```markdown
# Change impact: {{TARGET_DESCRIPTION}}

**Mode:** {{full — verified by the impact-analyst | quick — script only, names matched, unverified}}
**Changed:** {{N}} symbols in {{M}} files ({{BASE}} → {{HEAD}})
**Reach:** {{one sentence: the widest thing this change touches, from the analyst's header; for quick mode, the entry point kinds found}}

## Changed

| Symbol | Kind | Change | Where |
|---|---|---|---|
| `{{symbol}}` | {{kind}} | {{change}}{{, signature changed}} | `{{path}}:{{line}}` |

## Entry points

| Kind | Name | Where | Reaches |
|---|---|---|---|
| {{kind}} | {{name}} | `{{path}}:{{line}}` | `{{symbol}}`, … |

## Callers

- `{{path}}:{{line}}`{{ (via `CallingSymbol`)}} → `{{target}}` · {{hops}} hop(s){{ · unverified | omit when verified}}

## Tests

- **Covering:** `{{path}}` → `{{symbol}}`, …
- **Not reached by any test:** `{{symbol}}`, …

## Data and state

- {{kind}} `{{name}}` — `{{path}}:{{line}}`

## Contracts

- {{kind}} **{{name}}** — `{{path}}:{{line}}` — {{note}}

## Risks

- **{{area}}** — {{why}} ({{evidence, comma-separated}})

## Limits

- {{each limits entry}}
```

## Rules

- Every entry comes from `impact.json`. Do not add, drop or reword facts between the JSON and the report.
- In quick mode, every caller is marked unverified and the Mode line says so. A reader must never mistake a name match for a verified caller.
- No severities, no verdict, no emojis.
