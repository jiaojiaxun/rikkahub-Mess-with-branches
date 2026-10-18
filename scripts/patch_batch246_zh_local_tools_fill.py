#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch246: 补齐"本地工具"页缺失中文 + 剩余缺失全量取证（含上一轮错误结论的纠正）

【先说清楚一件事：我上一轮 (#9 结论) 推错了】
batch243b 的 B1 只搜索"值里含关键词"的行。values-zh 里 rh_lite_stream_render_title 的值是
「精简版流式渲染」——**中文里没有 "Lite" 字样**，所以 B1 没命中，我据此错误推断为"zh 缺 key"。
batch245 的 fill_zh 实测结果: `fill_zh nothing to add (all keys already present) skipped=2`
—— 两个 key 在 values-zh 里**本来就存在且已是中文**:
    values-zh: <string name="rh_lite_stream_render_title">精简版流式渲染</string>
               <string name="rh_lite_stream_render_desc">流式中的末条消息按纯文本直出（跳过 Markdown 与思考卡片动画），
                 生成完成自动切回完整渲染。长会话防卡顿。</string>
    values(en): "Lite streaming render" / "Stream the in-progress message as plain text ..."
=> 中文界面显示的是中文, 不是英文。batch245 对 #9 实际是**空操作**(只有 dump 生效),
   没有造成任何破坏(逐条"已存在则跳过"的保护起了作用), 但确实白跑了一趟。
=> 教训: 关键词命中不等于 key 缺失; 判定"缺 key"必须做 **key 集合比较**, 不能靠值里搜关键词。

【那么"中文界面出现英文"到底在哪 —— batch245 P2b 给出了真答案】
P2b: visible-ish missing = **121 条**(accessibility_* 另计 55 条)。已列出的前 70 条全部是:
  · assistant_page_local_tools_* —— 「本地工具」页里每个工具的名称与说明(压缩包/外部存储/键盘控制/密钥库/NFC/短信/壁纸)
  · gemini_* / grok_* —— Gemini 与 Grok 的 OAuth 账号相关界面
这些是用户真正**能在中文界面看到英文**的地方。本批先补「本地工具」这一组(用户最常打开),
其余在下批继续(dump 完整原文后再翻, 避免长文本被截断后盲译)。

【本批做什么】
 1. 向 values-zh/strings.xml 新增 20 条「本地工具」中文(纯新增, 不覆盖已有条目)。
    每条译文写入前做三项校验:
      a. 幂等: zh 已有该 key 则跳过(不会重复 key);
      b. 占位符: 从 en 原文提取 %1$s / %1$d / %% 集合, 译文必须包含同一集合, 否则跳过并报错
         (占位符不一致会导致运行时 MissingFormatArgumentException);
      c. 转义: 单引号 ' 转成 \\' (Android 资源要求), 并做 & < > 的 XML 转义。
    已跳过 assistant_page_local_tools_keyboard_setup_message —— 它在 dump 里被截断, 原文不完整, 不盲译。
 2. 全量 dump 剩余缺失项(值放宽到 400 字符), 供下一批继续补。

【为什么本批不可能产生假绿或改坏】
 - 只改 values-zh/strings.xml, 纯新增, 不动任何 .kt
 - 三项校验任一不通过就跳过该条(不写入), 不会写入坏资源
 - 落地判定 = snapshot 能读到 ci_diag_batch246.txt 且 values-zh 里出现新 key

五查:
 1. import 清单: 零(资源文件)
 2. 同文件冲突: values-zh/strings.xml 被在链 batch197v2 / batch92 / batch245 改过;
    本批只在 </resources> 之前追加, 不触碰任何已有条目 => 锚点不相交
 3. 作用域: 零
 4. 括号配对: 校验插入块 <string> 与 </string> 数量相等
 5. 函数签名: 零
Python 三查: Q 变量构造引号; NL 显式 concat 禁 join/f-string/walrus; helper 先定义后用; 失败记录并继续
'''
import re
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
BS = chr(92)
DIAG = 'ci_diag_batch246.txt'
STRINGS_EN = 'app/src/main/res/values/strings.xml'
STRINGS_ZH = 'app/src/main/res/values-zh/strings.xml'

# 「本地工具」页中文补齐(译文;英文原文见 batch245 P2b dump)
ZH_FILL = [
    ('assistant_page_local_tools_archive_title', '压缩包（zip）'),
    ('assistant_page_local_tools_archive_desc', '直接创建和打开 .zip 压缩包。v1 不支持密码。支持 file:// 与 content:// 路径。'),
    ('assistant_page_local_tools_external_storage_title', '外部存储'),
    ('assistant_page_local_tools_external_storage_desc', '让文件工具可以读写 U 盘、SD 卡、下载目录与云存储。每个目录需要先用 SAF 选择器授权一次。'),
    ('assistant_page_local_tools_keyboard_title', '键盘控制'),
    ('assistant_page_local_tools_keyboard_desc', '通过配套的 agent-keyboard 输入法操作当前输入框：输入、读取、按键、删除、移动光标、选中文本。共 8 个工具。'),
    ('assistant_page_local_tools_keyboard_setup_title', '设置 agent-keyboard'),
    ('assistant_page_local_tools_keyboard_status_installed', 'agent-keyboard 已安装 — 设为当前输入法即可使用这些工具'),
    ('assistant_page_local_tools_keyboard_status_not_installed', '未安装 agent-keyboard 应用'),
    ('assistant_page_local_tools_keystore_title', '密钥库'),
    ('assistant_page_local_tools_keystore_desc', '使用硬件级密钥（Android Keystore）生成、签名、加密与解密。共 7 个工具。'),
    ('assistant_page_local_tools_nfc_title', 'NFC'),
    ('assistant_page_local_tools_nfc_desc', '读写 NFC 标签上的 NDEF 记录。需要在应用处于前台时才能检测到标签。'),
    ('assistant_page_local_tools_nfc_unavailable', '此设备没有 NFC 硬件，因此无法启用这些工具。'),
    ('assistant_page_local_tools_sms_send_title', '发送短信'),
    ('assistant_page_local_tools_sms_send_desc', '以编程方式发送短信。需要 SEND_SMS 权限。每次调用都需要确认。'),
    ('assistant_page_local_tools_wallpaper_title', '壁纸'),
    ('assistant_page_local_tools_wallpaper_desc', '用本地图片设置桌面或锁屏壁纸。每次调用都需要确认。'),
    ('assistant_page_local_tools_section_keyboard', '键盘控制'),
    ('assistant_page_local_tools_section_privileged', '特权工具'),
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


def extract_values(lines):
    """返回 name -> 标签内原始值(未转义)"""
    values = {}
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
        name = s[i + 6:j]
        k = s.find('>', j)
        m = s.rfind('</string>')
        if k < 0 or m < 0 or m <= k:
            values[name] = ''
            continue
        values[name] = s[k + 1:m]
    return values


def placeholders(text):
    found = set()
    for m in re.finditer(r'%[0-9]+\\$[sd]', text):
        found.add(m.group(0))
    if '%%' in text:
        found.add('%%')
    return found


def xml_escape(text):
    out = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    out = out.replace(BS + SQPLACE, BS + SQPLACE)  # no-op, kept for clarity
    return out


SQPLACE = chr(39)


def android_escape(text):
    """Android string 资源要求单引号转义"""
    return text.replace(SQPLACE, BS + SQPLACE)


def fill_zh():
    zp = ROOT / STRINGS_ZH
    ep = ROOT / STRINGS_EN
    if not zp.exists() or not ep.exists():
        note('FATAL strings file missing zh=' + str(zp.exists()) + ' en=' + str(ep.exists()))
        return
    zlines = zp.read_text(encoding='utf-8').split(NL)
    en_values = extract_values(ep.read_text(encoding='utf-8').split(NL))
    have = extract_values(zlines)

    closing = -1
    for i in range(len(zlines) - 1, -1, -1):
        if zlines[i].strip() == '</resources>':
            closing = i
            break
    if closing < 0:
        note('FATAL </resources> not found in values-zh')
        return

    block = []
    added = []
    skipped_existing = []
    skipped_ph = []
    skipped_missing_en = []
    for key, zh_text in ZH_FILL:
        if key in have:
            skipped_existing.append(key)
            continue
        if key not in en_values:
            skipped_missing_en.append(key)
            continue
        en_ph = placeholders(en_values[key])
        zh_ph = placeholders(zh_text)
        if en_ph != zh_ph:
            skipped_ph.append(key + '(en=' + ','.join(sorted(en_ph)) + ' zh=' + ','.join(sorted(zh_ph)) + ')')
            continue
        block.append('    <!-- rhZhLocalTools246 -->')
        block.append('    <string name=' + Q + key + Q + '>' + xml_escape(android_escape(zh_text)) + '</string>')
        added.append(key)

    if not block:
        note('fill_zh nothing to add; existing=' + str(len(skipped_existing))
             + ' ph_mismatch=' + str(len(skipped_ph)) + ' no_en=' + str(len(skipped_missing_en)))
        for s in skipped_ph[:10]:
            note('fill_zh PH-SKIP ' + s)
        return

    joined = lines_to_text(block)
    if joined.count('<string') != joined.count('</string>'):
        note('FATAL inserted block tag imbalance, abort write')
        return

    zlines = zlines[:closing] + block + zlines[closing:]
    out = lines_to_text(zlines)
    for key in added:
        if ('name=' + Q + key + Q) not in out:
            note('FATAL selfcheck missing ' + key)
            return
    zp.write_text(out, encoding='utf-8')
    note('fill_zh ADDED=' + str(len(added)) + ' existing=' + str(len(skipped_existing))
         + ' ph_mismatch=' + str(len(skipped_ph)) + ' no_en=' + str(len(skipped_missing_en)))
    for s in skipped_ph[:10]:
        note('fill_zh PH-SKIP ' + s)


def dump_missing():
    en = read_lines(STRINGS_EN)
    zh = read_lines(STRINGS_ZH)
    if en is None or zh is None:
        note('P2 err strings missing')
        return
    ken = extract_values(en)
    kzh = extract_values(zh)
    missing = []
    invis = 0
    for name in ken:
        if name in kzh:
            continue
        if name.startswith('accessibility_'):
            invis += 1
            continue
        missing.append(name + ' :: ' + ken[name][:400])
    note('P2 visible-ish missing=' + str(len(missing)) + ' accessibility_excluded=' + str(invis))
    for m in sorted(missing):
        note('P2 ' + m)


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
        print('::error::batch246 diag written chars=' + str(len(body)) + ' lines=' + str(len(report)))
    except Exception as e:
        print('::error::batch246 diag write FAILED ' + str(e)[:300])
    sys.stdout.flush()


def main():
    for name, fn in [
        ('fill_zh local tools', fill_zh),
        ('dump remaining missing', dump_missing),
    ]:
        try:
            fn()
            note(name + ' OK')
        except SystemExit as e:
            note(name + ' EXIT ' + str(getattr(e, 'code', '?')))
        except Exception as e:
            note(name + ' EXCEPTION ' + type(e).__name__ + ' ' + str(e)[:300])
        print('::error::batch246 part done: ' + name)
        sys.stdout.flush()
    write_diag()
    print('::error::batch246 DONE lines=' + str(len(report)))


main()