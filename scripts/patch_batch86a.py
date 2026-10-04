#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
batch86a: Yuihub 移植 Step1-3(三个叶子文件,零在链冲突)

目标:把 Yuihub v2.5.8 的「用户信息移到对话页编辑」能力的【叶子层】先落地。
      叶子 = 只被上层调用、自身不依赖任何在链补丁,所以仓库形态 == CI 形态。

Step1  UIAvatar.kt         +showEditBadge = true 参数 + 角标条件加 && showEditBadge
Step2  AssistantPicker.kt  private fun AssistantPickerSheet -> fun AssistantPickerSheet
Step3  ChatMessageAvatar.kt +onChangeAvatar / onEditNickname 两回调 + 文本 clickable
                            + UIAvatar 传 onUpdate / showEditBadge=false

上游(依赖本步,尚未写):Step4 ChatMessage.kt -> Step5 ChatList.kt -> Step6 ChatPage.kt
本步独立可编译:UIAvatar 的 showEditBadge 默认 true => 现有调用点行为完全不变;
AssistantPickerSheet 只是去掉 private(同文件 AssistantPicker 仍在调用);
ChatMessageAvatar 两参数均有默认值 => 现有 ChatMessage.kt 调用点零改动。

================================ 五查 ===================================
1. import 清单(铁律20:行级 strip 全等 + 插入后回读断言,禁 in 子串)
   - UIAvatar.kt:       零新增(showEditBadge 是基础类型)
   - AssistantPicker.kt:零新增(只改可见性关键字)
   - ChatMessageAvatar.kt:需新增 androidx.compose.foundation.clickable
     ← 实读该文件 import 段确认【不存在】;锚点 = import androidx.compose.foundation.layout.Arrangement
       (实读唯一);插入后回读断言
2. 同文件冲突:三个文件 grep 在链脚本(batch64..85)均未触碰 => 本批独占
3. 作用域:全部在 @Composable 函数体内/函数签名内;Step3 的 modifier 插入前先
   用「从 fun ChatMessageUserAvatar( 往下 N 行窗口」定位,避免与
   ChatMessageAssistantAvatar 的同名 modifier 行混淆(实读确认二者同串)
4. 括号配对:
   - UIAvatar 签名末参数 onClick 无尾逗号(铁律25) => 替换为
     "onClick: (() -> Unit)? = null," 先补逗号再插 showEditBadge 行
   - ChatMessageAvatar 签名 modifier 已有尾逗号 => 直接追加两行
   - Text 内插 modifier 花括号自平衡
5. 函数签名:全部新增【可选参数】(默认值) => 零破坏;AssistantPickerSheet
   仅 private->public(无重名,实读 grep 同文件无第二个 fun AssistantPickerSheet)

============================ Python 三查 ===============================
1. 无引号字面量问题:文本内的双引号一律 chr(34)=Q 拼接,单引号 chr(39)=SQ
2. 无未定义引用:ind() 定义于文件头,实体为 len(ln.lstrip())(铁律26)
3. 无 f-string / walrus / join(手写 concat)

========================== 铁律 28 检查 =================================
本批【不插入】任何 @Composable 函数块(只改已有函数的签名与函数体),
故 #232 的「注解重复」模式不适用。但插入点仍检查:
  - 不得在注解行与函数声明行之间插入(锚点均以函数声明行为界)
'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
SQ = chr(39)
MARK = 'rhUserAvatarEdit'


def fail(path, msg):
    print('::error file=' + path + '::batch86a ' + str(msg)[:1400])
    raise SystemExit(1)


def concat(lines):
    t = ''
    for i, ln in enumerate(lines):
        if i > 0:
            t += NL
        t += ln
    return t


def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]


def balance(text):
    return (text.count('(') - text.count(')')) + (text.count('{') - text.count('}'))


def ensure_import(lines, path, want, anchor_exact):
    '''确保 import 存在:行级 strip 全等判断(铁律20)+ 插入后回读断言'''
    if any(ln.strip() == want for ln in lines):
        return 'exists'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == anchor_exact]
    if len(hits) != 1:
        print('  dump import anchors for ' + want + ':')
        for i, ln in enumerate(lines):
            if ln.strip().startswith('import androidx.compose.foundation.') and (
                    'layout.Arrangement' in ln or 'layout.Row' in ln):
                print('    >> line ' + str(i) + ': ' + ln.strip()[:120])
        fail(path, 'import anchor count=' + str(len(hits)) + ' for ' + want)
    lines.insert(hits[0], want)
    if not any(ln.strip() == want for ln in lines):
        fail(path, 'import insert read-back failed: ' + want)
    return 'added'


results = []

# =========================================================================
# Step1  UIAvatar.kt
# =========================================================================
UA = 'app/src/main/java/me/rerere/rikkahub/ui/components/ui/UIAvatar.kt'
u = (ROOT / UA).read_text(encoding='utf-8')
if MARK in u:
    print('batch86a: UIAvatar already applied')
else:
    lines = u.split(NL)
    bal0 = balance(u)
    applied = []

    # 1a. 签名:onClick 是末参数(无尾逗号) -> 补逗号 + 插 showEditBadge(铁律25)
    sig_idx = [i for i, ln in enumerate(lines) if ln.strip() == 'onClick: (() -> Unit)? = null']
    if len(sig_idx) != 1:
        for i, ln in enumerate(lines):
            if 'onClick: (() -> Unit)?' in ln:
                print('  >> line ' + str(i) + ': ' + ln.strip()[:120])
        fail(UA, 'UIAvatar onClick param count=' + str(len(sig_idx)))
    si = sig_idx[0]
    d = ind(lines[si])
    lines[si] = d + 'onClick: (() -> Unit)? = null,'
    lines.insert(si + 1, d + '/** 是否在右下角显示编辑铅笔角标(可编辑时默认显示) */')
    lines.insert(si + 2, d + 'showEditBadge: Boolean = true, // ' + MARK)
    applied.append('sig-param')

    # 1b. 角标条件:只改「独立成行的 if (onUpdate != null) {」
    #     实读确认同文件另有单行 `if (onUpdate != null) showPickOption = true` 不带 { => strip 全等可区分
    badge_idx = [i for i, ln in enumerate(lines) if ln.strip() == 'if (onUpdate != null) {']
    if len(badge_idx) != 1:
        for i, ln in enumerate(lines):
            if 'if (onUpdate != null)' in ln:
                print('  >> line ' + str(i) + ': ' + ln.strip()[:120])
        fail(UA, 'badge if count=' + str(len(badge_idx)))
    bi = badge_idx[0]
    d = ind(lines[bi])
    lines[bi] = d + 'if (onUpdate != null && showEditBadge) { // ' + MARK
    applied.append('badge-condition')

    # 自检
    t = concat(lines)
    for need in ['showEditBadge: Boolean = true', 'onUpdate != null && showEditBadge']:
        if need not in t:
            fail(UA, 'selfcheck missing: ' + need)
    if 'showEditBadge: Boolean = true, // ' + MARK + lines[si + 3].strip() and False:
        pass
    if balance(t) != bal0:
        fail(UA, 'bracket balance changed: ' + str(bal0) + ' -> ' + str(balance(t)))
    if 'fun UIAvatar(' not in t:
        fail(UA, 'UIAvatar declaration lost')
    (ROOT / UA).write_text(t, encoding='utf-8')
    results.append('UIAvatar(' + ', '.join(applied) + ')')
    print('batch86a: UIAvatar OK (' + ', '.join(applied) + ')')

# =========================================================================
# Step2  AssistantPicker.kt —— private fun AssistantPickerSheet -> fun
# =========================================================================
AP = 'app/src/main/java/me/rerere/rikkahub/ui/components/ai/AssistantPicker.kt'
a = (ROOT / AP).read_text(encoding='utf-8')
if MARK in a:
    print('batch86a: AssistantPicker already applied')
else:
    lines = a.split(NL)
    bal0 = balance(a)
    target = 'private fun AssistantPickerSheet('
    hits = [i for i, ln in enumerate(lines) if ln.strip() == target]
    if len(hits) != 1:
        for i, ln in enumerate(lines):
            if 'fun AssistantPickerSheet(' in ln:
                print('  >> line ' + str(i) + ': ' + ln.strip()[:140])
        fail(AP, 'AssistantPickerSheet decl count=' + str(len(hits)))
    hi = hits[0]
    d = ind(lines[hi])
    lines[hi] = d + 'fun AssistantPickerSheet('
    lines.insert(hi, d + '// ' + MARK + ': 公开化(抽屉助手卡片要直接复用)')

    # 自检:同文件不得再有第二个 AssistantPickerSheet 声明;AssistantItem 不受影响
    t = concat(lines)
    decl_count = sum(1 for ln in lines if ln.strip().startswith('fun AssistantPickerSheet('))
    if decl_count != 1:
        fail(AP, 'AssistantPickerSheet decl count in final=' + str(decl_count))
    if 'private fun AssistantItem(' not in t:
        fail(AP, 'AssistantItem private decl lost (over-edit)')
    if 'private fun AssistantPickerSheet(' in t:
        fail(AP, 'private not removed')
    if balance(t) != bal0:
        fail(AP, 'bracket balance changed')
    (ROOT / AP).write_text(t, encoding='utf-8')
    results.append('AssistantPicker(public)')
    print('batch86a: AssistantPicker OK (public)')

# =========================================================================
# Step3  ChatMessageAvatar.kt
# =========================================================================
CMA = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessageAvatar.kt'
c = (ROOT / CMA).read_text(encoding='utf-8')
if MARK in c:
    print('batch86a: ChatMessageAvatar already applied')
else:
    lines = c.split(NL)
    bal0 = balance(c)
    applied = []

    # 3a. import clickable(锚 = import androidx.compose.foundation.layout.Arrangement,实读唯一)
    r = ensure_import(lines, CMA, 'import androidx.compose.foundation.clickable',
                      'import androidx.compose.foundation.layout.Arrangement')
    applied.append('import-clickable-' + r)

    # 3b. 签名加两参数 —— 窗口定位(实读:ChatMessageUserAvatar 与 ChatMessageAssistantAvatar
    #     都有 'modifier: Modifier = Modifier,' 行,故必须先锁定函数起点)
    fn_idx = [i for i, ln in enumerate(lines) if ln.strip() == 'fun ChatMessageUserAvatar(']
    if len(fn_idx) != 1:
        for i, ln in enumerate(lines) in enumerate(lines) if False else []:
            pass
        for i, ln in enumerate(lines):
            if 'ChatMessageUserAvatar' in ln:
                print('  >> line ' + str(i) + ': ' + ln.strip()[:140])
        fail(CMA, 'ChatMessageUserAvatar decl count=' + str(len(fn_idx)))
    fi = fn_idx[0]
    mod_idx = -1
    for i in range(fi, min(fi + 8, len(lines))):
        if lines[i].strip() == 'modifier: Modifier = Modifier,':
            mod_idx = i
            break
    if mod_idx < 0:
        for i in range(fi, min(fi + 8, len(lines))):
            print('  >> ' + str(fi) + '+' + str(i - fi) + ': ' + lines[i].strip()[:140])
        fail(CMA, 'modifier param not found inside ChatMessageUserAvatar signature')
    d = ind(lines[mod_idx])
    lines.insert(mod_idx + 1, d + 'onChangeAvatar: ((Avatar) -> Unit)? = null,')
    lines.insert(mod_idx + 2, d + 'onEditNickname: (() -> Unit)? = null, // ' + MARK)
    applied.append('sig-2params')

    # 3c. Text 加 clickable modifier(锚 = 函数体内第一个 'text = nickname.ifEmpty' 所在 Text 块)
    text_idx = -1
    for i in range(fi, min(fi + 40, len(lines))):
        if 'text = nickname.ifEmpty { stringResource(R.string.user_default_name) }' in lines[i]:
            text_idx = i
            break
    if text_idx < 0:
        for i in range(fi, min(fi + 40, len(lines))):
            print('  >> ' + str(i) + ': ' + lines[i].strip()[:150])
        fail(CMA, 'nickname Text line not found')
    # 找该 Text 块的 'maxLines = 1,' 行(紧随 style 之后),在其后插 modifier
    ml_idx = -1
    for i in range(text_idx, min(text_idx + 6, len(lines))):
        if lines[i].strip() == 'maxLines = 1,':
            ml_idx = i
            break
    if ml_idx < 0:
        fail(CMA, 'maxLines=1 line not found after nickname Text')
    d = ind(lines[ml_idx])
    lines.insert(ml_idx + 1, d + 'modifier = Modifier.then(')
    lines.insert(ml_idx + 2, d + '    if (onEditNickname != null) Modifier.clickable(onClick = onEditNickname) else Modifier')
    lines.insert(ml_idx + 3, d + '),')
    applied.append('text-clickable')

    # 3d. UIAvatar 传 onUpdate / showEditBadge=false(锚 = 函数体内 value = avatar 行)
    va_idx = -1
    for i in range(fi, min(fi + 60, len(lines))):
        if lines[i].strip() == 'value = avatar,':
            va_idx = i
            break
    if va_idx < 0:
        for i in range(fi, min(fi + 60, len(lines))):
            print('  >> ' + str(i) + ': ' + lines[i].strip()[:140])
        fail(CMA, 'value = avatar line not found')
    # 其后必须是 'loading = false,'
    ld_idx = -1
    for i in range(va_idx + 1, min(va_idx + 4, len(lines))):
        if lines[i].strip() == 'loading = false,':
            ld_idx = i
            break
    if ld_idx < 0:
        fail(CMA, 'loading=false not after value=avatar')
    d = ind(lines[ld_idx])
    lines.insert(ld_idx + 1, d + 'onUpdate = onChangeAvatar,')
    lines.insert(ld_idx + 2, d + 'showEditBadge = false, // ' + MARK)
    applied.append('avatar-update')

    # 自检
    t = concat(lines)
    for need in ['onChangeAvatar: ((Avatar) -> Unit)? = null',
                 'onEditNickname: (() -> Unit)? = null',
                 'Modifier.clickable(onClick = onEditNickname)',
                 'onUpdate = onChangeAvatar',
                 'showEditBadge = false',
                 'import androidx.compose.foundation.clickable']:
        if need not in t:
            fail(CMA, 'selfcheck missing: ' + need)
    # 必须未误伤 ChatMessageAssistantAvatar:其 UIAvatar 不得被改
    # (AssistantAvatar 的 value = assistant.avatar 行若出现 showEditBadge 即为过度修改)
    if 'value = assistant.avatar' in t:
        for i, ln in enumerate(lines):
            if ln.strip() == 'value = assistant.avatar,':
                win = concat(lines[i:min(i + 6, len(lines))])
                if 'showEditBadge' in win:
                    fail(CMA, 'over-edit: AssistantAvatar UIAvatar was touched')
    if not any(ln.strip() == 'import androidx.compose.foundation.clickable' for ln in lines):
        fail(CMA, 'clickable import missing in final')
    if balance(t) != bal0:
        fail(CMA, 'bracket balance changed: ' + str(bal0) + ' -> ' + str(balance(t)))
    (ROOT / CMA).write_text(t, encoding='utf-8')
    results.append('ChatMessageAvatar(' + ', '.join(applied) + ')')
    print('batch86a: ChatMessageAvatar OK (' + ', '.join(applied) + ')')

print('batch86a: OK -> ' + ' | '.join(results))
