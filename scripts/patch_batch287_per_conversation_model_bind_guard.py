#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch287: 关闭总开关时，bindConfig 不得把助手模型写回会话固定值

【问题（读 ConversationConfig.kt 逻辑推演，非猜测）】
batch285 只改了 bindConfig 的 config == null 分支（新会话不固定模型）。
但 config != null 分支是：
    if (model == null || model.id == config.chatModelId) return this
    return copy(config = config.copy(chatModelId = model.id, builtInSearch = builtInSearch))
关闭总开关时 model = 助手模型（getChatModelOf 已闸门），与 config.chatModelId（旧会话固定值）不同
=> 每次保存会话都会把会话固定值覆写成助手当前模型。
后果：关闭期间打开旧会话并发消息，会话原本固定的模型就被静默覆盖；重新打开开关也回不来。

【修法】config != null 分支先判总开关：关闭时原样返回，一个字段都不动。
  - 关闭态本来就不读 config.chatModelId（getChatModelOf 已闸门），所以不更新 builtInSearch 无影响
  - 重新打开开关后，会话恢复使用自己原来固定的模型（符合"不删数据"的承诺）

五查:
 1. import: 零新增（displaySetting 是 Settings 属性，同函数已在用 settings.getChatModelOf）
 2. 同文件冲突: 批号 287 排在 285 之后；285 改的是 getChatModelOf/getAssistantOf/config==null 分支，
    本批锚点是 config != null 分支的两行，互不重叠
 3. 作用域: settings 是 bindConfig 的参数
 4. 括号配对: 只插入一条单行 if（无花括号）-> 差值不变
 5. 函数签名: 零改动

Python 三查: 无引号拼接；NL 显式 concat；helper 先定义；失败写 diag
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
BATCH = 'batch287'
MARK = 'rhPerConvModel287'
DIAG = 'ci_diag_batch287.txt'
CONF = 'app/src/main/java/me/rerere/rikkahub/data/model/ConversationConfig.kt'

report = []


def note(msg):
    report.append(str(msg)[:900])


def balance(text):
    return (text.count('(') - text.count(')')
            + text.count('{') - text.count('}')
            + text.count('[') - text.count(']'))


def lines_to_text(lines):
    out = ''
    for idx, line in enumerate(lines):
        if idx > 0:
            out += NL
        out += line
    return out


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
        print('::error::' + BATCH + ' diag written chars=' + str(len(body)))
    except Exception as e:
        print('::error::' + BATCH + ' diag write FAILED ' + str(e)[:200])
    sys.stdout.flush()


def main():
    p = ROOT / CONF
    if not p.exists():
        note('ABORT ConversationConfig.kt missing')
        write_diag()
        return
    t = p.read_text(encoding='utf-8')
    if MARK in t:
        note('already applied')
        write_diag()
        return
    bal0 = balance(t)
    lines = t.split(NL)
    hits = [i for i, ln in enumerate(lines) if ln.strip() == 'if (config != null) {']
    if len(hits) != 1:
        note('ABORT config-null anchor count=' + str(len(hits)))
        write_diag()
        return
    i = hits[0]
    nxt = i + 1
    if nxt >= len(lines) or lines[nxt].strip() != 'if (model == null || model.id == config.chatModelId) return this':
        note('ABORT next line mismatch: ' + repr(lines[nxt].strip() if nxt < len(lines) else 'EOF'))
        write_diag()
        return
    ind = lines[nxt][:len(lines[nxt]) - len(lines[nxt].lstrip())]
    add = [
        ind + '// ' + MARK + ': 关闭总开关时不要用助手模型覆盖会话固定值（重新打开开关要能恢复）',
        ind + 'if (!settings.displaySetting.perConversationModel) return this',
    ]
    lines = lines[:nxt] + add + lines[nxt:]
    t2 = lines_to_text(lines)
    if balance(t2) != bal0:
        note('ABORT balance ' + str(bal0) + ' -> ' + str(balance(t2)))
        write_diag()
        return
    if 'if (!settings.displaySetting.perConversationModel) return this' not in t2:
        note('ABORT selfcheck')
        write_diag()
        return
    p.write_text(t2, encoding='utf-8')
    note('conf OK: bindConfig keeps session model untouched while switch is off')
    write_diag()
    for line in report:
        print('::error::' + BATCH + ' ' + str(line)[:800])


main()