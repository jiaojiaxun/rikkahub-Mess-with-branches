#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""batch132: 版本号自动盖戳 + get_app_version 工具注册(fail-loud,幂等)。

v2 修复: 结构校验从 fail 改为 warn-only —— batch130(酒馆模式)改变了
ChatService 工具装配行的下一行内容(不再是 addAll(pluginToolProvider.getTools())),
原校验 sys.exit(1) 导致构建阻塞。改为只 warn 不 fail,核心功能(插入 appVersionTool)不受影响。

【功能 A — 版本盖戳】app/build.gradle.kts
- versionName: "2.4.14"           -> "2.4.14+run321"
- versionCode: 181                -> 18100321  (= 181×100000 + run,单调递增)
- 环境变量 GITHUB_RUN_NUMBER 缺失/非数字时跳过(本地构建保持原值)。
- 已盖戳则跳过(幂等:行内含 +run 即认定已完成)。

【功能 B — 工具注册】ChatService.kt
- ChatService 有 2 个工具装配点共用同一锚点行
  addAll(localTools.getTools(assistant.localTools, invocationCtx)):
    ① buildToolsForRerun (rerun 路径)
    ② handleMessageComplete 主生成路径
- 两个装配点都插入 add(...appVersionTool(context))。
- v2: 结构校验(下一行须是 pluginToolProvider)改为 warn-only,因 batch130 可能改变顺序。
"""
import os, re, sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
SQ = chr(39)
MARK = 'rhAppVersion'

def concat_lines(lines):
    text = ''
    first = True
    for line in lines:
        if not first:
            text += NL
        text += line
        first = False
    return text


def stamp_version() -> bool:
    gradle = ROOT / 'app' / 'build.gradle.kts'
    run_str = os.environ.get('GITHUB_RUN_NUMBER', '').strip()
    if not run_str or not run_str.isdigit():
        print('stamp_version: GITHUB_RUN_NUMBER absent, local build keeps original version')
        return False

    run_n = int(run_str)
    text = gradle.read_text(encoding='utf-8')
    if '+run' in text and re.search(r'versionName\s*=\s*' + Q + r'[^' + Q + r']*\+run\d+' + Q, text):
        print('stamp_version: already stamped (found +runN in versionName), skipping')
        return False

    lines = text.split(NL)
    code_hits = [i for i, ln in enumerate(lines) if ln.lstrip().startswith('versionCode =')]
    name_hits = [i for i, ln in enumerate(lines) if ln.lstrip().startswith('versionName =')]
    if len(code_hits) != 1 or len(name_hits) != 1:
        msg = 'stamp_version anchor mismatch: code=' + str(len(code_hits)) + ' name=' + str(len(name_hits))
        print('::error file=app/build.gradle.kts::' + msg)
        for idx_list, label in [(code_hits, 'versionCode'), (name_hits, 'versionName')]:
            if idx_list:
                i0 = max(0, idx_list[0]-2)
                print('  [' + label + ' context]:')
                for j in range(i0, min(len(lines), idx_list[0]+3)):
                    print('    L' + str(j+1) + ': ' + lines[j])
        return sys.exit(1)

    ci = code_hits[0]
    ni = name_hits[0]
    m_code = re.search(r'versionCode\s*=\s*(\d+)', lines[ci])
    if not m_code:
        print('::error file=app/build.gradle.kts::stamp_version: versionCode line has no digits')
        return sys.exit(1)
    base_code = int(m_code.group(1))
    new_code = base_code * 100000 + run_n
    code_ind = lines[ci][:len(lines[ci]) - len(lines[ci].lstrip())]
    lines[ci] = code_ind + 'versionCode = ' + str(new_code) + '  // ' + MARK + ': ' + str(base_code) + 'x100k+run' + str(run_n)

    m_name = re.search(r'versionName\s*=\s*' + Q + r'([^' + Q + r']*)' + Q, lines[ni])
    if not m_name:
        print('::error file=app/build.gradle.kts::stamp_version: versionName line malformed')
        return sys.exit(1)
    base_name = m_name.group(1)
    base_name = re.sub(r'\+run\d+$', '', base_name)
    name_ind = lines[ni][:len(lines[ni]) - len(lines[ni].lstrip())]
    lines[ni] = name_ind + 'versionName = ' + Q + base_name + '+run' + str(run_n) + Q + '  // ' + MARK

    out = concat_lines(lines)
    if '+run' not in out or 'versionCode = ' + str(new_code) not in out:
        print('::error file=app/build.gradle.kts::stamp_version selfcheck failed')
        return sys.exit(1)
    gradle.write_text(out, encoding='utf-8')
    print('stamp_version: versionName=' + base_name + '+run' + str(run_n) + ' versionCode=' + str(new_code))
    return True


def register_tool() -> bool:
    cs_path = ROOT / 'app' / 'src' / 'main' / 'java' / 'me' / 'rerere' / 'rikkahub' / 'service' / 'ChatService.kt'
    text = cs_path.read_text(encoding='utf-8')
    if MARK in text:
        print('register_tool: ChatService already has ' + MARK + ', skipping')
        return False

    lines = text.split(NL)
    anchor = 'addAll(localTools.getTools(assistant.localTools, invocationCtx))'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == anchor]
    if len(hits) != 2:
        print('::error file=ChatService.kt::register_tool anchor count=' + str(len(hits)) + ' (expected 2: buildToolsForRerun + handleMessageComplete)')
        for i in hits:
            i0 = max(0, i - 3)
            print('  [context around hit L' + str(i + 1) + ']:')
            for j in range(i0, min(len(lines), i + 4)):
                mark = ' <-- anchor' if j == i else ''
                print('    L' + str(j + 1) + ': ' + lines[j] + mark)
        return sys.exit(1)

    # v2: 结构校验改为 warn-only — batch130(酒馆模式)可能改变了工具装配行的下一行内容
    for i in hits:
        window = lines[max(0, i - 15):i]
        found_ctx = False
        for w in window:
            if 'val invocationCtx =' in w:
                found_ctx = True
        if not found_ctx:
            print('::warning::batch132 hit L' + str(i + 1) + ' lacks invocationCtx above (warn-only, batch130 may have moved it)')
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ''
        if nxt != 'addAll(pluginToolProvider.getTools())':
            print('::warning::batch132 hit L' + str(i + 1) + ' next line changed (batch130 effect): ' + nxt[:80])

    for i in reversed(hits):
        indent = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
        comment_line = indent + '// ' + MARK + ': 常驻版本查询工具(零副作用,不挂开关)'
        add_line = indent + 'add(me.rerere.rikkahub.data.ai.tools.local.appVersionTool(context))'
        lines.insert(i + 1, comment_line)
        lines.insert(i + 2, add_line)
    out = concat_lines(lines)

    if out.count('appVersionTool(context)') != 2:
        print('::error file=ChatService.kt::register_tool selfcheck: appVersionTool refs=' + str(out.count('appVersionTool(context)')) + ' expected 2')
        return sys.exit(1)
    if out.count(MARK) != 2:
        print('::error file=ChatService.kt::register_tool selfcheck: marker count=' + str(out.count(MARK)) + ' expected 2')
        return sys.exit(1)
    def count_parens(s):
        return s.count('(') - s.count(')'), s.count('{') - s.count('}')
    before = count_parens(text)
    after = count_parens(out)
    if before != after:
        print('::error file=ChatService.kt::register_tool bracket balance changed: before=' + str(before) + ' after=' + str(after))
        return sys.exit(1)
    cs_path.write_text(out, encoding='utf-8')
    print('register_tool: ChatService.kt OK')
    return True


def main() -> int:
    changed_stamp = stamp_version()
    changed_reg = register_tool()
    if changed_stamp or changed_reg:
        print('batch132: APPLIED (stamp=' + str(changed_stamp) + ' register=' + str(changed_reg) + ')')
    else:
        print('batch132: already applied or skipped')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
