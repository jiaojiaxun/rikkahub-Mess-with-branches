#!/usr/bin/env python3
# rhNoop373: 依赖 368 的修正批，368 已回退，本批同样空操作。
import os, sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
(root / "ci_diag_batch373_motion_fix.txt").write_text(
    "noop: reverted together with batch368\n",
    encoding="utf-8",
)
print("batch373 noop")
sys.exit(0)
