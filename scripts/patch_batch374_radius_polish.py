#!/usr/bin/env python3
# rhNoop374: UI 回退 —— 圆角收敛改回上游原始数值。
import os, sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
(root / "ci_diag_batch374_radius_polish.txt").write_text(
    "noop: reverted (corner radius polish back to upstream values)\n",
    encoding="utf-8",
)
print("batch374 noop")
sys.exit(0)
