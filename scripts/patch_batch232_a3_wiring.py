#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch232 v2: A3 —— ChatService 接线（修 v1 的两个 bug）

v1 编译红根因(读 run439 annotation 自查):
  ① import 补 getAssistantOf/getChatModelOf 时, 最后一个新 import 没加换行 →
     下一行原有的 `import ...ConversationCompaction` 被并进注释 → ChatService 找不到
     ConversationCompaction → 编译红。修法: 新 import 块末尾补 NL。
  ② 模型链 findModelById(...) 是多行调用(findModelById(\n X.chatModelId... \n)),
     v1 的单行锚点没中 → 模型链没换成。修法: 改用正则(空白容忍)匹配整个调用。

v1 的助手链(getAssistantById 链 → getAssistantOf)已验证单行可换, 保留。
其余不变: 全局换链 X∈conversation/initialConversation/currentConversation;
  报告替换处数走 ::error。幂等 marker rhA3Wiring。warn-only。只动 ChatService.kt。

注: run439 另有一组不归本批的错误(AssistantDetailVM 的 rhShortMemUI 短期记忆,
  enableShortMemory/getSessionMemoriesOfAssistantFlow 未定义)——那是并行会话的未完成工作,
  与本批无关, 需他们补字段/方法。
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

    # ① import 补 getAssistantOf + getChatModelOf(末尾补 NL, 不再吃掉下一行 import)
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

    # ② 读助手链 → getAssistantOf(X)（单行, 已验证可换）
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

    # ③ 选模型链 → getChatModelOf(X)（正则, 空白/换行容忍）
    def _model_sub(m):
        return 'settings.getChatModelOf(' + m.group(1) + ') // ' + MARK
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
    # 确认没有残留被并进注释的 import(v1 的坑)
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