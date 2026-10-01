#!/usr/bin/env python3
"""Batch-5 build-time patches: register the generate_image local tool.

Same convention as the other batches: anchored, idempotent, loud (::error + exit 1).
1. LocalTools.kt: LocalToolOption.ImageGeneration ("image_generation") + registration.
2. AssistantLocalToolPage.kt: switch for it.
"""
import re
import sys
from pathlib import Path

FAILURES = []
LOCAL_TOOLS = "app/src/main/java/me/rerere/rikkahub/data/ai/tools/LocalTools.kt"
TOOL_PAGE = "app/src/main/java/me/rerere/rikkahub/ui/pages/assistant/detail/AssistantLocalToolPage.kt"


def fail(path, msg):
    print(f"::error file={path}::batch5 patch failed: {msg}", flush=True)
    FAILURES.append(f"{path}: {msg}")


def patch(path, marker, transform):
    p = Path(path)
    if not p.exists():
        fail(path, "file not found")
        return
    src = p.read_text(encoding="utf-8")
    if marker in src:
        print(f"already patched ({marker}): {path}", flush=True)
        return
    out = transform(src)
    if not out or out == src or marker not in out:
        fail(path, f"anchor not found for {marker}")
        return
    p.write_text(out, encoding="utf-8")
    print(f"patched ({marker}): {path}", flush=True)


ENUM_RE = re.compile(
    r'(?P<indent>[ \t]*)@Serializable\s+@SerialName\("archive"\)\s+'
    r'data object Archive\s*:\s*LocalToolOption\(\)'
)
TOOLS_RE = re.compile(r"(?P<indent>[ \t]*)//[ \t]*Centralised opt-in to needsApproval\.")
PAGE_RE = re.compile(
    r"(?P<indent>[ \t]*)item\(\s*headlineContent = \{\s*"
    r"Text\(stringResource\(R\.string\.assistant_page_local_tools_javascript_engine_title\)\)"
)


def t_enum(src):
    m = ENUM_RE.search(src)
    if not m:
        return None
    ind = m.group("indent")
    extra = f'\n{ind}@Serializable @SerialName("image_generation") data object ImageGeneration : LocalToolOption()'
    return src[: m.end()] + extra + src[m.end():]


def t_tools(src):
    m = TOOLS_RE.search(src)
    if not m:
        return None
    ind = m.group("indent")
    block = (
        f"{ind}if (options.contains(LocalToolOption.ImageGeneration)) {{\n"
        f"{ind}    tools.add(me.rerere.rikkahub.data.ai.tools.local.createImageGenerationTool())\n"
        f"{ind}}}\n"
    )
    return src[: m.start()] + block + src[m.start():]


def t_page(src):
    m = PAGE_RE.search(src)
    if not m:
        return None
    ind = m.group("indent")
    block = (
        f"{ind}item(\n"
        f'{ind}    headlineContent = {{ Text("图片创作（AI 生成图片）") }},\n'
        f'{ind}    supportingContent = {{ Text("允许 AI 调用 generate_image，用图片创作页选的模型生图并存入图库；每次调用都会产生费用") }},\n'
        f"{ind}    trailingContent = {{\n"
        f"{ind}        Switch(\n"
        f"{ind}            checked = assistant.localTools.contains(LocalToolOption.ImageGeneration),\n"
        f"{ind}            onCheckedChange = {{ toggleLocalTool(LocalToolOption.ImageGeneration, it) }}\n"
        f"{ind}        )\n"
        f"{ind}    }}\n"
        f"{ind})\n"
    )
    return src[: m.start()] + block + src[m.start():]


def main():
    patch(LOCAL_TOOLS, 'SerialName("image_generation")', t_enum)
    patch(LOCAL_TOOLS, "createImageGenerationTool", t_tools)
    patch(TOOL_PAGE, "LocalToolOption.ImageGeneration", t_page)
    if FAILURES:
        print("batch5 patch failures:\n  " + "\n  ".join(FAILURES), flush=True)
        return 1
    print("batch5 patches applied", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
