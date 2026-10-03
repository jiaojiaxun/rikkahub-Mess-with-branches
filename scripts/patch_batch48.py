#!/usr/bin/env python3
'''batch48: 侧边栏复刻用户目标图（别人二改的效果）。

目标形态（用户 2026-10-03 两张截图拍板）：
- 顶部：液态玻璃助手卡——渐变圆环大头像 + 助手名 + 问候行 + 右侧 ⇆ 切换助手
  （切换助手放顶部；点卡片/⇆ 弹助手选择 sheet；点头像进助手详情；
   点问候行改昵称——保留原昵称编辑功能）
- 会话/文件分段 tabs（白色胶囊选中态）+ 右侧搜索/历史悬浮小圆钮（保留原入口）
- 底部：白色大圆角卡 4 列图文快捷（图像生成/收藏/统计/设置），
  每项图标带浅色圆底 + 边缘高亮 + Tooltip 悬浮框
- 液态玻璃质感 = 半透明 surface + primary 描边 + tonalElevation

锚点全部逐字节来自真实读取（2026-10-03 Range 分段读 ChatDrawer.kt）：
OLD1 菜单状态行 / OLD2 用户行+DrawerActions 调用 / OLD3 底部 AssistantPicker+圆钮 Row /
sheet 插入点（移动到助手 sheet 前）/ DrawerQuickEntry 插入点（FolderBar 前）。
新 API 均已验证：rememberAssistantState(settings){...} 与 state.currentAssistant/
setSelectAssistant（AssistantPicker.kt 原文）；AssistantItem(assistant,
isCurrentAssistant, onClick)（本文件移动 sheet 原文）；Screen.SettingFiles
（batch44 v2 经 #140 构建成功实证存在）。
铁律执行：所有 import 带 'import ' 前缀；零反斜杠（chr(10)+三引号）；
自检断言「新内容在场 + 旧块消失」。
'''
from pathlib import Path

ROOT = Path.cwd()
DRAWER = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatDrawer.kt'
STR_EN = 'app/src/main/res/values/strings.xml'
STR_ZH = 'app/src/main/res/values-zh/strings.xml'
NL = chr(10)
MARK = 'rhDrawer48'


def fail(path, msg):
    print('::error file=' + path + '::batch48 ' + str(msg)[:1500])
    raise SystemExit(1)


# ============================================================
# 0. strings（en + zh 双份，<resources> 开标签后插入，batch44 v2 验证过的稳点）
# ============================================================
def patch_strings(path, chats, files):
    p = ROOT / path
    s = p.read_text(encoding='utf-8')
    if 'rh_drawer_tab_chats' in s:
        print('batch48: strings already patched: ' + path)
        return
    i = s.find('<resources')
    if i < 0:
        fail(path, 'no <resources> tag')
    j = s.find('>', i)
    if j < 0:
        fail(path, '<resources> tag not closed')
    ins = (NL + '    <!-- rhDrawer48: drawer segmented tabs -->' + NL +
           '    <string name="rh_drawer_tab_chats">' + chats + '</string>' + NL +
           '    <string name="rh_drawer_tab_files">' + files + '</string>')
    s = s[:j + 1] + ins + s[j + 1:]
    p.write_text(s, encoding='utf-8')
    print('batch48: strings patched: ' + path)


patch_strings(STR_EN, 'Chats', 'Files')
patch_strings(STR_ZH, '会话', '文件')

# ============================================================
# 1. ChatDrawer.kt
# ============================================================
t = (ROOT / DRAWER).read_text(encoding='utf-8')
if MARK in t:
    print('batch48: drawer already patched')
    raise SystemExit(0)

# --- 1a. imports（全部带 import 前缀；锚点均为已验证的现有 import 行）---
IMPORT_JOBS = [
    ('import androidx.compose.foundation.combinedClickable' + NL,
     'import androidx.compose.foundation.BorderStroke' + NL +
     'import androidx.compose.foundation.background' + NL),
    ('import androidx.compose.foundation.shape.CircleShape' + NL,
     'import androidx.compose.foundation.shape.RoundedCornerShape' + NL),
    ('import androidx.compose.ui.graphics.vector.ImageVector' + NL,
     'import androidx.compose.ui.graphics.Brush' + NL),
    ('import androidx.compose.ui.text.style.TextOverflow' + NL,
     'import androidx.compose.ui.text.style.TextAlign' + NL),
    ('import me.rerere.rikkahub.ui.hooks.rememberIsPlayStoreVersion' + NL,
     'import me.rerere.rikkahub.ui.hooks.rememberAssistantState' + NL),
]
for anchor, ins in IMPORT_JOBS:
    if anchor not in t:
        fail(DRAWER, 'import anchor not found: ' + anchor.strip())
    if ins not in t:
        t = t.replace(anchor, anchor + ins, 1)

# --- 1b. OLD1: 菜单状态行 -> 助手卡状态 ---
OLD1 = (
    '    // Menu popup 状态' + NL +
    '    var showMenuPopup by remember { mutableStateOf(false) }' + NL
)
NEW1 = (
    '    // rhDrawer48: 顶部助手卡状态（切换助手放顶部；问候行点击改昵称）' + NL +
    '    val assistantState = rememberAssistantState(settings) { vm.updateSettings(it) }' + NL +
    '    var showAssistantSheet by remember { mutableStateOf(false) }' + NL
)
if OLD1 not in t:
    fail(DRAWER, 'OLD1 (menu popup state) not found')
t = t.replace(OLD1, NEW1, 1)

# --- 1c. OLD2: 用户头像行 + DrawerActions 调用 -> 液态玻璃助手卡 + 分段 tabs ---
OLD2 = '''            // 用户头像和昵称自定义区域
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 8.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                UIAvatar(
                    name = settings.displaySetting.userNickname.ifBlank { stringResource(R.string.user_default_name) },
                    value = settings.displaySetting.userAvatar,
                    onUpdate = { newAvatar ->
                        vm.updateSettings(
                            settings.copy(
                                displaySetting = settings.displaySetting.copy(
                                    userAvatar = newAvatar
                                )
                            )
                        )
                    },
                    modifier = Modifier.size(50.dp),
                )

                Column(
                    modifier = Modifier.weight(1f),
                    verticalArrangement = Arrangement.spacedBy(2.dp),
                ) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(4.dp),
                    ) {
                        Text(
                            text = settings.displaySetting.userNickname.ifBlank { stringResource(R.string.user_default_name) },
                            style = MaterialTheme.typography.titleMedium,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                            modifier = Modifier.clickable {
                                nicknameEditState.open(settings.displaySetting.userNickname)
                            }
                        )

                        Icon(
                            imageVector = HugeIcons.PencilEdit01,
                            contentDescription = stringResource(R.string.accessibility_edit_nickname),
                            modifier = Modifier
                                .onClick {
                                    nicknameEditState.open(settings.displaySetting.userNickname)
                                }
                                .size(LocalTextStyle.current.fontSize.toDp())
                        )
                    }
                    Greeting(
                        style = MaterialTheme.typography.labelMedium,
                    )
                }
            }

            DrawerActions(navController = navController)'''

NEW2 = '''            // rhDrawer48: 液态玻璃助手卡——切换助手放顶部（点击弹选择 sheet，点头像进详情）
            Surface(
                onClick = { showAssistantSheet = true },
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(20.dp),
                color = MaterialTheme.colorScheme.surfaceContainerHigh.copy(alpha = 0.82f),
                contentColor = MaterialTheme.colorScheme.onSurface,
                tonalElevation = 2.dp,
                border = BorderStroke(1.dp, MaterialTheme.colorScheme.primary.copy(alpha = 0.35f)),
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 12.dp, vertical = 10.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    Box(
                        modifier = Modifier
                            .size(52.dp)
                            .clip(CircleShape)
                            .background(
                                Brush.linearGradient(
                                    listOf(
                                        MaterialTheme.colorScheme.primary,
                                        MaterialTheme.colorScheme.tertiary,
                                    )
                                )
                            ),
                        contentAlignment = Alignment.Center,
                    ) {
                        UIAvatar(
                            name = assistantState.currentAssistant.name.ifBlank { stringResource(R.string.assistant_page_default_assistant) },
                            value = assistantState.currentAssistant.avatar,
                            onClick = {
                                navController.navigate(Screen.AssistantDetail(id = assistantState.currentAssistant.id.toString()))
                            },
                            modifier = Modifier.size(44.dp),
                        )
                    }

                    Column(
                        modifier = Modifier.weight(1f),
                        verticalArrangement = Arrangement.spacedBy(2.dp),
                    ) {
                        Text(
                            text = assistantState.currentAssistant.name.ifBlank { stringResource(R.string.assistant_page_default_assistant) },
                            style = MaterialTheme.typography.titleMedium,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                        Row(
                            modifier = Modifier.clickable {
                                nicknameEditState.open(settings.displaySetting.userNickname)
                            }
                        ) {
                            Greeting(
                                style = MaterialTheme.typography.labelSmall,
                            )
                        }
                    }

                    // ⇆ 切换助手
                    Surface(
                        onClick = { showAssistantSheet = true },
                        shape = CircleShape,
                        color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.9f),
                        border = BorderStroke(1.dp, MaterialTheme.colorScheme.primary.copy(alpha = 0.35f)),
                    ) {
                        Text(
                            text = "⇆",
                            style = MaterialTheme.typography.titleMedium,
                            color = MaterialTheme.colorScheme.onPrimaryContainer,
                            modifier = Modifier.padding(horizontal = 10.dp, vertical = 2.dp),
                        )
                    }
                }
            }

            // rhDrawer48: 会话/文件分段 tabs（白色胶囊选中态）+ 搜索/历史悬浮小圆钮
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                modifier = Modifier.fillMaxWidth(),
            ) {
                Surface(
                    shape = RoundedCornerShape(999.dp),
                    color = MaterialTheme.colorScheme.surfaceContainerLowest.copy(alpha = 0.6f),
                    border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.4f)),
                    modifier = Modifier.weight(1f),
                ) {
                    Row(
                        modifier = Modifier.padding(4.dp),
                        horizontalArrangement = Arrangement.spacedBy(4.dp),
                    ) {
                        Surface(
                            onClick = { },
                            shape = RoundedCornerShape(999.dp),
                            color = MaterialTheme.colorScheme.surface.copy(alpha = 0.95f),
                            border = BorderStroke(1.dp, MaterialTheme.colorScheme.primary.copy(alpha = 0.25f)),
                            modifier = Modifier.weight(1f),
                        ) {
                            Text(
                                text = stringResource(R.string.rh_drawer_tab_chats),
                                style = MaterialTheme.typography.labelMedium,
                                color = MaterialTheme.colorScheme.onSurface,
                                textAlign = TextAlign.Center,
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(vertical = 6.dp),
                            )
                        }
                        Surface(
                            onClick = { navController.navigate(Screen.SettingFiles) },
                            shape = RoundedCornerShape(999.dp),
                            color = MaterialTheme.colorScheme.surfaceContainerLowest.copy(alpha = 0.4f),
                            modifier = Modifier.weight(1f),
                        ) {
                            Text(
                                text = stringResource(R.string.rh_drawer_tab_files),
                                style = MaterialTheme.typography.labelMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                textAlign = TextAlign.Center,
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(vertical = 6.dp),
                            )
                        }
                    }
                }

                Surface(
                    onClick = { navController.navigate(Screen.MessageSearch) },
                    shape = CircleShape,
                    color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.9f),
                    border = BorderStroke(1.dp, MaterialTheme.colorScheme.primary.copy(alpha = 0.35f)),
                ) {
                    Icon(
                        imageVector = HugeIcons.Search01,
                        contentDescription = stringResource(R.string.chat_page_search_chats),
                        tint = MaterialTheme.colorScheme.onSurface,
                        modifier = Modifier
                            .padding(8.dp)
                            .size(18.dp),
                    )
                }
                Surface(
                    onClick = { navController.navigate(Screen.History) },
                    shape = CircleShape,
                    color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.9f),
                    border = BorderStroke(1.dp, MaterialTheme.colorScheme.primary.copy(alpha = 0.35f)),
                ) {
                    Icon(
                        imageVector = HugeIcons.TransactionHistory,
                        contentDescription = stringResource(R.string.chat_page_history),
                        tint = MaterialTheme.colorScheme.onSurface,
                        modifier = Modifier
                            .padding(8.dp)
                            .size(18.dp),
                    )
                }
            }'''

if OLD2 not in t:
    fail(DRAWER, 'OLD2 (user row + DrawerActions call) not found')
t = t.replace(OLD2, NEW2, 1)

# --- 1d. OLD3: 底部 AssistantPicker + 圆钮 Row -> 白色大圆角卡 4 列快捷 ---
OLD3 = '''            // 助手选择器
            AssistantPicker(
                settings = settings,
                onUpdateSettings = {
                    val updateJob = vm.updateSettings(it)
                    scope.launch {
                        updateJob.join()
                        val id = if (context.readBooleanPreference("create_new_conversation_on_start", true)) {
                            Uuid.random()
                        } else {
                            repo.getConversationsOfAssistant(it.assistantId)
                                .first()
                                .firstOrNull()
                                ?.id ?: Uuid.random()
                        }
                        navigateToChatPage(navigator = navController, chatId = id)
                    }
                },
                modifier = Modifier.fillMaxWidth(),
                onClickSetting = {
                    val currentAssistantId = settings.assistantId
                    navController.navigate(Screen.AssistantDetail(id = currentAssistantId.toString()))
                }
            )

            Row(
                horizontalArrangement = Arrangement.SpaceAround,
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 8.dp)
            ) {
                DrawerAction(
                    icon = {
                        Icon(
                            imageVector = HugeIcons.LookTop,
                            contentDescription = stringResource(R.string.assistant_page_title)
                        )
                    },
                    label = {
                        Text(stringResource(R.string.assistant_page_title))
                    },
                    onClick = {
                        navController.navigate(Screen.Assistant)
                    },
                )

                Box {
                    DrawerAction(
                        icon = {
                            Icon(HugeIcons.Sparkles, stringResource(R.string.menu))
                        },
                        label = {
                            Text(stringResource(R.string.menu))
                        },
                        onClick = {
                            showMenuPopup = true
                        },
                    )
                    DropdownMenu(
                        expanded = showMenuPopup,
                        onDismissRequest = { showMenuPopup = false }
                    ) {
                        DropdownMenuItem(
                            text = { Text(stringResource(R.string.stats_page_title)) },
                            leadingIcon = { Icon(HugeIcons.ChartColumn, null) },
                            onClick = {
                                showMenuPopup = false
                                navController.navigate(Screen.Stats)
                            }
                        )
                        DropdownMenuItem(
                            text = { Text(stringResource(R.string.chat_page_menu_image_generation)) },
                            leadingIcon = { Icon(HugeIcons.Image02, null) },
                            onClick = {
                                showMenuPopup = false
                                navController.navigate(Screen.ImageGen)
                            }
                        )
                    }
                }

                DrawerAction(
                    icon = {
                        Icon(HugeIcons.InLove, stringResource(R.string.favorite_page_title))
                    },
                    label = {
                        Text(stringResource(R.string.favorite_page_title))
                    },
                    onClick = {
                        navController.navigate(Screen.Favorite)
                    },
                )

                Spacer(Modifier.weight(1f))

                DrawerAction(
                    icon = {
                        Icon(HugeIcons.Settings03, null)
                    },
                    label = { Text(stringResource(R.string.settings)) },
                    onClick = {
                        navController.navigate(Screen.Setting)
                    },
                )
            }'''

NEW3 = '''            // rhDrawer48: 底部白色大圆角卡——4 列图文快捷（液态玻璃 + 边缘高亮 + 悬浮提示）
            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(24.dp),
                color = MaterialTheme.colorScheme.surfaceContainerHigh.copy(alpha = 0.82f),
                contentColor = MaterialTheme.colorScheme.onSurface,
                tonalElevation = 2.dp,
                border = BorderStroke(1.dp, MaterialTheme.colorScheme.primary.copy(alpha = 0.30f)),
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 12.dp, horizontal = 8.dp),
                    horizontalArrangement = Arrangement.SpaceEvenly,
                ) {
                    DrawerQuickEntry(
                        icon = { Icon(HugeIcons.Image02, null, tint = MaterialTheme.colorScheme.primary) },
                        label = stringResource(R.string.chat_page_menu_image_generation),
                        onClick = { navController.navigate(Screen.ImageGen) },
                    )
                    DrawerQuickEntry(
                        icon = { Icon(HugeIcons.InLove, null, tint = MaterialTheme.colorScheme.primary) },
                        label = stringResource(R.string.favorite_page_title),
                        onClick = { navController.navigate(Screen.Favorite) },
                    )
                    DrawerQuickEntry(
                        icon = { Icon(HugeIcons.ChartColumn, null, tint = MaterialTheme.colorScheme.primary) },
                        label = stringResource(R.string.stats_page_title),
                        onClick = { navController.navigate(Screen.Stats) },
                    )
                    DrawerQuickEntry(
                        icon = { Icon(HugeIcons.Settings03, null, tint = MaterialTheme.colorScheme.primary) },
                        label = stringResource(R.string.settings),
                        onClick = { navController.navigate(Screen.Setting) },
                    )
                }
            }'''

if OLD3 not in t:
    fail(DRAWER, 'OLD3 (bottom AssistantPicker + circle buttons Row) not found')
t = t.replace(OLD3, NEW3, 1)

# --- 1e. 助手切换 sheet（插在移动到助手 sheet 前，锚点已验证）---
SHEET_ANCHOR = '    // 移动到助手 Bottom Sheet' + NL
SHEET_BLOCK = '''    // rhDrawer48: 顶部助手卡的选择 sheet（复用 AssistantItem 行样式）
    if (showAssistantSheet) {
        ModalBottomSheet(
            onDismissRequest = { showAssistantSheet = false },
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(max = 400.dp)
                    .padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Text(
                    text = stringResource(R.string.assistant_page_title),
                    style = MaterialTheme.typography.titleLarge,
                    modifier = Modifier.padding(bottom = 8.dp)
                )
                LazyColumn(
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    items(settings.assistants, key = { it.id }) { assistant ->
                        AssistantItem(
                            assistant = assistant,
                            isCurrentAssistant = assistant.id == assistantState.currentAssistant.id,
                            onClick = {
                                assistantState.setSelectAssistant(assistant)
                                showAssistantSheet = false
                            },
                        )
                    }
                }
            }
        }
    }

'''
if SHEET_ANCHOR not in t:
    fail(DRAWER, 'sheet insertion anchor (移动到助手) not found')
t = t.replace(SHEET_ANCHOR, SHEET_BLOCK + SHEET_ANCHOR, 1)

# --- 1f. DrawerQuickEntry 私有组件（插在 FolderBar 前，锚点已验证）---
ENTRY_ANCHOR = '@Composable' + NL + 'private fun FolderBar('
ENTRY_BLOCK = '''@Composable
private fun DrawerQuickEntry(
    icon: @Composable () -> Unit,
    label: String,
    onClick: () -> Unit,
) {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(6.dp),
        modifier = Modifier
            .clip(RoundedCornerShape(16.dp))
            .clickable(onClick = onClick)
            .padding(horizontal = 12.dp, vertical = 4.dp),
    ) {
        Tooltip(tooltip = { Text(label) }) {
            Surface(
                shape = CircleShape,
                color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.55f),
                border = BorderStroke(1.dp, MaterialTheme.colorScheme.primary.copy(alpha = 0.30f)),
            ) {
                Box(modifier = Modifier.padding(10.dp)) {
                    icon()
                }
            }
        }
        Text(
            text = label,
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            maxLines = 1,
        )
    }
}

'''
if ENTRY_ANCHOR not in t:
    fail(DRAWER, 'DrawerQuickEntry insertion anchor (FolderBar) not found')
t = t.replace(ENTRY_ANCHOR, ENTRY_BLOCK + ENTRY_ANCHOR, 1)

# ============================================================
# 2. 自检：新内容在场 + 旧块消失（铁律3）
# ============================================================
for need in [
    MARK,
    'val assistantState = rememberAssistantState(settings)',
    'import me.rerere.rikkahub.ui.hooks.rememberAssistantState',
    'import androidx.compose.foundation.BorderStroke',
    'import androidx.compose.foundation.background',
    'import androidx.compose.foundation.shape.RoundedCornerShape',
    'import androidx.compose.ui.graphics.Brush',
    'import androidx.compose.ui.text.style.TextAlign',
    'private fun DrawerQuickEntry',
    'Screen.SettingFiles',
    'R.string.rh_drawer_tab_chats',
    'R.string.rh_drawer_tab_files',
]:
    if need not in t:
        fail(DRAWER, 'selfcheck missing: ' + need)

for gone in [
    'showMenuPopup',
    '// 助手选择器',
    '用户头像和昵称自定义区域',
    'AssistantPicker(',
    'DrawerActions(navController = navController)',
]:
    if gone in t:
        fail(DRAWER, 'selfcheck stale remnant: ' + gone)

(ROOT / DRAWER).write_text(t, encoding='utf-8')

for path in [STR_EN, STR_ZH]:
    s = (ROOT / path).read_text(encoding='utf-8')
    if 'rh_drawer_tab_chats' not in s or 'rh_drawer_tab_files' not in s:
        fail(path, 'selfcheck: tab strings missing')

print('batch48: OK (glass assistant card + tabs + bottom quick card + sheet + entries)')
