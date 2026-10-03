# Report template

Use this structure verbatim. Omit a severity section when it has no findings. The finding layout matches four-pass-review's merged report, so the two can sit side by side and test-gap-writer's fallback parser reads either.

```markdown
# Migration safety: {{TARGET_DESCRIPTION}}

**Verdict:** {{PASS | PASS_WITH_NOTES | REQUEST_CHANGES | FAIL | INCOMPLETE}}
**Migrations:** {{N}} ({{added A, modified M, deleted D, renamed R | omit zero counts}}) · {{framework(s)}} · {{BASE}} → {{HEAD}}
**Deploy model:** {{from the reviewer's header: what it judged against and where that came from}}
**Threshold:** {{THRESHOLD}}

## Critical ({{count}})

### [{{ID}}] {{title}}
`{{path}}:{{line}}` · confidence {{NN}} · migration-safety
{{One or two sentences: the failure scenario and who sees it.}}
**Fix:** {{concrete, minimal suggestion}}

## Major ({{count}})

### [{{ID}}] {{title}}
…

## Minor ({{count}})

- **[{{ID}}]** `{{path}}:{{line}}` — {{one-line description}} (confidence {{NN}}, migration-safety)

## Summary

{{The reviewer's Summary, one to three sentences.}}

## Notes

- {{Assumptions about the deploy model and table sizes, things the reviewer could not check; omit section if empty}}
```

## Rules

- Critical and major findings get a heading each. Minor findings are one bullet each.
- Sort within a section by confidence descending, then path.
- The verdict line is computed, not judged: any critical → `FAIL`; else any major → `REQUEST_CHANGES`; else any minor → `PASS_WITH_NOTES`; else `PASS`. `INCOMPLETE` when the reviewer failed or returned nothing usable, whatever else is known.
- Always carry the deploy model line. A PASS judged against an assumed deploy model is a weaker statement than one judged against a written one, and the reader must be able to tell which they have.
- No emojis. No praise section.
