from pathlib import Path

ROOT = Path.cwd()

def fail(path, msg):
    print(f"::error file={path}::batch28 {msg[:1400]}")
    raise SystemExit(1)

# ============================================================
# 任务 8：提示词清理（删除冗余系统提示词）
# 需要先定位 system prompt 设置的代码位置，可能在 Assistant 数据结构或设置页。
# 从任务清单"任务8 提示词清理"推测是删掉某些默认提示词或冗余字段。
# 保守：暂时只加 marker，待侦察后补实际改动。
# ============================================================

P1 = "app/src/main/java/me/rerere/rikkahub/data/model/Assistant.kt"
if not (ROOT / P1).exists():
    print("batch28: Assistant.kt not found, skipping (need reconnaissance)")
else:
    t1 = (ROOT / P1).read_text(encoding="utf-8")
    if "batch28 marker" in t1:
        print("batch28: Assistant already patched")
    else:
        # 占位 marker
        A = "package me.rerere.rikkahub.data.model\n"
        B = (
            "package me.rerere.rikkahub.data.model\n"
            "// batch28 TODO: 清理冗余系统提示词（任务8）\n"
        )
        if t1.count(A) != 1:
            fail(P1, f"package anchor count={t1.count(A)}")
        t1 = t1.replace(A, B, 1)
        (ROOT / P1).write_text(t1, encoding="utf-8")
        print("batch28: Prompt cleanup marker added (actual cleanup TODO)")
