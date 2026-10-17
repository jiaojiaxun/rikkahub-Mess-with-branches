#!/usr/bin/env python3
# batch223 v2: 占位 no-op —— v1 的 90 行 dump 会灌满 ::error 配额(每步最多 10 条),
#              遮蔽 batch221/222 的验证报告。v1 只读不改源码, 覆盖为 no-op 不影响任何文件。
#              诊断职责移交 batch224。
import sys

print('::notice::batch223 noop (v1 dump flooded ::error quota; superseded by batch224)')
sys.exit(0)
