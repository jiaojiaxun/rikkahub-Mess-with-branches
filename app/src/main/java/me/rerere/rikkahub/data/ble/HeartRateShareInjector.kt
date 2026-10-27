package me.rerere.rikkahub.data.ble

import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import me.rerere.ai.ui.UIMessagePart
import me.rerere.rikkahub.data.datastore.SettingsStore
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * rhHeartRateShare: 「发送消息时附带心率」的唯一注入实现。
 *
 * 只在三件事同时成立时注入：设置开关打开、心率带已连接、有可用读数。注入段固定放在
 * parts 首位，带 metadata rikkahub.hidden=true；UI 渲染层（ChatMessage 的 MessagePartsBlock
 * 调用点）据此过滤，模型侧照常收到（ProviderMessageUtils 不改）。
 *
 * 幂等：若传入 parts 已含隐藏段（编辑重发带回原始 parts 的情形）则不再插入，避免重复。
 */
object HeartRateShareInjector {
    const val HIDDEN_META_KEY = me.rerere.ai.ui.HIDDEN_PART_META_KEY // rhHiddenPart283: 键与 ai 模块同源

    fun maybePrepend(
        settingsStore: SettingsStore,
        content: List<UIMessagePart>,
    ): List<UIMessagePart> {
        if (!settingsStore.settingsFlow.value.shareHeartRateWithAI) return content
        val hr = HeartRateMonitor.state.value
        if (!hr.connected) return content
        val bpm = hr.bpm ?: return content
        if (content.any { part -> isHiddenPart(part) }) return content
        val stamp = SimpleDateFormat("HH:mm", Locale.getDefault()).format(Date(hr.lastUpdateMillis))
        val device = hr.deviceName?.takeIf { it.isNotBlank() }?.let { ", device " + it } ?: ""
        val text = "«用户当前心率：" + bpm + " bpm，采集时间 " + stamp + device + "，数据来源：BLE 心率带»"
        val part = UIMessagePart.Text(
            text = text,
            metadata = JsonObject(mapOf(HIDDEN_META_KEY to JsonPrimitive(true))),
        )
        return listOf(part) + content
    }

    /** part 是否是隐藏注入段（只给模型看，不进 UI）。 */
    fun isHiddenPart(part: UIMessagePart): Boolean {
        val meta = part.metadata ?: return false
        val flag = meta[HIDDEN_META_KEY] as? JsonPrimitive ?: return false
        return flag.content == "true"
    }
}
