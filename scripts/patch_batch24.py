from pathlib import Path

ROOT = Path.cwd()


def fail(path, msg):
    print(f"::error file={path}::batch24 {msg[:1400]}")
    raise SystemExit(1)


# ============================================================
# 工作区多选导出（任务池高优先级 #2）
# 实测基础（fix/batch1 全文精读 WorkspaceDetailPage.kt 27.8KB +
# WorkspaceDetailVM.kt 13.7KB）：
# - 现有单文件导出: CreateDocument launcher + vm.exportFile(entry, os)
# - 现有目录导出: OpenDocumentTree + vm.exportFolder(entry, tree) { uri -> resolver.openOutputStream(uri) }
# - vm.exportFile/exportFolder 均为 fire-and-forget(viewModelScope.launch)，
#   目录结果走 folderExportResult Flow 逐条 Toast，批量循环调用安全
# - ExperimentalFoundationApi 已在 app/build.gradle.kts 全局 optIn，
#   combinedClickable 无需注解
# 本批新增：长按进入多选 -> Checkbox 勾选 -> 路径栏替换为多选操作栏
# （全选/取消全选/导出选中）-> OpenDocumentTree 选目标目录 -> 逐项导出
# （目录 vm.exportFolder 递归，文件 tree.createFile + vm.exportFile）。
# 取消到 0 个选中自动退出多选；topBar 标题显示已选数，返回键退出。
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

if "selectionMode" in t1:
    print("batch24: WorkspaceDetailPage already patched")
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

    # 2c. 多选导出 launcher（锚点：folderExportLauncher 块后，插到 BackHandler 前）
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
        "    BackHandler(enabled = selectionMode) {\n"
        "        selectionMode = false\n"
        "        selectedPaths = emptySet()\n"
        "    }\n"
        "\n"
        "    BackHandler(enabled = pagerState.currentPage == 1 && state.path.isNotBlank()) {\n"
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

    # rowsCount 需要和 FilesPage 同源的行数：用状态推导（展开集合+缓存压平）
    # 直接在状态声明后补一行 val rowsCount
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

    # 2f. WorkspaceFilesPage 调用处补参数（锚点：contentPadding 行后）
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

    # 2l. Row 里插 Checkbox（锚点：Row padding + 第一个 if (entry.isDirectory)）
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
    print("batch24: WorkspaceDetailPage multi-select export wired")
