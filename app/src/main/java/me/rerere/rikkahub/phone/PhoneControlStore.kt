package me.rerere.rikkahub.phone

import android.content.Context

/**
 * rhPhone346 -- 手机操控的 App 级总开关。
 *
 * 与 Assistant.localTools 里的 per-assistant 开关是「或」的关系：
 * 任一为真就注册 11 个 phone_* 工具。这样从设置页开一次就全局可用，
 * 也不需要迁移旧助手的配置。
 */
object PhoneControlStore {
    private const val PREFS = "rh_phone_control"
    private const val KEY_ENABLED = "enabled"

    @Volatile
    var enabled: Boolean = false
        private set

    fun init(context: Context) {
        val sp = context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        enabled = sp.getBoolean(KEY_ENABLED, false)
    }

    fun set(context: Context, value: Boolean) {
        enabled = value
        context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putBoolean(KEY_ENABLED, value)
            .apply()
    }
}
