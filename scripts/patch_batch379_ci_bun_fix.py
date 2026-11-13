#!/usr/bin/env python3
# rhCiFix379: 修 CI 的 bun 安装 —— 504 让整条链断掉 5 天
#
# 事实链（已核实）：
#   · run663（378）失败：setup-bun 步骤 08:52:25→08:52:56（31 秒），annotations
#     `Error: Unexpected HTTP response: 504`（.github 第 16 行 = setup-bun 步骤）
#   · run664（366 v2）失败：08:55:45→08:56:56（71 秒），同样 504
#   · 此后 5 天没有任何成功构建：release 列表最新仍是 run660（08:01:42），
#     fix/batch1 最后一条提交就是 11-08 08:55:43
#   ⇒ CI 从 11-08 08:52 起一直处于「不可用」状态，375/377/378/366v2 从未被执行过。
#
# 根因：`oven-sh/setup-bun@v2` 在下载 bun 时打到 GitHub release CDN，偶发 504（网关超时）。
# 这是 actions 步骤，失败即整条 job 失败，后面 patch/compile/R8 全 skipped。
#
# 修法（只加容错，不改构建逻辑）：
#   1) setup-bun 加 `continue-on-error: true`，让它失败也不阻断
#   2) 新增 "Ensure bun (fallbacks)" 步骤，按顺序兜底：
#        a. 已有 bun（setup-bun 其实成功了） → 直接过
#        b. 官方脚本 https://bun.sh/install（重试 3 次，每次 curl 自带 3 次重试）
#        c. npm 全局装 bun（npm 包自带平台二进制，不依赖 GitHub release CDN）
#        d. 三条路都失败才 ::error + exit 1
#   3) 成功后把 ~/.bun/bin 写进 GITHUB_PATH，后续步骤照常可用
#
# 注意：本脚本改的是 workflow YAML，不是 Kotlin；sed warn-only 只改 scripts/patch_*.py，
# 不影响这里的 shell 退出码。

import os
import sys

REPO = os.getcwd()
WORKFLOW = os.path.join(REPO, ".github", "workflows", "build-apk.yml")
DIAG = os.path.join(REPO, "ci_diag_batch379_ci_bun_fix.txt")

OLD = (
    '      # :web needs bun (installWebUiDeps) and pnpm (buildWebUi on Linux).\n'
    '      - uses: oven-sh/setup-bun@v2\n'
    '        with:\n'
    '          bun-version: latest\n'
)

NEW = (
    '      # :web needs bun (installWebUiDeps) and pnpm (buildWebUi on Linux).\n'
    '      # rhCiFix379: setup-bun 的 release 下载偶发 504（网关超时），单次失败会让整条 job\n'
    '      # 失败、后面 patch/compile/R8 全部 skipped。改成主路径失败也继续，再兜底两种。\n'
    '      - name: Setup bun\n'
    '        id: setup_bun\n'
    '        uses: oven-sh/setup-bun@v2\n'
    '        with:\n'
    '          bun-version: latest\n'
    '        continue-on-error: true\n'
    '\n'
    '      - name: Ensure bun (fallbacks)\n'
    '        run: |\n'
    '          set -uo pipefail\n'
    '          if command -v bun >/dev/null 2>&1; then\n'
    '            echo "bun ready: $(bun --version)"\n'
    '            exit 0\n'
    '          fi\n'
    '          echo "::warning::setup-bun did not provide bun, trying fallbacks"\n'
    '          ok=0\n'
    '          for i in 1 2 3; do\n'
    '            if curl -fsSL --retry 3 --retry-delay 5 https://bun.sh/install | bash; then\n'
    '              ok=1\n'
    '              break\n'
    '            fi\n'
    '            echo "bun.sh attempt $i failed"\n'
    '            sleep 8\n'
    '          done\n'
    '          if [ "$ok" -eq 1 ] && [ -x "$HOME/.bun/bin/bun" ]; then\n'
    '            echo "BUN_INSTALL=$HOME/.bun" >> "$GITHUB_ENV"\n'
    '            echo "$HOME/.bun/bin" >> "$GITHUB_PATH"\n'
    '            echo "bun installed via bun.sh"\n'
    '            exit 0\n'
    '          fi\n'
    '          echo "::warning::bun.sh install failed, trying npm registry"\n'
    '          if npm install -g bun; then\n'
    '            echo "bun installed via npm"\n'
    '            exit 0\n'
    '          fi\n'
    '          echo "::error::bun installation failed through all fallbacks"\n'
    '          exit 1\n'
)

OUT = []


def log(line):
    OUT.append(line)
    print(line)


def main():
    failures = []

    if not os.path.isfile(WORKFLOW):
        log("missing-file:workflow")
        with open(DIAG, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("missing-file:workflow\nRESULT:FAIL\n")
        sys.exit(1)

    with open(WORKFLOW, "r", encoding="utf-8") as handle:
        text = handle.read()

    if "rhCiFix379" in text:
        log("already:fix")
    else:
        hits = text.count(OLD)
        log("anchor:" + str(hits))
        if hits != 1:
            failures.append("anchor:" + str(hits))
        else:
            text = text.replace(OLD, NEW)
            log("wrote:fix")

    with open(WORKFLOW, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    log("file-size:" + str(len(text)))

    # 复核
    with open(WORKFLOW, "r", encoding="utf-8") as handle:
        final = handle.read()
    checks = [
        ("continue-on-error", "continue-on-error: true" in final),
        ("fallback-step", "Ensure bun (fallbacks)" in final),
        ("bun-sh-install", "https://bun.sh/install" in final),
        ("npm-fallback", "npm install -g bun" in final),
        ("path-export", 'echo "$HOME/.bun/bin" >> "$GITHUB_PATH"' in final),
        ("pnpm-step-kept", "Install pnpm (used by :web:buildWebUi on Linux)" in final),
        ("setup-bun-kept", "oven-sh/setup-bun@v2" in final),
    ]
    for name, ok in checks:
        log("check:" + name + ":" + ("ok" if ok else "FAIL"))
        if not ok:
            failures.append("check:" + name)

    if failures:
        log("RESULT:FAIL")
        log("failures:" + "|".join(failures))
    else:
        log("RESULT:OK")

    with open(DIAG, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(OUT) + "\n")
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()