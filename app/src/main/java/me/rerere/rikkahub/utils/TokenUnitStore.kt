package me.rerere.rikkahub.utils

import android.content.Context

/**
 * rhTokenUnit338 -- token 计数单位的全局开关。
 *
 * 默认 K：沿用 [formatNumber] 的自适应（<1K 原值、1.2K、3.4M）。
 * 打开后统一按百万：0.13M / 1.50M / 128M。
 *
 * 为什么不用 DisplaySetting：那条链要走 PreferencesStore 的 JSON 序列化与备份格式，
 * 一个纯展示偏好不值得动数据契约。这里用独立 SharedPreferences，App 启动时 [init]。
 */
object TokenUnitStore {
    private const val PREFS = "rh_token_unit"
    private const val KEY = "millions"

    @Volatile
    var millions: Boolean = false
        private set

    fun init(context: Context) {
        val sp = context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        millions = sp.getBoolean(KEY, false)
    }

    fun set(context: Context, value: Boolean) {
        millions = value
        context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putBoolean(KEY, value)
            .apply()
    }
}

/** 按当前开关格式化 token 数：K 模式自适应，M 模式统一百万。 */
fun Int.formatTokens(): String {
    if (!TokenUnitStore.millions) return this.formatNumber()
    val absValue = kotlin.math.abs(this)
    if (absValue < 1000) return this.toString()
    val sign = if (this < 0) "-" else ""
    val m = absValue / 1_000_000.0
    return when {
        m >= 100.0 -> sign + m.toInt().toString() + "M"
        m >= 10.0 -> sign + m.toFixed(1) + "M"
        else -> sign + m.toFixed(2) + "M"
    }
}
