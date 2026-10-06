#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch118 v3: fix shouldReport anchor

v2 failed: anchor 'internal fun shouldReportEmptyGenerationStream' used
exact strip match (==), but the actual line is
'internal fun shouldReportEmptyGenerationStream(receivedAnyChunk: Boolean): Boolean ='
which doesn't equal the bare function name.

v3: use startswith() instead of == for this anchor.
MSG and SCH sections passed in v2, unchanged here.

Adversarial check on ALL GH anchors:
  1. GENERATION_STREAM_RETRY_MAX_DELAY_MS — exact, v2 passed ✓
  2. shouldReportEmptyGenerationStream — startswith (v3 fix) ✓
  3. turnStartMs — exact, verified against source ✓
  4. '// no tool calls, break' — exact, verified against source ✓
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhAutoResume'
MSG = 'ai/src/main/java/me/rerere/ai/ui/Message.kt'
SCH = 'ai/src/main/java/me/rerere/ai/ui/StreamChunkHandler.kt'
GH = 'app/src/main/java/me/rerere/rikkahub/data/ai/GenerationHandler.kt'


def fail(msg, lines=None, around=-1, path=GH):
    body = 'batch118v3 ' + str(msg)
    if lines is not None and 0 <= around < len(lines):
        lo = max(0, around - 3)
        hi = min(len(lines), around + 4)
        ctx = ' || '.join('L' + str(i + 1) + ':' + lines[i].strip()[:90] for i in range(lo, hi))
        body = body + ' || ctx: ' + ctx
    print('::error file=' + path + '::' + body[:1400])
    sys.stdout.flush()
    sys.exit(1)


def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]


def balance(text):
    return (text.count('(') - text.count(')')) + (text.count('{') - text.count('}'))


# ============================================================
# A. Message.kt (unchanged from v2, already passed)
# ============================================================
t = (ROOT / MSG).read_text(encoding='utf-8')
if MARK in t:
    print('batch118v3 MSG: already applied')
else:
    bal0 = balance(t)
    lines = t.split(NL)
    idx = -1
    for i, ln in enumerate(lines):
        s = ln.strip()
        if s == 'val translation: String? = null,' or s == 'val translation: String? = null':
            idx = i
            break
    if idx < 0:
        fail('translation field line not found', lines, 0, path=MSG)
    if not lines[idx].rstrip().endswith(','):
        lines[idx] = lines[idx].rstrip() + ','
    d = ind(lines[idx])
    lines[idx + 1:idx + 1] = [d + 'val finishReason: String? = null // ' + MARK]
    out = NL.join(lines)
    if 'finishReason' not in out:
        fail('MSG selfcheck missing finishReason', path=MSG)
    if balance(out) != bal0:
        fail('MSG balance changed', path=MSG)
    (ROOT / MSG).write_text(out, encoding='utf-8')
    print('batch118v3 MSG: OK')


# ============================================================
# B+C. StreamChunkHandler.kt (unchanged from v2, already passed)
# ============================================================
t = (ROOT / SCH).read_text(encoding='utf-8')
if MARK in t:
    print('batch118v3 SCH: already applied')
else:
    bal0 = balance(t)
    lines = t.split(NL)
    applied = []

    FINISH_ANCHOR = 'is StreamChunk.Finish -> copy('
    hits = [i for i, ln in enumerate(lines) if ln.strip() == FINISH_ANCHOR]
    if len(hits) != 1:
        fail('Finish handler anchor count=' + str(len(hits)), lines, hits[0] if hits else 0, path=SCH)
    fi = hits[0]
    fa_idx = -1
    for j in range(fi + 1, min(fi + 4, len(lines))):
        if 'finishedAt = Clock.System.now().toLocalDateTime(TimeZone.currentSystemDefault())' in lines[j]:
            fa_idx = j
            break
    if fa_idx < 0:
        fail('Finish handler finishedAt not found', lines, fi, path=SCH)
    d = ind(lines[fa_idx])
    if not lines[fa_idx].rstrip().endswith(','):
        lines[fa_idx] = lines[fa_idx].rstrip() + ','
    lines.insert(fa_idx + 1, d + 'finishReason = chunk.finishReason // ' + MARK)
    applied.append('finish-handler')

    USAGE_ANCHOR = 'usage = result.usage,'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == USAGE_ANCHOR]
    if len(hits) != 1:
        fail('usage=result anchor count=' + str(len(hits)), lines, hits[0] if hits else 0, path=SCH)
    ui = hits[0]
    fa2 = -1
    for j in range(ui + 1, min(ui + 4, len(lines))):
        if 'finishedAt = Clock.System.now().toLocalDateTime(TimeZone.currentSystemDefault())' in lines[j]:
            fa2 = j
            break
    if fa2 < 0:
        fail('handleTextGenerationResult finishedAt not found', lines, ui, path=SCH)
    d = ind(lines[fa2])
    lines.insert(fa2 + 1, d + 'finishReason = result.finishReason, // ' + MARK)
    applied.append('handleTextResult')

    out = NL.join(lines)
    for need in [MARK, 'chunk.finishReason', 'result.finishReason']:
        if need not in out:
            fail('SCH selfcheck missing: ' + need, path=SCH)
    if balance(out) != bal0:
        fail('SCH balance changed', path=SCH)
    (ROOT / SCH).write_text(out, encoding='utf-8')
    print('batch118v3 SCH: OK (' + ', '.join(applied) + ')')


# ============================================================
# D-G. GenerationHandler.kt (v3: fix shouldReport anchor)
# ============================================================
t = (ROOT / GH).read_text(encoding='utf-8')
if MARK in t:
    print('batch118v3 GH: already applied')
else:
    bal0 = balance(t)
    lines = t.split(NL)
    applied = []

    # D. MAX_RESUMES constant
    CONST_ANCHOR = 'private const val GENERATION_STREAM_RETRY_MAX_DELAY_MS = 4_000L'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == CONST_ANCHOR]
    if len(hits) != 1:
        fail('const anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
    ci = hits[0]
    d = ind(lines[ci])
    lines.insert(ci + 1, d + 'private const val MAX_RESUMES = 3 // ' + MARK)
    applied.append('const')

    # E. shouldResumeGeneration + keyword sets before shouldReportEmptyGenerationStream
    #    v3 fix: use startswith() instead of ==
    REPORT_PREFIX = 'internal fun shouldReportEmptyGenerationStream'
    hits = [i for i, ln in enumerate(lines) if ln.strip().startswith(REPORT_PREFIX)]
    if len(hits) != 1:
        fail('shouldReport anchor count=' + str(len(hits)) + ' (prefix=' + REPORT_PREFIX + ')', lines, hits[0] if hits else 0)
    ri = hits[0]
    d = ind(lines[ri])
    helper = [
        d + '// ' + MARK + ': auto-resume keyword sets',
        d + 'private val TRUNCATION_FINISH_REASONS = setOf(',
        d + '    "length", "max_tokens", "max_output_tokens", "incomplete",',
        d + '    "incomplete:max_output_tokens", "max_completion_tokens",',
        d + ')',
        d + '',
        d + 'private val BLOCKED_FINISH_REASONS = setOf(',
        d + '    "content_filter", "safety", "blocked", "error",',
        d + ')',
        d + '',
        d + 'private fun shouldResumeGeneration(finishReason: String?, text: String): Boolean {',
        d + '    val lower = finishReason?.lowercase()',
        d + '    if (lower != null && lower in BLOCKED_FINISH_REASONS) return false',
        d + '    if (lower != null && lower in TRUNCATION_FINISH_REASONS) return true',
        d + '    if (text.isBlank() && lower == null) return true',
        d + '    return false',
        d + '}',
        d + '',
    ]
    lines[ri:ri] = helper
    applied.append('helper')

    # F. resumeCount before for loop
    TURN_ANCHOR = 'val turnStartMs = android.os.SystemClock.elapsedRealtime()'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == TURN_ANCHOR]
    if len(hits) != 1:
        fail('turnStartMs anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
    ti = hits[0]
    d = ind(lines[ti])
    lines.insert(ti + 1, d + 'var resumeCount = 0 // ' + MARK)
    applied.append('resumeCount')

    # G. resume logic in if(tools.isEmpty()) block
    BREAK_ANCHOR = '// no tool calls, break'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == BREAK_ANCHOR]
    if len(hits) != 1:
        fail('no tool calls break anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
    bi = hits[0]
    d = ind(lines[bi])
    resume_block = [
        d + '// ' + MARK + ': auto-resume after truncation',
        d + 'val assistantText = messages.last().parts',
        d + '    .filterIsInstance<UIMessagePart.Text>()',
        d + '    .joinToString("") { it.text }',
        d + 'val msgFinishReason = messages.last().finishReason',
        d + 'if (shouldResumeGeneration(msgFinishReason, assistantText) && resumeCount < MAX_RESUMES) {',
        d + '    resumeCount++',
        d + '    Log.i(TAG, "generateText: resuming after truncation (finishReason=$msgFinishReason, attempt=$resumeCount/$MAX_RESUMES)")',
        d + '    messages = messages + UIMessage.user("\u7ee7\u7eed")',
        d + '    continue',
        d + '}',
    ]
    lines[bi:bi] = resume_block
    applied.append('resume-logic')

    out = NL.join(lines)
    for need in [MARK, 'MAX_RESUMES', 'shouldResumeGeneration', 'resumeCount', 'UIMessage.user']:
        if need not in out:
            fail('GH selfcheck missing: ' + need)
    if balance(out) != bal0:
        fail('GH balance changed: ' + str(bal0) + ' -> ' + str(balance(out)))
    (ROOT / GH).write_text(out, encoding='utf-8')
    print('batch118v3 GH: OK (' + ', '.join(applied) + ')')
