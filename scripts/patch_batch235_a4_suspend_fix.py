#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch235: 修复 A4 setConversationModel 的 suspend 编译错 (ChatService.kt:2766)

根因(读 run446 annotation):
  A4(batch234_a4_ui_wiring) 新增 ChatService.setConversationModel, 声明为普通 fun,
  但函数体调用 suspend 函数 conversationRepo.updateConversationConfig →
  ILLEGAL_SUSPEND_FUNCTION_CALL @ ChatService.kt:2766。

修复: setConversationModel 改 suspend(最小修复)。
  理由(A4 调用方核对): A4 的 ChatVM.setChatModel 已在 viewModelScope.launch 块内调用
  chatService.setConversationModel(...) → suspend 调用天然合法;
  suspend 函数体内可调用任意(含非 suspend)函数, 无其他连锁。
  对比方案(appScope.launch 包落库)否决: 调用方无法等待落库完成, 时序不确定, 失败无感知。

幂等: 已是 suspend 则 skip(并行会话若自行修复亦安全)。warn-only。只动 ChatService.kt。

五查:
1. import: 无新 import
2. 同文件冲突: 锚点 `fun setConversationModel(` 是 A4 独有的新函数签名行, 与 A3/A4 其他区域不相交
3. 作用域: 仅改函数修饰符, 体内逻辑不变
4. 括号配对: 修饰符追加不改括号
5. 函数签名: fun→suspend fun; 调用方(ChatVM, launch 块内)兼容; 无其他调用点(run446 编译错仅报 2766 一处)
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
CS = 'app/src/main/java/me/rerere/rikkahub/service/ChatService.kt'
MARK = 'rhA4Suspend235'


def fail(msg):
    print('::error::batch235 ' + str(msg)[:1200])
    sys.stdout.flush()
    sys.exit(0)


def main():
    p = ROOT / CS
    if not p.exists():
        fail('ChatService.kt missing')
    t = p.read_text(encoding='utf-8')
    if MARK in t:
        print('::notice::batch235 OK already (marker present)')
        sys.exit(0)
    if 'suspend fun setConversationModel(' in t:
        print('::notice::batch235 OK already (already suspend)')
        sys.exit(0)
    old = '    fun setConversationModel(conversationId: Uuid, modelId: Uuid) {'
    n = t.count(old)
    if n != 1:
        fail('anchor count=' + str(n) + ' (expected 1)')
    bal0 = (t.count('(') - t.count(')')) + (t.count('{') - t.count('}'))
    new = '    suspend fun setConversationModel(conversationId: Uuid, modelId: Uuid) { // ' + MARK
    t = t.replace(old, new, 1)
    bal1 = (t.count('(') - t.count(')')) + (t.count('{') - t.count('}'))
    if bal1 != bal0:
        fail('balance changed ' + str(bal0) + '->' + str(bal1))
    p.write_text(t, encoding='utf-8')
    print('::notice::batch235 OK - setConversationModel now suspend (A4 ChatService.kt:2766 fix)')


main()