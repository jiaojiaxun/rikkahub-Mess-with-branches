package me.rerere.rikkahub.phone

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
