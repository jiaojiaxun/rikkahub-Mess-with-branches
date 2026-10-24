#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch300: chat top bar bubbles and shared dock width.'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhTopBarBubbles300'
DIAG = 'ci_diag_batch300_topbar.txt'
PAGE = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatPage.kt'
BUBBLES = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/RhChatTopBarBubbles.kt'
PLAN = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/PlanBar.kt'
report = []
failures = []


def note(message):
    report.append(str(message)[:900])


def fail(message):
    failures.append(str(message)[:300])
    report.append('FAIL ' + str(message)[:520])


def balance(text):
    return (text.count('(') - text.count(')')
            + text.count('{') - text.count('}')
            + text.count('[') - text.count(']'))


def ensure_import(lines, line, anchor):
    stripped = [item.strip() for item in lines]
    if line in stripped:
        return True
    hits = [index for index, item in enumerate(stripped) if item == anchor]
    if len(hits) != 1:
        fail('import anchor ' + anchor + ' count=' + str(len(hits)))
        return False
    lines.insert(hits[0] + 1, line)
    return True


BUBBLES_TEXT = '''package me.rerere.rikkahub.ui.pages.chat

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.scaleIn
import androidx.compose.animation.scaleOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.LocalIndication
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import me.rerere.hugeicons.HugeIcons
import me.rerere.hugeicons.stroke.Cancel01
import me.rerere.hugeicons.stroke.LeftToRightListBullet

private val RhBubbleVisualSize = 38.dp
private val RhBubbleHitSize = 48.dp

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun RhChatTopBarBubbleFrame(
    contentDescription: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    onLongClick: (() -> Unit)? = null,
    content: @Composable () -> Unit,
) {
    val interactionSource = remember { MutableInteractionSource() }
    val pressed by interactionSource.collectIsPressedAsState()
    val scale by animateFloatAsState(
        targetValue = if (pressed) 0.90f else 1f,
        animationSpec = spring(
            dampingRatio = Spring.DampingRatioMediumBouncy,
            stiffness = Spring.StiffnessMedium,
        ),
        label = "rhTopBarBubblePress",
    )
    Box(
        modifier = modifier
            .size(RhBubbleHitSize)
            .graphicsLayer {
                scaleX = scale
                scaleY = scale
            }
            .semantics(mergeDescendants = true) {
                this.contentDescription = contentDescription
            }
            .clip(CircleShape)
            .combinedClickable(
                interactionSource = interactionSource,
                indication = LocalIndication.current,
                role = Role.Button,
                onClick = onClick,
                onLongClick = onLongClick,
            ),
        contentAlignment = Alignment.Center,
    ) {
        Surface(
            modifier = Modifier.size(RhBubbleVisualSize),
            shape = CircleShape,
            color = MaterialTheme.colorScheme.surfaceContainerHigh.copy(alpha = 0.84f),
            border = BorderStroke(
                1.dp,
                MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.55f),
            ),
            tonalElevation = 0.dp,
            shadowElevation = 2.dp,
        ) {
            Box(
                modifier = Modifier.fillMaxSize(),
                contentAlignment = Alignment.Center,
            ) {
                content()
            }
        }
    }
}

@Composable
fun RhChatTopBarBubble(
    icon: ImageVector,
    contentDescription: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    onLongClick: (() -> Unit)? = null,
) {
    RhChatTopBarBubbleFrame(
        contentDescription = contentDescription,
        onClick = onClick,
        modifier = modifier,
        onLongClick = onLongClick,
    ) {
        Icon(
            imageVector = icon,
            contentDescription = null,
            modifier = Modifier.size(18.dp),
            tint = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
fun RhChatTopBarPreviewBubble(
    close: Boolean,
    contentDescription: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    RhChatTopBarBubbleFrame(
        contentDescription = contentDescription,
        onClick = onClick,
        modifier = modifier,
    ) {
        AnimatedContent(
            targetState = close,
            transitionSpec = {
                (
                    fadeIn(tween(130))
                        + scaleIn(
                            initialScale = 0.68f,
                            animationSpec = spring(stiffness = Spring.StiffnessMediumLow),
                        )
                    ) togetherWith (
                    fadeOut(tween(90))
                        + scaleOut(targetScale = 0.68f)
                    )
            },
            label = "rhTopBarPreviewGlyph",
        ) { isClose ->
            Icon(
                imageVector = if (isClose) HugeIcons.Cancel01 else HugeIcons.LeftToRightListBullet,
                contentDescription = null,
                modifier = Modifier.size(18.dp),
                tint = if (isClose) {
                    MaterialTheme.colorScheme.primary
                } else {
                    MaterialTheme.colorScheme.onSurfaceVariant
                },
            )
        }
    }
}
'''

TOP_BAR_TEXT = '''@Suppress("UNUSED_PARAMETER")
@Composable
private fun TopBar(
    hazeState: HazeState,
    settings: Settings,
    assistant: Assistant, // rhTopModel260
    currentChatModel: Model?, // rhTopModel260
    conversation: Conversation,
    drawerState: DrawerState,
    bigScreen: Boolean,
    previewMode: Boolean,
    onClickMenu: () -> Unit,
    onNewChat: () -> Unit,
    onUpdateTitle: (String) -> Unit,
    onImportSharedConversation: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    val toaster = LocalToaster.current
    val titleState = useEditState<String> {
        onUpdateTitle(it)
    }
    var showUtilitiesMenu by remember { mutableStateOf(false) }
    val rhHtmlMode = if (me.rerere.rikkahub.data.ai.tools.local.ChatHtmlSkinGlobal.isReady) {
        val rhSkinState by me.rerere.rikkahub.data.ai.tools.local.ChatHtmlSkinGlobal.store
            .stateFlow.collectAsStateWithLifecycle()
        rhSkinState.htmlModeEnabled
    } else {
        false
    }
    val rhHasUserMessage = conversation.messageNodes.any { node ->
        node.messages.any { it.role == me.rerere.ai.core.MessageRole.USER }
    }
    val rhEditTitleWarning = stringResource(R.string.chat_page_edit_title_warning)
    val rhSecondBubbleLabel = stringResource(
        if (rhHtmlMode) R.string.chat_html_exit_native else R.string.accessibility_chat_options
    )

    Box(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .statusBarsPadding()
                .heightIn(min = 58.dp)
                .padding(horizontal = 16.dp, vertical = 7.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            RhChatTopBarBubble(
                icon = HugeIcons.Menu03,
                contentDescription = stringResource(R.string.accessibility_messages),
                onClick = {
                    scope.launch { drawerState.open() }
                },
                onLongClick = {
                    showUtilitiesMenu = true
                },
            )
            Spacer(modifier = Modifier.weight(1f))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                RhChatTopBarPreviewBubble(
                    close = previewMode || rhHtmlMode,
                    contentDescription = rhSecondBubbleLabel,
                    onClick = {
                        if (rhHtmlMode) {
                            me.rerere.rikkahub.data.ai.tools.local.ChatHtmlSkinGlobal.store.setMode(false)
                        } else {
                            onClickMenu()
                        }
                    },
                )
                RhChatTopBarBubble(
                    icon = HugeIcons.MessageAdd01,
                    contentDescription = stringResource(R.string.chat_page_new_message),
                    onClick = onNewChat,
                )
            }
        }

        DropdownMenu(
            expanded = showUtilitiesMenu,
            onDismissRequest = { showUtilitiesMenu = false },
        ) {
            DropdownMenuItem(
                text = { Text(stringResource(R.string.chat_page_edit_title)) },
                onClick = {
                    showUtilitiesMenu = false
                    if (conversation.messageNodes.isNotEmpty()) {
                        titleState.open(conversation.title)
                    } else {
                        toaster.show(rhEditTitleWarning, type = ToastType.Warning)
                    }
                },
            )
            if (!rhHasUserMessage) {
                DropdownMenuItem(
                    text = { Text(stringResource(R.string.chat_page_import_shared_conversation)) },
                    leadingIcon = { Icon(HugeIcons.FileImport, contentDescription = null) },
                    onClick = {
                        showUtilitiesMenu = false
                        onImportSharedConversation()
                    },
                )
            }
            if (rhHtmlMode) {
                DropdownMenuItem(
                    text = { Text(stringResource(R.string.chat_html_exit_native)) },
                    leadingIcon = { Icon(HugeIcons.Cancel01, contentDescription = null) },
                    onClick = {
                        showUtilitiesMenu = false
                        me.rerere.rikkahub.data.ai.tools.local.ChatHtmlSkinGlobal.store.setMode(false)
                    },
                )
            }
        }
    }

    titleState.EditStateContent { title, onUpdate ->
        AlertDialog(
            onDismissRequest = {
                titleState.dismiss()
            },
            title = {
                Text(stringResource(R.string.chat_page_edit_title))
            },
            text = {
                OutlinedTextField(
                    value = title,
                    onValueChange = onUpdate,
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                )
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        titleState.confirm()
                    }
                ) {
                    Text(stringResource(R.string.chat_page_save))
                }
            },
            dismissButton = {
                TextButton(onClick = { titleState.dismiss() }) {
                    Text(stringResource(R.string.chat_page_cancel))
                }
            },
        )
    }
}
'''


def patch_page():
    path = ROOT / PAGE
    text = path.read_text(encoding='utf-8')
    if MARK in text:
        note('page already applied')
        return
    if text.count('private fun TopBar(') != 1:
        fail('TopBar count=' + str(text.count('private fun TopBar(')))
        return
    start = text.find('@Composable' + NL + 'private fun TopBar(')
    if start < 0:
        fail('TopBar annotation anchor missing')
        return
    tail = text[start:]
    if 'titleState.EditStateContent' not in tail:
        fail('TopBar tail shape unexpected')
        return
    if tail.count('@Composable' + NL + 'private fun ') != 1:
        fail('TopBar is not the final private composable')
        return
    prefix = text[:start]
    lines = prefix.split(NL)
    imports = [
        (
            'import androidx.compose.foundation.layout.Arrangement',
            'import androidx.compose.foundation.layout.Column',
        ),
        (
            'import androidx.compose.foundation.layout.Row',
            'import androidx.compose.foundation.layout.Column',
        ),
        (
            'import androidx.compose.foundation.layout.Spacer',
            'import androidx.compose.foundation.layout.size',
        ),
        (
            'import androidx.compose.foundation.layout.heightIn',
            'import androidx.compose.foundation.layout.fillMaxWidth',
        ),
        (
            'import androidx.compose.foundation.layout.statusBarsPadding',
            'import androidx.compose.foundation.layout.size',
        ),
    ]
    for line, anchor in imports:
        if not ensure_import(lines, line, anchor):
            return
    prefix = NL.join(lines)
    new_page = prefix + TOP_BAR_TEXT
    if balance(new_page) != 0:
        fail('new page balance=' + str(balance(new_page)))
        return
    required = [
        'RhChatTopBarBubble(',
        'RhChatTopBarPreviewBubble(',
        'HugeIcons.Menu03',
        'HugeIcons.MessageAdd01',
        'statusBarsPadding()',
        'onLongClick = {',
        'chat_html_exit_native',
        'chat_page_edit_title_warning',
        'titleState.EditStateContent',
    ]
    for token in required:
        if token not in new_page:
            fail('page missing ' + token)
            return
    removed = [
        'chat_page_edit_title_warning)',  # dialog text remains with different punctuation
        'val model = currentChatModel',
        'assistant.name.ifBlank',
        'TopAppBar(',
    ]
    for token in removed:
        if token == 'chat_page_edit_title_warning)':
            continue
        if token in new_page:
            fail('old topbar token still present ' + token)
            return
    if new_page.count('RhChatTopBarBubble(') != 2:
        fail('menu/new bubble call count != 2')
        return
    if new_page.count('RhChatTopBarPreviewBubble(') != 1:
        fail('preview bubble call count != 1')
        return
    path.write_text(new_page, encoding='utf-8')
    note('page OK: title removed, three bubbles, utilities menu')


def patch_plan():
    path = ROOT / PLAN
    text = path.read_text(encoding='utf-8')
    if MARK + '-plan' in text:
        note('plan already applied')
        return
    old_shape = 'shape = RoundedCornerShape(18.dp),'
    new_shape = 'shape = MaterialTheme.shapes.largeIncreased, // ' + MARK + '-plan'
    if text.count(old_shape) != 1:
        fail('PlanBar shape anchor count=' + str(text.count(old_shape)))
        return
    text = text.replace(old_shape, new_shape, 1)
    text = text.replace('animationSpec = tween(200),', 'animationSpec = tween(260),', 1)
    if 'MaterialTheme.shapes.largeIncreased' not in text:
        fail('PlanBar shape not written')
        return
    path.write_text(text, encoding='utf-8')
    note('plan OK: shared radius and calmer spring timing')


def patch_plan_call():
    path = ROOT / PAGE
    text = path.read_text(encoding='utf-8')
    if MARK + '-dock' in text:
        note('dock already applied')
        return
    old = 'me.rerere.rikkahub.ui.components.message.PlanBar(todos = rhPlanTodos)'
    new = (
        'me.rerere.rikkahub.ui.components.message.PlanBar(' + NL
        + '                        todos = rhPlanTodos,' + NL
        + '                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp), // ' + MARK + '-dock' + NL
        + '                    )'
    )
    if text.count(old) != 1:
        fail('PlanBar call anchor count=' + str(text.count(old)))
        return
    text = text.replace(old, new, 1)
    path.write_text(text, encoding='utf-8')
    note('dock OK: PlanBar shares ChatInput horizontal 8dp')


def write_bubbles():
    path = ROOT / BUBBLES
    if path.exists():
        existing = path.read_text(encoding='utf-8')
        if MARK + '-bubbles' in existing:
            note('bubbles already applied')
            return
    text = BUBBLES_TEXT
    if balance(text) != 0:
        fail('bubbles balance=' + str(balance(text)))
        return
    for token in [
        'fun RhChatTopBarBubble(',
        'fun RhChatTopBarPreviewBubble(',
        'combinedClickable(',
        'AnimatedContent(',
        'RhBubbleVisualSize = 38.dp',
        'RhBubbleHitSize = 48.dp',
    ]:
        if token not in text:
            fail('bubbles missing ' + token)
            return
    text = text.replace(
        'package me.rerere.rikkahub.ui.pages.chat' + NL,
        'package me.rerere.rikkahub.ui.pages.chat' + NL + NL + '// ' + MARK + '-bubbles' + NL,
        1,
    )
    path.write_text(text, encoding='utf-8')
    note('bubbles OK: self-contained component file')


def write_diag():
    body = NL.join(report) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
    except Exception as exc:
        print('::error::batch300 diag write failed ' + str(exc)[:200])
    for line in report:
        print('::error::batch300 ' + line)


def main():
    steps = [
        ('bubbles', write_bubbles),
        ('page-topbar', patch_page),
        ('plan-style', patch_plan),
        ('plan-width', patch_plan_call),
    ]
    for name, action in steps:
        try:
            action()
        except Exception as exc:
            fail(name + ' EXCEPTION ' + type(exc).__name__ + ' ' + str(exc)[:300])
    write_diag()
    if failures:
        print('::error::batch300 FAILED count=' + str(len(failures)))
        raise SystemExit(1)
    print('batch300: OK')


main()
