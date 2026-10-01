# Eval suite

What this measures: whether the four passes actually find seeded defects, and —
the half that matters more — whether they stay quiet on code that is correct.
The whole design of this plugin bets on suppressing false positives, so half the
cases here exist to catch the plugin crying wolf.

## Running it

The dollar figures throughout are API-price equivalents of the tokens a run
uses, not charges — see **What it costs** for what that means on a
subscription versus an API key.

```bash
# one case, one run -- what you want while iterating (~$1.40 API-equivalent)
claude plugin eval --allow-tools Bash --ablation none --runs 1 \
  --case 'precision-guarded-null' .

# the whole suite, one run each, no baseline arm (~$10)
claude plugin eval --allow-tools Bash --ablation none --runs 1 .

# the full thing: 3 runs, both ablation arms (~$55 -- read "What it costs")
claude plugin eval --allow-tools Bash .
```

`--allow-tools Bash` is not optional. Bash is a gated tool: the case
frontmatter asking for it is not enough, the operator has to grant it too.
Without the grant the review skill cannot run the `git` commands in its
frontmatter, degrades into guesswork, and every case fails for a reason that
has nothing to do with review quality.

## What it costs

**Every dollar figure in this file is an API-price equivalent, not a bill.**
The eval CLI counts the tokens each run used and prices them at Anthropic's
published API rates; that is the number it prints and the number quoted here.
What it turns into depends on how you are signed in:

- **Subscription login** (Pro/Max, the default for Claude Code): the runs draw
  on your plan's usage allowance, the same as an interactive session. No charge
  appears; the figure tells you roughly how much of that allowance a run
  consumes.
- **API key** (`ANTHROPIC_API_KEY`, or Bedrock/Vertex): the figure is what you
  will actually be billed.

Read this before running the suite. Each run is a full Claude session on your
own credential, and a run of this plugin is not cheap: the review spawns four
reviewer subagents and then verifiers, so a single run comes to around
**$1.20 to $1.50 of API-equivalent usage, and 3-4 minutes**. Token counts are
measured; the dollar figure is those tokens at API list price.

The defaults multiply that hard. `claude plugin eval` with no arguments is
7 cases x 3 runs x 2 ablation arms = **42 sessions, roughly $55**. That is
almost never what you want.

Sensible shapes:

| Command | Runs | API-equivalent |
|---|---|---|
| `--case <one> --runs 1 --ablation none` | 1 | ~$1.40 |
| `--runs 1 --ablation none` (whole suite, one pass) | 7 | ~$10 |
| `--ablation none` (whole suite, 3 runs) | 21 | ~$28 |
| no flags | 42 | ~$55 |

Set `--max-cost-usd` generously or not at all. The ceiling is checked before
each run launches, so a limit below the cost of one run does not prevent the
spend — it just crosses mid-run and skips the paid grader, which reports the
case as score 0 for a reason that has nothing to do with the plugin. If you
cap, cap above one run's cost.

Always bound it while iterating:

```bash
claude plugin eval --case 'precision-guarded-null' --runs 1 \
  --ablation none --max-cost-usd 3.00 --allow-tools Bash .
```

Cases are given `timeout_seconds: 900`. The default 300s is not enough: a
four-pass review spawns four reviewers and then verifiers, and times out
mid-review at five minutes.

Useful flags:

| Flag | Why |
|---|---|
| `--trust-plugin` | Skips the first-run trust prompt. Required in CI. |
| `--keep-temp` | Preserves each run's workspace and `trace.jsonl`. The only way to see what the agent actually said when a case fails. |
| `--ablation with-without` | Also runs a no-plugin baseline arm and reports the delta, which is what tells you the plugin is doing the work rather than the base model. |
| `--ablation none` | Skips the baseline arm. Halves the cost while iterating. |
| `-j 4` | Up to 4 runs at once. They share one rate limit. |
| `--max-cost-usd N` | Hard ceiling on API-equivalent spend, checked before each run launches. Set it above the cost of one run (~$1.40) or the grader is skipped mid-run and the case reports 0. |
| `--threshold 0.8` | Exit 1 if any case scores below this. Default is 1.0. |

Results land in `evals/results/<timestamp>/` (git-ignored) with an
`aggregate-result.json` and a self-contained `report.html`.

## Baseline

Plugin 0.2.0, Claude Code 2.1.277, 2026-09-30, `--runs 3 --ablation none`:
**$23.16 API-equivalent over 96 minutes**, 21 runs.

| Case | Score | Pass rate |
|---|---|---|
| recall-correctness | 1.00 | 3/3 |
| recall-compliance | 1.00 | 3/3 |
| recall-consistency | 1.00 | 3/3 |
| **recall-completeness** | **0.67** | **2/3** |
| precision-guarded-null | 1.00 | 3/3 |
| precision-documented-exception | 1.00 | 3/3 |
| single-pass | 1.00 | 3/3 |

An earlier single-run pass of the same suite scored 7/7. It was not wrong, it
was underpowered: one run per case measures whether a case *can* pass, not how
often it does. `recall-completeness` is the case that moved, and only three
runs made it visible. This is why the CLI defaults to 3 and why the 1-run shape
is for iterating, not for recording a baseline.

`recall-completeness` is known-flaky, and the traces put the cause in the suite
rather than the plugin — see **What inlining costs** below. Treat 0.67 as the
number to beat, not as a plugin defect.

`recall-completeness` **was** flaky and is now fixed. The evidence is the
spread, not the pass rate — six green runs prove little on their own, but a
variance collapse is the pathology going away:

| Batch | Scores | Turns | Seconds | Spread |
|---|---|---|---|---|
| baseline (Step 1 attempted) | 1 / 1 / **0** | 12 / 12 / 8 | 135 / 243 / **705** | 570 |
| diagnostic, same prompts | 1 / 1 / 1 | 14 / 11 / 11 | 197 / 127 / 144 | 70 |
| after "there is no repository" | 1 / 1 / 1 | 10 / 10 / 9 | 133 / 124 / **548** | 424 |
| **after the pre-resolved packet** | **6 / 6** | **9-10** | **95-124** | **29** |

Telling the lead there was no repository cut the turn count but left the long
tail, because Step 1 still had to be attempted and abandoned. Handing it a
resolved packet removes the step. Max run time went 705s to 124s and cost per
run fell from about $1.00 to $0.81.

**The table above the fix is the last full-suite baseline, and it predates
this change.** Only `recall-completeness` has been re-measured since. The other
six were green before and the packet change can only reduce flailing, but they
have not been re-run: treat the full-suite numbers as pre-fix until someone
spends the 90 minutes.

## The cases

### Recall — does the right pass catch a seeded defect?

Each fixture seeds exactly one unambiguous defect, and the grader checks both
that it was found *and* that it was attributed to the pass that owns it. A
finding with the wrong ID prefix scores zero: the passes are supposed to divide
the work, and a correctness reviewer reporting a compliance violation means the
scope boundaries have stopped holding.

| Case | Fixture | Seeded defect | Must be reported by |
|---|---|---|---|
| `recall-correctness` | `fixtures/billing` | `invoice.customer.email` dereferenced when `customer` is nullable | `COR-` |
| `recall-completeness` | `fixtures/orders` | `compute_total` renamed to `calculate_total`, one call site missed | `CMP-` |
| `recall-compliance` | `fixtures/payments` | Logs a customer email against a written NEVER rule | `CPL-` |
| `recall-consistency` | `fixtures/inventory` | Fourth repository departs from three siblings on naming, method and logging | `CNS-` |

### Precision — does it stay quiet when the code is fine?

These fixtures are bait: code written to look like a defect to a reviewer who
pattern-matches instead of reading.

| Case | Fixture | The bait |
|---|---|---|
| `precision-guarded-null` | `fixtures/notify` | `user.email.lower()` looks unguarded; an early `if user.email is None: return` makes it safe |
| `precision-documented-exception` | `fixtures/audit` | `AccessLog` looks like a break from the `<Thing>Repository` convention; the written conventions document that exact exception |

Their graders score on **whether the false positive appears**, not on the
overall verdict. A clean fixture can still legitimately draw a finding for
having no tests, and failing the case for that would measure the wrong thing.

### Behaviour

| Case | Asserts |
|---|---|
| `single-pass` | `--passes correctness` returns only `COR-` findings and no merged four-pass report |

## Fixtures and generated prompts

Fixtures are plain Python, dependency-free, tens of lines each, and require no
network, install or build. Each carries an `INTENT.md` that becomes the change
description in the prompt, which is what the completeness pass judges against.

**The prompts are generated. Do not edit `*/prompt.md` by hand.**

```bash
python3 evals/build_prompts.py           # regenerate from fixtures/
python3 evals/build_prompts.py --check   # fail if any prompt is stale
```

Each eval run gets its own isolated workspace, so a prompt pointing at
`evals/fixtures/<name>/` sends the agent looking for files that are not there.
So `build_prompts.py` inlines the fixture files into each prompt instead, and
`fixtures/` stays the readable source of truth.

Each prompt also opens with a **pre-resolved Review Packet** telling the skill
to skip Step 1. That is not decoration: Step 1 resolves a review target against
a repository, and with no repository to resolve against, the lead searched for
one — see the numbers under **What inlining costs**.

### Why not a real git repository?

That would be better: it would make the cases exercise Step 1 for real, and let
the suite see revision-dependent bugs, which it currently cannot. The mechanism
is `scaffold_script` in a `case.yaml`. On Claude Code 2.1.277 that key passes
schema validation and then produces nothing — a probe that wrote a marker file
and ran with `--scaffold` left no trace in the workspace, the sandbox or
anywhere on disk. Until that works, the packet approach is what keeps the
measurement stable. Worth re-probing on a later CLI; the probe costs about
$0.15.

### What inlining costs

Inlining solves the workspace problem and creates a smaller one. The skill's
first step resolves a review target and builds a packet of `git` commands, and
with no repository on disk there is nothing for it to resolve. Traces from the
3-run baseline show the lead doing exactly that: repeated `ls`, `find`,
`Glob **/*` and `git rev-parse --is-inside-work-tree`, and in the run that
failed, two `sleep` calls and 705 seconds — against 135s and 243s for the two
that passed. Same prompt, same plugin; the difference was whether it stopped
hunting in time.

So each prompt now opens by saying there is no repository and not to look for
one. That is why `recall-completeness` was the case that moved: its pass is the
one that leans hardest on searching a tree.

Two things follow, and both are limits on what these numbers mean:

- **The suite measures the four passes' judgement, not the skill's target
  resolution.** Step 1, `--since`, PR fetching and rule-file enumeration at the
  base are not exercised here at all. They are covered by
  `tests/test_skill_invariants.py`, which is static.
- **No case runs against a real checkout**, so any bug that only appears when
  the working tree is not the change under review — the class that produced the
  revision-naive `git grep` defect — is invisible to this suite. A fixture that
  is a real git repository would close that, and needs `--scaffold`.

Comment lines containing `EVAL:` are stripped when the prompt is generated.
That is where a fixture records which defect it seeds, or that it is bait —
useful to whoever maintains the suite, and fatal to the measurement if the
reviewer reads it. Keep every such note on an `EVAL:` line.

Two fixture files are deliberately misnamed:

- `fixtures/payments/CLAUDE.fixture.md`
- `fixtures/audit/CONVENTIONS.fixture.md`

A real `CLAUDE.md` inside this repository would be loaded as live instructions
by any Claude Code session working in that subtree, including this plugin's own
reviews of itself. The `.fixture.md` suffix keeps them inert; each case prompt
tells the reviewer to treat the file as the rule source for that directory.

## Adding a case

```bash
claude plugin eval init --bare my-case     # writes prompt.md + graders/criteria.md
```

Then:

1. Put the code under `fixtures/<name>/` with an `INTENT.md`. Keep it small —
   every extra file is tokens in every run.
2. Seed at most one defect, and record which pass owns it on an `EVAL:` comment
   line so it is stripped from the prompt. A fixture with two defects cannot
   tell you which pass missed which.
3. Register the case in `CASES` in `evals/build_prompts.py`, then run
   `python3 evals/build_prompts.py`. Do not write `prompt.md` yourself.
4. Write the grader as a checklist with an explicit "score 1 only if all of
   these hold". Say what does *not* matter — wording, line numbers, extra
   findings — or the judge will penalise harmless variation.
5. For a precision case, name the false positive precisely and score on its
   absence alone. Do not make the overall verdict part of the score: a clean
   fixture can still legitimately draw a "no tests" finding.
6. Run it with `--runs 1 --ablation none --allow-tools Bash` while iterating,
   then with the defaults before committing.

## CI

`python3 evals/build_prompts.py --check` does run in CI: it is free and
deterministic, and it catches a fixture edited without regenerating the prompt.

The scored suite is not wired into CI, deliberately: it
needs a credential, costs money per run, and is non-deterministic, so it would
make every pull request slow, expensive and flaky. Run it before a release, and
after any change to an agent prompt, the merge step or the confidence rubric —
those are the changes that alter what the plugin finds, and nothing else in the
test suite will notice.
