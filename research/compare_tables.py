#!/usr/bin/env python3
"""Compatibility wrapper: bundle comparison moved to tools/compare_tables.py."""

import os
import runpy

_HERE = os.path.dirname(os.path.abspath(__file__))
_NEW = os.path.normpath(os.path.join(_HERE, "..", "..", "tools", "compare_tables.py"))

if __name__ == "__main__":
    runpy.run_path(_NEW, run_name="__main__")
else:
    import sys
    sys.path.insert(0, os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "tools"))
    from compare_tables import *  # noqa: E402,F401,F403
