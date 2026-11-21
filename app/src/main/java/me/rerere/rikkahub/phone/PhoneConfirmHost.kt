package me.rerere.rikkahub.phone

import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle

/**
 * rhPhone349 -- 动作级确认弹窗。挂在聊天页，观察 PhoneConfirmBus。
 *
 * 后台（聊天页不在前台）时不会显示，bus 30 秒后按拒绝处理。
 */
@Composable
fun PhoneConfirmHost() {
    val request by PhoneConfirmBus.current.collectAsStateWithLifecycle()
    val r = request ?: return
    AlertDialog(
        onDismissRequest = { PhoneConfirmBus.answer(false) },
        title = { Text("允许这一步吗？") },
        text = { Text(r.sentence) },
        confirmButton = {
            TextButton(onClick = { PhoneConfirmBus.answer(true) }) { Text("允许") }
        },
        dismissButton = {
            TextButton(onClick = { PhoneConfirmBus.answer(false) }) { Text("拒绝") }
        },
    )
}
