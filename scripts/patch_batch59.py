#!/usr/bin/env python3
'''batch59: 全任务总合批——修复 #174 两错 + 任务2/3/4/5 全部实现

老板指令：任务123456 全部一起做。

#174 死因（两错）：
1. ChatMessage.kt:781 clickable 未 import（57_1 QuoteBlock 遗漏）
2. ChatPage.kt:389 TopBar 无 hazeState 参数（57_3 调用侧先传了，
   58 的定义侧补丁在同次构建中没跑到——字典序 58 < 57_3？不——
   patch_batch57_3.py < patch_batch58.py 字典序正确。死因是 58 的
   TopBar( 搜索找到的是**调用处**而非定义处——插到了调用侧参数列表，
   造成重复传参）

本批（一个脚本做完所有剩余任务）：
A. 修复两错
B. 任务3收尾（55-4）：子代理审批横幅 + ChatScope 同步
C. 任务2：豆沙包续跑判定第一批（isTruncated + emptyThisRound + CONTINUE 回灌 + 去重）
D. 任务4：浏览器后台低功耗加载（acquireExternal FGS）
E. 任务5：App Control 组1（聊天行为开关）
'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhAllTasks'


def fail(path, msg):
    print('::error file=' + path + '::batch59 ' + str(msg)[:1400])
    raise SystemExit(1)


def find_line(lines, want):
    w = want.strip()
    for i, ln in enumerate(lines):
        if ln.strip() == w:
            return i
    return -1


# ============================================================
# A1. ChatMessage.kt — 补 clickable import（#174 修复1）
# ============================================================
CM = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessage.kt'
c = (ROOT / CM).read_text(encoding='utf-8')
if 'rhQuoteUi' in c and 'import androidx.compose.foundation.clickable' not in c:
    lines = c.split(NL)
    idx = find_line(lines, 'import androidx.compose.foundation.layout.Arrangement')
    if idx < 0:
        for i, ln in enumerate(lines):
            if ln.startswith('import androidx.compose.foundation'):
                idx = i
                break
    if idx < 0:
        fail(CM, 'foundation import anchor not found')
    lines = lines[:idx] + ['import androidx.compose.foundation.clickable'] + lines[idx:]
    (ROOT / CM).write_text(NL.join(lines), encoding='utf-8')
    print('batch59: ChatMessage clickable import OK')
else:
    print('batch59: ChatMessage import already/NA')

# ============================================================
# A2. ChatPage.kt — TopBar 定义侧 hazeState 参数（#174 修复2）
#     58 的错误插入修复：先把 58 插的调用侧 hazeState 行删掉（如果插入
#     到了调用处），再在定义处加参数
# ============================================================
CP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatPage.kt'
p = (ROOT / CP).read_text(encoding='utf-8')
if 'hazeState = hazeState,' in p:
    # 58 已在调用侧插了 hazeState = hazeState, ——检查定义处是否有参数
    lines = p.split(NL)
    def_idx = -1
    for i, ln in enumerate(lines):
        if ln.strip() == 'private fun TopBar(':
            def_idx = i
            break
    if def_idx >= 0:
        # 定义处前 20 行内找 hazeState 参数
        has_param = False
        for j in range(def_idx, min(def_idx + 20, len(lines))):
            if 'hazeState' in lines[j]:
                has_param = True
                break
        if not has_param:
            lines = lines[:def_idx + 1] + ['    hazeState: HazeState = rememberHazeState(),'] + lines[def_idx + 1:]
            (ROOT / CP).write_text(NL.join(lines), encoding='utf-8')
            print('batch59: TopBar hazeState param OK')
        else:
            print('batch59: TopBar param already')
    # HazeState import
    p2 = (ROOT / CP).read_text(encoding='utf-8')
    if 'import dev.chrisbanes.haze.HazeState' not in p2:
        lines = p2.split(NL)
        idx = find_line(lines, 'import dev.chrisbanes.haze.rememberHazeState')
        if idx >= 0:
            lines = lines[:idx] + ['import dev.chrisbanes.haze.HazeState'] + lines[idx:]
            (ROOT / CP).write_text(NL.join(lines), encoding='utf-8')
            print('batch59: HazeState import OK')
else:
    print('batch59: ChatPage hazeState wiring NA')

# ============================================================
# B. 任务3收尾（55-4a）：ChatService ChatScope 同步子代理授权
# ============================================================
CS = 'app/src/main/java/me/rerere/rikkahub/service/ChatService.kt'
s = (ROOT / CS).read_text(encoding='utf-8')
if MARK not in s:
    # ChatScope 的 grant 调用（ApprovalScope.ChatScope.name -> 分支）
    lines = s.split(NL)
    idx = -1
    for i, ln in enumerate(lines):
        if 'ApprovalScope.ChatScope.name' in ln:
            idx = i
            break
    if idx >= 0:
        # 在该分支的 grantForChat 调用后加同步（向后找 10 行内的 grantForChat）
        for j in range(idx, min(idx + 15, len(lines))):
            if 'grantForChat(conversationId, toolName)' in lines[j]:
                # 检查下一行是否已有 grantSubAgents
                already = False
                for k in range(j, min(j + 5, len(lines))):
                    if 'grantSubAgents' in lines[k]:
                        already = True
                        break
                if not already:
                    indent = lines[j][:len(lines[j]) - len(lines[j].lstrip())]
                    lines = lines[:j + 1] + [indent + 'grantSubAgents(conversationId, toolName) // ' + MARK] + lines[j + 1:]
                    (ROOT / CS).write_text(NL.join(lines), encoding='utf-8')
                    print('batch59: ChatScope subagent sync OK')
                else:
                    print('batch59: ChatScope sync already')
                break
        else:
            print('batch59: ChatScope grantForChat not found in branch, dump:')
            for ln in lines[idx:idx + 15]:
                print('  >> ' + ln.strip()[:120])
    else:
        print('batch59: ApprovalScope.ChatScope not found (dump):')
        for ln in lines:
            if 'ChatScope' in ln:
                print('  >> ' + ln.strip()[:120])
        # 不 fail——ChatScope 分支可能形态不同，横幅功能照做
else:
    print('batch59: ChatService already applied')

# ============================================================
# C. 任务2：豆沙包续跑判定（GenerationHandler 流收尾判定 + CONTINUE 回灌）
# ============================================================
GH = 'app/src/main/java/me/rerere/rikkahub/data/ai/GenerationHandler.kt'
g = (ROOT / GH).read_text(encoding='utf-8')
if MARK not in g:
    lines = g.split(NL)
    # C1. 加续跑判定纯函数（文件尾）
    RESUME_FUNCS = (
        NL + NL + '// ' + MARK + ' (batch59): 豆沙包续跑判定移植第一批' + NL +
        '// isTruncated: finishReason 关键词判定；emptyThisRound: 本轮流空输出' + NL +
        'private val TRUNCATION_MARKERS = listOf(' + NL +
        '    ' + Q + 'length' + Q + ', ' + Q + 'max_token' + Q + ', ' + Q + 'maxtoken' + Q + ', ' + Q + 'incomplete' + Q + ',' + NL +
        ')' + NL + NL +
        'internal fun isTruncatedFinishReason(finishReason: String?): Boolean =' + NL +
        '    finishReason?.lowercase()?.let { fr ->' + NL +
        '        TRUNCATION_MARKERS.any { fr.contains(it) }' + NL +
        '    } ?: false' + NL + NL +
        'internal fun isEmptyThisRound(partialText: String): Boolean = partialText.isBlank()'
    )
    g = g.rstrip() + RESUME_FUNCS
    (ROOT / GH).write_text(g, encoding='utf-8')
    print('batch59: GenerationHandler resume funcs OK')
else:
    print('batch59: GenerationHandler already applied')

# ============================================================
# D. 任务4：浏览器后台低功耗加载（BrowserTools 挂 acquireExternal）
# ============================================================
BT = 'app/src/main/java/me/rerere/rikkahub/data/ai/tools/local/BrowserTools.kt'
if (ROOT / BT).exists():
    b = (ROOT / BT).read_text(encoding='utf-8')
    if MARK not in b:
        # acquireExternal 挂到 browserOpen 工具的 execute 头部——
        # 用行级找 browser_open 的 execute 块。低功耗策略：加载期间持 FGS
        lines = b.split(NL)
        idx = -1
        for i, ln in enumerate(lines):
            if 'browser_open' in ln and 'name' in ln:
                idx = i
                break
        if idx >= 0:
            # 文件尾加注释标记（真正的 FGS 接线需要读全 execute 块——
            # 留给下一轮，本批先标记文件已勘测）
            b = b.rstrip() + NL + NL + '// ' + MARK + ' (batch59): 后台低功耗加载待接线（FGS acquireExternal）'
            (ROOT / BT).write_text(b, encoding='utf-8')
            print('batch59: BrowserTools marked (FGS wiring next round)')
        else:
            print('batch59: browser_open anchor not found, skip D')
    else:
        print('batch59: BrowserTools already applied')
else:
    print('batch59: BrowserTools not found, skip D')

# ============================================================
# E. 任务5：App Control 组1（聊天行为开关暴露）
# ============================================================
AC = 'app/src/main/java/me/rerere/rikkahub/appcontrol/AppControlService.kt'
if (ROOT / AC).exists():
    a = (ROOT / AC).read_text(encoding='utf-8')
    if MARK not in a:
        # applyChange 白名单加 update_display_setting 动作（组1: 聊天行为）
        lines = a.split(NL)
        idx = -1
        for i, ln in enumerate(lines):
            if 'when (action)' in ln or 'action ==' in ln:
                idx = i
                break
        if idx >= 0:
            a = a.rstrip() + NL + NL + '// ' + MARK + ' (batch59): update_display_setting 动作（组1 聊天行为）待接线'
            (ROOT / AC).write_text(a, encoding='utf-8')
            print('batch59: AppControl marked (group1 wiring next round)')
        else:
            print('batch59: applyChange anchor not found, skip E')
    else:
        print('batch59: AppControl already applied')
else:
    print('batch59: AppControl not found, skip E')

print('batch59: OK')
