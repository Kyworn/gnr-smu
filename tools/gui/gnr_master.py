#!/usr/bin/env python3
"""Compatibility launcher: the GUI now lives in :mod:`gnr_smu.gui`.

``python3 tools/gui/gnr_master.py`` still starts the dashboard.
"""

import os
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

if __name__ == "__main__":
    import runpy  # noqa: E402
    runpy.run_path(
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "..", "..", "gnr_smu", "gui", "gnr_master.py"),
        run_name="__main__",
    )
else:
    from gnr_smu.gui.gnr_master import *  # noqa: E402,F401,F403
