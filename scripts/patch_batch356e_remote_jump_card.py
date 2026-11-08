#!/usr/bin/env python3
# rhRemote356e: 详情页 SSH 连接卡补跳板机地址行
# 官方详情页条目顺序: 地址 -> 跳板机(如有) -> 远程目录 -> 主机密钥。
# 353 只做了地址/目录/指纹, 这里补跳板机(356c 让数据层有了 jumpHost)。
import os

DIAG = "ci_diag_batch356e_remote.txt"
ROOT = os.environ.get("GITHUB_WORKSPACE", os.getcwd())

path = "app/src/main/java/me/rerere/rikkahub/ui/pages/extensions/workspace/WorkspaceDetailPage.kt"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

diag = []
ok = True

ANCHOR = """                            WorkspaceInfoRow(
                                stringResource(R.string.workspace_ssh_editor_remote_dir),
                                settings.remoteDir,
                            )
"""
REPL = """                            settings.jumpHost?.let { jump ->
                                WorkspaceInfoRow(
                                    stringResource(R.string.workspace_ssh_editor_jump_host),
                                    "${jump.username}@${jump.host}:${jump.port}",
                                )
                            }
                            WorkspaceInfoRow(
                                stringResource(R.string.workspace_ssh_editor_remote_dir),
                                settings.remoteDir,
                            )
"""

if "settings.jumpHost?.let { jump ->" in text:
    diag.append("jump-row:already")
elif text.count(ANCHOR) == 1:
    text = text.replace(ANCHOR, REPL, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    diag.append("jump-row:ok")
else:
    diag.append("jump-row:ANCHOR-MISMATCH(" + str(text.count(ANCHOR)) + ")")
    ok = False

# 自检: 跳板行必须落在 SSH 卡内(地址行之后), 且引用 SshJumpHostSettings 的字段来自 settings
if "settings.jumpHost?.let { jump ->" not in text:
    diag.append("MISS:jump-row")
    ok = False
addr_idx = text.find("stringResource(R.string.workspace_detail_ssh_address)")
jump_idx = text.find("settings.jumpHost?.let { jump ->")
dir_idx = text.find("stringResource(R.string.workspace_ssh_editor_remote_dir),", addr_idx)
if not (addr_idx >= 0 and jump_idx > addr_idx and dir_idx > jump_idx):
    diag.append("ORDER:bad(" + str(addr_idx) + "," + str(jump_idx) + "," + str(dir_idx) + ")")
    ok = False

diag.append("RESULT:" + ("OK" if ok else "FAIL"))
with open(os.path.join(ROOT, DIAG), "w", encoding="utf-8") as f:
    f.write("\n".join(diag) + "\n")
print(" | ".join(diag))
if not ok:
    print("::error title=batch356e::" + " | ".join(diag))
