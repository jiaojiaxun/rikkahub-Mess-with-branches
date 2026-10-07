#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""batch132: 版本号自动盖戳 + get_app_version 工具注册(fail-loud,幂等)。

【功能 A — 版本盖戳】app/build.gradle.kts
- versionName: "2.4.14"           -> "2.4.14+run321"
- versionCode: 181                -> 18100321  (= 181×100000 + run,单调递增)
- 环境变量 GITHUB_RUN_NUMBER 缺失/非数字时跳过(本地构建保持原值)。
- 已盖戳则跳过(幂等:行内含 +run 即认定已完成)。
- 锚点: 以 'versionCode =' 与 'versionName =' 开头的行,精确计数各 1,否则 fail。

【功能 B — 工具注册】app/src/main/java/me/rerere/rikkahub/service/ChatService.kt
- 在 tools buildList 的 localTools.getTools(assistant.localTools, invocationCtx) 之后
  插入 add(me.rerere...appVersionTool(context)),使主路径常驻拥有版本工具。
- 酒馆模式在该行上方提前 return@buildList,因此酒馆不含它,保持"只留 4 样"的纯净。
- marker: rhAppVersion ;锚点计数必须恰好 1,否则 dump 现场并 exit(1)。

【五查+Python三查全覆盖】
1.import清单: 工具调用用全限定名(免 import);versionName 自平衡(仅改引号内)。
2.同文件冲突: build.gradle 同文件编辑=batch131 删 dep 与本脚本改 version,锚点不相交;
  ChatService 同文件=batch70/95/101/130 均不碰 localTools 调用行,本脚本自身唯一标记。
3.作用域: ChatService 插入行与 addAll(localTools) 同级(buildList lambda顶层),
  context 已在 batch130 tavern 块内验证可达。
4.括号配平: 插入行括号自平衡(1开1闭,注释不含括号);全文件前后括号差值检验。
5.函数签名: 不改任何签名。

Python三查: ①引号=chr构造,字符串只定义一次(常量 Q/SQ/NL); ②NL 手写 concat,
禁 join/f-string/walrus; ③helper 先定义后用,失败显式 exit(1)+::error。
"""
import os, re, sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)  # "
SQ = chr(39)  # '
MARK = 'rhAppVersion'

# ===== 【功能 A: 版本盖戳到 app/build.gradle.kts】 =====
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
    """盖版本戳;返回 True=已变更,False=已盖戳或跳过(环境变量缺失)。"""
    gradle = ROOT / 'app' / 'build.gradle.kts'
    run_str = os.environ.get('GITHUB_RUN_NUMBER', '').strip()
    if not run_str or not run_str.isdigit():
        # 本地构建:GITHUB_RUN_NUMBER 不存在或非数字 → 保持原版本号,不报错
        print('stamp_version: GITHUB_RUN_NUMBER absent, local build keeps original version')
        return False

    run_n = int(run_str)
    text = gradle.read_text(encoding='utf-8')
    # 幂等:已盖戳则跳过
    if '+run' in text and re.search(r'versionName\s*=\s*' + Q + r'[^' + Q + r']*\+run\d+' + Q, text):
        print('stamp_version: already stamped (found +runN in versionName), skipping')
        return False

    lines = text.split(NL)
    # 精确定位(前缀匹配): versionCode = <digits>  与  versionName = "<base>"
    code_hits = [i for i, ln in enumerate(lines) if ln.lstrip().startswith('versionCode =')]
    name_hits = [i for i, ln in enumerate(lines) if ln.lstrip().startswith('versionName =')]
    if len(code_hits) != 1 or len(name_hits) != 1:
        msg = 'stamp_version anchor mismatch: code=' + str(len(code_hits)) + ' name=' + str(len(name_hits))
        print('::error file=app/build.gradle.kts::' + msg)
        # dump 前后 3 行给出现场
        for idx_list, label in [(code_hits, 'versionCode'), (name_hits, 'versionName')]:
            if idx_list:
                i0 = max(0, idx_list[0]-2)
                print('  [' + label + ' context]:')
                for j in range(i0, min(len(lines), idx_list[0]+3)):
                    print('    L' + str(j+1) + ': ' + lines[j])
        return sys.exit(1)

    ci = code_hits[0]
    ni = name_hits[0]
    # versionCode: 提取原基线(首个数字),新值 = base×100000 + run
    m_code = re.search(r'versionCode\s*=\s*(\d+)', lines[ci])
    if not m_code:
        print('::error file=app/build.gradle.kts::stamp_version: versionCode line has no digits')
        return sys.exit(1)
    base_code = int(m_code.group(1))
    new_code = base_code * 100000 + run_n
    code_ind = lines[ci][:len(lines[ci]) - len(lines[ci].lstrip())]
    lines[ci] = code_ind + 'versionCode = ' + str(new_code) + '  // ' + MARK + ': ' + str(base_code) + '×100k+run' + str(run_n)

    # versionName: 提取原基线(去掉既有 +run 后缀),附加新 +runN
    m_name = re.search(r'versionName\s*=\s*' + Q + r'([^' + Q + r']*)' + Q, lines[ni])
    if not m_name:
        print('::error file=app/build.gradle.kts::stamp_version: versionName line malformed')
        return sys.exit(1)
    base_name = m_name.group(1)
    # 去除可能的旧 +run 后缀(支持重新盖戳 re-run)
    base_name = re.sub(r'\+run\d+$', '', base_name)
    name_ind = lines[ni][:len(lines[ni]) - len(lines[ni].lstrip())]
    lines[ni] = name_ind + 'versionName = ' + Q + base_name + '+run' + str(run_n) + Q + '  // ' + MARK

    out = concat_lines(lines)
    # 自检:盖戳后必须包含 +run
    if '+run' not in out or 'versionCode = ' + str(new_code) not in out:
        print('::error file=app/build.gradle.kts::stamp_version selfcheck failed')
        return sys.exit(1)
    gradle.write_text(out, encoding='utf-8')
    print('stamp_version: versionName=' + base_name + '+run' + str(run_n) + ' versionCode=' + str(new_code))
    return True

# ===== 【功能 B: 工具注册到 ChatService.kt】 =====
def register_tool() -> bool:
    """注册 appVersionTool 到 ChatService 主路径;返回 True=已变更,False=已注册。"""
    cs_path = ROOT / 'app' / 'src' / 'main' / 'java' / 'me' / 'rerere' / 'rikkahub' / 'service' / 'ChatService.kt'
    text = cs_path.read_text(encoding='utf-8')
    if MARK in text:
        print('register_tool: ChatService already has ' + MARK + ', skipping')
        return False

    lines = text.split(NL)
    # 锚点: 在 tools buildList 内,localTools.getTools(assistant.localTools, invocationCtx) 调用行
    # (酒馆分支上方已 return@buildList,此行只在主路径被执行)
    anchor = 'addAll(localTools.getTools(assistant.localTools, invocationCtx))'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == anchor]
    # 收窄: 命中行上方 12 行内必须含 invocationCtx 定义,防止误中其他工具组装路径
    scoped = []
    for i in hits:
        window = lines[max(0, i - 12):i]
        found = False
        for w in window:
            if 'val invocationCtx =' in w:
                found = True
        if found:
            scoped.append(i)
    if len(scoped) != 1:
        print('::error file=ChatService.kt::register_tool anchor count=' + str(len(scoped)) + ' (expected 1, raw=' + str(len(hits)) + ')')
        if scoped:
            i0 = max(0, scoped[0]-3)
            print('  [context around first hit]:')
            for j in range(i0, min(len(lines), scoped[0]+4)):
                mark = ' <-- anchor' if j == scoped[0] else ''
                print('    L' + str(j+1) + ': ' + lines[j] + mark)
        return sys.exit(1)

    idx = scoped[0]
    indent = lines[idx][:len(lines[idx]) - len(lines[idx].lstrip())]
    # 插入两行: ①注释行 ②add(...) 调用
    comment_line = indent + '// ' + MARK + ': 常驻版本查询工具(零副作用;酒馆模式在其之前 return,不包含)'
    add_line = indent + 'add(me.rerere.rikkahub.data.ai.tools.local.appVersionTool(context))'
    lines.insert(idx + 1, comment_line)
    lines.insert(idx + 2, add_line)
    out = concat_lines(lines)

    # 自检: marker + 调用串必须出现
    if MARK not in out or 'appVersionTool(context)' not in out:
        print('::error file=ChatService.kt::register_tool selfcheck failed (marker or call missing)')
        return sys.exit(1)
    # 括号配平检验(全文件):插入行内括号平衡,全文差值不变
    def count_parens(s: str) -> tuple:
        # 简化计数(忽略字符串内):只检验插入前后总数差值=0
        return s.count('(') - s.count(')'), s.count('{') - s.count('}')
    before = count_parens(text)
    after = count_parens(out)
    if before != after:
        print('::error file=ChatService.kt::register_tool bracket balance changed: before=' + str(before) + ' after=' + str(after))
        return sys.exit(1)
    cs_path.write_text(out, encoding='utf-8')
    print('register_tool: ChatService.kt OK')
    return True

# ===== 主流程 =====
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