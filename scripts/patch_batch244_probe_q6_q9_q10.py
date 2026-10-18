#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch244: #9 / #6 / #10 定位取证（纯只读，不改任何源文件）

【上一批 (batch243b, d48fe02c / run#457) 的真实结果 —— 从 ci_diag_batch243b.txt 实读】
    A1 wrote ChatMessageReasoning.kt            -> A1 OK
    A2 wrote TranslationHandler.kt + AppModule.kt -> A2 OK
    B1 values-zh/strings.xml hits=3
       L720  setting_display_page_paste_long_text_as_file_desc = "当粘贴的文本超过阈值时，自动将其保存为文件附件"
       L1215 assistant_page_local_tools_download_desc = "从网址下载文件到公共下载文件夹，并将文本内容（笔记、转录、笑话、脚本）保存为文件。"
       L1334 local_llm_litert_name = "本地 · LiteRT"
    B1 values/strings.xml hits=3
       L14   rh_lite_stream_render_title = "Lite streaming render"
       L1449 local_llm_litert_name = "Local · LiteRT"
       L1874 backup_page_local_backup_export_pure = "Lite backup (no attachments)"
    B2 SettingScheduledJobs refs total=7 files=4
       RouteActivity.kt=4, SettingPage.kt=1, SettingScheduledJobsPage.kt=1, SettingsSearchIndex.kt=1
  => batch243 的假绿已被修正版彻底修掉（三个文件都写了盘）。

【本次取证要回答的三个问题】
Q9 (用户: 没看懂 LITE"转文件") —— 两个已确认的疑点:
   ① rh_lite_stream_render_title 在 **values/strings.xml(英文) 有、values-zh 里没有** ⇒ 中文界面会回退显示英文
      "Lite streaming render" ⇒ 极可能就是用户看不懂的那个 LITE。
   ② 中文里唯一"转文件"语义的条目是 setting_display_page_paste_long_text_as_file_desc,
      但它的措辞是"保存为文件附件", 用户未必能对应上"转文件"。
   本次要 dump: en/zh 的 key 差集(定位所有"中文界面显示英文"的项) + 上述 key 在 .kt 里的引用点(含上下文)。
Q6 (用户: 定时任务怎么会有两个) —— RouteActivity.kt 里有 4 处 SettingScheduledJobs 引用,
   需要看这 4 行到底是"1 个 Screen 定义 + 1 个路由注册"还是"2 个入口"。
   本次要 dump: RouteActivity / SettingsSearchIndex / SettingPage 里每一处引用行(含上下文 2 行)。
Q10 (用户: 引用功能用不了) —— 等待 UI 现象输入, 本批只 dump 引用链现状计数, 不做任何改动。

本批为**纯只读**: 不写任何源文件, 只写 ci_diag_batch244.txt。
=> 不存在"改坏了"的风险; 是否存在"假绿"的判定标准 = snapshot 分支里能否读到 ci_diag_batch244.txt。

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
DIAG = 'ci_diag_batch244.txt'
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
    """返回 name -> 该行原文 的字典"""
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
        ('cn_zhuanwenjian', ['转文件', '存为文件', '保存为文件']),
        ('cron', ['SettingScheduledJobs']),
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
                        ctx = ' / '.join('L' + str(k + 1) + ':' + lines[k].strip()[:110] for k in range(lo, hi))
                        hits.append(path.name + ' ' + ctx)
                        break
        note('P2 [' + label + '] hits=' + str(len(hits)))
        for h in hits[:24]:
            note('P2 [' + label + '] ' + h[:300])


# ---------------------------------------------------------------------------
# P3. 定时任务入口逐行 dump (#6 定性)
# ---------------------------------------------------------------------------
def probe_cron_entries():
    targets = [
        'app/src/main/java/me/rerere/rikkahub/RouteActivity.kt',
        'app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingsSearchIndex.kt',
        'app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingPage.kt',
    ]
    for rel in targets:
        lines = read_lines(rel)
        if lines is None:
            note('P3 ' + rel + ' NOT FOUND')
            continue
        hits = [i for i, line in enumerate(lines) if 'SettingScheduledJobs' in line]
        note('P3 ' + Path(rel).name + ' hits=' + str(len(hits)))
        for i in hits:
            lo = max(0, i - 2)
            hi = min(len(lines), i + 3)
            ctx = ' / '.join('L' + str(k + 1) + '[' + str(len(lines[k]) - len(lines[k].lstrip())) + ']:' + lines[k].strip()[:120] for k in range(lo, hi))
            note('P3 ' + Path(rel).name + ' ' + ctx[:420])


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
        print('::error::batch244 diag written chars=' + str(len(body)) + ' lines=' + str(len(report)))
    except Exception as e:
        print('::error::batch244 diag write FAILED ' + str(e)[:300])
    sys.stdout.flush()


def main():
    for name, fn in [
        ('P1 key gap', probe_key_gap),
        ('P2 keyword refs', probe_keywords),
        ('P3 cron entries', probe_cron_entries),
    ]:
        try:
            fn()
            note(name + ' OK')
        except SystemExit as e:
            note(name + ' EXIT ' + str(getattr(e, 'code', '?')))
        except Exception as e:
            note(name + ' EXCEPTION ' + type(e).__name__ + ' ' + str(e)[:300])
        print('::error::batch244 part done: ' + name)
        sys.stdout.flush()
    write_diag()
    print('::error::batch244 DONE read-only probe lines=' + str(len(report)))


main()