#!/usr/bin/env python3
"""The version: written out as text (the release workflow, the RK3326
Provisioner and RK3326 Linux's rk-apps read it with a regex), ending in
-b.<BUILD> for the Stump build it was tested with, and the CHANGELOG's top
section for it.
    python3 tests/run_version.py
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import firefly  # noqa: E402

src = open(os.path.join(HERE, "..", "firefly", "__init__.py"), encoding="utf-8").read()
m = re.search(r'^__version__ = "([^"]+)"$', src, re.M)
assert m, "__version__ must be a plain string on its own line (the release workflow reads it)"
v = m.group(1)
assert v == firefly.__version__
assert re.fullmatch(r"\d+\.\d+\.\d+-b\.\d+", v), v
assert v.endswith("-b.%d" % firefly.BUILD), "%s doesn't end in -b.%d (BUILD)" % (v, firefly.BUILD)
assert firefly.STUMP_RELEASE == "1.0.0-beta.%d" % firefly.BUILD
log = open(os.path.join(HERE, "..", "..", "CHANGELOG.md"), encoding="utf-8").read()
top = re.search(r"^## (\S+)", log, re.M).group(1)
assert top == v, "CHANGELOG's first section is %s, not %s" % (top, v)
print("ok: version %s (Stump %s)" % (v, firefly.STUMP_RELEASE))
