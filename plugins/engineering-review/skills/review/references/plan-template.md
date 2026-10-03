# Plan template

Render the plan with this structure. Omit a section with nothing in it, except "Would run", which says "Nothing" when nothing is selected.

```markdown
# Engineering review plan: {{TARGET_DESCRIPTION}}

**Changed:** {{N}} files ({{BASE}} → {{HEAD}})
**Would run:** {{K}} plugin(s), in parallel · {{sum of the selected plugins' cost lines, e.g. "4 reviewer agents + 1 reviewer agent + 1 analyst agent"}}

## Would run

| Plugin | Kind | Output | Why | Cost |
|---|---|---|---|---|
| `{{plugin}}`{{ · **not installed** | omit when installed}} | {{kind}} | {{findings.json \| impact.json}} | {{matched}} file(s): `{{evidence[0]}}`, …{{ and N more | when matched > evidence}} | {{cost}} |

## Skipped

| Plugin | Why |
|---|---|
| `{{plugin}}` | {{reason}} |

## Afterwards, if you want it

- `{{plugin}}` — {{summary}} Offered after {{after}}.

## Not installed

- `{{plugin}}`: `/plugin install {{plugin}}@jarrydh-agents`

{{One line, only when the user did not pass --plan: "Running the plan is not built yet; this is what it would do."}}
```

## Rules

- Every row comes from the script's JSON. Do not add, drop or reorder plugins, and do not reword a reason.
- When nothing is selected, "Would run" says "Nothing: no changed file is one these plugins review." and the Skipped table shows why for each.
- No emojis.
