#!/usr/bin/env python3
'''batch85v2: Yuihub 四宫格动作条 —— 修 #232 注解重复

#232 验尸（根因唯一，证据充分）：
  ChatDrawer.kt:863  This annotation is not repeatable.
  → 919/925/928/930 连带（@Composable 上下文判定失败）

根因：fn_block 第一行是 '@Composable'，而锚点 'private fun DrawerAction(' 的
上一行本就是 '@Composable' → 插入后两个 @Composable 连写 → 注解不可重复。

v2 修复（新铁律 28）：
锚点改为【两行组合】'@Composable' + 'private fun DrawerAction('，
在 @Composable 行【之前】插入整个 fn_block（含其首行 @Composable）。
这样结果形态为：
    @Composable            ← 新 DrawerActionBar 的
    private fun DrawerActionBar(...) { ... }
    // rhDrawerGridStack
    @Composable            ← 新 DrawerActionStack 的
    private fun DrawerActionStack(...) { ... }
    @Composable            ← 原有的（未动）
    private fun DrawerAction(

其余逻辑与 v1 完全一致（配平扫描替换 + 8 符号 sanity + import 回读断言）。

【五查（改点专项）】
1. import：同 v1（background ensure + 回读断言）
2. 同文件冲突：锚点改两行组合后唯一性更强，仍与 batch74v4 注入行对齐
3. 作用域：新函数体在文件顶层（private @Composable），插入位置正确
4. 括号配对：fn_block 自平衡（Row{ } / Column{ }）；替换仍用配平扫描 + 前后配平断言
5. 函数签名：不改现有签名；新增 2 个 private @Composable

Python 三查：引号变量构造 / 无未定义 / 无 f-string / ind() = len(ln.lstrip())
'''
from pathlib import Path
ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
M = 'rhDrawerGrid'
MARK74 = 'RoundedCornerShape(20.dp)'


def fail(p, m):
    print('::error file=' + p + '::batch85v2 ' + str(m)[:1400])
    raise SystemExit(1)


def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]


def balance(text):
    return (text.count('(') - text.count(')')) + (text.count('{') - text.count('}'))


def find_block_end(lines, start):
    depth = 0
    seen = False
    for i in range(start, len(lines)):
        for ch in lines[i]:
            if ch in '({':
                depth += 1
                seen = True
            elif ch in ')}':
                depth -= 1
        if seen and depth <= 0:
            return i
    return -1


CD = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatDrawer.kt'
t = (ROOT / CD).read_text(encoding='utf-8')

if M in t:
    print('batch85v2: already applied')
else:
    lines = t.split(NL)
    applied = []
    bal_before = balance(t)

    # ---------- 1. ensure import background ----------
    BG_IMPORT = 'import androidx.compose.foundation.background'
    if not any(ln.strip() == BG_IMPORT for ln in lines):
        hits = [i for i, ln in enumerate(lines) if ln.strip() == 'import androidx.compose.foundation.clickable']
        if len(hits) != 1:
            fail(CD, 'clickable import anchor count=' + str(len(hits)))
        lines.insert(hits[0], BG_IMPORT)
        if not any(ln.strip() == BG_IMPORT for ln in lines):
            fail(CD, 'background import insert self-check failed')
        applied.append('import-background')
    else:
        applied.append('import-background-exists')

    # ---------- 2. 定位并替换 batch74v4 的 Surface 包装 ----------
    mark_hits = [i for i, ln in enumerate(lines) if MARK74 in ln and 'rhDrawerPolish' in ln]
    if len(mark_hits) != 1:
        print('batch85v2: dump rhDrawerPolish markers:')
        for i, ln in enumerate(lines):
            if 'rhDrawerPolish' in ln:
                print('  >> ' + str(i) + ': ' + ln.strip()[:150])
        fail(CD, 'batch74v4 Surface marker count=' + str(len(mark_hits)))
    mi = mark_hits[0]
    surf_start = -1
    for i in range(mi, max(mi - 8, -1), -1):
        if lines[i].strip() == 'Surface(':
            surf_start = i
            break
    if surf_start < 0:
        print('batch85v2: dump above marker:')
        for i in range(max(0, mi - 8), mi + 1):
            print('  >> ' + str(i) + ' [' + str(len(ind(lines[i]))) + '] ' + lines[i].strip()[:120])
        fail(CD, 'Surface( not found above batch74v4 marker')
    surf_end = find_block_end(lines, surf_start)
    if surf_end < 0:
        fail(CD, 'batch74v4 Surface block unbalanced from line ' + str(surf_start))
    d = ind(lines[surf_start])
    print('batch85v2: replacing lines ' + str(surf_start) + '..' + str(surf_end))

    region = NL.join(lines[surf_start:surf_end + 1])
    for need_sym in ['HugeIcons.Image02', 'HugeIcons.ChartColumn', 'HugeIcons.InLove',
                     'HugeIcons.Settings03', 'Screen.ImageGen', 'Screen.Stats',
                     'Screen.Favorite', 'Screen.Setting']:
        if need_sym not in region:
            print('batch85v2: dump region for missing symbol ' + need_sym + ':')
            for i in range(surf_start, surf_end + 1):
                print('  >> ' + str(i) + ': ' + lines[i].strip()[:120])
            fail(CD, 'sanity: region missing ' + need_sym)

    call_block = [
        d + '// ' + M + ' (batch85): 等分四宫格动作条（对齐 Yuihub v2.5.8）',
        d + 'DrawerActionBar(',
        d + '    imageGenerationLabel = stringResource(R.string.chat_page_menu_image_generation),',
        d + '    favoritesLabel = stringResource(R.string.favorite_page_title),',
        d + '    statsLabel = stringResource(R.string.stats_page_title),',
        d + '    settingsLabel = stringResource(R.string.settings),',
        d + '    onImageGeneration = { navController.navigate(Screen.ImageGen) },',
        d + '    onFavorites = { navController.navigate(Screen.Favorite) },',
        d + '    onStats = { navController.navigate(Screen.Stats) },',
        d + '    onSettings = { navController.navigate(Screen.Setting) },',
        d + '    modifier = Modifier.fillMaxWidth(),',
        d + ')',
    ]
    lines[surf_start:surf_end + 1] = call_block
    applied.append('grid-call')

    # ---------- 3. 插入两个新函数（锚：@Composable + private fun DrawerAction( 两行组合）----------
    combo = []
    for i in range(len(lines) - 1):
        if lines[i].strip() == '@Composable' and lines[i + 1].strip() == 'private fun DrawerAction(':
            combo.append(i)
    if len(combo) != 1:
        print('batch85v2: dump @Composable+DrawerAction combos:')
        for i in range(len(lines) - 1):
            if 'fun DrawerAction' in lines[i] or 'fun DrawerAction' in lines[i + 1]:
                print('  >> ' + str(i) + ': ' + lines[i].strip()[:80] + ' | ' + lines[i + 1].strip()[:80])
        fail(CD, 'Composable+DrawerAction combo count=' + str(len(combo)))
    ins = combo[0]   # 在 @Composable 行【之前】插入（铁律 28）
    fn_block = [
        '@Composable',
        'private fun DrawerActionBar(',
        '    imageGenerationLabel: String,',
        '    favoritesLabel: String,',
        '    statsLabel: String,',
        '    settingsLabel: String,',
        '    onImageGeneration: () -> Unit,',
        '    onFavorites: () -> Unit,',
        '    onStats: () -> Unit,',
        '    onSettings: () -> Unit,',
        '    modifier: Modifier = Modifier,',
        ') {',
        '    Row(',
        '        verticalAlignment = Alignment.CenterVertically,',
        '        horizontalArrangement = Arrangement.spacedBy(2.dp),',
        '        modifier = modifier',
        '            .fillMaxWidth()',
        '            .clip(MaterialTheme.shapes.large)',
        '            .background(MaterialTheme.colorScheme.surfaceContainerLow)',
        '            .border(1.dp, MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f), MaterialTheme.shapes.large)',
        '            .padding(horizontal = 4.dp, vertical = 5.dp),',
        '    ) {',
        '        DrawerActionStack(HugeIcons.Image02, imageGenerationLabel, onImageGeneration, Modifier.weight(1f))',
        '        DrawerActionStack(HugeIcons.InLove, favoritesLabel, onFavorites, Modifier.weight(1f))',
        '        DrawerActionStack(HugeIcons.ChartColumn, statsLabel, onStats, Modifier.weight(1f))',
        '        DrawerActionStack(HugeIcons.Settings03, settingsLabel, onSettings, Modifier.weight(1f))',
        '    }',
        '}',
        '',
        '@Composable',
        'private fun DrawerActionStack(',
        '    icon: ImageVector,',
        '    label: String,',
        '    onClick: () -> Unit,',
        '    modifier: Modifier = Modifier,',
        ') {',
        '    Column(',
        '        horizontalAlignment = Alignment.CenterHorizontally,',
        '        verticalArrangement = Arrangement.spacedBy(3.dp),',
        '        modifier = modifier',
        '            .clip(MaterialTheme.shapes.medium)',
        '            .clickable(onClick = onClick)',
        '            .padding(vertical = 6.dp),',
        '    ) {',
        '        Icon(icon, label, Modifier.size(17.dp))',
        '        Text(',
        '            text = label,',
        '            style = MaterialTheme.typography.labelSmall,',
        '            color = MaterialTheme.colorScheme.onSurfaceVariant,',
        '            maxLines = 1,',
        '            overflow = TextOverflow.Ellipsis,',
        '        )',
        '    }',
        '}',
        '',
    ]
    for j, b in enumerate(fn_block):
        lines.insert(ins + j, b)
    applied.append('two-functions')

    # ---------- 4. 自检 ----------
    t2 = NL.join(lines)
    for need in [M, 'private fun DrawerActionBar(', 'private fun DrawerActionStack(',
                 'onStats = { navController.navigate(Screen.Stats) }']:
        if need not in t2:
            fail(CD, 'selfcheck missing: ' + need)
    if 'Screen.Stats(' in t2:
        fail(CD, 'Screen.Stats with args must NOT exist (data object)')
    if not any(ln.strip() == BG_IMPORT for ln in lines):
        fail(CD, 'background import missing in final')
    # 关键断言（铁律 28）：不得出现连续两个 @Composable
    for i in range(len(lines) - 1):
        if lines[i].strip() == '@Composable' and lines[i + 1].strip() == '@Composable':
            print('batch85v2: dump consecutive @Composable at ' + str(i) + ':')
            for k in range(max(0, i - 2), min(len(lines), i + 4)):
                print('  >> ' + str(k) + ': ' + lines[k].strip()[:100])
            fail(CD, 'consecutive @Composable detected (annotation not repeatable)')
    if balance(t2) != bal_before:
        fail(CD, 'bracket balance changed: before=' + str(bal_before) + ' after=' + str(balance(t2)))
    (ROOT / CD).write_text(t2, encoding='utf-8')
    print('batch85v2: OK (' + ', '.join(applied) + ')')

print('batch85v2: done')