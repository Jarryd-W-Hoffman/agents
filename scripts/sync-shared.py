#!/usr/bin/env python3
"""Keep the code plugins share identical across every plugin that carries it.

A plugin may not read outside its own directory (an install copies only that
directory), so code two plugins need is copied into each. Copies drift. This
script is the check that they have not, and the way to bring them back:

    python3 scripts/sync-shared.py           check; exit 1 naming every copy that differs
    python3 scripts/sync-shared.py --write   overwrite every copy from its canonical file

Edit the canonical file, never a copy, then run --write. `scripts/check.sh`
runs the check, so CI fails on a copy that was edited in place.

Standard library only; runs on Python 3.9.
"""

from __future__ import annotations

import filecmp
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CONTRACT = "shared/finding-contract"
CONTRACT_FILES = ("finding.schema.json", "finding_contract.py")

# canonical directory -> (file names in it, directories each plugin copy lives in)
SHARED = {
    CONTRACT: (CONTRACT_FILES, (
        "plugins/four-pass-review/skills/review/scripts",
        "plugins/test-gap-writer/skills/write-tests/scripts",
    )),
}


def pairs():
    for src_dir, (names, copies) in SHARED.items():
        for dst_dir in copies:
            for name in names:
                yield os.path.join(src_dir, name), os.path.join(dst_dir, name)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args not in ([], ["--write"]):
        print("usage: sync-shared.py [--write]", file=sys.stderr)
        return 2
    write = args == ["--write"]
    stale = []
    for src, dst in pairs():
        src_abs, dst_abs = os.path.join(ROOT, src), os.path.join(ROOT, dst)
        if not os.path.isfile(src_abs):
            print(f"sync-shared: canonical file missing: {src}", file=sys.stderr)
            return 1
        if os.path.isfile(dst_abs) and filecmp.cmp(src_abs, dst_abs, shallow=False):
            continue
        if write:
            os.makedirs(os.path.dirname(dst_abs), exist_ok=True)
            shutil.copyfile(src_abs, dst_abs)
            print(f"sync-shared: wrote {dst}")
        else:
            stale.append((src, dst))
    for src, dst in stale:
        state = "differs from" if os.path.exists(os.path.join(ROOT, dst)) else "is missing; copy of"
        print(f"sync-shared: {dst} {state} {src}", file=sys.stderr)
    if stale:
        print("sync-shared: edit the canonical file, then run "
              "`python3 scripts/sync-shared.py --write`", file=sys.stderr)
        return 1
    if not write:
        print(f"sync-shared: {sum(1 for _ in pairs())} shared copies in step")
    return 0


if __name__ == "__main__":
    sys.exit(main())
