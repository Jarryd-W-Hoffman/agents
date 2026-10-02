# Eval suite

What this measures: whether the analyst finds what reaches a change when a name search cannot, whether it drops what a name search wrongly matched, and whether the skill launches nothing when there is nothing to map.

The harness, the cost model and the reasons for inlining fixtures are the same as four-pass-review's; read [its evals/README.md](../../four-pass-review/evals/README.md) first. As with migration-safety, `--allow-tools Bash` needs Claude Code's sandbox (`bubblewrap` and `socat` on Linux); without them every run is refused before it starts.

```bash
# from plugins/change-impact/
claude plugin eval --allow-tools Bash --ablation none --runs 1 --case 'recall-route-job-schedule' --max-cost-usd 2.00 .
claude plugin eval --allow-tools Bash --ablation none --runs 1 .
```

No baseline has been recorded yet.

## The cases

Every case is built so the scan alone fails it. `tests/test_evals.py` checks that: if the scan ever found the answer by itself, the case would be measuring grep.

| Case | Fixture | What the scan gives | What the analyst must add or remove |
|---|---|---|---|
| `recall-route-job-schedule` | `invoice-total` | The controller and the job that call `InvoiceService::total`, the test, and a collision with `TokenService::total` | The route two hops out, the `invoices:remind` command that dispatches the job, and its daily schedule, which names the command only by its signature string |
| `recall-event-listener` | `order-event` | References to `OrderPlaced` in the controller and the provider | The queued listener wired through `EventServiceProvider::$listen`, and the event payload as a contract for events already on the queue |
| `recall-untested` | `untested-export` | The one console caller of `ReportExporter::toCsv` | That no test reaches `toCsv`; `SalesReportTest` is a near-miss |
| `precision-name-collision` | `collision` | Four `generate()` call sites | Drop the three that call `PdfRenderer::generate` and `TokenService::generate`; keep `ReportController` and its route |
| `nothing-to-map` | `docs-and-tests` | `analyse: false` | Nothing: stop, launch no analyst |

## Fixtures

`INTENT.md` plus `base/` and `head/` trees of plain PHP, nothing to install. `build_prompts.py` diffs the trees, runs the skill's own scan over them, and inlines the scan, the diff and the head tree into the prompt. `EVAL:` comment lines say what a case measures and are stripped from the prompt; keep every such note on an `EVAL:` line.

**The prompts are generated. Do not edit `*/prompt.md` by hand.**

## Not measured yet

- Python, JS or Go fixtures. The scan handles them and has unit tests; the analyst's procedure is Laravel-first.
- `--quick` end to end. Its output is the scan's `to_impact`, which is unit-tested and validated against the contract.
- Container bindings, policies and observers. The next cases to add.
