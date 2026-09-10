#!/usr/bin/env python3
import os
import re

ROOT = "app/templates"
EXT = re.compile(r'{%\s*extends\s+"([^"]+)"\s*%}')

def domain(path):
    if path.startswith("admin/"): return "admin"
    if path.startswith("sub/"): return "subscriber"
    if "cockpit" in path: return "cockpit"
    return "global"

def exists(p):
    return os.path.isfile(os.path.join(ROOT, p))

def scan():
    res = {"missing":[], "cross":[], "ok":[], "noparent":[]}
    for d,_,fs in os.walk(ROOT):
        for f in fs:
            if not f.endswith(".html"): continue
            full = os.path.join(d,f)
            rel = os.path.relpath(full, ROOT)
            dom = domain(rel)
            with open(full) as fh:
                t = fh.read()
            m = EXT.search(t)
            if not m:
                res["noparent"].append((rel,dom))
                continue
            parent = m.group(1)
            if not exists(parent):
                res["missing"].append((rel,dom,parent))
                continue
            pdom = domain(parent)
            if dom != pdom and pdom != "global":
                res["cross"].append((rel,dom,parent,pdom))
            else:
                res["ok"].append((rel,dom,parent))
    return res

r = scan()

print("\n=== DOMAIN INTEGRITY AUDIT ===")
print("\nOK LINKS:")
for x in r["ok"]: print(" ",x)

print("\nMISSING PARENTS:")
for x in r["missing"]: print(" ",x)

print("\nCROSS‑DOMAIN:")
for x in r["cross"]: print(" ",x)

print("\nNO PARENT:")
for x in r["noparent"]: print(" ",x)
