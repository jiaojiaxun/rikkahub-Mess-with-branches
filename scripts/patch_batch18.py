from pathlib import Path

ROOT = Path.cwd()


def patch(path: str, replacements: list[tuple[str, str]]) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    for old, new in replacements:
        count = text.count(old)
        if count != 1:
            raise SystemExit(f"{path}: anchor count {count} != 1: {old[:100]!r}")
        text = text.replace(old, new, 1)
    target.write_text(text, encoding="utf-8")


# ChatMessageTools.kt
#  - ChatMessageToolStep expanded default true -> false. Anchored on its unique sibling
#    state vars because AskUserToolStep declares its own `expanded` var; that one must
#    stay true: a pending ask_user question has to stay visible for the user to answer.
#  - The three tool titles go maxLines 2 -> 1, each anchored on its unique text= expression
#    (the bare `maxLines = 2,` pattern is not unique enough to count on).
patch(
    "app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessageTools.kt",
    [
        (
            """    var showResult by remember { mutableStateOf(false) }
    var showDenyDialog by remember { mutableStateOf(false) }
    var expanded by remember { mutableStateOf(true) }""",
            """    var showResult by remember { mutableStateOf(false) }
    var showDenyDialog by remember { mutableStateOf(false) }
    var expanded by remember { mutableStateOf(false) }""",
        ),
        (
            """                text = stringResource(R.string.chat_message_tool_call_generic, tool.toolName),
                style = MaterialTheme.typography.titleSmall,
                color = MaterialTheme.colorScheme.secondary,
                modifier = Modifier.shimmer(isLoading = loading),
                maxLines = 2,""",
            """                text = stringResource(R.string.chat_message_tool_call_generic, tool.toolName),
                style = MaterialTheme.typography.titleSmall,
                color = MaterialTheme.colorScheme.secondary,
                modifier = Modifier.shimmer(isLoading = loading),
                maxLines = 1,""",
        ),
        (
            """                text = renderer.title(context),
                style = MaterialTheme.typography.titleSmall,
                color = MaterialTheme.colorScheme.secondary,
                modifier = Modifier.shimmer(isLoading = loading),
                maxLines = 2,""",
            """                text = renderer.title(context),
                style = MaterialTheme.typography.titleSmall,
                color = MaterialTheme.colorScheme.secondary,
                modifier = Modifier.shimmer(isLoading = loading),
                maxLines = 1,""",
        ),
        (
            """                    questions.size
                ),
                style = MaterialTheme.typography.titleSmall,
                color = MaterialTheme.colorScheme.secondary,
                modifier = Modifier.shimmer(isLoading = loading),
                maxLines = 2,""",
            """                    questions.size
                ),
                style = MaterialTheme.typography.titleSmall,
                color = MaterialTheme.colorScheme.secondary,
                modifier = Modifier.shimmer(isLoading = loading),
                maxLines = 1,""",
        ),
    ],
)

# ChainOfThought.kt: collapsed step indicator becomes a right chevron (matches the
# reference screenshot's `>`); the expanded state keeps ArrowUp01.
patch(
    "app/src/main/java/me/rerere/rikkahub/ui/components/ui/ChainOfThought.kt",
    [
        (
            """                } else if (hasContent) {
                    Icon(
                        imageVector = if (expanded) HugeIcons.ArrowUp01 else HugeIcons.ArrowDown01,""",
            """                } else if (hasContent) {
                    Icon(
                        imageVector = if (expanded) HugeIcons.ArrowUp01 else HugeIcons.ArrowRight01,""",
        ),
    ],
)

print("batch18: tool steps default collapsed + single-line titles + right-arrow indicator")
