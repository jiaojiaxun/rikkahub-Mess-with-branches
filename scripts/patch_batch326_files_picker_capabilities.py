"""batch326 — the "文件与工具" sheet duplicated the composer's + entries.

The + menu already offers 拍照 / 照片 / 上传文件 (and video/audio when the
provider supports it). The FilesPicker sheet opened by 「文件与工具」 repeated
exactly those three, wasting the most reachable row.

Replace that row with the two controls that had no home there:
  1) 联网搜索 — switch bound to assistant.enableWebSearch
  2) 思考深度 — the existing ReasoningButton (tavern mode / squeeze / stream /
     reasoning level), so every capability it owns stays reachable.

No new parameters: FilesPicker already receives `assistant`, `state`
(ChatInputState) and `onUpdateAssistant`. Attachment entry points remain in the
＋ menu only.
"""

import os

ROOT = os.getcwd()
TARGET = os.path.join(
    ROOT,
    "app/src/main/java/me/rerere/rikkahub/ui/components/ai/FilesPicker.kt",
)
DIAG = os.path.join(ROOT, "ci_diag_batch326_files_picker.txt")

log = []


def note(m):
    print(m)
    log.append(str(m))


def bal(t):
    return (t.count('{') - t.count('}'), t.count('(') - t.count(')'))


OLD = '''        FlowRow(
            modifier = Modifier.fillMaxWidth().wrapContentWidth(Alignment.CenterHorizontally),
            horizontalArrangement = Arrangement.spacedBy(16.dp, Alignment.Start),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            TakePicButton(onLaunchCamera = onTakePic)

            ImagePickButton(onClick = onPickImage)

            if (provider != null && provider is ProviderSetting.Google) {
                VideoPickButton(onClick = onPickVideo)

                AudioPickButton(onClick = onPickAudio)
            }

            FilePickButton(onClick = onPickFile)
        }'''

NEW = '''        // rhDsh326: attachments live in the composer's + menu; this sheet hosts
        // the two capability controls instead of repeating them.
        ListItem(
            leadingContent = {
                Icon(
                    imageVector = HugeIcons.Search01,
                    contentDescription = null,
                )
            },
            headlineContent = { Text("联网搜索") },
            supportingContent = { Text("开启后本轮使用搜索工具") },
            trailingContent = {
                Switch(
                    checked = assistant.enableWebSearch,
                    onCheckedChange = { enabled ->
                        onUpdateAssistant(assistant.copy(enableWebSearch = enabled))
                    },
                )
            },
            colors = ListItemDefaults.colors(
                containerColor = MaterialTheme.colorScheme.surfaceContainer
            ),
            modifier = Modifier
                .clip(MaterialTheme.shapes.large)
                .clickable {
                    onUpdateAssistant(assistant.copy(enableWebSearch = !assistant.enableWebSearch))
                },
        )

        ListItem(
            leadingContent = {
                Icon(
                    imageVector = HugeIcons.Brain02,
                    contentDescription = null,
                )
            },
            headlineContent = { Text("思考深度") },
            supportingContent = { Text("思考强度 · 流式输出 · 酒馆模式") },
            trailingContent = {
                ReasoningButton(
                    tavernMode = state.tavernMode,
                    onUpdateTavernMode = state.onToggleTavernMode,
                    squeezeTokenEnabled = state.squeezeTokenEnabled,
                    onUpdateSqueezeToken = state.onToggleSqueezeToken,
                    reasoningLevel = assistant.reasoningLevel,
                    onUpdateReasoningLevel = {
                        onUpdateAssistant(assistant.copy(reasoningLevel = it))
                    },
                    streamOutput = assistant.streamOutput,
                    onUpdateStreamOutput = { enabled ->
                        onUpdateAssistant(assistant.copy(streamOutput = enabled))
                    },
                    onlyIcon = true,
                )
            },
            colors = ListItemDefaults.colors(
                containerColor = MaterialTheme.colorScheme.surfaceContainer
            ),
            modifier = Modifier.clip(MaterialTheme.shapes.large),
        )'''


def main():
    src = open(TARGET, "r", encoding="utf-8").read()
    before = bal(src)

    if "rhDsh326" in src:
        note("already applied, skip")
        return

    # imports
    imp1 = "import androidx.compose.material3.Surface\n"
    if src.count(imp1) != 1:
        raise SystemExit("import Surface anchor count=" + str(src.count(imp1)))
    src = src.replace(imp1, imp1 + "import androidx.compose.material3.Switch\n")

    imp2 = "import me.rerere.hugeicons.stroke.Camera01\n"
    if src.count(imp2) != 1:
        raise SystemExit("import Camera01 anchor count=" + str(src.count(imp2)))
    src = src.replace(
        imp2,
        imp2
        + "import me.rerere.hugeicons.stroke.Brain02\n"
        + "import me.rerere.hugeicons.stroke.Search01\n",
    )

    count = src.count(OLD)
    note("flowrow anchor count=" + str(count))
    if count != 1:
        raise SystemExit("flowrow anchor count=" + str(count))

    src = src.replace(OLD, NEW)

    after = bal(src)
    note("balance " + str(before) + " -> " + str(after))
    if after != before:
        raise SystemExit("balance drift")

    for must in ["联网搜索", "思考深度", "ReasoningButton(", "Switch(", "rhDsh326"]:
        if must not in src:
            raise SystemExit("missing " + must)
    if "TakePicButton(onLaunchCamera = onTakePic)" in src:
        raise SystemExit("attachment row still present")

    open(TARGET, "w", encoding="utf-8").write(src)
    note("files picker rewritten")
    print("::error title=rhDsh326::OK attachments deduped, search + reasoning hosted")
    open(DIAG, "w", encoding="utf-8").write("\n".join(log) + "\n")


main()