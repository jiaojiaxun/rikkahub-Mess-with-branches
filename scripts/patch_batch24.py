from pathlib import Path

ROOT = Path.cwd()


def fail(path, msg):
    print(f"::error file={path}::batch24 {msg[:1400]}")
    raise SystemExit(1)


# ============================================================
# 工作区多选导出（任务池高优先级 #2）v2 完整版
# v2 修复：BackHandler 优先级。v1 把 selectionMode 的 BackHandler 插在
# path 的 BackHandler 之前（代码顺序），Compose 的 OnBackPressedDispatcher
# 是后进先出——后注册的（path goUp）会先消费返回事件，多选时在子目录里
# 按返回会 goUp 而不是退出多选。修复：path BackHandler 的 enabled 加
# && !selectionMode，多选时禁用它，让 selectionMode 的 BackHandler 生效。
# CI 每次从干净 checkout 跑全部 patch，本文件为完整版（含 v1 全部逻辑）。
# ============================================================

# ---------- 1) strings.xml 末尾追加 ----------
PS = "app/src/main/res/values/strings.xml"
ts = (ROOT / PS).read_text(encoding="utf-8")
NEW_STRINGS = (
    '    <string name="workspace_detail_selected_count">已选 %1$d/%2$d 项</string>\n'
    '    <string name="workspace_detail_select_all">全选</string>\n'
    '    <string name="workspace_detail_deselect_all">取消全选</string>\n'
    '    <string name="workspace_detail_export_selected">导出选中</string>\n'
    '    <string name="workspace_detail_exit_selection">退出多选</string>\n'
)
if "workspace_detail_selected_count" in ts:
    print("batch24: strings already patched")
else:
    A = "</resources>"
    if ts.count(A) != 1:
        fail(PS, f"resources close tag count={ts.count(A)}")
    ts = ts.replace(A, NEW_STRINGS + A, 1)
    (ROOT / PS).write_text(ts, encoding="utf-8")
    print("batch24: 5 strings appended")

# ---------- 2) WorkspaceDetailPage.kt ----------
P1 = "app/src/main/java/me/rerere/rikkahub/ui/pages/extensions/workspace/WorkspaceDetailPage.kt"
t1 = (ROOT / P1).read_text(encoding="utf-8")

if "&& !selectionMode" in t1:
    print("batch24 v2: WorkspaceDetailPage already patched")
else:
    # 2a. imports: combinedClickable / Checkbox / TextButton / Dispatchers / withContext
    A = "import androidx.compose.foundation.clickable\n"
    B = (
        "import androidx.compose.foundation.clickable\n"
        "import androidx.compose.foundation.combinedClickable\n"
    )
    if t1.count(A) != 1:
        fail(P1, f"import clickable count={t1.count(A)}")
    t1 = t1.replace(A, B, 1)

    A = "import androidx.compose.material3.Card\n"
    B = (
        "import androidx.compose.material3.Card\n"
        "import androidx.compose.material3.Checkbox\n"
    )
    if t1.count(A) != 1:
        fail(P1, f"import Card count={t1.count(A)}")
    t1 = t1.replace(A, B, 1)

    A = "import androidx.compose.material3.Text\n"
    B = (
        "import androidx.compose.material3.Text\n"
        "import androidx.compose.material3.TextButton\n"
    )
    if t1.count(A) != 1:
        fail(P1, f"import Text count={t1.count(A)}")
    t1 = t1.replace(A, B, 1)

    A = "import kotlinx.coroutines.launch\n"
    B = (
        "import kotlinx.coroutines.Dispatchers\n"
        "import kotlinx.coroutines.launch\n"
        "import kotlinx.coroutines.withContext\n"
    )
    if t1.count(A) != 1:
        fail(P1, f"import launch count={t1.count(A)}")
    t1 = t1.replace(A, B, 1)

    # 2b. 多选状态（锚点：exportTarget 声明前）
    A = "    var exportTarget by remember { mutableStateOf<WorkspaceFileEntry?>(null) }\n"
    B = (
        "    var selectionMode by remember { mutableStateOf(false) }\n"
        "    var selectedPaths by remember { mutableStateOf(setOf<String>()) }\n"
        "    var multiExportTargets by remember { mutableStateOf(listOf<WorkspaceFileEntry>()) }\n"
        "    var exportTarget by remember { mutableStateOf<WorkspaceFileEntry?>(null) }\n"
    )
    if t1.count(A) != 1:
        fail(P1, f"exportTarget decl count={t1.count(A)}")
    t1 = t1.replace(A, B, 1)

    # rowsCount：与 FilesPage 同源推导
    A = (
        "    var selectionMode by remember { mutableStateOf(false) }\n"
    )
    B = (
        "    var selectionMode by remember { mutableStateOf(false) }\n"
        "    val rowsCount = remember(state.entries, state.expandedPaths, state.childrenCache) {\n"
        "        flattenWorkspaceTree(state.entries, state.expandedPaths, state.childrenCache).size\n"
        "    }\n"
    )
    if t1.count(A) != 1:
        fail(P1, f"selectionMode decl count={t1.count(A)}")
    t1 = t1.replace(A, B, 1)

    # 2c. 多选导出 launcher + BackHandler（v2：path BackHandler enabled 加 && !selectionMode）
    A = "    BackHandler(enabled = pagerState.currentPage == 1 && state.path.isNotBlank()) {\n"
    B = (
        "    val multiExportLauncher = rememberLauncherForActivityResult(\n"
        "        contract = ActivityResultContracts.OpenDocumentTree(),\n"
        "    ) { uri ->\n"
        "        val targets = multiExportTargets.also { multiExportTargets = emptyList() }\n"
        "        if (uri == null || targets.isEmpty()) return@rememberLauncherForActivityResult\n"
        "        val destinationTree = DocumentFile.fromTreeUri(context, uri) ?: return@rememberLauncherForActivityResult\n"
        "        scope.launch {\n"
        "            withContext(Dispatchers.IO) {\n"
        "                targets.forEach { entry ->\n"
        "                    if (entry.isDirectory) {\n"
        "                        vm.exportFolder(entry, destinationTree) { docUri ->\n"
        "                            context.contentResolver.openOutputStream(docUri)\n"
        "                        }\n"
        "                    } else {\n"
        "                        val fileDoc = destinationTree.createFile(\"application/octet-stream\", entry.name)\n"
        "                        if (fileDoc != null) {\n"
        "                            context.contentResolver.openOutputStream(fileDoc.uri)?.let { output ->\n"
        "                                vm.exportFile(entry, output)\n"
        "                            }\n"
        "                        }\n"
        "                    }\n"
        "                }\n"
        "            }\n"
        "        }\n"
        "        selectionMode = false\n"
        "        selectedPaths = emptySet()\n"
        "    }\n"
        "\n"
        "    fun startMultiExport(entries: List<WorkspaceFileEntry>) {\n"
        "        if (entries.isEmpty()) return\n"
        "        multiExportTargets = entries\n"
        "        multiExportLauncher.launch(null)\n"
        "    }\n"
        "\n"
        "    // v2: 多选时禁用 path BackHandler，避免它在多选中先消费返回（dispatcher 后进先出）\n"
        "    BackHandler(enabled = selectionMode) {\n"
        "        selectionMode = false\n"
        "        selectedPaths = emptySet()\n"
        "    }\n"
        "\n"
        "    BackHandler(enabled = pagerState.currentPage == 1 && state.path.isNotBlank() && !selectionMode) {\n"
    )
    if t1.count(A) != 1:
        fail(P1, f"BackHandler anchor count={t1.count(A)}")
    t1 = t1.replace(A, B, 1)

    # 2d. topBar 标题：多选时显示已选数
    A = (
        "                title = {\n"
        "                    Text(\n"
        "                        text = state.workspace?.name ?: stringResource(R.string.workspace_detail_title),\n"
        "                        maxLines = 1,\n"
        "                        overflow = TextOverflow.Ellipsis,\n"
        "                    )\n"
        "                },\n"
    )
    B = (
        "                title = {\n"
        "                    if (selectionMode) {\n"
        "                        Text(stringResource(R.string.workspace_detail_selected_count, selectedPaths.size, rowsCount))\n"
        "                    } else {\n"
        "                        Text(\n"
        "                            text = state.workspace?.name ?: stringResource(R.string.workspace_detail_title),\n"
        "                            maxLines = 1,\n"
        "                            overflow = TextOverflow.Ellipsis,\n"
        "                        )\n"
        "                    }\n"
        "                },\n"
    )
    if t1.count(A) != 1:
        fail(P1, f"title anchor count={t1.count(A)}")
    t1 = t1.replace(A, B, 1)

    # 2e. topBar navigationIcon：多选时变退出按钮
    A = "                navigationIcon = { BackButton() },\n"
    B = (
        "                navigationIcon = {\n"
        "                    if (selectionMode) {\n"
        "                        IconButton(onClick = {\n"
        "                            selectionMode = false\n"
        "                            selectedPaths = emptySet()\n"
        "                        }) {\n"
        "                            Icon(HugeIcons.ArrowTurnBackward, contentDescription = stringResource(R.string.workspace_detail_exit_selection))\n"
        "                        }\n"
        "                    } else {\n"
        "                        BackButton()\n"
        "                    }\n"
        "                },\n"
    )
    if t1.count(A) != 1:
        fail(P1, f"navigationIcon anchor count={t1.count(A)}")
    t1 = t1.replace(A, B, 1)

    # 2f. WorkspaceFilesPage 调用处补参数
    A = (
        "                1 -> WorkspaceFilesPage(\n"
        "                    state = state,\n"
        "                    contentPadding = PaddingValues(),\n"
    )
    B = (
        "                1 -> WorkspaceFilesPage(\n"
        "                    state = state,\n"
        "                    contentPadding = PaddingValues(),\n"
        "                    selectionMode = selectionMode,\n"
        "                    selectedPaths = selectedPaths,\n"
        "                    onToggleSelect = { entry ->\n"
        "                        val next = if (entry.path in selectedPaths) selectedPaths - entry.path else selectedPaths + entry.path\n"
        "                        selectedPaths = next\n"
        "                        if (next.isEmpty()) selectionMode = false\n"
        "                    },\n"
        "                    onEnterSelection = { entry ->\n"
        "                        selectionMode = true\n"
        "                        selectedPaths = setOf(entry.path)\n"
        "                    },\n"
        "                    onSelectedPathsChange = {\n"
        "                        selectedPaths = it\n"
        "                        if (it.isEmpty()) selectionMode = false\n"
        "                    },\n"
        "                    onExportSelected = { entries -> startMultiExport(entries) },\n"
    )
    if t1.count(A) != 1:
        fail(P1, f"FilesPage call anchor count={t1.count(A)}")
    t1 = t1.replace(A, B, 1)

    # 2g. WorkspaceFilesPage 签名补参数
    A = (
        "    onOpen: (WorkspaceFileEntry) -> Unit,\n"
        "    onDelete: (WorkspaceFileEntry) -> Unit,\n"
        "    onExport: (WorkspaceFileEntry) -> Unit,\n"
        "    onShare: (WorkspaceFileEntry) -> Unit,\n"
        ") {\n"
        "    val rows = remember(state.entries, state.expandedPaths, state.childrenCache) {\n"
    )
    B = (
        "    onOpen: (WorkspaceFileEntry) -> Unit,\n"
        "    onDelete: (WorkspaceFileEntry) -> Unit,\n"
        "    onExport: (WorkspaceFileEntry) -> Unit,\n"
        "    onShare: (WorkspaceFileEntry) -> Unit,\n"
        "    selectionMode: Boolean,\n"
        "    selectedPaths: Set<String>,\n"
        "    onToggleSelect: (WorkspaceFileEntry) -> Unit,\n"
        "    onEnterSelection: (WorkspaceFileEntry) -> Unit,\n"
        "    onSelectedPathsChange: (Set<String>) -> Unit,\n"
        "    onExportSelected: (List<WorkspaceFileEntry>) -> Unit,\n"
        ") {\n"
        "    val rows = remember(state.entries, state.expandedPaths, state.childrenCache) {\n"
    )
    if t1.count(A) != 1:
        fail(P1, f"FilesPage signature anchor count={t1.count(A)}")
    t1 = t1.replace(A, B, 1)

    # 2h. PathBar item 替换为多选栏/路径栏切换
    A = (
        "        item {\n"
        "            WorkspacePathBar(\n"
        "                path = state.path,\n"
        "                canGoUp = state.path.isNotBlank(),\n"
        "                onGoUp = onGoUp,\n"
        "            )\n"
        "        }\n"
    )
    B = (
        "        item {\n"
        "            if (selectionMode) {\n"
        "                val allPaths = rows.map { it.entry.path }.toSet()\n"
        "                WorkspaceMultiSelectBar(\n"
        "                    selectedCount = selectedPaths.size,\n"
        "                    totalCount = rows.size,\n"
        "                    allSelected = allPaths.isNotEmpty() && selectedPaths.containsAll(allPaths),\n"
        "                    onToggleSelectAll = {\n"
        "                        onSelectedPathsChange(if (selectedPaths.containsAll(allPaths)) emptySet() else allPaths)\n"
        "                    },\n"
        "                    onExportSelected = {\n"
        "                        onExportSelected(rows.filter { it.entry.path in selectedPaths }.map { it.entry })\n"
        "                    },\n"
        "                )\n"
        "            } else {\n"
        "                WorkspacePathBar(\n"
        "                    path = state.path,\n"
        "                    canGoUp = state.path.isNotBlank(),\n"
        "                    onGoUp = onGoUp,\n"
        "                )\n"
        "            }\n"
        "        }\n"
    )
    if t1.count(A) != 1:
        fail(P1, f"PathBar item anchor count={t1.count(A)}")
    t1 = t1.replace(A, B, 1)

    # 2i. WorkspaceFileCard 调用补参数
    A = (
        "                onDelete = { onDelete(row.entry) },\n"
        "                onExport = { onExport(row.entry) },\n"
        "                onShare = { onShare(row.entry) },\n"
        "            )\n"
    )
    B = (
        "                onDelete = { onDelete(row.entry) },\n"
        "                onExport = { onExport(row.entry) },\n"
        "                onShare = { onShare(row.entry) },\n"
        "                selectionMode = selectionMode,\n"
        "                selected = row.entry.path in selectedPaths,\n"
        "                onToggleSelect = { onToggleSelect(row.entry) },\n"
        "                onEnterSelection = { onEnterSelection(row.entry) },\n"
        "            )\n"
    )
    if t1.count(A) != 1:
        fail(P1, f"FileCard call anchor count={t1.count(A)}")
    t1 = t1.replace(A, B, 1)

    # 2j. WorkspaceFileCard 签名补参数
    A = (
        "    onOpen: () -> Unit,\n"
        "    onToggleExpand: () -> Unit,\n"
        "    onDelete: () -> Unit,\n"
        "    onExport: () -> Unit,\n"
        "    onShare: () -> Unit,\n"
        ") {\n"
        "    var menuExpanded by remember { mutableStateOf(false) }\n"
    )
    B = (
        "    onOpen: () -> Unit,\n"
        "    onToggleExpand: () -> Unit,\n"
        "    onDelete: () -> Unit,\n"
        "    onExport: () -> Unit,\n"
        "    onShare: () -> Unit,\n"
        "    selectionMode: Boolean,\n"
        "    selected: Boolean,\n"
        "    onToggleSelect: () -> Unit,\n"
        "    onEnterSelection: () -> Unit,\n"
        ") {\n"
        "    var menuExpanded by remember { mutableStateOf(false) }\n"
    )
    if t1.count(A) != 1:
        fail(P1, f"FileCard signature anchor count={t1.count(A)}")
    t1 = t1.replace(A, B, 1)

    # 2k. Card clickable -> combinedClickable
    A = (
        "    Card(\n"
        "        modifier = Modifier\n"
        "            .fillMaxWidth()\n"
        "            .clickable(onClick = onOpen),\n"
    )
    B = (
        "    Card(\n"
        "        modifier = Modifier\n"
        "            .fillMaxWidth()\n"
        "            .combinedClickable(\n"
        "                onClick = { if (selectionMode) onToggleSelect() else onOpen() },\n"
        "                onLongClick = { if (selectionMode) onToggleSelect() else onEnterSelection() },\n"
        "            ),\n"
    )
    if t1.count(A) != 1:
        fail(P1, f"Card clickable anchor count={t1.count(A)}")
    t1 = t1.replace(A, B, 1)

    # 2l. Row 里插 Checkbox
    A = (
        "            verticalAlignment = Alignment.CenterVertically,\n"
        "        ) {\n"
        "            if (entry.isDirectory) {\n"
    )
    B = (
        "            verticalAlignment = Alignment.CenterVertically,\n"
        "        ) {\n"
        "            if (selectionMode) {\n"
        "                Checkbox(\n"
        "                    checked = selected,\n"
        "                    onCheckedChange = { onToggleSelect() },\n"
        "                )\n"
        "            }\n"
        "            if (entry.isDirectory) {\n"
    )
    if t1.count(A) != 1:
        fail(P1, f"Row checkbox anchor count={t1.count(A)}")
    t1 = t1.replace(A, B, 1)

    # 2m. 新增 WorkspaceMultiSelectBar composable（插在 WorkspacePathBar 定义前）
    A = (
        "@Composable\n"
        "private fun WorkspacePathBar(\n"
    )
    B = (
        "@Composable\n"
        "private fun WorkspaceMultiSelectBar(\n"
        "    selectedCount: Int,\n"
        "    totalCount: Int,\n"
        "    allSelected: Boolean,\n"
        "    onToggleSelectAll: () -> Unit,\n"
        "    onExportSelected: () -> Unit,\n"
        ") {\n"
        "    Row(\n"
        "        modifier = Modifier.fillMaxWidth(),\n"
        "        verticalAlignment = Alignment.CenterVertically,\n"
        "        horizontalArrangement = Arrangement.spacedBy(8.dp),\n"
        "    ) {\n"
        "        Text(\n"
        "            text = stringResource(R.string.workspace_detail_selected_count, selectedCount, totalCount),\n"
        "            modifier = Modifier.weight(1f),\n"
        "            style = MaterialTheme.typography.bodyMedium,\n"
        "            color = MaterialTheme.colorScheme.onSurfaceVariant,\n"
        "        )\n"
        "        TextButton(onClick = onToggleSelectAll) {\n"
        "            Text(\n"
        "                stringResource(\n"
        "                    if (allSelected) R.string.workspace_detail_deselect_all\n"
        "                    else R.string.workspace_detail_select_all\n"
        "                )\n"
        "            )\n"
        "        }\n"
        "        TextButton(onClick = onExportSelected, enabled = selectedCount > 0) {\n"
        "            Text(stringResource(R.string.workspace_detail_export_selected))\n"
        "        }\n"
        "    }\n"
        "}\n"
        "\n"
        "@Composable\n"
        "private fun WorkspacePathBar(\n"
    )
    if t1.count(A) != 1:
        fail(P1, f"PathBar def anchor count={t1.count(A)}")
    t1 = t1.replace(A, B, 1)

    (ROOT / P1).write_text(t1, encoding="utf-8")
    print("batch24 v2: multi-select export wired (BackHandler priority fixed)")
