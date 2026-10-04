#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
batch86b v4 — 【纯诊断·通道修正版】dump 全部塞进 ::error message

#238 教训(重要):
  我 v3 用 print() 做 dump —— print 只进 job 日志,匿名无法下载;
  **只有 ::error 的 message 字段才会变成 check-run annotation**。
  所以 v3 的 dump 我根本没拿到。v4 把 dump 写进 ::error message 里。

本脚本【绝不修改任何文件】,只 dump:
  1. ChatMessage.kt 的 `fun ChatMessage(` 参数区
  2. ChatMessage.kt 的 `ChatMessageUserAvatar(` 调用区
  3. ChatList.kt 的 `fun ChatList(` 参数区
  4. ChatList.kt 的 `private fun ChatListNormal(` 参数区
  5. ChatList.kt 的 `ChatListNormal(` 调用区
  6. ChatList.kt 的 `ChatMessage(` 调用区
  7. 测试文件 ModelContextLengthResolverTest.kt(glob 定位)第 50-65 行
     —— #238 报 commonFamiliesResolve FAILED @L58

为什么必须拿真值:
  #237 报 "onChangeAvatar on receiver of type 'Modifier'" + ChatList 两处
  "No parameter with name 'onEditNickname'" =>
  签名插入【没落到参数区】、调用插入【落进去了】=> 我的 paren_close 在 CI 形态
  下返回了错误的闭合行。必须看 CI 真实行文本才能修准(铁律22)。
'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
CHUNK = 1500  # ::error message 每段上限(保守)


def collect(rel, anchors, before, after, label, out):
    p = ROOT / rel
    if not p.exists():
        out.append('[' + label + '] FILE MISSING ' + rel)
        return
    lines = p.read_text(encoding='utf-8').split(NL)
    out.append('[' + label + '] ' + rel + ' lines=' + str(len(lines)))
    for a in anchors:
        hits = [i for i, ln in enumerate(lines) if ln.strip() == a]
        out.append('  anchor=' + repr(a) + ' hits=' + str(len(hits)))
        for h in hits[:2]:
            for i in range(max(0, h - before), min(len(lines), h + after)):
                mark = '>>' if i == h else '  '
                out.append('    ' + mark + ' L' + str(i + 1) + ': ' + repr(lines[i]))
    return


def main():
    out = []
    out.append('==== batch86b v4 DIAGNOSTIC (no file modified) ====')
    out.append('cwd=' + str(ROOT))
    collect('app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessage.kt',
            ['fun ChatMessage(', 'ChatMessageUserAvatar('], 2, 42, 'A+B ChatMessage.kt', out)
    collect('app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatList.kt',
            ['fun ChatList(', 'private fun ChatListNormal(', 'ChatListNormal(', 'ChatMessage('],
            2, 42, 'C-F ChatList.kt', out)

    # 测试文件:glob 定位(路径未知)
    tests = list(ROOT.glob('app/src/test/**/ModelContextLengthResolverTest.kt'))
    out.append('[G test] glob hits=' + str(len(tests)))
    for tp in tests:
        tl = tp.read_text(encoding='utf-8').split(NL)
        out.append('  file=' + str(tp))
        for i in range(40, min(72, len(tl))):
            out.append('    L' + str(i + 1) + ': ' + repr(tl[i]))

    text = NL.join(out)
    print(text)
    # 分片发 ::error —— 只有 message 会变成 annotation
    parts = []
    cur = ''
    for ln in out:
        if len(cur) + len(ln) + 1 > CHUNK:
            parts.append(cur)
            cur = ''
        cur += ln + NL
    if cur:
        parts.append(cur)
    for idx, part in enumerate(parts):
        print('::error file=scripts/patch_batch86b.py::dump[' + str(idx + 1) + '/' + str(len(parts)) + '] ' + part.replace(NL, ' | '))


main()