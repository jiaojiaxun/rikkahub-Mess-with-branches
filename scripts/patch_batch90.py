#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch90: READ-ONLY recon dump of ChatDrawer.kt in CI form (Step7 prep).

绝不修改任何文件。只把 Step7 需要改的几个区域按行号 + 精确缩进打到
::error annotation(匿名唯一可读通道),然后 sys.exit(1) 让构建在浪费 APK 前停下。

为什么需要:api.github.com/contents 读到的是【仓库原始形态】,不含在链
patch(batch74v4 白边 / batch85 四宫格)的效果。Step7 要改 ChatDrawer.kt,
必须先拿 CI 真形态,再写正式 patch(铁律 22)。

回读区域:
  imports / 顶部用户 Row / nicknameEditState / AssistantPicker 调用
  / 昵称对话框 / 底部动作区(batch85 产物) / 文件末函数区

拿到输出后:把本脚本替换为正式 Step7 patch(重命名 batch90 或另开编号)。
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
CD = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatDrawer.kt'


def emit(tag, text):
    s = str(text)
    if not s:
        s = '(empty)'
    for k in range(0, len(s), 1500):
        print('::error file=' + CD + '::batch90 ' + tag + ' [' + str(k) + '] ' + s[k:k + 1500])
    sys.stdout.flush()


def ind_len(ln):
    return len(ln) - len(ln.lstrip())


def window(lines, start, end):
    lo = max(0, start)
    hi = min(len(lines), end)
    parts = []
    for i in range(lo, hi):
        parts.append('L' + str(i + 1) + '[' + str(ind_len(lines[i])) + ']' + lines[i].strip()[:110])
    return ' | '.join(parts)


t = (ROOT / CD).read_text(encoding='utf-8')
lines = t.split(NL)
emit('meta', 'totalLines=' + str(len(lines)) + ' bytes=' + str(len(t)))

# 1. import 区全量
first_import = -1
last_import = -1
for i, ln in enumerate(lines):
    if ln.startswith('import '):
        if first_import < 0:
            first_import = i
        last_import = i
emit('imports', window(lines, first_import, last_import + 1))

# 2. 关键锚点窗口(每个锚点只取前 2 个命中,窗口 45 行)
tokens = [
    ('userRowComment', '用户头像'),
    ('greeting', 'Greeting('),
    ('nicknameState', 'val nicknameEditState = useEditState<String>'),
    ('pickerComment', '助手选择器'),
    ('pickerCall', 'AssistantPicker('),
    ('nicknameDialog', 'nicknameEditState.EditStateContent'),
    ('menuPopup', 'var showMenuPopup'),
    ('settings03', 'HugeIcons.Settings03'),
    ('drawerActionBar', 'DrawerActionBar('),
    ('drawerActionFn', 'private fun DrawerAction('),
    ('modalSheet', 'ModalDrawerSheet('),
]
for tag, tok in tokens:
    hits = [i for i, ln in enumerate(lines) if tok in ln]
    if not hits:
        emit('anchor:' + tag, 'NOT FOUND: ' + tok)
        continue
    emit('anchor:' + tag, 'hits=' + str([h + 1 for h in hits]))
    for h in hits[:2]:
        emit('win:' + tag + ':L' + str(h + 1), window(lines, h - 1, h + 45))

print('batch90: recon dump complete (read-only, no files modified)')
sys.exit(1)
