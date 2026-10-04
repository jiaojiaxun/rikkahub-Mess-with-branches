#!/usr/bin/env python3
'''batch66: UI-1 批 b——ChatMessageQuoteBlock 组件（ChatMessage.kt 文件尾追加）

五查（基于 ChatMessage.kt 实读 0-3000 imports 段 + 3000-7500 签名段）：
1. import 清单：组件用 clickable（缺，脚本自动补）；background/形状/布局/
   Material3/TextOverflow/dp/Alignment/Modifier 均在现有 imports（逐项核过）
2. 同文件冲突：ChatMessage.kt 无在链脚本碰（57_1 已删）
3. 作用域：顶层 fun，文件尾追加，不引用外部状态
4. 括号配对：追加块整体写入（自身平衡）
5. 函数签名：全新组件，本批无调用方（批 c 才挂载）→ 零签名风险

Python 三查：无引号问题；无未定义引用；无 f-string/walrus/join
'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhQuoteBlock'


def fail(path, msg):
    print('::error file=' + path + '::batch66 ' + str(msg)[:1400])
    raise SystemExit(1)


CM = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessage.kt'
c = (ROOT / CM).read_text(encoding='utf-8')
if MARK in c:
    print('batch66: already applied')
else:
    lines = c.split(NL)
    changed = []

    # 1. clickable import（检查后插入）
    if 'import androidx.compose.foundation.clickable' not in c:
        idx = -1
        for i, ln in enumerate(lines):
            if ln.strip() == 'import androidx.compose.foundation.background':
                idx = i
                break
        if idx < 0:
            fail(CM, 'foundation.background import anchor not found')
        lines = lines[:idx] + ['import androidx.compose.foundation.clickable'] + lines[idx:]
        changed.append('clickable-import')

    # 2. 组件追加到文件尾
    COMPONENT = (
        NL + NL +
        '/** ' + MARK + ': 引用块——消息上方的引用预览小卡（UI-1 批 b，纯组件）。' + NL +
        ' * 数据由调用方解析后传入；点击回调由调用方处理（跳转/高亮）。 */' + NL +
        '@Composable' + NL +
        'fun ChatMessageQuoteBlock(' + NL +
        '    senderName: String,' + NL +
        '    previewText: String,' + NL +
        '    onClick: () -> Unit,' + NL +
        ') {' + NL +
        '    Surface(' + NL +
        '        shape = RoundedCornerShape(8.dp),' + NL +
        '        color = MaterialTheme.colorScheme.surfaceContainerHigh,' + NL +
        '        modifier = Modifier' + NL +
        '            .fillMaxWidth(0.92f)' + NL +
        '            .clickable(onClick = onClick),' + NL +
        '    ) {' + NL +
        '        Row(' + NL +
        '            verticalAlignment = Alignment.CenterVertically,' + NL +
        '            horizontalArrangement = Arrangement.spacedBy(6.dp),' + NL +
        '            modifier = Modifier.padding(start = 10.dp, end = 10.dp, top = 6.dp, bottom = 6.dp),' + NL +
        '        ) {' + NL +
        '            Box(' + NL +
        '                modifier = Modifier' + NL +
        '                    .size(width = 3.dp, height = 18.dp)' + NL +
        '                    .background(MaterialTheme.colorScheme.primary),' + NL +
        '            )' + NL +
        '            Column {' + NL +
        '                Text(' + NL +
        '                    text = senderName,' + NL +
        '                    style = MaterialTheme.typography.labelSmall,' + NL +
        '                    color = MaterialTheme.colorScheme.primary,' + NL +
        '                )' + NL +
        '                Text(' + NL +
        '                    text = previewText,' + NL +
        '                    style = MaterialTheme.typography.bodySmall,' + NL +
        '                    color = MaterialTheme.colorScheme.onSurfaceVariant,' + NL +
        '                    maxLines = 2,' + NL +
        '                    overflow = TextOverflow.Ellipsis,' + NL +
        '                )' + NL +
        '            }' + NL +
        '        }' + NL +
        '    }' + NL +
        '}'
    )
    body = NL.join(lines).rstrip() + COMPONENT
    changed.append('component')

    # 3. 自检
    if MARK not in body:
        fail(CM, 'component marker missing')
    if 'fun ChatMessageQuoteBlock(' not in body:
        fail(CM, 'component function missing')
    if 'import androidx.compose.foundation.clickable' not in body:
        fail(CM, 'clickable import missing')
    (ROOT / CM).write_text(body, encoding='utf-8')
    print('batch66: OK (' + ', '.join(changed) + ')')

print('batch66: done')
