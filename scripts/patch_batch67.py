#!/usr/bin/env python3
'''batch67: 思考链折叠态全部收起（collapsedVisibleCount 2→0）

老板需求（截图圈注）：「2步太多了 我要这样全部折叠」——
折叠态不再露尾部 2 步，全部收成一行控制条（图标 + "再显示 N 步"），
点击展开全部步骤。

现状（ChainOfThought.kt 实读 0-13500）：
- collapsedVisibleCount: Int = 2 —— 折叠时保留尾部 2 步可见
- visibleSteps = expanded ? steps : steps.takeLast(collapsedVisibleCount)
- canCollapse = steps.size > collapsedVisibleCount
- 控制条文字 = chain_of_thought_show_more_steps（steps.size - collapsedVisibleCount）

调用方核实（ChatMessage.kt 15000-21500 实读）：
- ChatMessage 里 ChainOfThought(...) 未显式传 collapsedVisibleCount
  （只传 modifier/steps/collapsedAdaptiveWidth/forceExpanded/cardColors）
- → 改组件默认值即可全局生效，零调用方改动

改后行为：
- steps.size=1: 折叠态="再显示 1 步"单行条，点击展开
- steps.size=12: 折叠态="再显示 12 步"单行条（不再露 2 步）
- 展开态不变；forceExpanded（待审批强制展开）逻辑不变

五查：
1. import 清单：无新增符号（纯默认值改动）
2. 同文件冲突：ChainOfThought.kt 无其他在链脚本碰（batch66 碰 ChatMessage.kt
   是另一文件）；本批单文件单行
3. 作用域：函数默认参数值，改动点唯一（签名行）
4. 括号配对：无括号改动
5. 函数签名：默认值变化不破坏任何调用方（调用方均未传该参数——已核实）

Python 三查：无引号字面量 / 无未定义引用 / 无 f-string/walrus/join
'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
OLD = '    collapsedVisibleCount: Int = 2,'
NEW = '    collapsedVisibleCount: Int = 0, // rhCollapseAll: 折叠态全部收起（老板需求）'


def fail(path, msg):
    print('::error file=' + path + '::batch67 ' + str(msg)[:1400])
    raise SystemExit(1)


CF = 'app/src/main/java/me/rerere/rikkahub/ui/components/ui/ChainOfThought.kt'
t = (ROOT / CF).read_text(encoding='utf-8')
if 'rhCollapseAll' in t:
    print('batch67: already applied')
else:
    if t.count(OLD) != 1:
        print('batch67: dump collapsedVisibleCount lines:')
        for ln in t.split(NL):
            if 'collapsedVisibleCount' in ln:
                print('  >> ' + ln.strip()[:140])
        fail(CF, 'collapsedVisibleCount default line count=' + str(t.count(OLD)))
    # 调用方核实：仓库内不应有显式传参覆盖（防改默认值无效）
    CALLER = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessage.kt'
    c = (ROOT / CALLER).read_text(encoding='utf-8')
    if 'collapsedVisibleCount' in c:
        fail(CALLER, 'caller explicitly passes collapsedVisibleCount - default change would not take effect')
    lines = t.split(NL)
    for i, ln in enumerate(lines):
        if ln == OLD:
            lines[i] = NEW
            break
    out = NL.join(lines)
    if 'collapsedVisibleCount: Int = 0,' not in out:
        fail(CF, 'replacement missing after apply')
    (ROOT / CF).write_text(out, encoding='utf-8')
    print('batch67: collapsedVisibleCount 2 -> 0 (collapse-all by default)')

print('batch67: OK')
