#!/usr/bin/env python3
# rhNoop368: UI 回退 —— 导航转场改回上游默认。
# 用户评估后认为自定义转场无价值，脚本改为空操作（不写任何源码）。
import os, sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
(root / "ci_diag_batch368_motion_nav.txt").write_text(
    "noop: reverted (navigation transition back to upstream default)\n",
    encoding="utf-8",
)
print("batch368 noop")
sys.exit(0)
