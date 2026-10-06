#!/usr/bin/env python3
'''batch67 v2: keep thinking steps visible (revert collapse-all)

User feedback: "思考不显示了 应该要加入步骤中 不然有思考的地方还是空的".
batch67 v1 collapsed ALL steps (collapsedVisibleCount 2->0). v2 reverts to 2
so the last 2 steps (usually the thinking/reasoning step) remain visible.

Five checks:
1. import: none
2. conflict: ChainOfThought.kt touched by batch67 only
3. scope: function default param
4. brackets: single line edit
5. signature: default value change only
'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
OLD = '    collapsedVisibleCount: Int = 0, // rhCollapseAll: 折叠态全部收起（老板需求）'
NEW = '    collapsedVisibleCount: Int = 2, // rhCollapseAll: 恢复显示最后2步（含思考）'


def fail(path, msg):
    print('::error file=' + path + '::batch67v2 ' + str(msg)[:1400])
    raise SystemExit(1)


CF = 'app/src/main/java/me/rerere/rikkahub/ui/components/ui/ChainOfThought.kt'
t = (ROOT / CF).read_text(encoding='utf-8')
if 'rhCollapseAll: 恢复显示最后2步' in t:
    print('batch67v2: already applied')
else:
    if OLD not in t:
        fail(CF, 'batch67 v1 marker not found (expected collapsedVisibleCount = 0)')
    t = t.replace(OLD, NEW, 1)
    (ROOT / CF).write_text(t, encoding='utf-8')
    print('batch67v2: collapsedVisibleCount 0 -> 2 (thinking steps visible)')

print('batch67v2: OK')
