#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch217: 修榨干 token 开关不显示——ReasoningButton→ReasoningPicker 断链（warn-only）

run405 诊断(batch215-diag)破案:
  ReasoningPicker[sq=1,wire=0,cb=4] ChatInput[wire=2] ChatVM[wire=2] ChatInputState[wire=1]
  全链条注入都在, 但 ReasoningButton 内部调用 ReasoningPicker 的调用点没传
  squeezeTokenEnabled/onUpdateSqueezeToken(cb=4 = 两处签名+门控+invoke, 调用点 0 次)
  → ReasoningPicker 收到的 onUpdateSqueezeToken 永远是签名默认 null
  → if (onUpdateSqueezeToken != null) 永远 false → 开关永不渲染。

修法: ReasoningButton 内的 ReasoningPicker 调用点补传两个参数。
锚点: onUpdateReasoningLevel = onUpdateReasoningLevel(全文件唯一, startswith 宽松匹配,
      兼容行尾有无逗号两种形态; Preview 里的 onUpdateReasoningLevel = { level = it } 不匹配)。
铁律25: 原行是末参数(无尾逗号) → 先补逗号再插。
幂等 marker: rhBatch217Wire。warn-only; balance 校验; 失败只 ::warning。
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
BATCH = 'batch217'
MARK = 'rhBatch217Wire'

RP = 'app/src/main/java/me/rerere/rikkahub/ui/components/ai/ReasoningPicker.kt'

applied = []
skipped = []


def ok(tag):
    if tag not in applied:
        applied.append(tag)


def skip(tag, why):
    skipped.append(tag + '<' + str(why)[:80] + '>')


def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]


def balance(text):
    return (text.count('(') - text.count(')')) + (text.count('{') - text.count('}'))


def concat(lines):
    t = ''
    for i, ln in enumerate(lines):
        if i > 0:
            t += NL
        t += ln
    return t


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


def main():
    src = read(RP)
    if src is None:
        skip('wire', 'missing')
        return
    if MARK in src:
        ok('wire-exists')
        return
    lines = src.split(NL)
    bal0 = balance(src)

    hits = [i for i, ln in enumerate(lines)
            if ln.strip().startswith('onUpdateReasoningLevel = onUpdateReasoningLevel')]
    if len(hits) != 1:
        skip('wire', 'anchor=' + str(len(hits)))
        return
    ci = hits[0]
    d = ind(lines[ci])
    if not lines[ci].rstrip().endswith(','):
        lines[ci] = lines[ci].rstrip() + ','
    lines.insert(ci + 1, d + 'squeezeTokenEnabled = squeezeTokenEnabled, // ' + MARK + ' (batch217)')
    lines.insert(ci + 2, d + 'onUpdateSqueezeToken = onUpdateSqueezeToken, // ' + MARK + ' (batch217)')

    out = concat(lines)
    if balance(out) != bal0:
        skip('wire', 'balance')
        return
    if MARK not in out or 'squeezeTokenEnabled = squeezeTokenEnabled' not in out:
        skip('wire', 'selfcheck')
        return
    write(RP, out)
    ok('wire')
    print('::warning::' + BATCH + ' applied=[' + joinlist(applied) + '] skipped=[' + joinlist(skipped) + ']')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('::warning::' + BATCH + ' crashed: ' + str(exc)[:400])
    sys.exit(0)