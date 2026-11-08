#!/usr/bin/env python3
# rhRemote355f: 死功能审查修复 —— SSH 工作区详情页隐藏 Rootfs 安装卡
# 353 后 WorkspaceBasicPage 无条件渲染 WorkspaceInstallCard; SSH 点"安装 Rootfs"会调
# repository.installRootfs → require(capabilities().rootfs) 抛异常。官方 SSH 工作区隐藏 Rootfs 相关。
import os

DIAG = "ci_diag_batch355f_remote.txt"
ROOT = os.environ.get("GITHUB_WORKSPACE", os.getcwd())

path = "app/src/main/java/me/rerere/rikkahub/ui/pages/extensions/workspace/WorkspaceDetailPage.kt"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

diag = []
ok = True

ANCHOR = """        item {
            // rhWsInstallCard: Rootfs 安装卡片(Linux 环境)
            WorkspaceInstallCard(workspace = workspace)
        }
"""
REPL = """        if (workspace?.capabilities()?.rootfs != false) {
            item {
                // rhWsInstallCard: Rootfs 安装卡片(Linux 环境); SSH 工作区没有 rootfs, 不显示
                WorkspaceInstallCard(workspace = workspace)
            }
        }
"""

if "if (workspace?.capabilities()?.rootfs != false) {" in text:
    diag.append("install-gate:already")
elif text.count(ANCHOR) == 1:
    text = text.replace(ANCHOR, REPL, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    diag.append("install-gate:ok")
else:
    diag.append("install-gate:ANCHOR-MISMATCH(" + str(text.count(ANCHOR)) + ")")
    ok = False

# 自检: 卡仍在(只加门控不删功能) + 门控表达式正确 + capabilities 可解析(WorkspaceEntity 有该方法, 349 加的)
if "WorkspaceInstallCard(workspace = workspace)" not in text:
    diag.append("MISS:install-card-removed")
    ok = False
if "capabilities()?.rootfs != false" not in text:
    diag.append("MISS:gate")
    ok = False
# 门控必须包住整个 item（括号配平）
seg_start = text.find("if (workspace?.capabilities()?.rootfs != false) {")
if seg_start >= 0:
    depth = 0
    end = -1
    for i in range(seg_start, min(len(text), seg_start + 800)):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end < 0 or "WorkspaceInstallCard" not in text[seg_start:end]:
        diag.append("BRACE:gate-not-wrapping-card")
        ok = False
    else:
        diag.append("BRACE:ok")

diag.append("RESULT:" + ("OK" if ok else "FAIL"))
with open(os.path.join(ROOT, DIAG), "w", encoding="utf-8") as f:
    f.write("\n".join(diag) + "\n")
print(" | ".join(diag))
if not ok:
    print("::error title=batch355f::" + " | ".join(diag))
