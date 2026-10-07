#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch123: quote UI repair + CI evidence dump (best effort, never fails the build)

Context (2026-10-07):
- Quote chain patches 65/68/69/70/71/72/73/95 all applied in CI (builds were green), yet
  the user reports: after sending a quoted message the quote UI block is still invisible.
- Static audit found two concrete defects:
  A. The UI block condition reads node.currentMessage.quotedMessageId while the displayed
     message is group.displayMessage - if the two diverge the block never mounts.
  B. Click-to-jump compares a NODE id against a MESSAGE id and never matches.
- batch95 injects a visible prefix into the sender's own message when the id reaches
  ChatService; the user did not report seeing it, so the id may be null at write time.
  This script dumps the transport chain so the next CI run yields ground truth.

Policy: diagnostic script - missing anchors skip with ::warning instead of exit(1),
because failing the patch step would block the whole build. The dump is the payload.
'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
D = chr(34)
MARK = 'rhQuoteRepair123'
CL = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatList.kt'
CP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatPage.kt'
VM = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatVM.kt'
CS = 'app/src/main/java/me/rerere/rikkahub/service/ChatService.kt'

info = {'fix': 'skip'}
warns = []


def w(msg):
    print('::warning::' + msg)


def trim(s, n):
    return s.strip()[:n]


def read(p):
    return (ROOT / p).read_text(encoding='utf-8')


try:
    vm_lines = read(VM).split(NL)
    sig_i = -1
    for i, ln in enumerate(vm_lines):
        if 'fun handleMessageSend(' in ln:
            sig_i = i
            break
    vm_sig = vm_lines[sig_i] if sig_i >= 0 else 'MISSING'
    call_i = -1
    if sig_i >= 0:
        for j in range(sig_i, min(sig_i + 24, len(vm_lines))):
            if 'chatService.sendMessage(' in vm_lines[j]:
                call_i = j
                break
    vm_call = vm_lines[call_i] if call_i >= 0 else 'MISSING'
    info['vmSig'] = trim(vm_sig, 120)
    info['vmCall'] = trim(vm_call, 150)

    cs_lines = read(CS).split(NL)
    cs_sig = 'MISSING'
    for ln in cs_lines:
        if ln.strip().startswith('fun sendMessage(') and 'quotedMessageId' in ln:
            cs_sig = trim(ln, 150)
            break
    if cs_sig == 'MISSING':
        for ln in cs_lines:
            if ln.strip().startswith('fun sendMessage('):
                cs_sig = trim(ln, 150)
                break
    cs_w = 'MISSING'
    for ln in cs_lines:
        if 'quotedMessageId = quotedMessageId' in ln:
            cs_w = trim(ln, 130)
            break
    info['csSig'] = cs_sig
    info['csW'] = cs_w

    cp_text = read(CP)
    cp_lines = cp_text.split(NL)
    send_lines = [trim(ln, 100) for ln in cp_lines if 'vm.handleMessageSend' in ln]
    info['cpn'] = str(len(send_lines))
    info['cp2'] = str(cp_text.count('quotedMessageId = quotingMessage?.id'))
    info['sends'] = ' ;; '.join(send_lines[:3]) if send_lines else 'MISSING'

    cl_text = read(CL)
    if MARK in cl_text:
        info['fix'] = 'already'
    else:
        cl_lines = cl_text.split(NL)
        a_i = -1
        for i, ln in enumerate(cl_lines):
            if ln.strip() == 'node.currentMessage.quotedMessageId?.let { quotedId ->':
                a_i = i
                break
        if a_i < 0:
            warns.append('rhQuoteRepair123: mount anchor not found; skipped')
        else:
            depth = 0
            close_i = -1
            for j in range(a_i, min(a_i + 40, len(cl_lines))):
                depth += cl_lines[j].count('{') - cl_lines[j].count('}')
                if depth == 0 and j > a_i:
                    close_i = j
                    break
            span = NL.join(cl_lines[a_i:close_i + 1]) if close_i > a_i else ''
            if close_i <= a_i or 'ChatMessageQuoteBlock(' not in span or 'quotedMsg' not in span:
                warns.append('rhQuoteRepair123: block span scan failed; skipped')
            elif span.count('{') - span.count('}') != 0:
                warns.append('rhQuoteRepair123: span not balanced; skipped')
            else:
                d = cl_lines[a_i][:len(cl_lines[a_i]) - len(cl_lines[a_i].lstrip())]
                new_block = [
                    d + 'val rhQuoteId = group.displayMessage.quotedMessageId ?: node.currentMessage.quotedMessageId // ' + MARK,
                    d + 'rhQuoteId?.let { quotedId ->',
                    d + '    val quotedMsg = conversation.messageNodes.flatMap { it.messages }.firstOrNull { it.id == quotedId }',
                    d + '    ChatMessageQuoteBlock(',
                    d + '        senderName = quotedMsg?.let { msg ->',
                    d + '            if (msg.role == me.rerere.ai.core.MessageRole.USER) {',
                    d + '                ' + D + '你' + D,
                    d + '            } else {',
                    d + '                assistant?.name?.ifBlank { null } ?: ' + D + '助手' + D,
                    d + '            }',
                    d + '        } ?: ' + D + '引用' + D + ',',
                    d + '        previewText = quotedMsg?.toText()?.take(80)?.ifBlank { ' + D + '（引用的消息已不在对话中）' + D + ' } ?: ' + D + '（引用的消息已不在对话中）' + D + ',',
                    d + '        onClick = {',
                    d + '            val qIdx = displayGroups.indexOfFirst { g -> g.nodes.any { n -> n.messages.any { m -> m.id == quotedId } } }',
                    d + '            if (qIdx >= 0) scope.launch { state.scrollToItem(qIdx) }',
                    d + '        },',
                    d + '    )',
                    d + '}',
                ]
                nb = NL.join(new_block)
                if nb.count('{') - nb.count('}') != 0:
                    warns.append('rhQuoteRepair123: new block unbalanced; skipped')
                else:
                    out = NL.join(cl_lines[:a_i] + new_block + cl_lines[close_i + 1:])
                    if out.count('{') - out.count('}') == cl_text.count('{') - cl_text.count('}'):
                        (ROOT / CL).write_text(out, encoding='utf-8')
                        info['fix'] = 'OK'
                    else:
                        warns.append('rhQuoteRepair123: file balance changed; rolled back')

    cl_text2 = read(CL)
    cl_line = 'MISSING'
    for ln in cl_text2.split(NL):
        if 'rhQuoteId = group.displayMessage.quotedMessageId' in ln:
            cl_line = trim(ln, 150)
            break
    if cl_line == 'MISSING':
        for ln in cl_text2.split(NL):
            if 'quotedMessageId?.let { quotedId ->' in ln:
                cl_line = trim(ln, 150)
                break
    info['clId'] = cl_line
except Exception as e:
    w('rhQuoteRepair123 exception: ' + str(e)[:160])

for k in ['vmSig', 'vmCall', 'csSig', 'csW', 'clId', 'cpn', 'sends']:
    if k not in info:
        info[k] = 'MISSING'
if 'cp2' not in info:
    info['cp2'] = '0'

for m in warns:
    w(m)

# Last two lines: echoed by the workflow's tail -n 2 and surfaced as check annotations.
print('::notice::rhQE1 vmSig=[' + info['vmSig'] + '] vmCall=[' + info['vmCall'] + '] csSig=[' + info['csSig'] + '] csW=[' + info['csW'] + ']')
print('::notice::rhQE2 fix=' + info.get('fix', 'skip') + ' w=' + str(len(warns)) + ' cpn=' + info['cpn'] + ' cp2=' + info['cp2'] + ' sends=[' + info['sends'] + '] cl=[' + info['clId'] + ']')