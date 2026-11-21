package me.rerere.rikkahub.phone

import android.content.Context
import android.content.SharedPreferences

/**
 * rhPhone347 -- 手机操控的策略存储（对齐 dsh-go 的 PhonePolicies）。
 *
 * 确认模式：ASK 每次都问 / TASK 本任务免确认 / ALWAYS 始终免确认。
 * 解除限制：systemPages（系统页可操作）、secretFields（可填密码框）、ownApp（可操作自己）。
 *
 * 用独立 SharedPreferences，不动 Settings/DisplaySetting 的序列化与备份格式。
 */
object PhonePoliciesStore {
    private const val PREFS = "rh_phone_policies"
    private const val KEY_MODE = "confirm_mode"
    private const val KEY_UNLOCK_SYSTEM = "unlock_system_pages"
    private const val KEY_UNLOCK_SECRET = "unlock_secret_fields"
    private const val KEY_UNLOCK_OWN = "unlock_own_app"

    @Volatile
    var current: PhonePolicies = PhonePolicies()
        private set

    fun init(context: Context) {
        val sp = prefs(context)
        current = PhonePolicies(
            confirmMode = ConfirmMode.fromWire(sp.getString(KEY_MODE, null)) ?: ConfirmMode.ASK,
            unlocks = PhoneUnlocks(
                systemPages = sp.getBoolean(KEY_UNLOCK_SYSTEM, false),
                secretFields = sp.getBoolean(KEY_UNLOCK_SECRET, false),
                ownApp = sp.getBoolean(KEY_UNLOCK_OWN, false),
            ),
        )
    }

    fun setConfirmMode(context: Context, mode: ConfirmMode) {
        prefs(context).edit().putString(KEY_MODE, mode.wire).apply()
        current = current.copy(confirmMode = mode)
    }

    /** key: system / secret / own */
    fun setUnlock(context: Context, key: String, value: Boolean) {
        val editor = prefs(context).edit()
        when (key) {
            "system" -> {
                editor.putBoolean(KEY_UNLOCK_SYSTEM, value)
                current = current.copy(unlocks = current.unlocks.copy(systemPages = value))
            }
            "secret" -> {
                editor.putBoolean(KEY_UNLOCK_SECRET, value)
                current = current.copy(unlocks = current.unlocks.copy(secretFields = value))
            }
            "own" -> {
                editor.putBoolean(KEY_UNLOCK_OWN, value)
                current = current.copy(unlocks = current.unlocks.copy(ownApp = value))
            }
        }
        editor.apply()
    }

    private fun prefs(context: Context): SharedPreferences =
        context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
}
