#!/usr/bin/env python3
# rhRemote353: 工作区详情页适配 SSH
#   - 基本信息页: SSH 显示连接信息卡 + 编辑入口
#   - 工具审批: 按能力过滤 (SSH 隐藏 write/edit/create_folder/read_folder)
#   - DetailVM.refresh: 竞态取消, 远程列目录只保留最新一次
import os

MARK = "rhRemote353"
DIAG = "ci_diag_batch353_remote.txt"
ROOT = os.environ.get("GITHUB_WORKSPACE", os.getcwd())


def log(msg):
    print(msg)


def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write(path, text):
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


# 1) WorkspaceDetailPage: 基本信息页加 SSH 卡 + 编辑入口
# 锚点: WorkspaceBasicPage 的 item { Card(...) } 块结束, 工具审批卡之前
BASIC_ANCHOR = """        item {
            WorkspaceToolApprovalCard(
                workspace = workspace,
                onToolApprovalChange = onToolApprovalChange,
            )
        }
"""
BASIC_NEW = r'''        if (workspace?.isSsh() == true) {
            item {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CustomColors.cardColorsOnSurfaceContainer,
                ) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        Text(
                            text = stringResource(R.string.workspace_detail_ssh_connection),
                            style = MaterialTheme.typography.titleMedium,
                        )
                        val settings = workspace.sshSettings()
                        if (settings != null) {
                            WorkspaceInfoRow(
                                stringResource(R.string.workspace_detail_ssh_address),
                                "${settings.username}@${settings.host}:${settings.port}",
                            )
                            WorkspaceInfoRow(
                                stringResource(R.string.workspace_ssh_editor_remote_dir),
                                settings.remoteDir,
                            )
                            WorkspaceInfoRow(
                                stringResource(R.string.workspace_ssh_editor_host_key),
                                settings.hostKey?.fingerprint ?: stringResource(R.string.workspace_ssh_editor_host_key_unconfirmed),
                            )
                        }
                        androidx.compose.material3.OutlinedButton(
                            onClick = {
                                navController.navigate(Screen.WorkspaceSshEditor(workspace.id))
                            },
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Text(stringResource(R.string.workspace_ssh_editor_title_edit))
                        }
                    }
                }
            }
        }

''' + BASIC_ANCHOR

# 2) 工具审批按能力过滤
APPROVAL_ANCHOR = """            workspaceToolApprovalItems().forEach { (toolName, label) ->"""
APPROVAL_NEW = """            workspaceToolApprovalItems(workspace).forEach { (toolName, label) ->"""

APPROVAL_FN_ANCHOR = """@Composable
private fun workspaceToolApprovalItems() = listOf(
    "workspace_read_file" to stringResource(R.string.workspace_detail_tool_read_file),
    "workspace_write_file" to stringResource(R.string.workspace_detail_tool_write_file),
    "workspace_edit_file" to stringResource(R.string.workspace_detail_tool_edit_file),
    "workspace_create_folder" to stringResource(R.string.workspace_detail_tool_create_folder),
    "workspace_read_folder" to stringResource(R.string.workspace_detail_tool_list_files),
)"""
APPROVAL_FN_NEW = """@Composable
private fun workspaceToolApprovalItems(workspace: WorkspaceEntity?): List<Pair<String, String>> {
    val capabilities = workspace?.capabilities()
    return buildList {
        add("workspace_read_file" to stringResource(R.string.workspace_detail_tool_read_file))
        if (capabilities?.fileWriteTools != false) {
            add("workspace_write_file" to stringResource(R.string.workspace_detail_tool_write_file))
            add("workspace_edit_file" to stringResource(R.string.workspace_detail_tool_edit_file))
            add("workspace_create_folder" to stringResource(R.string.workspace_detail_tool_create_folder))
        }
        if (capabilities?.localFiles != false) {
            add("workspace_read_folder" to stringResource(R.string.workspace_detail_tool_list_files))
        }
    }
}"""

# 3) DetailVM.refresh 竞态取消
VM_ANCHOR = """    fun refresh() {
        viewModelScope.launch {"""
VM_NEW = """    private var refreshJob: kotlinx.coroutines.Job? = null

    fun refresh() {
        // 远程工作区列目录要走网络, 快速切换目录时旧请求可能晚到, 只保留最新一次
        refreshJob?.cancel()
        refreshJob = viewModelScope.launch {"""

# 4) DetailPage 顶部加编辑入口 (SSH 时显示在 actions)
# 现有 actions 只有导入和刷新; SSH 下加编辑按钮
ACTIONS_ANCHOR = """                actions = {
                    if (pagerState.currentPage == 1) {"""
ACTIONS_NEW = """                actions = {
                    if (state.workspace?.isSsh() == true) {
                        IconButton(onClick = { navController.navigate(Screen.WorkspaceSshEditor(state.workspace!!.id)) }) {
                            Icon(HugeIcons.Settings03, contentDescription = stringResource(R.string.workspace_ssh_editor_title_edit))
                        }
                    }
                    if (pagerState.currentPage == 1) {"""

STRINGS_EN = r'''  <string name="workspace_detail_ssh_connection">SSH connection</string>
  <string name="workspace_detail_ssh_address">Address</string>
'''
STRINGS_ZH = r'''  <string name="workspace_detail_ssh_connection">SSH 连接</string>
  <string name="workspace_detail_ssh_address">地址</string>
'''


def patch(path, edits, diag):
    text = read(path)
    for label, needle, repl in edits:
        if repl in text:
            diag.append(label + ":already")
            continue
        if text.count(needle) != 1:
            diag.append(label + ":ANCHOR-MISMATCH(" + str(text.count(needle)) + ")")
            continue
        text = text.replace(needle, repl, 1)
        diag.append(label + ":ok")
    write(path, text)


def main():
    diag = []
    ok = True

    page_path = "app/src/main/java/me/rerere/rikkahub/ui/pages/extensions/workspace/WorkspaceDetailPage.kt"
    patch(page_path, [
        ("basic-ssh", BASIC_ANCHOR, BASIC_NEW),
        ("approval-gate", APPROVAL_ANCHOR, APPROVAL_NEW),
        ("approval-fn", APPROVAL_FN_ANCHOR, APPROVAL_FN_NEW),
        ("actions-edit", ACTIONS_ANCHOR, ACTIONS_NEW),
    ], diag)

    vm_path = "app/src/main/java/me/rerere/rikkahub/ui/pages/extensions/workspace/WorkspaceDetailVM.kt"
    patch(vm_path, [
        ("vm-race", VM_ANCHOR, VM_NEW),
    ], diag)

    for path, block, label in (
        ("app/src/main/res/values/strings.xml", STRINGS_EN, "strings-en"),
        ("app/src/main/res/values-zh/strings.xml", STRINGS_ZH, "strings-zh"),
    ):
        text = read(path)
        if 'name="workspace_detail_ssh_connection"' in text:
            diag.append(label + ":already")
            continue
        anchor = "</resources>"
        if text.count(anchor) != 1:
            diag.append(label + ":ANCHOR-MISMATCH")
            ok = False
            continue
        text = text.replace(anchor, block + "\n" + anchor, 1)
        write(path, text)
        diag.append(label + ":ok")

    # 自检
    page = read(page_path)
    if "workspace_detail_ssh_connection" not in page:
        diag.append("page:MISS-ssh-card")
        ok = False
    if "workspaceToolApprovalItems(workspace)" not in page:
        diag.append("page:MISS-approval-gate")
        ok = False
    if "capabilities?.fileWriteTools != false" not in page:
        diag.append("page:MISS-capability-filter")
        ok = False
    vm = read(vm_path)
    if "refreshJob?.cancel()" not in vm:
        diag.append("vm:MISS-race")
        ok = False

    diag.append("RESULT:" + ("OK" if ok else "FAIL"))
    with open(os.path.join(ROOT, DIAG), "w", encoding="utf-8") as f:
        f.write("\n".join(diag) + "\n")
    log(" | ".join(diag))
    if not ok:
        print("::error title=batch353::" + " | ".join(diag))


main()
