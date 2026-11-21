#!/usr/bin/env python3
# rhNoop369: UI 回退 —— 思考抽屉动画改回上游默认。
import os, sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
(root / "ci_diag_batch369_motion_drawer.txt").write_text(
    "noop: reverted (thought drawer animation back to upstream default)\n",
    encoding="utf-8",
)
print("batch369 noop")
sys.exit(0)
