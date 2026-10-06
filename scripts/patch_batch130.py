#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch130: 酒馆模式(会话级) —— 借思考深度面板的位置

需求:每个会话独立开关;开了只留 提示词 + 记忆 + 搜索 + 文件,其余本地工具不注册。
入口借思考深度面板位置,与思考深度数据无关(思考深度改助手级 reasoningLevel,
酒馆开关改会话级 boolean,两套数据互不相干)。

架构决定(第三人称自审后):
- 不碰数据库。Conversation 加列 → 升 Room v35 → 同步 ImportedDatabaseReconciler 的
  EXPECTED_VERSION/IDENTITY_HASH,而 hash 要编译生成 schema json 才有 → 死循环。
  改用 TavernModeStore.kt(独立 SharedPreferences,按会话 ID 存 boolean),零迁移零冲突。
- 不碰 ChatPage.kt(batch70/80/119/patch_chat_page_html 四脚本碰过)。
  接线走 ChatInputState + ChatVM,页面零改动。
- 工具裁剪用 buildList 内 return@buildList 提前结束:加完搜索+文件就返回,
  插件/工作区/技能/MCP 自然跳过,一行都不用包 if。

改动 6 个现有文件 + 1 个新文件(TavernModeStore.kt 由仓库直接提交,本脚本不创建):
 B ChatInputState.kt    tavernMode 状态 + 切换回调
 C ChatVM.kt            init 接线 + setTavernMode
 D ReasoningPicker.kt   ReasoningButton/ReasoningPicker 加参 + Switch
 E ChatInput.kt         从 state 读状态,传参给 ReasoningButton
 F ChatService.kt       buildList 内按会话裁剪工具
 G strings.xml(en) / H strings-zh.xml

五查:
1. import 清单:Switch 用 androidx.compose.material3.Switch(精确行匹配);
   Row/Column/Arrangement/Alignment/Modifier/fillMaxWidth 已在 ReasoningPicker import
2. 同文件冲突:ChatService 被 batch70/95 碰过(锚点在 handleMessageComplete 的 tools
   buildList,batch70/95 碰的是 sendMessage/processedContent,不重叠);
   ChatVM 被 batch72 碰过(仅 handleMessageSend);其余 4 文件无在链脚本触碰
3. 作用域:Switch 在 ModalBottomSheet 的 Column 内;tavernMode 声明在 buildList lambda 顶部
4. 括号配对:插入块均自平衡;return@buildList 不改变配平
5. 函数签名:ReasoningButton/ReasoningPicker/ChatInput 均加带默认值参数,旧调用方兼容

Python 三查:
1. 引号一律 chr() 构造;同一字面量只拼一次
2. Kotlin 串内无换行(无需 KNL);NL 仅拼行
3. helper 先定义后用;锚点找不到即 dump 现场行 + exit(1)
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
D = chr(34)
MARK = 'rhTavernMode'

IS = 'app/src/main/java/me/rerere/rikkahub/ui/hooks/ChatInputState.kt'
VM = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatVM.kt'
RP = 'app/src/main/java/me/rerere/rikkahub/ui/components/ai/ReasoningPicker.kt'
CI = 'app/src/main/java/me/rerere/rikkahub/ui/components/ai/ChatInput.kt'
CS = 'app/src/main/java/me/rerere/rikkahub/service/ChatService.kt'
EN = 'app/src/main/res/values/strings.xml'
ZH = 'app/src/main/res/values-zh/strings.xml'


def fail(path, msg, lines=None, around=-1):
    body = 'batch130 ' + str(msg)
    if lines is not None and 0 <= around < len(lines):
        lo = max(0, around - 3)
        hi = min(len(lines), around + 4)
        ctx = ' || '.join('L' + str(i + 1) + ':' + lines[i].strip()[:100] for i in range(lo, hi))
        body = body + ' || ctx: ' + ctx
    print('::error file=' + path + '::' + body[:1500])
    sys.stdout.flush()
    sys.exit(1)


def ind_of(ln):
    return ln[:len(ln) - len(ln.lstrip())]


def balance(text):
    return (text.count('(') - text.count(')')) + (text.count('{') - text.count('}'))


def find_one(lines, path, needle, label):
    hits = [i for i, ln in enumerate(lines) if needle in ln]
    if len(hits) != 1:
        fail(path, label + ' count=' + str(len(hits)), lines, hits[0] if hits else 0)
    return hits[0]


# ============================================================
# B. ChatInputState.kt —— 加 tavernMode 状态 + 切换回调
# ============================================================
ist = (ROOT / IS).read_text(encoding='utf-8')
if MARK not in ist:
    lines = ist.split(NL)
    bal0 = balance(ist)

    ai = find_one(lines, IS, 'var editingMessage by mutableStateOf<Uuid?>(null)', 'editingMessage field')
    aind = ind_of(lines[ai])
    block = [
        aind + '// ' + MARK + ' (会话级酒馆模式):由 ChatVM 注入,页面无需改动',
        aind + 'var tavernMode by mutableStateOf(false)',
        aind + 'var onToggleTavernMode: ((Boolean) -> Unit)? = null',
    ]
    for j, b in enumerate(block):
        lines.insert(ai + 1 + j, b)

    out = NL.join(lines)
    for need in [
        'var tavernMode by mutableStateOf(false)',
        'var onToggleTavernMode: ((Boolean) -> Unit)? = null',
    ]:
        if need not in out:
            fail(IS, 'selfcheck missing: ' + need, lines, 0)
    if balance(out) != bal0:
        fail(IS, 'balance changed', lines, 0)
    (ROOT / IS).write_text(out, encoding='utf-8')
    print('batch130: ChatInputState OK')
else:
    print('batch130: ChatInputState already applied')


# ============================================================
# C. ChatVM.kt —— init 接线 + setTavernMode
# ============================================================
vm = (ROOT / VM).read_text(encoding='utf-8')
if MARK not in vm:
    lines = vm.split(NL)
    bal0 = balance(vm)

    # C1: init 内接线(插在 addConversationReference 之后)
    ii = find_one(lines, VM, 'chatService.addConversationReference(_conversationId)', 'init anchor')
    iind = ind_of(lines[ii])
    iblock = [
        iind + '// ' + MARK + ': 从独立 Store 读当前会话的酒馆状态,交给输入组件',
        iind + 'inputState.tavernMode = me.rerere.rikkahub.data.datastore.TavernModeStore.isEnabled(context, _conversationId.toString())',
        iind + 'inputState.onToggleTavernMode = { enabled -> setTavernMode(enabled) }',
    ]
    for j, b in enumerate(iblock):
        lines.insert(ii + 1 + j, b)

    # C2: setTavernMode 函数插在 updateConversation 函数之后
    ui = find_one(lines, VM, 'fun updateConversation(newConversation: Conversation)', 'updateConversation anchor')
    ui_end = -1
    depth = 0
    started = False
    for j in range(ui, len(lines)):
        for ch in lines[j]:
            if ch == '{':
                depth += 1
                started = True
            elif ch == '}':
                depth -= 1
        if started and depth <= 0:
            ui_end = j
            break
    if ui_end < 0:
        fail(VM, 'updateConversation block end not found', lines, ui)
    fblock = [
        '',
        '    /** ' + MARK + ': 会话级酒馆模式开关(只影响当前会话,不改助手)。 */',
        '    fun setTavernMode(enabled: Boolean) {',
        '        inputState.tavernMode = enabled',
        '        me.rerere.rikkahub.data.datastore.TavernModeStore.setEnabled(context, _conversationId.toString(), enabled)',
        '    }',
    ]
    for j, b in enumerate(fblock):
        lines.insert(ui_end + 1 + j, b)

    out = NL.join(lines)
    for need in [
        'inputState.tavernMode = me.rerere.rikkahub.data.datastore.TavernModeStore.isEnabled',
        'inputState.onToggleTavernMode = { enabled -> setTavernMode(enabled) }',
        'fun setTavernMode(enabled: Boolean) {',
        'TavernModeStore.setEnabled(context, _conversationId.toString(), enabled)',
    ]:
        if need not in out:
            fail(VM, 'selfcheck missing: ' + need, lines, 0)
    if balance(out) != bal0:
        fail(VM, 'balance changed', lines, 0)
    (ROOT / VM).write_text(out, encoding='utf-8')
    print('batch130: ChatVM OK')
else:
    print('batch130: ChatVM already applied')


# ============================================================
# D. ReasoningPicker.kt —— 面板加 Switch
# ============================================================
rp = (ROOT / RP).read_text(encoding='utf-8')
if MARK not in rp:
    lines = rp.split(NL)
    bal0 = balance(rp)

    # D1: import Switch(若缺)
    if 'import androidx.compose.material3.Switch' not in rp:
        si = -1
        for i, ln in enumerate(lines):
            if ln.strip() == 'import androidx.compose.material3.Slider':
                si = i
                break
        if si < 0:
            si = find_one(lines, RP, 'import androidx.compose.material3.ModalBottomSheet', 'ModalBottomSheet import')
        lines.insert(si + 1, 'import androidx.compose.material3.Switch // ' + MARK)

    # D2: ReasoningButton 签名加参(插在 onUpdateReasoningLevel 之后,该行有尾逗号)
    bi = find_one(lines, RP, 'fun ReasoningButton(', 'ReasoningButton decl')
    upd = -1
    for j in range(bi, min(bi + 12, len(lines))):
        if 'onUpdateReasoningLevel: (ReasoningLevel) -> Unit,' in lines[j]:
            upd = j
            break
    if upd < 0:
        fail(RP, 'ReasoningButton onUpdateReasoningLevel param not found', lines, bi)
    uind = ind_of(lines[upd])
    lines.insert(upd + 1, uind + 'tavernMode: Boolean = false, // ' + MARK)
    lines.insert(upd + 2, uind + 'onUpdateTavernMode: ((Boolean) -> Unit)? = null, // ' + MARK)

    # D3: ReasoningButton 内调用 ReasoningPicker —— 在 ReasoningPicker( 之后第一行插参
    ci = -1
    for j in range(upd, min(upd + 30, len(lines))):
        if lines[j].strip().startswith('ReasoningPicker('):
            ci = j
            break
    if ci < 0:
        fail(RP, 'ReasoningPicker call inside ReasoningButton not found', lines, upd)
    cind = ind_of(lines[ci])
    lines.insert(ci + 1, cind + '    tavernMode = tavernMode,')
    lines.insert(ci + 2, cind + '    onUpdateTavernMode = onUpdateTavernMode,')

    # D4: ReasoningPicker 签名加参
    pi = find_one(lines, RP, 'fun ReasoningPicker(', 'ReasoningPicker decl')
    pupd = -1
    for j in range(pi, min(pi + 12, len(lines))):
        if 'onUpdateReasoningLevel: (ReasoningLevel) -> Unit,' in lines[j]:
            pupd = j
            break
    if pupd < 0:
        fail(RP, 'ReasoningPicker onUpdateReasoningLevel param not found', lines, pi)
    pind = ind_of(lines[pupd])
    lines.insert(pupd + 1, pind + 'tavernMode: Boolean = false, // ' + MARK)
    lines.insert(pupd + 2, pind + 'onUpdateTavernMode: ((Boolean) -> Unit)? = null, // ' + MARK)

    # D5: 在 ModalBottomSheet 的 Column 内、标题 Column 之后插入 Switch
    hint = find_one(lines, RP, 'stringResource(R.string.reasoning_picker_hint)', 'picker hint')
    hi_end = -1
    for j in range(hint, min(hint + 12, len(lines))):
        if lines[j].strip() == '}' and len(ind_of(lines[j])) < len(ind_of(lines[hint])):
            hi_end = j
            break
    if hi_end < 0:
        fail(RP, 'header Column close not found', lines, hint)
    hind = ind_of(lines[hi_end])
    sw = [
        '',
        hind + '// ' + MARK + ': 会话级酒馆模式开关(借位显示,与思考深度数据无关)',
        hind + 'if (onUpdateTavernMode != null) {',
        hind + '    Row(',
        hind + '        modifier = Modifier.fillMaxWidth(),',
        hind + '        verticalAlignment = Alignment.CenterVertically,',
        hind + '        horizontalArrangement = Arrangement.SpaceBetween,',
        hind + '    ) {',
        hind + '        Column(modifier = Modifier.weight(1f)) {',
        hind + '            Text(',
        hind + '                text = stringResource(R.string.setting_tavern_mode),',
        hind + '                style = MaterialTheme.typography.titleSmall,',
        hind + '            )',
        hind + '            Text(',
        hind + '                text = stringResource(R.string.setting_tavern_mode_desc),',
        hind + '                style = MaterialTheme.typography.bodySmall,',
        hind + '                color = MaterialTheme.colorScheme.onSurfaceVariant,',
        hind + '            )',
        hind + '        }',
        hind + '        Switch(',
        hind + '            checked = tavernMode,',
        hind + '            onCheckedChange = { onUpdateTavernMode?.invoke(it) },',
        hind + '        )',
        hind + '    }',
        hind + '}',
    ]
    for j, b in enumerate(sw):
        lines.insert(hi_end + 1 + j, b)

    out = NL.join(lines)
    for need in [
        'import androidx.compose.material3.Switch',
        'tavernMode: Boolean = false,',
        'onUpdateTavernMode: ((Boolean) -> Unit)? = null,',
        'text = stringResource(R.string.setting_tavern_mode),',
        'onCheckedChange = { onUpdateTavernMode?.invoke(it) },',
    ]:
        if need not in out:
            fail(RP, 'selfcheck missing: ' + need, lines, 0)
    if balance(out) != bal0:
        fail(RP, 'balance changed', lines, 0)
    (ROOT / RP).write_text(out, encoding='utf-8')
    print('batch130: ReasoningPicker OK')
else:
    print('batch130: ReasoningPicker already applied')


# ============================================================
# E. ChatInput.kt —— 在 ReasoningButton 调用最前面传参
# ============================================================
ci = (ROOT / CI).read_text(encoding='utf-8')
if MARK not in ci:
    lines = ci.split(NL)
    bal0 = balance(ci)

    # ReasoningButton( 调用唯一;在它之后第一行插参(reasoningLevel 行有尾逗号)
    rbi = find_one(lines, CI, 'ReasoningButton(', 'ReasoningButton call')
    aind = ind_of(lines[rbi]) + '    '
    lines.insert(rbi + 1, aind + 'tavernMode = state.tavernMode, // ' + MARK)
    lines.insert(rbi + 2, aind + 'onUpdateTavernMode = state.onToggleTavernMode,')

    out = NL.join(lines)
    for need in [
        'tavernMode = state.tavernMode,',
        'onUpdateTavernMode = state.onToggleTavernMode,',
    ]:
        if need not in out:
            fail(CI, 'selfcheck missing: ' + need, lines, 0)
    if balance(out) != bal0:
        fail(CI, 'balance changed', lines, 0)
    (ROOT / CI).write_text(out, encoding='utf-8')
    print('batch130: ChatInput OK')
else:
    print('batch130: ChatInput already applied')


# ============================================================
# F. ChatService.kt —— buildList 内按会话裁剪工具
# ============================================================
cs = (ROOT / CS).read_text(encoding='utf-8')
if MARK not in cs:
    lines = cs.split(NL)
    bal0 = balance(cs)

    # F1: 在 tools buildList 的开头插 tavern 判定 + 提前返回
    # 锚点: if (useExternalWebSearch) { —— 在 handleMessageComplete 的 tools buildList 内唯一
    ti = find_one(lines, CS, 'if (useExternalWebSearch) {', 'tools useExternalWebSearch anchor')
    tind = ind_of(lines[ti])
    tavern_block = [
        tind + '// ' + MARK + ': 会话级酒馆模式 —— 只留 提示词 + 记忆 + 搜索 + 文件',
        tind + '// 记忆工具在 GenerationHandler 的 toolsInternal 里单独加,不在这里;提示词是 system prompt,不走 tools',
        tind + 'val rhTavern = me.rerere.rikkahub.data.datastore.TavernModeStore.isEnabled(context, conversationId.toString())',
        tind + 'if (rhTavern) {',
        tind + '    if (useExternalWebSearch) {',
        tind + '        addAll(createSearchTools(settings))',
        tind + '    }',
        tind + '    val rhCtx = me.rerere.rikkahub.data.ai.tools.ToolInvocationContext(',
        tind + '        callerAssistantId = assistant.id.toString(),',
        tind + '        callerConversationId = conversationId.toString(),',
        tind + '        modelCanSeeImages = me.rerere.ai.provider.Modality.IMAGE in model.inputModalities,',
        tind + '    )',
        tind + '    addAll(localTools.getTools(listOf(me.rerere.rikkahub.data.ai.tools.LocalToolOption.Files), rhCtx))',
        tind + '    return@buildList',
        tind + '}',
    ]
    for j, b in enumerate(tavern_block):
        lines.insert(ti + j, b)

    out = NL.join(lines)
    for need in [
        'val rhTavern = me.rerere.rikkahub.data.datastore.TavernModeStore.isEnabled(context, conversationId.toString())',
        'addAll(localTools.getTools(listOf(me.rerere.rikkahub.data.ai.tools.LocalToolOption.Files), rhCtx))',
        'return@buildList',
        'createSearchTools',
    ]:
        if need not in out:
            fail(CS, 'selfcheck missing: ' + need, lines, 0)
    if balance(out) != bal0:
        fail(CS, 'balance changed', lines, 0)
    (ROOT / CS).write_text(out, encoding='utf-8')
    print('batch130: ChatService OK')
else:
    print('batch130: ChatService already applied')


# ============================================================
# G/H. strings
# ============================================================
def add_strings(path, title, desc):
    txt = (ROOT / path).read_text(encoding='utf-8')
    if MARK in txt:
        print('batch130: ' + path + ' already applied')
        return
    lines = txt.split(NL)
    ri = -1
    for i, ln in enumerate(lines):
        if ln.strip() == '</resources>':
            ri = i
            break
    if ri < 0:
        fail(path, '</resources> not found', lines, 0)
    block = [
        '    <string name=' + D + 'setting_tavern_mode' + D + '>' + title + '</string> <!-- ' + MARK + ' -->',
        '    <string name=' + D + 'setting_tavern_mode_desc' + D + '>' + desc + '</string>',
    ]
    for j, b in enumerate(block):
        lines.insert(ri + j, b)
    out = NL.join(lines)
    for need in ['setting_tavern_mode', 'setting_tavern_mode_desc']:
        if need not in out:
            fail(path, 'selfcheck missing: ' + need, lines, 0)
    (ROOT / path).write_text(out, encoding='utf-8')
    print('batch130: ' + path + ' OK')


add_strings(EN, 'Tavern mode', 'Only persona, memory, search and files; all other tools are off')
add_strings(ZH, '酒馆模式', '只保留人设、记忆、搜索和文件,其余工具全部关闭')

print('batch130: ALL OK')
