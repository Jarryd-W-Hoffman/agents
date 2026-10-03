# Report template

Use this structure verbatim. Omit a severity section when it has no findings. The finding layout matches fourpass's merged report.

```markdown
# Regression hunt: {{TARGET_DESCRIPTION}}

**Verdict:** {{PASS | PASS_WITH_NOTES | REQUEST_CHANGES | FAIL | INCOMPLETE}}
**History:** {{the scan's reason line}} · {{BASE}} → {{HEAD}}
**Read:** {{from the reviewer's header: the fixes and reverts it read, by short SHA}}
**Threshold:** {{THRESHOLD}}

## Critical ({{count}})

### [{{ID}}] {{title}}
`{{path}}:{{line}}` · confidence {{NN}} · regressions
{{The earlier commit by short SHA and subject, the invariant, and how this change breaks it, in one or two sentences.}}
**Fix:** {{concrete, minimal suggestion}}

## Major ({{count}})

### [{{ID}}] {{title}}
…

## Minor ({{count}})

- **[{{ID}}]** `{{path}}:{{line}}` — {{one-line description}} (confidence {{NN}}, regressions)

## Kept

- `{{short sha}}` {{subject}} — {{the invariant, and where the head still enforces it}}

## Notes

- {{history the reviewer could not follow, anything else it flagged; omit section if empty}}
```

## Rules

- Every finding names its earlier commit by short SHA in the body. A finding without one does not belong in this report.
- "Kept" lists the fixes and reverts whose invariants the reviewer checked and found intact, so the reader sees what was verified, not only what failed.
- The verdict is computed: any critical → `FAIL`; else any major → `REQUEST_CHANGES`; else any minor → `PASS_WITH_NOTES`; else `PASS`. `INCOMPLETE` when the reviewer did not report.
- No emojis.
