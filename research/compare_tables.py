#!/usr/bin/env python3
"""Compatibility wrapper: bundle comparison moved to tools/compare_tables.py."""

import os
import runpy

_HERE = os.path.dirname(os.path.abspath(__file__))
_NEW = os.path.normpath(os.path.join(_HERE, "..", "tools", "compare_tables.py"))

if __name__ == "__main__":
    runpy.run_path(_NEW, run_name="__main__")
else:
    import importlib.util

    _spec = importlib.util.spec_from_file_location("tools_compare_tables", _NEW)
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    globals().update({k: v for k, v in vars(_mod).items()
                      if not k.startswith("_")})
