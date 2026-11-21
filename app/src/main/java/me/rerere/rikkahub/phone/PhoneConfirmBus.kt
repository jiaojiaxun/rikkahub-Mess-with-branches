package me.rerere.rikkahub.phone

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.withTimeoutOrNull

/**
 * rhPhone349 -- 动作级确认通道。
 *
 * PhoneCore 在需要用户点头的那一步挂起在这里，UI 侧的 PhoneConfirmHost 弹窗，
 * 用户点允许/拒绝后 resume。30 秒没人理按拒绝处理（安全默认）。
 *
 * 不用 RikkaHub 的工具审批卡：那张卡是「一次工具调用」粒度，问的是
 * 「是否允许 phone_tap 执行」，而不是「是否在微信点发送」。
 */
object PhoneConfirmBus {
    class Request(
        val sentence: String,
        val appLabel: String?,
        val packageName: String?,
        val reason: String,
        val completer: CompletableDeferred<Boolean>,
    )

    private val _current = MutableStateFlow<Request?>(null)
    val current: StateFlow<Request?> = _current.asStateFlow()

    suspend fun ask(sentence: String, appLabel: String?, pkg: String?, reason: String): Boolean {
        val deferred = CompletableDeferred<Boolean>()
        _current.value = Request(sentence, appLabel, pkg, reason, deferred)
        return try {
            withTimeoutOrNull(30_000L) { deferred.await() } ?: false
        } finally {
            _current.value = null
        }
    }

    fun answer(allow: Boolean) {
        _current.value?.completer?.complete(allow)
    }
}
