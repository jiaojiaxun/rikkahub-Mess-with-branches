#!/usr/bin/env python3
'''batch65: UI-1 数据层重做——UIMessage.quotedMessageId（沿用 #173 曾绿策略）

曾绿证据：#173（57_1 v2）同策略构建全绿（patch + 编译 + R8），后因渲染层
连环错被连坐删除。本批重建数据层，为 UI-1 后续批（渲染/交互）铺路。

CI 形态关键事实（#172 dump 实证）：
- CI 里 translation 行为 'val translation: String? = null,'（带尾逗号）
- 仓库实读形态无尾逗号（两种都要兼容）
- 锚点用行级 strip 精确匹配 + 必要时补逗号写回

五查：
1. import 清单：新字段用 Uuid（Message.kt 已 import kotlin.uuid.Uuid）
2. 同文件冲突：ai 模块 Message.kt 无在链脚本碰（57_1 已删）
3. 作用域：UIMessage data class 字段区
4. 括号配对：纯字段行插入（自带尾逗号）
5. 函数签名：@Serializable data class 加可选字段（默认 null）→ 旧 JSON 兼容

Python 三查：无引号问题；无未定义引用；无 f-string/walrus/join
'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhQuoteData'


def fail(path, msg):
    print('::error file=' + path + '::batch65 ' + str(msg)[:1400])
    raise SystemExit(1)


MS = 'ai/src/main/java/me/rerere/ai/ui/Message.kt'
t = (ROOT / MS).read_text(encoding='utf-8')
if MARK in t:
    print('batch65: already applied')
else:
    lines = t.split(NL)
    idx = -1
    for i, ln in enumerate(lines):
        s = ln.strip()
        if s == 'val translation: String? = null,' or s == 'val translation: String? = null':
            idx = i
            break
    if idx < 0:
        print('batch65: dump lines containing translation:')
        for ln in lines:
            if 'val translation' in ln:
                print('  >> ' + ln.strip()[:160])
        fail(MS, 'translation field line not found')
    if not lines[idx].rstrip().endswith(','):
        lines[idx] = lines[idx].rstrip() + ','
    insert = [
        '    // ' + MARK + ' (UI-1/65): 引用回复目标 id；null=普通消息，旧 JSON 兼容',
        '    val quotedMessageId: Uuid? = null,',
    ]
    lines = lines[:idx + 1] + insert + lines[idx + 1:]
    text = NL.join(lines)
    if MARK not in text or 'val quotedMessageId: Uuid? = null,' not in text:
        fail(MS, 'selfcheck failed: inserted field missing')
    if not lines[idx].rstrip().endswith(','):
        fail(MS, 'translation line still lacks trailing comma')
    (ROOT / MS).write_text(text, encoding='utf-8')
    print('batch65: UIMessage.quotedMessageId inserted after translation')

print('batch65: OK')
