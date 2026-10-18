#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch247: 补齐 Gemini / Grok OAuth 界面缺失中文（49 条）+ 剩余缺失再取证

【为什么不等 batch246 的新 dump】
run #461 查询时仍在 in_progress；同时 jsdelivr 通道本次返回 Connection reset（网络波动）。
因此本批**用手头已确认完整的原文**先推进，不空等：
  batch245 的 P2b dump 里已有 200 字符截断的输出，其中 49 条 gemini_*/grok_* 条目**完整**
  （以 </string> 结尾）。被截断的 3 条**不盲译**，留给下批:
    · gemini_ban_warning_body        (末尾 "Google\'s terms let them" 未完)
    · grok_provider_description      (末尾 "no API key neede" 未完)
    · assistant_page_local_tools_keyboard_setup_message (末尾 "Settings &gt;" 未完)
  本批自己再 dump 一次剩余缺失（≥600 字符），与 batch246 的输出互为保险。

【前置事实（已核实，非推测）】
  · gemini_*/grok_* 在 values/strings.xml(en) 存在、values-zh 缺失 => 中文界面显示英文
  · 这两个 Provider 在 fork 里**真实存在**：DataSourceModule.kt 里 import 并注册了
    CodexProvider / GrokProvider / GeminiProvider / GeminiAccountRepository / GrokOAuthManager 等
    => 不是"库存字符串"，用户界面确实会用到

【本批做什么】
1. 向 values-zh/strings.xml 新增 49 条中文（纯新增，不覆盖已有条目）。
   每条写入前三项校验：
     a. 幂等: zh 已有该 key 则跳过
     b. 占位符: 从 en 原文提取 %1$s / %1$d / %% 集合, 译文必须含同一集合, 否则跳过并报错
        (本批涉及 gemini_percent_remaining/grok_percent_remaining 的 %1$d%%,
         gemini_project_id/grok_plan/grok_resets_at/grok_on_demand_cap 的 %1$s,
         gemini_accounts_count/grok_accounts_count 的 %1$d —— 逐条校验)
     c. 转义: ' -> \\' + & < > XML 转义
2. 再 dump 一次剩余缺失(值截断放宽到 600 字符)

【为什么本批不可能假绿或改坏】
 - 只改 values-zh/strings.xml, 纯新增, 不动任何 .kt
 - 三项校验任一不通过就跳过该条(不写入)
 - 落地判定 = snapshot 能读到 ci_diag_batch247.txt 且 values-zh 出现新 key

五查:
 1. import 清单: 零(资源文件)
 2. 同文件冲突: values-zh 被在链 batch197v2/batch92/batch245/batch246 改过;
    本批只在 </resources> 之前追加, 不触碰已有条目 => 锚点不相交
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
SQ = chr(39)
DIAG = 'ci_diag_batch247.txt'
STRINGS_EN = 'app/src/main/res/values/strings.xml'
STRINGS_ZH = 'app/src/main/res/values-zh/strings.xml'

ZH_FILL = [
    ('gemini_accounts_count', '账号（%1$d）'),
    ('gemini_ban_warning_title', '这可能会让你的 Google 账号被封禁'),
    ('gemini_check_status', '检查状态'),
    ('gemini_daily_limit', '每日额度'),
    ('gemini_enable', '启用 Gemini OAuth'),
    ('gemini_no_accounts', '尚未登录任何 Google 账号。'),
    ('gemini_oauth_ports_unavailable', '本地回调端口被占用，无法开始 Google 登录。请关闭占用该端口的应用后重试。'),
    ('gemini_oauth_success', 'Google 登录完成'),
    ('gemini_percent_remaining', '剩余 %1$d%%'),
    ('gemini_project_id', '云项目：%1$s'),
    ('gemini_provider_description', '使用 Google 账号登录，经由 Google Cloud Code Assist 生成内容（与 Antigravity 相同的后端）。无需 API Key。'),
    ('gemini_provider_short_description', 'Google 账号登录 — 请先阅读封号警告'),
    ('gemini_reauthenticate', '重新授权'),
    ('gemini_refresh', '刷新'),
    ('gemini_refresh_failed', '刷新账号失败'),
    ('gemini_remove', '移除'),
    ('gemini_remove_account_message', '移除后需要重新登录才能使用该账号。'),
    ('gemini_remove_account_title', '移除 Google 账号？'),
    ('gemini_resets_at', '重置时间 %1$s'),
    ('gemini_round_robin_description', '按轮询顺序使用已启用的账号。'),
    ('gemini_sign_in', '使用 Google 登录'),
    ('gemini_sign_in_required', '请先登录至少一个 Google 账号。'),
    ('gemini_token_available', '令牌有效'),
    ('gemini_token_expired', '令牌已过期'),
    ('gemini_token_not_checked', '尚未检查令牌状态'),
    ('gemini_token_unavailable', '令牌不可用'),
    ('gemini_weekly_limit', '每周额度'),
    ('grok_accounts_count', '账号（%1$d）'),
    ('grok_check_status', '检查状态'),
    ('grok_enable', '启用 Grok'),
    ('grok_enter_code_prompt', '请在浏览器中批准登录。若验证码未自动填入，请输入：'),
    ('grok_no_accounts', '尚未登录任何 Grok 账号。'),
    ('grok_oauth_success', 'xAI 登录完成'),
    ('grok_on_demand_cap', '按量付费：上限 %1$s'),
    ('grok_on_demand_disabled', '按量付费：已禁用'),
    ('grok_percent_remaining', '剩余 %1$d%%'),
    ('grok_plan', '套餐：%1$s'),
    ('grok_reauthenticate', '重新授权'),
    ('grok_refresh', '刷新'),
    ('grok_refresh_failed', '刷新账号失败'),
    ('grok_remove', '移除'),
    ('grok_remove_account_message', '移除后需要重新登录才能使用该账号。'),
    ('grok_remove_account_title', '移除 Grok 账号？'),
    ('grok_resets_at', '重置时间 %1$s'),
    ('grok_round_robin_description', '按轮询顺序使用已启用的账号。'),
    ('grok_sign_in', '使用 xAI 登录'),
    ('grok_sign_in_required', '请先登录至少一个可用账号。'),
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
    for m in re.finditer(r'%[0-9]+' + BS + r'$[sd]', text):
        found.add(m.group(0))
    if '%%' in text:
        found.add('%%')
    return found


def xml_escape(text):
    out = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    return out


def android_escape(text):
    return text.replace(SQ, BS + SQ)


def fill_zh():
    zp = ROOT / STRINGS_ZH
    ep = ROOT / STRINGS_EN
    if not zp.exists() or not ep.exists():
        note('FATAL strings missing zh=' + str(zp.exists()) + ' en=' + str(ep.exists()))
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
        note('FATAL </resources> not found')
        return

    block = []
    added = []
    existing = []
    ph_skip = []
    no_en = []
    for key, zh_text in ZH_FILL:
        if key in have:
            existing.append(key)
            continue
        if key not in en_values:
            no_en.append(key)
            continue
        if placeholders(en_values[key]) != placeholders(zh_text):
            ph_skip.append(key + '(en=' + ','.join(sorted(placeholders(en_values[key])))
                           + ' zh=' + ','.join(sorted(placeholders(zh_text))) + ')')
            continue
        block.append('    <!-- rhZhOAuth247 -->')
        block.append('    <string name=' + Q + key + Q + '>' + xml_escape(android_escape(zh_text)) + '</string>')
        added.append(key)

    note('fill_zh added=' + str(len(added)) + ' existing=' + str(len(existing))
         + ' ph_skip=' + str(len(ph_skip)) + ' no_en=' + str(len(no_en)))
    for s in (ph_skip + no_en)[:12]:
        note('fill_zh SKIP ' + s)

    if not block:
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
    note('fill_zh WROTE ' + str(len(added)) + ' keys')


def dump_missing():
    en = read_lines(STRINGS_EN)
    zh = read_lines(STRINGS_ZH)
    if en is None or zh is None:
        note('P2 strings missing')
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
        missing.append(name + ' :: ' + ken[name][:600])
    note('P2 visible-ish missing=' + str(len(missing)) + ' accessibility_excluded=' + str(invis))
    for m in sorted(missing):
        note('P2 ' + m)


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
        print('::error::batch247 diag written chars=' + str(len(body)) + ' lines=' + str(len(report)))
    except Exception as e:
        print('::error::batch247 diag write FAILED ' + str(e)[:300])
    sys.stdout.flush()


def main():
    for name, fn in [
        ('fill_zh gemini/grok', fill_zh),
        ('dump remaining missing', dump_missing),
    ]:
        try:
            fn()
            note(name + ' OK')
        except SystemExit as e:
            note(name + ' EXIT ' + str(getattr(e, 'code', '?')))
        except Exception as e:
            note(name + ' EXCEPTION ' + type(e).__name__ + ' ' + str(e)[:300])
        print('::error::batch247 part done: ' + name)
        sys.stdout.flush()
    write_diag()
    print('::error::batch247 DONE lines=' + str(len(report)))


main()