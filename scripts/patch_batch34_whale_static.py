#!/usr/bin/env python3
# 大肥鱼 B3：从 Ayuilos/Miffan 拉取完整的 WhaleGirlStaticReview.kt（含 StaticWhaleContours
# 67KB 纯路径数据），改包名后覆盖仓库里的占位版 StaticWhaleContours.kt。
# 失败即大声报错退出，保证 CI 不会用不完整轮廓出包。
import pathlib
import sys
import urllib.request

SRC_URL = (
    "https://raw.githubusercontent.com/Ayuilos/Miffan/master/"
    "app/src/main/java/me/ayuilos/miffan/ui/components/ui/WhaleGirlStaticReview.kt"
)
DST = pathlib.Path(
    "app/src/main/java/me/rerere/rikkahub/ui/components/ui/WhaleGirlStaticReview.kt"
)
PLACEHOLDER = pathlib.Path(
    "app/src/main/java/me/rerere/rikkahub/ui/components/ui/StaticWhaleContours.kt"
)


def main() -> int:
    req = urllib.request.Request(SRC_URL, headers={"User-Agent": "rikkahub-ci"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            content = resp.read().decode("utf-8")
    except Exception as exc:  # noqa: BLE001
        print(f"::error file=scripts/patch_batch34_whale_static.py::failed to fetch {SRC_URL}: {exc}")
        return 1

    if "object StaticWhaleContours" not in content:
        print("::error file=scripts/patch_batch34_whale_static.py::StaticWhaleContours not found in downloaded file")
        return 1

    content = content.replace("package me.ayuilos.miffan", "package me.rerere.rikkahub")
    if "me.ayuilos" in content:
        print("::error file=scripts/patch_batch34_whale_static.py::residual me.ayuilos reference after rewrite")
        return 1

    DST.write_text(content, encoding="utf-8")
    if PLACEHOLDER.exists():
        PLACEHOLDER.unlink()
    print(f"whale static contours fetched: {len(content)} bytes -> {DST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
