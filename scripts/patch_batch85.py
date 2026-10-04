#!/usr/bin/env python3
'''batch85: Yuihub 移植 B 项——底部动作行改等分四宫格

参考：xiaoyuili/Yuihub v2.5.8 提交 12b2776（侧滑页四宫格动作条）
目标：jiaojiaxun/rikkahub-Mess-with-branches @ fix/batch1

【前置对抗性检查结论（本轮实测，必须记录）】
1. Yuihub 原脚本（写于 batch74v4 之前）的锚点是裸 Row( 行；但 batch74v4 已在
   底部 Row 前插入 Surface(shape=RoundedCornerShape(20.dp), color=surfaceContainerLow) { ... }
   包装 → 若按原锚点替换，会残留 Surface(){ } 空壳 → 语法错。
   本脚本改为锚「batch74v4 之后」的形态：先找 RoundedCornerShape(20.dp) 标记行，
   向上找最近的 Surface( 行，再配平扫描其闭合 }，整块替换。
2. 四宫格四项（图像生成/收藏/统计/设置）语义与 fork 现状的映射：
   - 图像生成：fork 原藏在 Box{DropdownMenu} 第 2 项 → 提升为顶层格
   - 统计：fork 原藏在 Box{DropdownMenu} 第 1 项 → 提升为顶层格
   - 收藏/设置：fork 原本就是独立 DrawerAction → 原位语义
   - fork 原有的「助手」格（→ Screen.Assistant）：本批删除。
     ✅ 已实读确认无功能回归：SettingPage 的「通用设置」CardGroup 里有
        item(onClick = { navController.navigate(Screen.Assistant) }) 同级入口。
3. Screen.Stats 在 fork 是 data object（无参）→ 必须写 Screen.Stats，不能带 chatId
   （Yuihub 原实现写 Screen.Stats(chatId=...) 会编译挂——勘误文档 §1 必挂项）。
4. R.string.stats_page_title 在 fork 存在（ChatDrawer 自己就在用）→ 不硬编码。

【五查】
1. import：需 ensure `androidx.compose.foundation.background`（ChatDrawer 现无此 import）；
   其余符号（border/clickable/clip/Surface/Text/Icon/ImageVector/Row/Column/
   Arrangement/Alignment/size/padding/fillMaxWidth/TextOverflow/HugeIcons/
   Image02/InLove/ChartColumn/Settings03/Screen/stringResource）均已实读确认存在。
   ← 行级 strip 全等检查 + 插入后回读断言（铁律 20）
2. 同文件冲突：ChatDrawer.kt 被 batch74v4 碰过（底部 Surface 包装 + 顶部 border）
   → 本批锚点全部取「链后形态」，与 batch74v4 注入行精确对齐，不重叠别的脚本
3. 作用域：@Composable ChatDrawerContent 函数体内；Modifier.weight(1f) 在 Row 内（RowScope）
4. 括号配对：结构化替换用【配平扫描】（起点 Surface( 行深度归零处为终点），
   替换后断言全文件括号配平与替换前一致（铁律 19c + 21）
5. 函数签名：不改任何现有签名；新增 2 个 private @Composable 函数（零破坏）

【Python 三查】
1. 引号一律 chr(34)/chr(39) 构造；2. 无未定义引用；3. 无 f-string/walrus/join；
4. ind() = len(ln.lstrip())（铁律 26：函数体正确性）
'''
from pathlib import Path
ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
M = 'rhDrawerGrid'
MARK74 = 'RoundedCornerShape(20.dp)'   # batch74v4 注入的 Surface shape 标记


def fail(p, m):
    print('::error file=' + p + '::batch85 ' + str(m)[:1400])
    raise SystemExit(1)


def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]


def balance(text):
    return (text.count('(') - text.count(')')) + (text.count('{') - text.count('}'))


def find_block_end(lines, start):
    '''从 start 行（应含开括号）扫描，返回深度首次归零的行号（-1 表示不配平）。'''
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
    print('batch85: already applied')
else:
    lines = t.split(NL)
    applied = []
    bal_before = balance(t)

    # ---------- 1. ensure import background（行级 strip 全等，铁律 20）----------
    BG_IMPORT = 'import androidx.compose.foundation.background'
    if not any(ln.strip() == BG_IMPORT for ln in lines):
        hits = [i for i, ln in enumerate(lines) if ln.strip() == 'import androidx.compose.foundation.clickable']
        if len(hits) != 1:
            fail(CD, 'clickable import anchor count=' + str(len(hits)))
        lines.insert(hits[0], BG_IMPORT)
        if not any(ln.strip() == BG_IMPORT for ln in lines):
            fail(CD, 'background import insert self-check failed')  # 回读断言（铁律 20）
        applied.append('import-background')
    else:
        applied.append('import-background-exists')

    # ---------- 2. 定位 batch74v4 的 Surface 包装 ----------
    mark_hits = [i for i, ln in enumerate(lines) if MARK74 in ln and 'rhDrawerPolish' in ln]
    if len(mark_hits) != 1:
        print('batch85: dump rhDrawerPolish markers:')
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
        print('batch85: dump above marker:')
        for i in range(max(0, mi - 8), mi + 1):
            print('  >> ' + str(i) + ' [' + str(len(ind(lines[i]))) + '] ' + lines[i].strip()[:120])
        fail(CD, 'Surface( not found above batch74v4 marker')
    surf_end = find_block_end(lines, surf_start)
    if surf_end < 0:
        fail(CD, 'batch74v4 Surface block unbalanced from line ' + str(surf_start))
    d = ind(lines[surf_start])
    print('batch85: replacing lines ' + str(surf_start) + '..' + str(surf_end) + ' (indent=' + str(len(d)) + ')')

    # 替换前必须确认区间内含四宫格的四个来源符号（防锚点漂移误删）
    region = NL.join(lines[surf_start:surf_end + 1])
    for need_sym in ['HugeIcons.Image02', 'HugeIcons.ChartColumn', 'HugeIcons.InLove',
                     'HugeIcons.Settings03', 'Screen.ImageGen', 'Screen.Stats',
                     'Screen.Favorite', 'Screen.Setting']:
        if need_sym not in region:
            print('batch85: dump region for missing symbol ' + need_sym + ':')
            for i in range(surf_start, surf_end + 1):
                print('  >> ' + str(i) + ': ' + lines[i].strip()[:120])
            fail(CD, 'sanity: region missing ' + need_sym)

    # ---------- 3. 生成四宫格调用块 ----------
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

    # ---------- 4. 插入两个新 @Composable 函数 ----------
    fn_hits = [i for i, ln in enumerate(lines) if ln.strip() == 'private fun DrawerAction(']
    if len(fn_hits) != 1:
        print('batch85: dump DrawerAction candidates:')
        for i, ln in enumerate(lines):
            if 'fun DrawerAction' in ln:
                print('  >> ' + str(i) + ': ' + ln.strip()[:150])
        fail(CD, 'private fun DrawerAction( anchor count=' + str(len(fn_hits)))
    fi = fn_hits[0]
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
        '// rhDrawerGridStack: 图标在上、小字在下，靠小字自解释（不再依赖长按 Tooltip）',
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
        lines.insert(fi + j, b)
    applied.append('two-functions')

    # ---------- 5. 自检 ----------
    t2 = NL.join(lines)
    for need in [M, 'private fun DrawerActionBar(', 'private fun DrawerActionStack(',
                 'onStats = { navController.navigate(Screen.Stats) }',
                 'Screen.Stats(']:  # 最后一个必须"不存在"
        if need == 'Screen.Stats(':
            if need in t2:
                fail(CD, 'Screen.Stats with args must NOT exist (data object)')
            continue
        if need not in t2:
            fail(CD, 'selfcheck missing: ' + need)
    if not any(ln.strip() == BG_IMPORT for ln in lines):
        fail(CD, 'background import missing in final')
    if balance(t2) != bal_before:
        fail(CD, 'bracket balance changed: before=' + str(bal_before) + ' after=' + str(balance(t2)))
    (ROOT / CD).write_text(t2, encoding='utf-8')
    print('batch85: OK (' + ', '.join(applied) + ')')

print('batch85: done')