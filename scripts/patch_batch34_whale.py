#!/usr/bin/env python3
"""batch34: 从 Ayuilos/Miffan (AGPL-3.0) 拉取鲸鱼渲染器数据文件并适配包名。

原因：WhaleGirlColorRegions.kt (30KB) 与 WhaleGirlStaticReview.kt (67KB,
内含 StaticWhaleContours 全部轮廓数据) 体量太大，无法通过 MCP 推送内嵌，
改由 CI runner 直接从上游拉取（runner 可访问 raw.githubusercontent.com）。

幂等：每次运行重新拉取覆盖。失败会 ::error 并 exit 1，绝不静默跳过。
"""
import sys
import urllib.request
from pathlib import Path

FILES = [
    (
        "app/src/main/java/me/ayuilos/miffan/ui/components/ui/WhaleGirlColorRegions.kt",
        "app/src/main/java/me/rerere/rikkahub/ui/components/ui/WhaleGirlColorRegions.kt",
    ),
    (
        "app/src/main/java/me/ayuilos/miffan/ui/components/ui/WhaleGirlStaticReview.kt",
        "app/src/main/java/me/rerere/rikkahub/ui/components/ui/WhaleGirlStaticReview.kt",
    ),
]


def fetch(path: str) -> str:
    url = f"https://raw.githubusercontent.com/Ayuilos/Miffan/master/{path}"
    req = urllib.request.Request(url, headers={"User-Agent": "rikkahub-ci"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8")


def main() -> None:
    for src, dst in FILES:
        content = fetch(src)
        content = content.replace("me.ayuilos.miffan", "me.rerere.rikkahub")
        if "me.ayuilos" in content:
            print(f"::error file={dst}::residual me.ayuilos reference after rewrite ({src})")
            sys.exit(1)
        out = Path(dst)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
        print(f"[batch34] fetched {src} -> {dst} ({len(content)} bytes)")

    # 删除占位 Stub，避免与 WhaleGirlStaticReview.kt 内的 StaticWhaleContours 重复定义
    stub = Path("app/src/main/java/me/rerere/rikkahub/ui/components/ui/StaticWhaleContours.kt")
    if stub.exists():
        stub.unlink()
        print("[batch34] removed stub StaticWhaleContours.kt (superseded by StaticReview)")

    print("[batch34] OK")


if __name__ == "__main__":
    main()
