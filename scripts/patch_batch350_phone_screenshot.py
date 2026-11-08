#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rhPhone350 -- 截图标号 + phone_screen 的 image 参数（对齐 dsh-go 的 ScreenShooter）。

dsh-go 的 screen 工具有 image:true：返回带编号的截图，模型能看图定位。
现在只有文字，遇到游戏/自绘界面（文本树很差的页面）就无能为力。

本批四件事：
1. 新 phone/PhoneScreenshot.kt：
   - AccessibilityService.takeScreenshot（API 30+）拿硬件缓冲；
   - 转 ARGB_8888 拷贝，用 Canvas 在每个元素中心画 [id] 黑底白字；
   - 存到 cacheDir/phone_screen_<ts>.png，返回 file:// URL。
2. PhoneCore.Result 加 imageUrl（默认 null，兼容所有现有构造点）。
3. screen() 读 args.image，成功时带 imageUrl。
4. PhoneTools.run 返回 Text + Image 两部分；screenTool 的 schema 加 image 参数。

不做（下一批）：A11yKeeper、操作日志、任务卡、通知兜底。
"""
import os
import sys

MARK = "rhPhone350"
DIAG = "ci_diag_batch350_screenshot.txt"
Q = chr(34)
ROOT = os.path.abspath(os.getcwd())
rows = []

SHOT = r'''package me.rerere.rikkahub.phone

import android.accessibilityservice.AccessibilityService
import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.os.Build
import android.view.Display
import java.io.File
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/**
 * rhPhone350 -- 截图标号（对齐 dsh-go 的 a11y/ScreenShooter.kt）。
 *
 * 只读用途：让模型在文字树很差（游戏、自绘界面、小程序）时还能看到布局。
 * takeScreenshot 需要 API 30+；失败或超时返回 null，调用方退回纯文字。
 */
object PhoneScreenshot {
    private const val TIMEOUT_MS = 5_000L

    fun captureToCache(
        context: Context,
        service: AccessibilityService,
        elements: List<ScreenElement>,
    ): String? {
        if (Build.VERSION.SDK_INT < 30) return null
        val latch = CountDownLatch(1)
        var raw: Bitmap? = null
        val started = runCatching {
            service.takeScreenshot(
                Display.DEFAULT_DISPLAY,
                context.mainExecutor,
                object : AccessibilityService.TakeScreenshotCallback {
                    override fun onSuccess(result: AccessibilityService.ScreenshotResult) {
                        raw = runCatching {
                            Bitmap.wrapHardwareBuffer(result.hardwareBuffer, result.colorSpace)
                                ?.copy(Bitmap.Config.ARGB_8888, true)
                        }.getOrNull()
                        runCatching { result.hardwareBuffer.close() }
                        latch.countDown()
                    }

                    override fun onFailure(errorCode: Int) {
                        latch.countDown()
                    }
                },
            )
        }.isSuccess
        if (!started) return null
        if (!latch.await(TIMEOUT_MS, TimeUnit.MILLISECONDS)) return null
        val base = raw ?: return null
        val labeled = runCatching { drawLabels(base, elements) }.getOrElse { base }
        val file = File(context.cacheDir, "phone_screen_" + System.currentTimeMillis() + ".png")
        val ok = runCatching {
            file.outputStream().use { out -> labeled.compress(Bitmap.CompressFormat.PNG, 90, out) }
        }.isSuccess
        if (!ok) return null
        return "file://" + file.absolutePath
    }

    private fun drawLabels(src: Bitmap, elements: List<ScreenElement>): Bitmap {
        val out = src.copy(Bitmap.Config.ARGB_8888, true)
        val canvas = Canvas(out)
        val textPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.WHITE
            textSize = 28f
            isFakeBoldText = true
        }
        val bgPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.parseColor("#CC000000")
        }
        for (el in elements) {
            if (el.bounds.isEmpty) continue
            val label = "[" + el.id + "]"
            val w = textPaint.measureText(label) + 12f
            val h = 34f
            val x = el.bounds.centerX.toFloat() - w / 2f
            val y = el.bounds.centerY.toFloat() - h / 2f
            canvas.drawRoundRect(x, y, x + w, y + h, 8f, 8f, bgPaint)
            canvas.drawText(label, x + 6f, y + 26f, textPaint)
        }
        return out
    }
}
'''


def note(msg):
    line = "[batch350] " + str(msg)
    print(line)
    rows.append(line)


def flush():
    try:
        with open(os.path.join(ROOT, DIAG), "w", encoding="utf-8") as f:
            f.write("\n".join(rows) + "\n")
    except Exception:
        pass


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def write(rel, text):
    path = os.path.join(ROOT, rel)
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def parens(t):
    return (t.count("(") - t.count(")"), t.count("{") - t.count("}"), t.count("[") - t.count("]"))


def step_shot():
    rel = "app/src/main/java/me/rerere/rikkahub/phone/PhoneScreenshot.kt"
    path = os.path.join(ROOT, rel)
    if os.path.exists(path):
        if MARK in read(rel):
            note("skip PhoneScreenshot")
            return
        note("exists without marker")
        return
    write(rel, SHOT)
    if "fun captureToCache(" not in read(rel):
        note("write-back bad")
        return
    note("wrote PhoneScreenshot.kt")


def step_result():
    rel = "app/src/main/java/me/rerere/rikkahub/phone/PhoneCore.kt"
    text = read(rel)
    if "val imageUrl: String?" in text:
        note("skip Result (already applied)")
        return
    needle = "    class Result(val text: String, val failed: Boolean = false)"
    if text.count(needle) != 1:
        note("Result anchor count=" + str(text.count(needle)))
        return
    repl = "    class Result(val text: String, val failed: Boolean = false, val imageUrl: String? = null) // " + MARK
    text = text.replace(needle, repl, 1)
    write(rel, text)
    note("PhoneCore: Result.imageUrl added")


def step_screen():
    rel = "app/src/main/java/me/rerere/rikkahub/phone/PhoneCore.kt"
    text = read(rel)
    if "PhoneScreenshot.captureToCache" in text:
        note("skip screen (already applied)")
        return
    needle = "        return Result(snap.formatted.text)\n    }\n\n    private fun collect("
    if text.count(needle) != 1:
        note("screen return anchor count=" + str(text.count(needle)))
        return
    repl = """        val wantImage = args.bool("image")
        val imageUrl = if (wantImage) {
            PhoneScreenshot.captureToCache(context, service, snap.formatted.elements)
        } else {
            null
        }
        return Result(snap.formatted.text, imageUrl = imageUrl) // """ + MARK + """
    }

    private fun collect("""
    text = text.replace(needle, repl, 1)
    write(rel, text)
    note("PhoneCore: screen reads image arg")


def step_tools_run():
    rel = "app/src/main/java/me/rerere/rikkahub/phone/PhoneTools.kt"
    text = read(rel)
    if MARK in text:
        note("skip PhoneTools run (already applied)")
        return
    needle = """private suspend fun run(context: Context, name: String, args: JsonObject): List<UIMessagePart> {
    val result = PhoneCore.call(context, name, args)
    return listOf(UIMessagePart.Text(result.text))
}"""
    if text.count(needle) != 1:
        note("run anchor count=" + str(text.count(needle)))
        return
    repl = """private suspend fun run(context: Context, name: String, args: JsonObject): List<UIMessagePart> {
    val result = PhoneCore.call(context, name, args)
    // """ + MARK + """: 截图标号随文字一起返回
    val parts = mutableListOf<UIMessagePart>(UIMessagePart.Text(result.text))
    result.imageUrl?.let { parts.add(UIMessagePart.Image(url = it)) }
    return parts
}"""
    text = text.replace(needle, repl, 1)

    # screenTool 的 schema 加 image
    schema_needle = '                put("detail", boolProp("附上元素坐标"))'
    if text.count(schema_needle) != 1:
        note("screen schema anchor count=" + str(text.count(schema_needle)))
        return
    text = text.replace(
        schema_needle,
        schema_needle + '\n                put("image", boolProp("附带标号截图（只对能看图的模型有用）"))',
        1,
    )
    write(rel, text)
    note("PhoneTools: run Text+Image, screen schema +image")


def main():
    step_shot()
    step_result()
    step_screen()
    step_tools_run()
    note("DONE")
    flush()
    print("::error::batch350 END lines=" + str(len(rows)))
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        note("EXCEPTION " + type(exc).__name__ + " " + str(exc)[:240])
        flush()
        sys.exit(0)