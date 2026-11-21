#!/usr/bin/env python3
# rhImageId381: 生成图片的短编号注册表
import os, sys
from pathlib import Path

ROOT = Path(os.environ.get("GITHUB_WORKSPACE") or ".")
DIAG = ROOT / "ci_diag_batch381_image_ids.txt"
TARGET = ROOT / "app/src/main/java/me/rerere/rikkahub/utils/RhImageIdRegistry.kt"
out = []


def log(msg):
    out.append(msg)
    print(msg)


SRC = r'''package me.rerere.rikkahub.utils

import android.content.Context
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonPrimitive
import java.io.File
import java.security.MessageDigest

/**
 * rhImageId381 — generated-image short ids.
 *
 * id = SHA-256 of the image bytes (64 lowercase hex chars), so the same picture always
 * gets the same id. The id -> absolute path map is persisted in
 * filesDir/rh_image_ids.json so the markdown renderer can turn `!img[<id>]` back into a
 * real image inside the reply body.
 */
object RhImageIdRegistry {
    private const val FILE_NAME = "rh_image_ids.json"
    private val json = Json { ignoreUnknownKeys = true }
    private val ids = HashMap<String, String>()

    @Volatile
    private var appContext: Context? = null

    @Synchronized
    fun init(context: Context) {
        if (appContext != null) return
        val app = context.applicationContext
        appContext = app
        val file = File(app.filesDir, FILE_NAME)
        if (!file.isFile) return
        runCatching {
            val obj = json.parseToJsonElement(file.readText()) as? JsonObject ?: return
            obj.forEach { (key, value) ->
                val path = value.jsonPrimitive.contentOrNull
                if (!path.isNullOrBlank()) ids[key] = path
            }
        }
    }

    @Synchronized
    fun register(path: String): String? {
        val file = File(path)
        if (!file.isFile) return null
        val id = runCatching { sha256(file) }.getOrNull() ?: return null
        ids[id] = file.absolutePath
        persist()
        return id
    }

    @Synchronized
    fun resolve(id: String): String? {
        val key = id.lowercase()
        val path = ids[key] ?: return null
        if (File(path).isFile) return path
        ids.remove(key)
        persist()
        return null
    }

    private fun persist() {
        val app = appContext ?: return
        runCatching {
            val obj = JsonObject(ids.mapValues { (_, value) -> JsonPrimitive(value) })
            File(app.filesDir, FILE_NAME).writeText(obj.toString())
        }
    }

    private fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buffer = ByteArray(8192)
            while (true) {
                val read = input.read(buffer)
                if (read <= 0) break
                digest.update(buffer, 0, read)
            }
        }
        val bytes = digest.digest()
        val builder = StringBuilder(bytes.size * 2)
        for (byte in bytes) {
            val value = byte.toInt() and 0xFF
            builder.append(Character.forDigit(value shr 4, 16))
            builder.append(Character.forDigit(value and 0x0F, 16))
        }
        return builder.toString()
    }
}
'''

try:
    if TARGET.is_file() and "rhImageId381" in TARGET.read_text(encoding="utf-8"):
        log("registry:already")
    else:
        TARGET.parent.mkdir(parents=True, exist_ok=True)
        TARGET.write_text(SRC, encoding="utf-8")
        log("registry:wrote")
except Exception as exc:
    log("EXCEPTION:" + repr(exc))
    print("::error title=batch381::" + repr(exc))

DIAG.write_text("\n".join(out) + "\n", encoding="utf-8")
sys.exit(0)
