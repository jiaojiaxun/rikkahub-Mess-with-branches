package me.rerere.rikkahub.service

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

private const val TAG = "CronBootReceiver"

/**
 * 开机/应用更新后重建全部定时任务的 WorkManager 排期。
 */
class CronBootReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        val action = intent.action
        if (action != Intent.ACTION_BOOT_COMPLETED &&
            action != Intent.ACTION_MY_PACKAGE_REPLACED
        ) return

        val pending = goAsync()
        CoroutineScope(Dispatchers.IO).launch {
            try {
                val scheduler = org.koin.core.context.GlobalContext.get()
                    .get<CronJobScheduler>()
                scheduler.scheduleAllEnabled()
                Log.i(TAG, "rescheduled all enabled cron jobs")
            } catch (error: Throwable) {
                Log.w(TAG, "cron boot reschedule failed", error)
            } finally {
                pending.finish()
            }
        }
    }
}
