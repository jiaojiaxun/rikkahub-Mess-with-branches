#!/usr/bin/env python3
# rhRemote352b: 导航接线 + 工作区列表类型选择 + 文案
#   - RouteActivity: Screen.WorkspaceSshEditor + entry + import
#   - WorkspacePage: 新建先选类型(本地/SSH), 本地走原名对话框, SSH 跳编辑页
#   - strings.xml: 英文 + 中文文案
import os

MARK = "rhRemote352b"
DIAG = "ci_diag_batch352b_remote.txt"
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


# RouteActivity 修改
ROUTE_IMPORT_ANCHOR = "import me.rerere.rikkahub.ui.pages.extensions.workspace.WorkspaceFileEditorPage\n"
ROUTE_IMPORT_NEW = ROUTE_IMPORT_ANCHOR + "import me.rerere.rikkahub.ui.pages.extensions.workspace.WorkspaceSshEditorPage\n"

ROUTE_SCREEN_ANCHOR = "    @Serializable\n    data class WorkspaceFileEditor(val id: String, val area: String, val path: String) : Screen\n"
ROUTE_SCREEN_NEW = ROUTE_SCREEN_ANCHOR + "\n    @Serializable\n    data class WorkspaceSshEditor(val id: String? = null) : Screen\n"

ROUTE_ENTRY_ANCHOR = "                            entry<Screen.SkillDetail> { key ->\n"
ROUTE_ENTRY_NEW = (
    "                            entry<Screen.WorkspaceSshEditor> { key ->\n"
    "                                WorkspaceSshEditorPage(key.id)\n"
    "                            }\n"
    "\n"
    + ROUTE_ENTRY_ANCHOR
)

# WorkspacePage 修改
# 1) 新建按钮改为弹类型选择
WP_FAB_ANCHOR = "            FloatingActionButton(onClick = { showAddDialog = true }) {"
WP_FAB_NEW = "            FloatingActionButton(onClick = { showTypeSheet = true }) {"

# 2) showAddDialog 前加 showTypeSheet
WP_STATE_ANCHOR = "    var showAddDialog by rememberSaveable { mutableStateOf(false) }\n"
WP_STATE_NEW = "    var showTypeSheet by rememberSaveable { mutableStateOf(false) }\n" + WP_STATE_ANCHOR

# 3) 类型选择 sheet: 插在 showAddDialog 判断之前
WP_SHEET_ANCHOR = "    if (showAddDialog) {\n"
WP_SHEET_NEW = r'''    if (showTypeSheet) {
        androidx.compose.material3.ModalBottomSheet(onDismissRequest = { showTypeSheet = false }) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Text(
                    text = stringResource(R.string.workspace_page_create),
                    style = MaterialTheme.typography.titleMedium,
                )
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable {
                            showTypeSheet = false
                            showAddDialog = true
                        },
                    colors = CustomColors.cardColorsOnSurfaceContainer,
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text(
                            text = stringResource(R.string.workspace_page_type_local),
                            style = MaterialTheme.typography.titleSmall,
                        )
                        Text(
                            text = stringResource(R.string.workspace_page_type_local_desc),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable {
                            showTypeSheet = false
                            navController.navigate(Screen.WorkspaceSshEditor())
                        },
                    colors = CustomColors.cardColorsOnSurfaceContainer,
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text(
                            text = stringResource(R.string.workspace_page_type_ssh),
                            style = MaterialTheme.typography.titleSmall,
                        )
                        Text(
                            text = stringResource(R.string.workspace_page_type_ssh_desc),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
        }
    }

''' + WP_SHEET_ANCHOR

# 4) 列表项副标题: SSH 显示地址, 本地显示原样
WP_SUBTITLE_ANCHOR = "                    Text(\n                        text = stringResource(R.string.workspace_detail_area_files),\n"
WP_SUBTITLE_NEW = r'''                    Text(
                        text = if (workspace.isSsh()) {
                            workspace.sshSettings()?.let { "${it.username}@${it.host}:${it.port}" }
                                ?: stringResource(R.string.workspace_page_type_ssh)
                        } else {
                            stringResource(R.string.workspace_detail_area_files)
                        },
'''

STRINGS_EN = r'''  <string name="workspace_page_type_local">Local workspace</string>
  <string name="workspace_page_type_local_desc">Runs in a Linux sandbox on this device; requires Rootfs</string>
  <string name="workspace_page_type_ssh">SSH remote workspace</string>
  <string name="workspace_page_type_ssh_desc">Connect to your own server over SSH</string>
  <string name="workspace_ssh_editor_not_found">Workspace not found</string>
  <string name="workspace_ssh_editor_missing_fields">Host, port and username are required</string>
  <string name="workspace_ssh_editor_missing_remote_dir">Remote directory is required</string>
  <string name="workspace_ssh_editor_save_failed">Save failed</string>
  <string name="workspace_ssh_editor_title_new">New SSH workspace</string>
  <string name="workspace_ssh_editor_title_edit">Edit SSH workspace</string>
  <string name="workspace_ssh_editor_save">Save</string>
  <string name="workspace_ssh_editor_basic">Basic</string>
  <string name="workspace_ssh_editor_name">Name</string>
  <string name="workspace_ssh_editor_name_placeholder">My server</string>
  <string name="workspace_ssh_editor_connection">Connection</string>
  <string name="workspace_ssh_editor_host">Host</string>
  <string name="workspace_ssh_editor_host_placeholder">example.com or 192.168.1.1</string>
  <string name="workspace_ssh_editor_port">Port</string>
  <string name="workspace_ssh_editor_username">Username</string>
  <string name="workspace_ssh_editor_auth">Authentication</string>
  <string name="workspace_ssh_editor_password">Password</string>
  <string name="workspace_ssh_editor_private_key">Private key</string>
  <string name="workspace_ssh_editor_saved_keep">(saved; leave empty to keep)</string>
  <string name="workspace_ssh_editor_import_key">Import key file</string>
  <string name="workspace_ssh_editor_passphrase">Passphrase</string>
  <string name="workspace_ssh_editor_passphrase_placeholder">Optional, if the key is encrypted</string>
  <string name="workspace_ssh_editor_working_dir">Working directory</string>
  <string name="workspace_ssh_editor_remote_dir">Remote directory</string>
  <string name="workspace_ssh_editor_security">Security</string>
  <string name="workspace_ssh_editor_host_key">Host key</string>
  <string name="workspace_ssh_editor_host_key_unconfirmed">Not confirmed yet. Test the connection to fetch and confirm it.</string>
  <string name="workspace_ssh_editor_connecting">Connecting…</string>
  <string name="workspace_ssh_editor_test">Test connection</string>
  <string name="workspace_ssh_editor_connected">Connected</string>
  <string name="workspace_ssh_editor_shell">Shell</string>
  <string name="workspace_ssh_editor_home_dir">Home: %1$s</string>
  <string name="workspace_ssh_editor_dir_missing">Directory does not exist: %1$s</string>
  <string name="workspace_ssh_editor_host_key_changed">Host key changed</string>
  <string name="workspace_ssh_editor_host_key_confirm">Confirm host key</string>
  <string name="workspace_ssh_editor_host_key_changed_message">The host key of %1$s differs from the saved one. This could be a man-in-the-middle attack, or the server was reinstalled.</string>
  <string name="workspace_ssh_editor_host_key_first_message">First connection to %1$s. Verify the fingerprint with the server administrator, e.g. by running %2$s on the server.</string>
  <string name="workspace_ssh_editor_trust_new_key">Trust new key</string>
  <string name="workspace_ssh_editor_trust_continue">Trust and continue</string>
  <string name="workspace_ssh_editor_connect_failed">Connection failed</string>
  <string name="workspace_ssh_editor_error">Error</string>
  <string name="workspace_ssh_editor_save_anyway_message">%1$s\n\nSave this configuration anyway?</string>
  <string name="workspace_ssh_editor_save_anyway">Save anyway</string>
'''

STRINGS_ZH = r'''  <string name="workspace_page_type_local">本地工作区</string>
  <string name="workspace_page_type_local_desc">在本机的 Linux 沙箱里运行，需要安装 Rootfs</string>
  <string name="workspace_page_type_ssh">SSH 远程工作区</string>
  <string name="workspace_page_type_ssh_desc">通过 SSH 连接你自己的服务器</string>
  <string name="workspace_ssh_editor_not_found">工作区不存在</string>
  <string name="workspace_ssh_editor_missing_fields">请填写主机、端口和用户名</string>
  <string name="workspace_ssh_editor_missing_remote_dir">请填写远程工作目录</string>
  <string name="workspace_ssh_editor_save_failed">保存失败</string>
  <string name="workspace_ssh_editor_title_new">新建 SSH 工作区</string>
  <string name="workspace_ssh_editor_title_edit">编辑 SSH 工作区</string>
  <string name="workspace_ssh_editor_save">保存</string>
  <string name="workspace_ssh_editor_basic">基本信息</string>
  <string name="workspace_ssh_editor_name">名称</string>
  <string name="workspace_ssh_editor_name_placeholder">我的服务器</string>
  <string name="workspace_ssh_editor_connection">连接</string>
  <string name="workspace_ssh_editor_host">主机</string>
  <string name="workspace_ssh_editor_host_placeholder">example.com 或 192.168.1.1</string>
  <string name="workspace_ssh_editor_port">端口</string>
  <string name="workspace_ssh_editor_username">用户名</string>
  <string name="workspace_ssh_editor_auth">认证方式</string>
  <string name="workspace_ssh_editor_password">密码</string>
  <string name="workspace_ssh_editor_private_key">私钥</string>
  <string name="workspace_ssh_editor_saved_keep">（已保存，留空则沿用）</string>
  <string name="workspace_ssh_editor_import_key">导入私钥文件</string>
  <string name="workspace_ssh_editor_passphrase">私钥口令</string>
  <string name="workspace_ssh_editor_passphrase_placeholder">可选，私钥加密时填写</string>
  <string name="workspace_ssh_editor_working_dir">工作目录</string>
  <string name="workspace_ssh_editor_remote_dir">远程目录</string>
  <string name="workspace_ssh_editor_security">安全</string>
  <string name="workspace_ssh_editor_host_key">主机密钥</string>
  <string name="workspace_ssh_editor_host_key_unconfirmed">尚未确认。测试连接以获取并确认指纹。</string>
  <string name="workspace_ssh_editor_connecting">连接中…</string>
  <string name="workspace_ssh_editor_test">测试连接</string>
  <string name="workspace_ssh_editor_connected">已连接</string>
  <string name="workspace_ssh_editor_shell">Shell</string>
  <string name="workspace_ssh_editor_home_dir">主目录：%1$s</string>
  <string name="workspace_ssh_editor_dir_missing">目录不存在：%1$s</string>
  <string name="workspace_ssh_editor_host_key_changed">主机密钥已变化</string>
  <string name="workspace_ssh_editor_host_key_confirm">确认主机密钥</string>
  <string name="workspace_ssh_editor_host_key_changed_message">%1$s 的主机密钥与已保存的不一致。可能是中间人攻击，也可能是服务器重装过。</string>
  <string name="workspace_ssh_editor_host_key_first_message">首次连接 %1$s。请与服务器管理员核对指纹，例如在服务器上运行 %2$s。</string>
  <string name="workspace_ssh_editor_trust_new_key">信任新密钥</string>
  <string name="workspace_ssh_editor_trust_continue">信任并继续</string>
  <string name="workspace_ssh_editor_connect_failed">连接失败</string>
  <string name="workspace_ssh_editor_error">错误</string>
  <string name="workspace_ssh_editor_save_anyway_message">%1$s\n\n仍然保存这份配置吗？</string>
  <string name="workspace_ssh_editor_save_anyway">仍然保存</string>
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

    # RouteActivity
    route_path = "app/src/main/java/me/rerere/rikkahub/RouteActivity.kt"
    patch(route_path, [
        ("route-import", ROUTE_IMPORT_ANCHOR, ROUTE_IMPORT_NEW),
        ("route-screen", ROUTE_SCREEN_ANCHOR, ROUTE_SCREEN_NEW),
        ("route-entry", ROUTE_ENTRY_ANCHOR, ROUTE_ENTRY_NEW),
    ], diag)

    # WorkspacePage
    wp_path = "app/src/main/java/me/rerere/rikkahub/ui/pages/extensions/workspace/WorkspacePage.kt"
    patch(wp_path, [
        ("wp-fab", WP_FAB_ANCHOR, WP_FAB_NEW),
        ("wp-state", WP_STATE_ANCHOR, WP_STATE_NEW),
        ("wp-sheet", WP_SHEET_ANCHOR, WP_SHEET_NEW),
        ("wp-subtitle", WP_SUBTITLE_ANCHOR, WP_SUBTITLE_NEW),
    ], diag)

    # strings
    for path, block, label in (
        ("app/src/main/res/values/strings.xml", STRINGS_EN, "strings-en"),
        ("app/src/main/res/values-zh/strings.xml", STRINGS_ZH, "strings-zh"),
    ):
        text = read(path)
        if 'name="workspace_page_type_local"' in text:
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
    route = read(route_path)
    if "WorkspaceSshEditor" not in route or "WorkspaceSshEditorPage" not in route:
        diag.append("route:MISS")
        ok = False
    wp = read(wp_path)
    if "showTypeSheet" not in wp or "Screen.WorkspaceSshEditor()" not in wp:
        diag.append("wp:MISS")
        ok = False
    if wp.count("showAddDialog = true") != 1:
        # 新建对话框应该只在类型 sheet 的本地分支里出现一次
        diag.append("wp:addDialog-count=" + str(wp.count("showAddDialog = true")))
        ok = False

    diag.append("RESULT:" + ("OK" if ok else "FAIL"))
    with open(os.path.join(ROOT, DIAG), "w", encoding="utf-8") as f:
        f.write("\n".join(diag) + "\n")
    log(" | ".join(diag))
    if not ok:
        print("::error title=batch352b::" + " | ".join(diag))


main()
