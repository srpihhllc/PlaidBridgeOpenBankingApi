#!/usr/bin/env python3
"""
Detect leading-tab or mixed leading whitespace issues in Python files.
Usage:
  python tools/find_indent_issues.py app/blueprints/auth_routes.py
"""
import sys
from pathlib import Path

def show(path):
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    problems = []
    for i, ln in enumerate(lines, start=1):
        # capture leading whitespace
        prefix_len = 0
        while prefix_len < len(ln) and ln[prefix_len] in (" ", "\t"):
            prefix_len += 1
        prefix = ln[:prefix_len]
        if "\t" in prefix:
            problems.append((i, prefix, ln))
        elif prefix.count(" ") and ("\t" in ln[:prefix_len] if prefix_len else False):
            problems.append((i, prefix, ln))
    if not problems:
        print(f"No leading-tab or mixed-leading whitespace issues found in {path}")
        return 0
    print(f"Issues found in {path}:")
    for i, prefix, ln in problems:
        visible_prefix = prefix.replace("\t","\\t").replace(" ","·")
        print(f"{i:4d}: leading[{visible_prefix}] -> {ln[len(prefix):]}")
    return 1

def main():
    if len(sys.argv) < 2:
        print("Usage: python tools/find_indent_issues.py path/to/file.py")
        sys.exit(2)
    for p in sys.argv[1:]:
        path = Path(p)
        if not path.exists():
            print("Not found:", path)
            continue
        rc = show(path)
        if rc:
            # print small surrounding context for first issue
            lines = path.read_text(encoding="utf-8").splitlines()
            idx = [i for i,_,_ in [(i,*None) for i in range(1,1)]]
    # exit code indicates detection count is >0
if __name__ == "__main__":
    sys.exit(main())
