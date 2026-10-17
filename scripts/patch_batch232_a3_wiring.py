#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch232 v3: A3 —— ChatService 接线（修 v2 的自查发现的真 bug）

v2 自查发现(snapshot 亲验 rerunToolInternal):
  模型换链的行尾注释 `// rhA3Wiring` 把同一行后面的 `?: return RerunToolResult.Failure(...)`
  吃掉了(那是对 model 空值的兜底)。后果: model 变成 Model?(可空), 但下游
  buildToolsForRerun(model=...) 要非空 Model → 类型不匹配。
  run441 没报它是被 MemoryRepository 的错挡住了。

修法: 模型换链不带行尾注释(保留 `?:` 兜底)。幂等 marker 由 import 块 + 助手链提供,
  模型链不需要自己的 marker。

其余不变: import 块末尾补 NL(v1 的坑); 助手链单行换(已验证); 模型链多行正则;
  报告替换处数走 ::error。幂等 marker rhA3Wiring。warn-only。只动 ChatService.kt。

注: AssistantDetailVM/MemoryRepository 的短期记忆(rhShortMem)未完成工作是并行会话的,
  与本批无关——他们正在补字段/方法。
'''
from pathlib import Path
import re
import sys

ROOT = Path.cwd()
NL = chr(10)
BATCH = 'batch232'
MARK = 'rhA3Wiring'
CS = 'app/src/main/java/me/rerere/rikkahub/service/ChatService.kt'

MODEL_CHAIN_RE = re.compile(
    r'settings\.findModelById\(\s*(\w+)\.chatModelId\s*\?:\s*assistant\.chatModelId\s*\?:\s*settings\.chatModelId\s*\)'
)

applied = []
skipped = []


def joinlist(items):
    t = ''
    for i, s in enumerate(items):
        if i > 0:
            t += ','
        t += s
    return t


def read(path):
    p = ROOT / path
    if not p.exists():
        return None
    try:
        return p.read_text(encoding='utf-8')
    except Exception:
        return None


def write(path, text):
    p = ROOT / path
    if not p.parent.exists():
        p.parent.mkdir(parents=True)
    p.write_text(text, encoding='utf-8')


def balance(text):
    return (text.count('(') - text.count(')')) + (text.count('{') - text.count('}'))


def main():
    src = read(CS)
    if src is None:
        skipped.append('missing')
        print('::error::' + BATCH + ' SKIP missing')
        return
    if MARK in src:
        applied.append('exists')
        print('::error::' + BATCH + ' OK already')
        return
    bal0 = balance(src)
    out = src

    # ① import 补 getAssistantOf + getChatModelOf(末尾补 NL)
    imp_anchor = 'import me.rerere.rikkahub.data.model.Conversation\n'
    if out.count(imp_anchor) == 1:
        out = out.replace(
            imp_anchor,
            imp_anchor +
            'import me.rerere.rikkahub.data.model.getAssistantOf // ' + MARK + NL +
            'import me.rerere.rikkahub.data.model.getChatModelOf // ' + MARK + NL,
            1,
        )
        applied.append('imports')
    else:
        skipped.append('import-anchor=' + str(out.count(imp_anchor)))

    # ② 读助手链 → getAssistantOf(X)（单行）
    n_assistant = 0
    for var in ('initialConversation', 'currentConversation', 'conversation'):
        old = 'settings.getAssistantById(' + var + '.assistantId) ?: settings.getCurrentAssistant()'
        new = 'settings.getAssistantOf(' + var + ') // ' + MARK
        n_assistant += out.count(old)
        out = out.replace(old, new)
    if n_assistant > 0:
        applied.append('assistant x' + str(n_assistant))
    else:
        skipped.append('assistant-none')

    # ③ 选模型链 → getChatModelOf(X)（正则, 空白/换行容忍; 不带行尾注释, 不吃 `?:` 兜底）
    def _model_sub(m):
        return 'settings.getChatModelOf(' + m.group(1) + ')'
    out, n_model = MODEL_CHAIN_RE.subn(_model_sub, out)
    if n_model > 0:
        applied.append('model x' + str(n_model))
    else:
        skipped.append('model-none')

    # ④ 校验 + 落盘
    if balance(out) != bal0:
        skipped.append('balance')
        print('::error::' + BATCH + ' SKIP balance')
        return
    if n_assistant == 0 and n_model == 0:
        skipped.append('no-op')
        print('::error::' + BATCH + ' SKIP no-op')
        return
    if '// rhA3Wiringimport ' in out:
        skipped.append('import-merge-check')
        print('::error::' + BATCH + ' SKIP import-merge-check')
        return
    write(CS, out)
    print('::error::' + BATCH + ' OK applied=[' + joinlist(applied) + '] skipped=[' + joinlist(skipped) + ']')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('::error::' + BATCH + ' crashed: ' + str(exc)[:300])
    sys.exit(0)