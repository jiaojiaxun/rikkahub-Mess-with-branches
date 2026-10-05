package me.rerere.rikkahub.data.ai.tools.local

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.os.Build
import androidx.core.app.NotificationCompat
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import me.rerere.ai.core.InputSchema
import me.rerere.ai.core.Tool
import me.rerere.ai.ui.UIMessagePart

fun notificationTool(
    context: Context,
): Tool = Tool(
    name = "send_notification",
    description = """
        Send a system notification to the user's status bar, like a WeChat message notification.
        The notification appears in the notification shade and may make a sound/vibrate depending on system settings.
        Use this to proactively notify the user of important information, completed tasks, or reminders.
        The notification is clickable but does not open a specific screen — it serves as a visual alert.
    """.trimIndent().replace("\n", " "),
    parameters = {
        InputSchema.Obj(
            properties = buildJsonObject {
                put("title", buildJsonObject {
                    put("type", "string")
                    put("description", "The title of the notification (shown in the status bar)")
                })
                put("text", buildJsonObject {
                    put("type", "string")
                    put("description", "The main text/content of the notification")
                })
                put("channel_id", buildJsonObject {
                    put("type", "string")
                    put("description", "Optional channel ID for grouping notifications (default: 'default')")
                })
            },
            required = listOf("title", "text")
        )
    },
    execute = {
        val params = it.jsonObject
        val title = params["title"]?.jsonPrimitive?.contentOrNull
            ?: error("title is required")
        val text = params["text"]?.jsonPrimitive?.contentOrNull
            ?: error("text is required")
        val channelId = params["channel_id"]?.jsonPrimitive?.contentOrNull ?: "default"

        val nm = context.getSystemService(NotificationManager::class.java)

        // Create channel (idempotent — safe to call every time)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                channelId,
                "AI Notifications",
                NotificationManager.IMPORTANCE_HIGH,
            ).apply {
                description = "Notifications sent by the AI assistant"
                enableVibration(true)
            }
            nm.createNotificationChannel(channel)
        }

        val notificationId = System.currentTimeMillis().toInt()

        val builder = NotificationCompat.Builder(context, channelId)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle(title)
            .setContentText(text)
            .setStyle(NotificationCompat.BigTextStyle().bigText(text))
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setAutoCancel(true)

        nm.notify(notificationId, builder.build())

        val payload = buildJsonObject {
            put("success", true)
            put("notification_id", notificationId)
            put("title", title)
            put("text", text)
        }
        listOf(UIMessagePart.Text(payload.toString()))
    }
)
