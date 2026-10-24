#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch270: 补 ChatInput.kt 缺失的 findModelById import（修 batch268 的编译红）

【run#492 编译红（annotations 实读）】
    ChatInput.kt:311 Unresolved reference 'findModelById' on receiver of type 'Settings'.
    ChatInput.kt:333 同上
根因：findModelById 是 me.rerere.rikkahub.data.datastore 下的顶层扩展函数，需要显式 import。
ChatInput.kt 的 import 区有 getCurrentChatModel / getCurrentAssistant / getQuickMessagesOfAssistant，
唯独没有 findModelById。batch268 把它当成员函数用 => unresolved（两处）。

【本批唯一改动】
ChatInput.kt import 区加一行（在 getCurrentAssistant 之前，保持字母序）：
    import me.rerere.rikkahub.data.datastore.findModelById

【佐证（snapshot 实读）】
ChatService.kt 的 import 区：
    import me.rerere.rikkahub.data.datastore.findModelById
    import me.rerere.rikkahub.data.datastore.findProvider
（同包并列，路径确凿）

【顺带说明】batch268 的两处替换本身已落地（snapshot 实读两处都改成了
findModelById(conversationChatModelId ?: assistant.chatModelId ?: settings.chatModelId)），
且同一条 Elvis 链在 rhConvModel255（ModelSelector 行）已编译通过 => 类型兼容（Uuid? 族）。
本批只补 import，不改任何逻辑。

五查:
 1. import 清单: 恰好新增 1 条；锚点 strip 全等唯一，否则 ABORT
 2. 同文件冲突: 只动 import 区；batch268 的替换行在函数体内，互不重叠
 3. 作用域: import 文件级，天然全局
 4. 括号: 新行无括号 => balance 不变（断言）
 5. 签名: 零改动
Python 三查: Q 构造引号; NL 显式 concat; helper 先定义后用; 失败即中止不写盘

【失败保护】锚点不唯一 / import 已存在 / balance 变化 => ABORT 不写盘。
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
DIAG = 'ci_diag_batch270.txt'
TARGET = 'app/src/main/java/me/rerere/rikkahub/ui/components/ai/ChatInput.kt'

IMPORT_NEW = 'import me.rerere.rikkahub.data.datastore.findModelById'
ANCHOR = 'import me.rerere.rikkahub.data.datastore.getCurrentAssistant'
MARK = 'rhConvModel268'
CALL = 'settings.findModelById(conversationChatModelId ?: assistant.chatModelId ?: settings.chatModelId)'

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


class Abort(Exception):
    pass


def unique(lines, needle, label):
    hits = [i for i, ln in enumerate(lines) if ln.strip() == needle]
    if len(hits) != 1:
        note('ABORT ' + label + ': count=' + str(len(hits)) + ' (need 1) -> ' + repr(needle))
        raise Abort(label)
    return hits[0]


def patch():
    p = ROOT / TARGET
    if not p.exists():
        note('ABORT missing ChatInput.kt')
        return
    t = p.read_text(encoding='utf-8')
    if IMPORT_NEW in t:
        note('already applied')
        return
    if MARK not in t:
        note('ABORT prerequisite missing: batch268 (rhConvModel268) not applied')
        raise Abort('prerequisite')
    bal0 = balance(t)
    lines = t.split(NL)

    a = unique(lines, ANCHOR, 'import anchor')
    lines[a:a] = [IMPORT_NEW]

    t2 = lines_to_text(lines)
    if balance(t2) != bal0:
        note('ABORT balance changed ' + str(bal0) + ' -> ' + str(balance(t2)))
        raise Abort('balance')

    ls2 = t2.split(NL)
    if len([i for i, ln in enumerate(ls2) if ln.strip() == IMPORT_NEW]) != 1:
        note('ABORT import selfcheck failed')
        raise Abort('selfcheck')
    if t2.count(CALL) != 2:
        note('ABORT findModelById call count=' + str(t2.count(CALL)) + ' (need 2, batch268 sites)')
        raise Abort('call count')

    p.write_text(t2, encoding='utf-8')
    note('ChatInput OK: findModelById import added (alphabetical position)')


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
        print('::error::batch270 diag written chars=' + str(len(body)))
    except Exception as e:
        print('::error::batch270 diag write FAILED ' + str(e)[:200])
    sys.stdout.flush()


def main():
    try:
        patch()
        note('1 chatinput import DONE')
    except Abort as e:
        note('1 chatinput import ABORTED (no file written): ' + str(e))
    except Exception as e:
        note('1 chatinput import EXCEPTION ' + type(e).__name__ + ' ' + str(e)[:300])
    print('::error::batch270 part: chatinput import')
    sys.stdout.flush()
    write_diag()
    for line in report:
        print('::error::batch270 ' + str(line)[:800])
    print('::error::batch270 END lines=' + str(len(report)))


main()
