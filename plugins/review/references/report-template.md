# Report template

Render the merged report from `summary.json` and the merged `findings.json` with this structure. Omit a section with nothing in it.

```markdown
# Review: {{TARGET_DESCRIPTION}}

**Verdict:** {{verdict}}{{ — {{incomplete_because, joined}} | only when INCOMPLETE}}
**Findings:** {{critical}} critical · {{major}} major · {{minor}} minor{{ (findings alone say {{findings_verdict}}) | only when INCOMPLETE}}

## Plugins

| Plugin | Status | Findings | Files |
|---|---|---|---|
| `{{plugin}}` | {{reported \| nothing to do \| not installed \| failed: reason}}{{ · note | when the plugin's entry has a note}} | {{critical}}/{{major}}/{{minor}} | `{{path}}`, … |

## Critical ({{count}})

### [{{ID}}] {{title}}
`{{path}}:{{line}}` · confidence {{NN}} · {{pass}}
{{body}}
{{**Fix:** fix | omit when absent}}

## Major ({{count}})

### [{{ID}}] {{title}}
…

## Minor ({{count}})

- **[{{ID}}]** `{{path}}:{{line}}` — {{title}} (confidence {{NN}}, {{pass}})

## Overlaps

- `{{ids[0]}}` and `{{ids[1]}}` — `{{path}}:{{lines[0]}}-{{lines[1]}}`. Two plugins flagged the same lines; they may be one problem. Both are kept.

## Impact

{{From summary.json's impact: "{{changed}} symbols changed, reached by {{entry_points}} entry points and {{callers}} callers; {{uncovered}} changed symbols no test reaches; {{risks}} risks." Then: "Full map: `{{path}}`." Say "unverified" when mode is quick.}}

## Skipped by the plan

- `{{plugin}}` — {{reason}}
```

## Rules

- The verdict line is `summary.json`'s `verdict`, as computed. Do not soften or raise it.
- `INCOMPLETE` names every plugin that did not report, and why, on the verdict line. A reader must not mistake an incomplete review for a clean one.
- Every finding keeps its original ID and pass, so the user can ask about it by name and see which plugin raised it.
- Findings come from the merged `findings.json` only, in its order. Do not add, drop, merge or reword findings.
- No emojis.
