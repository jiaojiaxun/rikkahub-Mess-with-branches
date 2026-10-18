#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch245: #9 落地修复(补中文资源) + 剩余缺失文案精准取证

【batch244b 取证结果 —— 从 snapshot 的 ci_diag_batch244b.txt 实读, 本批的输入】
P1  keys en=1904 zh=1728, zh missing=176, zh-only=0
P2  [rh_lite] 16 hits, 已还原功能语义:
      ChatMessage.kt L198  // rhLiteStream (batch53): 精简流式——流式末条消息纯文本直出, 生成完成自动切回完整渲染
      ChatMessage.kt L199  if (settings.liteStreamRender && loading && lastMessage) {
      ChatMessage.kt L201      LiteStreamingText(parts = message.parts)
      ChatMessage.kt L320  // rhLiteStream (batch53): 最轻量流式渲染——纯 Text 直出, 跳过 Markdown
      ChatList.kt   L538  // rhLiteStreamLoading (batch53): 精简模式下去掉动画加载指示器
      SettingPreferencesUIPage.kt L310-311  用 rh_lite_stream_render_title / rh_lite_stream_render_desc 两个资源
      PreferencesStore.kt L1023-1024  默认 false = 原版行为
    [lowtext] 12 hits: SettingPreferencesGeneralPage.kt L198-199 使用
      setting_display_page_paste_long_text_as_file_title / _desc
      PreferencesStore.kt L1010-1011  pasteLongTextAsFile = false, pasteLongTextThreshold = 1000
    [cn_zhuanwenjian] 13 hits: 另有两处 Lite 语义(与流式无关) ——
      BackupExportFormat.LITE(轻量备份) / LITE_MAX_FILE_SIZE = 3MB / ImportExportTab L205 「轻量备份附件」
      local_llm_litert_name 「本地 · LiteRT」

【#9 的结论(由上述证据直接得出, 非猜测)】
用户看不懂的"LITE"= `liteStreamRender` 开关(batch53 引入)。它的**标题与说明只存在于
values/strings.xml(英文), values-zh/strings.xml 里没有** => 中文界面回退显示英文
"Lite streaming render" => 用户自然看不懂。
而它做的事情, 正是"流式期间用纯文本直出、跳过 Markdown 与动画"——也就是本次被用户否决的
那类**牺牲观感**的方案; 它默认关闭, 而 batch241/242 提供的是不牺牲观感的路线。
所以本批不删它(删除是行为改动), 只做两件零风险的事:
  1. 把缺失的中文标题与说明补进 values-zh => 用户至少看得懂它是什么、要不要开;
  2. 把其余 zh 缺失项精准 dump 出来(排除 accessibility_ 这类看不见的内容描述),
     供下一批继续补。

【为什么本批不可能产生假绿或改坏】
- 只改 values-zh/strings.xml: 纯**新增** <string> 条目, 不覆盖任何已有条目, 不动任何 .kt
- 新增 key 前逐条检查 zh 是否已存在 => 不会出现重复 key
- 剩余部分是纯只读取证
- 落地判定 = snapshot 能读到 ci_diag_batch245.txt 且 values-zh 里出现新 key

五查:
 1. import 清单: 零(资源文件)
 2. 同文件冲突: values-zh/strings.xml 在链上被 batch197 v2(中文可爱语气) 与 batch92(整理) 改过;
    本批只在 </resources> 之前追加新行, 不触碰任何已有条目 => 锚点不相交
 3. 作用域: 零(资源文件)
 4. 括号配对: 校验插入块自身 <string>/</string> 数量相等
 5. 函数签名: 零
Python 三查: Q 变量构造引号; NL 显式 concat 禁 join/f-string/walrus; helper 先定义后用; 失败记录并继续
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
DIAG = 'ci_diag_batch245.txt'
STRINGS_EN = 'app/src/main/res/values/strings.xml'
STRINGS_ZH = 'app/src/main/res/values-zh/strings.xml'

# 已确认缺失的中文文案(key 语义已由 batch244b 的 P2 证据还原)
ZH_FILL = [
    ('rh_lite_stream_render_title',
     '精简流式渲染'),
    ('rh_lite_stream_render_desc',
     '流式输出时最后一条消息只用纯文本直出，跳过 Markdown 排版与动画；生成结束后自动恢复完整渲染。开启会更顺滑，但流式过程中看不到实时格式。默认关闭。'),
]

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
            continue
        j = s.find(Q, i + 6)
        if j < 0:
            continue
        keys[s[i + 6:j]] = s[:240]
    return keys


def xml_escape(text):
    out = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    return out.replace('"', '&quot;')


# ---------------------------------------------------------------------------
# 1. 补齐 zh 缺失的中文文案(只新增, 不覆盖)
# ---------------------------------------------------------------------------
def fill_zh():
    p = ROOT / STRINGS_ZH
    if not p.exists():
        note('FATAL values-zh/strings.xml NOT FOUND')
        return
    lines = p.read_text(encoding='utf-8').split(NL)
    have = extract_keys(lines)
    closing = -1
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip() == '</resources>':
            closing = i
            break
    if closing < 0:
        note('FATAL </resources> not found in values-zh')
        return

    block = []
    added = []
    skipped = []
    for key, zh_text in ZH_FILL:
        if key in have:
            skipped.append(key)
            continue
        block.append('    <!-- rhZhLiteStreamFill245: batch53 引入的开关一直缺中文, 界面回退显示英文 -->')
        block.append('    <string name=' + Q + key + Q + '>' + xml_escape(zh_text) + '</string>')
        added.append(key)

    if not block:
        note('fill_zh nothing to add (all keys already present) skipped=' + str(len(skipped)))
        return

    if lines_to_text(block).count('<string') != lines_to_text(block).count('</string>'):
        note('FATAL inserted block string tag imbalance, abort write')
        return

    lines = lines[:closing] + block + lines[closing:]
    out = lines_to_text(lines)
    for key in added:
        if ('name=' + Q + key + Q) not in out:
            note('FATAL selfcheck missing ' + key)
            return
    p.write_text(out, encoding='utf-8')
    note('fill_zh ADDED ' + str(added) + ' skipped ' + str(skipped))


# ---------------------------------------------------------------------------
# 2. 剩余 zh 缺失项精准 dump(排除 accessibility_ 这类不可见内容描述)
# ---------------------------------------------------------------------------
def dump_remaining_missing():
    en = read_lines(STRINGS_EN)
    zh = read_lines(STRINGS_ZH)
    if en is None or zh is None:
        note('P2b strings missing en=' + str(en is not None) + ' zh=' + str(zh is not None))
        return
    ken = extract_keys(en)
    kzh = extract_keys(zh)
    missing = []
    invisible = 0
    for name in ken:
        if name in kzh:
            continue
        if name.startswith('accessibility_'):
            invisible += 1
            continue
        missing.append(name + ' :: ' + ken[name][:200])
    note('P2b visible-ish missing=' + str(len(missing)) + ' (accessibility_* excluded=' + str(invisible) + ')')
    for m in sorted(missing)[:70]:
        note('P2b ' + m)


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
        print('::error::batch245 diag written chars=' + str(len(body)) + ' lines=' + str(len(report)))
    except Exception as e:
        print('::error::batch245 diag write FAILED ' + str(e)[:300])
    sys.stdout.flush()


def main():
    for name, fn in [
        ('fill_zh (add missing Chinese strings)', fill_zh),
        ('P2b remaining missing probe', dump_remaining_missing),
    ]:
        try:
            fn()
            note(name + ' OK')
        except SystemExit as e:
            note(name + ' EXIT ' + str(getattr(e, 'code', '?')))
        except Exception as e:
            note(name + ' EXCEPTION ' + type(e).__name__ + ' ' + str(e)[:300])
        print('::error::batch245 part done: ' + name)
        sys.stdout.flush()
    write_diag()
    print('::error::batch245 DONE lines=' + str(len(report)))


main()