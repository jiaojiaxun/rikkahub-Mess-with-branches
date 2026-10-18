#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch244b: #9 / #10 定位取证 v2（纯只读）—— 移除 #6 相关探针 + 修正 #458 的失败重跑

【run #458 (b166d6db) 失败定位 —— 与脚本无关】
失败步骤: Run actions/setup-java@v5，在 0.5 秒内失败（非下载超时——那会花 10-30 秒）。
下游全部 skipped：Convert scripts to warn-only / Apply source patches 都**没有执行**，
本批脚本一次都没运行（ci_diag_batch244.txt 不存在可证）。
同一 setup-java 配置在 #454/#455/#456/#457 四连成功 => 配置无问题，判定为 GitHub/jetbrains 源的瞬时故障。
处理方式：推修正版触发新 run，而不是 rerun（匿名通道没有 rerun API 权限）。

【按用户指示：#6 已解决，不再触碰】
- 移除原 P3（RouteActivity / SettingsSearchIndex / SettingPage 的 SettingScheduledJobs 逐行 dump）
- 移除 P2 里的 'cron' 关键词组（SettingScheduledJobs）
- 本批只保留 #9 与 #10 的只读取证。

【本批要回答的两个问题】
Q9（没看懂 LITE"转文件"）—— batch243b 的 B1 已确认两个疑点：
  ① rh_lite_stream_render_title 在 values/strings.xml(英文) 有、values-zh 里没有
     => 中文界面回退显示英文 "Lite streaming render" => 极可能就是用户看不懂的那个 LITE;
  ② 中文里唯一"转文件"语义的条目是 setting_display_page_paste_long_text_as_file_desc
     = "当粘贴的文本超过阈值时，自动将其保存为文件附件"，措辞里没有"转文件"三字。
  本批 dump: en/zh 的 key 差集(定位所有"中文界面显示英文"项) + 相关 key 在 .kt 里的引用点(含上下文)。
Q10（引用功能用不了）—— 等待 UI 现象输入, 本批只 dump 引用链现状计数, 不做任何改动。

本批为**纯只读**: 不写任何源文件, 只写 ci_diag_batch244b.txt。
=> 不存在"改坏了"的风险; 是否存在"假绿"的判定标准 = snapshot 分支里能否读到 ci_diag_batch244b.txt。

五查(针对本批):
 1. import 清单: 零 import 改动(不改源文件)
 2. 同文件冲突: 不适用(只读)
 3. 作用域: 不适用(只读)
 4. 括号配对: 不适用(只读)
 5. 函数签名: 不适用(只读)
Python 三查: Q/SQ 变量构造引号; NL 显式 concat 禁 join/f-string/walrus; helper 先定义后用; 失败记录并继续
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
SQ = chr(39)
DIAG = 'ci_diag_batch244b.txt'
STRINGS_EN = 'app/src/main/res/values/strings.xml'
STRINGS_ZH = 'app/src/main/res/values-zh/strings.xml'

report = []


def note(msg):
    report.append(str(msg)[:900])


def lines_to_text(lines):
    out = ''
    for idx, line in enumerate(lines):
        if idx > 0:
            out += NL
        out += line
    return out


def read_lines(rel):
    p = ROOT / rel
    if not p.exists():
        return None
    return p.read_text(encoding='utf-8').split(NL)


def extract_keys(lines):
    keys = {}
    for line in lines:
        s = line.strip()
        if not s.startswith('<string'):
            continue
        i = s.find('name=' + Q)
        if i < 0:
            i = s.find('name=' + SQ)
            if i < 0:
                continue
            j = s.find(SQ, i + 6)
        else:
            j = s.find(Q, i + 6)
        if j < 0:
            continue
        name = s[i + 6:j]
        keys[name] = s[:240]
    return keys


# ---------------------------------------------------------------------------
# P1. en / zh 的 string key 差集 —— 定位"中文界面显示英文"的条目
# ---------------------------------------------------------------------------
def probe_key_gap():
    en = read_lines(STRINGS_EN)
    zh = read_lines(STRINGS_ZH)
    if en is None or zh is None:
        note('P1 strings file missing en=' + str(en is not None) + ' zh=' + str(zh is not None))
        return
    ken = extract_keys(en)
    kzh = extract_keys(zh)
    note('P1 keys en=' + str(len(ken)) + ' zh=' + str(len(kzh)))
    missing = []
    for name in ken:
        if name not in kzh:
            missing.append('MISSING_IN_ZH ' + name + ' :: ' + ken[name][:180])
    note('P1 zh missing count=' + str(len(missing)))
    for m in sorted(missing)[:60]:
        note('P1 ' + m)
    extra = 0
    for name in kzh:
        if name not in ken:
            extra += 1
    note('P1 zh-only keys=' + str(extra))


# ---------------------------------------------------------------------------
# P2. 关键词在所有 .kt 里的引用行(含上下文) —— 定位 #9 / #10 的 UI 位置
# ---------------------------------------------------------------------------
def probe_keywords():
    root = ROOT / 'app/src/main/java'
    if not root.exists():
        note('P2 app/src/main/java NOT FOUND')
        return
    groups = [
        ('rh_lite', ['rh_lite', 'rhLite', 'lite_stream', 'LiteStream']),
        ('lowtext', ['paste_long_text_as_file', 'long_text_as_file', 'LongTextAsFile']),
        ('cn_zhuanwenjian', ['转文件', '存为文件', '保存为文件', 'LITE']),
        ('quote', ['quotedMessageId', 'ChatMessageQuoteBlock', 'onQuote']),
    ]
    files = []
    for path in root.rglob('*.kt'):
        files.append(path)
    note('P2 scanned kt files=' + str(len(files)))
    for label, kws in groups:
        hits = []
        for path in files:
            try:
                lines = path.read_text(encoding='utf-8').split(NL)
            except Exception:
                continue
            for i, line in enumerate(lines):
                for kw in kws:
                    if kw in line:
                        lo = max(0, i - 1)
                        hi = min(len(lines), i + 2)
                        ctx = ' / '.join(
                            'L' + str(k + 1) + ':' + lines[k].strip()[:110]
                            for k in range(lo, hi)
                        )
                        hits.append(path.name + ' ' + ctx)
                        break
        note('P2 [' + label + '] hits=' + str(len(hits)))
        for h in hits[:24]:
            note('P2 [' + label + '] ' + h[:300])


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
        print('::error::batch244b diag written chars=' + str(len(body)) + ' lines=' + str(len(report)))
    except Exception as e:
        print('::error::batch244b diag write FAILED ' + str(e)[:300])
    sys.stdout.flush()


def main():
    for name, fn in [
        ('P1 key gap', probe_key_gap),
        ('P2 keyword refs', probe_keywords),
    ]:
        try:
            fn()
            note(name + ' OK')
        except SystemExit as e:
            note(name + ' EXIT ' + str(getattr(e, 'code', '?')))
        except Exception as e:
            note(name + ' EXCEPTION ' + type(e).__name__ + ' ' + str(e)[:300])
        print('::error::batch244b part done: ' + name)
        sys.stdout.flush()
    write_diag()
    print('::error::batch244b DONE read-only probe lines=' + str(len(report)))


main()