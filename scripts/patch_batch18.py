from pathlib import Path

ROOT = Path.cwd()


# --- ChatMessageTools.kt: default collapsed + single-line titles ---
tools = ROOT / "app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessageTools.kt"
text = tools.read_text(encoding="utf-8")

old_state = "var expanded by remember { mutableStateOf(true) }"
state_count = text.count(old_state)
if state_count != 1:
    raise SystemExit(f"ChatMessageTools.kt: expanded-state anchor count {state_count} != 1")
text = text.replace(old_state, "var expanded by remember { mutableStateOf(false) }", 1)

old_max = "maxLines = 2,"
max_count = text.count(old_max)
if max_count != 3:
    raise SystemExit(f"ChatMessageTools.kt: maxLines anchor count {max_count} != 3")
text = text.replace(old_max, "maxLines = 1,")

tools.write_text(text, encoding="utf-8")


# --- ChainOfThought.kt: collapsed step indicator becomes a right chevron ---
cot = ROOT / "app/src/main/java/me/rerere/rikkahub/ui/components/ui/ChainOfThought.kt"
cot_text = cot.read_text(encoding="utf-8")

old_indicator = """                } else if (hasContent) {
                    Icon(
                        imageVector = if (expanded) HugeIcons.ArrowUp01 else HugeIcons.ArrowDown01,"""
indicator_count = cot_text.count(old_indicator)
if indicator_count != 1:
    raise SystemExit(f"ChainOfThought.kt: step-indicator anchor count {indicator_count} != 1")
cot_text = cot_text.replace(
    old_indicator,
    """                } else if (hasContent) {
                    Icon(
                        imageVector = if (expanded) HugeIcons.ArrowUp01 else HugeIcons.ArrowRight01,""",
    1,
)

cot.write_text(cot_text, encoding="utf-8")

print("batch18: tool steps default collapsed + single-line titles + right-arrow indicator")
