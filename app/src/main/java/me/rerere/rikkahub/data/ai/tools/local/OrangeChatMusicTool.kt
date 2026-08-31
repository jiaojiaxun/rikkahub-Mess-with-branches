/*
 * 橘瓣 OrangeChat
 * 衍生自 RikkaHub (https://github.com/rikkahub/rikkahub)，原作者 RE
 * 本项目基于 GNU AGPL v3 开源，详见根目录 LICENSE 文件
 *
 * 本项目精简版移除了通知监听权限；媒体控制改用系统媒体按键和媒体搜索 Intent。
 */
package me.rerere.rikkahub.data.ai.tools.local

import android.app.SearchManager
import android.content.Context
import android.content.Intent
import android.media.AudioManager
import android.view.KeyEvent
import android.provider.MediaStore
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonObject
import me.rerere.ai.core.InputSchema
import me.rerere.ai.core.Tool
import me.rerere.ai.ui.UIMessagePart

fun createMusicTool(context: Context): Tool = Tool(
    name = "control_music",
    needsApproval = { true },
    description = "Control music playback without notification access. Supports play, pause, next, previous and play_search through system media keys and media intents. Current-track metadata and precise seeking are unavailable without notification access.",
    parameters = {
        InputSchema.Obj(
            properties = buildJsonObject {
                putJsonObject("action") {
                    put("type", JsonPrimitive("string"))
                    put("description", JsonPrimitive("Action: play, pause, next, previous, seek, play_search, or get_now_playing"))
                    put("enum", buildJsonArray {
                        add(JsonPrimitive("get_now_playing"))
                        add(JsonPrimitive("play"))
                        add(JsonPrimitive("pause"))
                        add(JsonPrimitive("next"))
                        add(JsonPrimitive("previous"))
                        add(JsonPrimitive("seek"))
                        add(JsonPrimitive("play_search"))
                    })
                }
                putJsonObject("position_ms") {
                    put("type", JsonPrimitive("integer"))
                    put("description", JsonPrimitive("Seeking is not available in the slim build; retained for compatibility."))
                }
                putJsonObject("query") {
                    put("type", JsonPrimitive("string"))
                    put("description", JsonPrimitive("Search query for play_search"))
                }
                putJsonObject("artist") {
                    put("type", JsonPrimitive("string"))
                    put("description", JsonPrimitive("Optional artist for play_search"))
                }
                putJsonObject("title") {
                    put("type", JsonPrimitive("string"))
                    put("description", JsonPrimitive("Optional title for play_search"))
                }
            },
            required = listOf("action"),
        )
    },
    execute = { args ->
        val params = args.jsonObject
        val action = params["action"]?.jsonPrimitive?.contentOrNull.orEmpty()
        fun result(success: Boolean, message: String, extra: Map<String, String> = emptyMap()) =
            listOf(UIMessagePart.Text(buildJsonObject {
                put("success", success)
                put("action", action)
                put("message", message)
                extra.forEach { (key, value) -> put(key, value) }
            }.toString()))

        try {
            when (action) {
                "play", "pause", "next", "previous" -> {
                    val keyCode = when (action) {
                        "play" -> KeyEvent.KEYCODE_MEDIA_PLAY
                        "pause" -> KeyEvent.KEYCODE_MEDIA_PAUSE
                        "next" -> KeyEvent.KEYCODE_MEDIA_NEXT
                        else -> KeyEvent.KEYCODE_MEDIA_PREVIOUS
                    }
                    val audio = context.getSystemService(AudioManager::class.java)
                        ?: return@Tool result(false, "系统媒体服务不可用")
                    val now = System.currentTimeMillis()
                    audio.dispatchMediaKeyEvent(KeyEvent(now, now, KeyEvent.ACTION_DOWN, keyCode, 0))
                    audio.dispatchMediaKeyEvent(KeyEvent(now, now, KeyEvent.ACTION_UP, keyCode, 0))
                    result(true, "已发送 $action 媒体控制按键")
                }
                "get_now_playing" -> result(
                    true,
                    "精简版已移除通知监听，无法读取当前曲目元数据；可使用 play、pause、next 或 previous 控制播放。",
                )
                "seek" -> result(false, "精简版不申请通知监听，暂不支持精确拖动")
                "play_search" -> {
                    val query = params["query"]?.jsonPrimitive?.contentOrNull.orEmpty()
                    val artist = params["artist"]?.jsonPrimitive?.contentOrNull.orEmpty()
                    val title = params["title"]?.jsonPrimitive?.contentOrNull.orEmpty()
                    if (query.isBlank() && artist.isBlank() && title.isBlank()) {
                        return@Tool result(false, "play_search 至少需要 query、artist 或 title 之一")
                    }
                    val intent = Intent(MediaStore.INTENT_ACTION_MEDIA_PLAY_FROM_SEARCH).apply {
                        putExtra(MediaStore.EXTRA_MEDIA_FOCUS, if (artist.isNotBlank() || title.isNotBlank()) {
                            MediaStore.Audio.Artists.ENTRY_CONTENT_TYPE
                        } else {
                            MediaStore.Audio.Media.ENTRY_CONTENT_TYPE
                        })
                        putExtra(SearchManager.QUERY, query)
                        if (artist.isNotBlank()) putExtra(MediaStore.EXTRA_MEDIA_ARTIST, artist)
                        if (title.isNotBlank()) putExtra(MediaStore.EXTRA_MEDIA_TITLE, title)
                        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK
                            or Intent.FLAG_ACTIVITY_CLEAR_TOP)
                    }
                    if (context.packageManager.queryIntentActivities(intent, 0).isEmpty()) {
                        return@Tool result(false, "没有找到支持媒体搜索播放的应用")
                    }
                    context.startActivity(intent)
                    result(true, "已发送媒体搜索播放请求", mapOf("query" to query, "artist" to artist, "title" to title))
                }
                else -> result(false, "未知 action：$action")
            }
        } catch (error: Exception) {
            result(false, error.message ?: "媒体控制失败")
        }
    },
)
