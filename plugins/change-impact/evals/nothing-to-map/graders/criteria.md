---
type: llm
weight: 1
---

The change touches only `README.md` and a test file: `impact-scan.py`
returned `"analyse": false`. The skill must stop at that point, say there is
no production impact to map, and launch no analyst.

Score 1 only if all of these hold:
- The response says, in any wording, that only docs and/or tests changed and
  there is nothing to map.
- The response contains no impact map: no entry points, callers or risks
  sections, and no impact.json.

Score 0 if it maps the change or analyses the code.
