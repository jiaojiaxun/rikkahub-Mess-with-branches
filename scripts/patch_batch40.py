#!/usr/bin/env python3
"""batch40: 诊断压缩重复请求问题（不改源码，只报告）

用户报告：上下文压缩“重复请求、取消又请求”。
本脚本读取 ChatService.kt，找到 compressConversation 函数及其调用点，
把关键代码上下文打印成 ::notice annotation，供下一步诊断。

不改任何源码。
"""
from pathlib import Path

ROOT = Path.cwd()
P = "app/src/main/java/me/rerere/rikkahub/service/ChatService.kt"

if not (ROOT / P).exists():
    print('::error file=' + P + '::batch40 ChatService.kt not found')
    raise SystemExit(1)

t = (ROOT / P).read_text(encoding="utf-8")
lines = t.split('\n')

# 找所有包含 compress 的行号
hits = []
for idx, line in enumerate(lines, 1):
    low = line.lower()
    if 'compress' in low or 'compaction' in low or 'autoCompact' in low:
        hits.append((idx, line.strip()[:120]))

if not hits:
    print('::notice::batch40: no compress/compaction references found in ChatService.kt')
else:
    # 打印前 40 条（防止 annotation 太多）
    for idx, line in hits[:40]:
        print('::notice::batch40 L' + str(idx) + ': ' + line)
    if len(hits) > 40:
        print('::notice::batch40 ... and ' + str(len(hits) - 40) + ' more')

print('batch40: OK (diagnostic only)')
