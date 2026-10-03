# Runner brief template

Fill this in once per selected, installed plugin and send it as a `general-purpose` subagent's prompt. Replace every `{{…}}` placeholder.

```text
Run one plugin's skill and report where its output is. Do nothing else.

Skill: {{SKILL}}                      e.g. migrations:check
Arguments: {{USER_TARGET_ARGUMENT}}   exactly as the user gave it: empty, a PR number, or a ref. No other flags.
Repository root: {{ABSOLUTE_PATH}}

1. First make a fresh directory for this plugin's output with `mktemp -d`. Wherever the skill tells you to save files in "your scratchpad directory" or a temporary directory, use that fresh directory instead. Other plugins are running at the same time from the same session, and they save files with the same names (findings.json, report.md); a shared directory lets one overwrite another, or pick up a file left by an earlier run.
2. Invoke the skill above with the Skill tool, with those arguments and nothing more. Follow its instructions to the end. It launches agents of its own; let it.
3. Do not review, fix, test or comment on anything yourself, and do not pass flags such as --comment. If the skill asks a question it needs answered to continue, answer it the way the skill's own defaults say; if it has none, stop and report failed.
4. When the skill has finished, reply with exactly this block and nothing after it:

STATUS: reported | nothing_to_do | failed
FINDINGS: <absolute path of the findings.json the skill saved, or none>
IMPACT: <absolute path of the impact.json the skill saved, or none>
REPORT: <absolute path of the report.md or impact.md the skill saved, or none>
VERDICT: <the skill's verdict line, or none>
REASON: <one line when STATUS is not reported, e.g. "no migrations in this change"; otherwise none>
NOTE: <one line if something went wrong that did not stop the result, e.g. "report.md could not be saved"; otherwise none>

STATUS meanings:
- reported: the skill finished and saved its machine-readable output, findings.json or impact.json. That file is the result; give its path. If the human-readable report (report.md, impact.md) could not be saved, this is still reported: give REPORT: none and say so under NOTE.
- nothing_to_do: the skill decided there was nothing to review or map, and said so, without saving files.
- failed: anything else. The skill would not load, stopped on an error, or finished without saving findings.json or impact.json. Say which in REASON.
```

## Notes for the lead

- Use the user's target argument verbatim, not the base and head you resolved: each plugin resolves the target itself, the same way it does when run alone.
- One brief per plugin. The briefs differ only in `{{SKILL}}`.
