#!/usr/bin/env python3
# rhRemote356d: 修 356a 的 import 遗漏 —— Repository 用了 SshJumpHostDraft/SshJumpHostSettings
# 短名却只 import 了 SshJumpHostConfig, 导致 L523-525 Unresolved + L107/119/135 类型推断连锁失败。
# v2: 追加结构自检(锚点/函数/import 计数), 同时触发完整重建验证 346-356d 全链。
import os

MARK = "rhRemote356d"
DIAG = "ci_diag_batch356d_remote.txt"
ROOT = os.environ.get("GITHUB_WORKSPACE", os.getcwd())

ANCHOR = "import me.rerere.workspace.ssh.SshJumpHostConfig\n"
ADD = "import me.rerere.rikkahub.data.model.SshJumpHostDraft\nimport me.rerere.rikkahub.data.model.SshJumpHostSettings\n"

path = "app/src/main/java/me/rerere/rikkahub/data/repository/WorkspaceRepository.kt"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

diag = []
ok = True
if "import me.rerere.rikkahub.data.model.SshJumpHostSettings" in text:
    diag.append("import:already")
else:
    count = text.count(ANCHOR)
    if count != 1:
        diag.append("ANCHOR-MISMATCH(" + str(count) + ")")
        ok = False
    else:
        text = text.replace(ANCHOR, ANCHOR + ADD, 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        diag.append("import:added")

# 自检: 三个跳板类型 import + 现有 SshWorkspaceDraft/Settings import 必须全部在
for needle in (
    "import me.rerere.rikkahub.data.model.SshWorkspaceDraft",
    "import me.rerere.rikkahub.data.model.SshWorkspaceSettings",
    "import me.rerere.rikkahub.data.model.SshJumpHostDraft",
    "import me.rerere.rikkahub.data.model.SshJumpHostSettings",
    "import me.rerere.workspace.ssh.SshJumpHostConfig",
):
    if needle not in text:
        diag.append("MISS:" + needle)
        ok = False

# v2 结构自检: 跳板转换函数与消费点必须真实存在, 防止"import 加了但功能体不在"的假绿
for needle in (
    "private fun SshJumpHostDraft.toSettings(previous: SshJumpHostSettings?): SshJumpHostSettings",
    "jumpHost = jumpHost?.toSettings(previous?.jumpHost)",
    "jumpHost = jumpHost?.let { jump ->",
    "suspend fun probeSsh(id: String?, draft: SshWorkspaceDraft): SshProbeResult",
    "suspend fun saveSsh(id: String?, draft: SshWorkspaceDraft): WorkspaceEntity",
    "suspend fun shell(id: String): String = readFromBackend(id) { it.shell() }",
):
    if needle not in text:
        diag.append("STRUCT-MISS:" + needle[:48])
        ok = False

# 括号平衡整文件校验
left = text.count("(")
right = text.count(")")
diag.append("balance:" + str(left) + "/" + str(right))
if left != right:
    ok = False

diag.append("lines:" + str(text.count("\n") + 1))
diag.append("RESULT:" + ("OK" if ok else "FAIL"))
with open(os.path.join(ROOT, DIAG), "w", encoding="utf-8") as f:
    f.write("\n".join(diag) + "\n")
print(" | ".join(diag))
if not ok:
    print("::error title=batch356d::" + " | ".join(diag))
