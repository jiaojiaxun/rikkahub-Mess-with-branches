package me.rerere.rikkahub.data.ai.tools.local

import android.app.AppOpsManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Environment
import android.os.PowerManager
import android.os.Process
import android.provider.Settings
import androidx.core.content.ContextCompat
import androidx.core.net.toUri

object PermissionHelper {
    fun hasRuntime(ctx: Context, perms: List<String>): Boolean =
        perms.all { ContextCompat.checkSelfPermission(ctx, it) == PackageManager.PERMISSION_GRANTED }

    fun hasWriteSettings(ctx: Context): Boolean = Settings.System.canWrite(ctx)

    fun writeSettingsIntent(ctx: Context): Intent =
        Intent(Settings.ACTION_MANAGE_WRITE_SETTINGS, "package:${ctx.packageName}".toUri())

    fun hasUsageAccess(ctx: Context): Boolean =
        ctx.getSystemService(AppOpsManager::class.java)?.let { manager ->
            manager.checkOpNoThrow(
                AppOpsManager.OPSTR_GET_USAGE_STATS,
                Process.myUid(),
                ctx.packageName,
            ) == AppOpsManager.MODE_ALLOWED
        } == true

    fun usageAccessIntent(): Intent = Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS)

    /**
     * True iff the app is exempted from Doze battery optimizations. Without this exemption,
     * OEM-aggressive ROMs (Xiaomi/OPPO/OnePlus/Vivo) cut network for foreground services when
     * screen turns off, which can interrupt long-running network work.
     */
    fun ignoresBatteryOptimizations(ctx: Context): Boolean =
        ctx.getSystemService(PowerManager::class.java)
            ?.isIgnoringBatteryOptimizations(ctx.packageName) ?: false

    /**
     * Direct prompt to whitelist the app from Doze. Required-permission per Play Store policy
     * is `REQUEST_IGNORE_BATTERY_OPTIMIZATIONS`; manifest declares it.
     */
    fun requestIgnoreBatteryOptimizationsIntent(ctx: Context): Intent =
        Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS)
            .setData("package:${ctx.packageName}".toUri())

    /** Fallback page for users who declined the prompt; shows the system-wide list. */
    fun batteryOptimizationsListIntent(): Intent =
        Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS)

    /**
     * "All files access" — gates File.listFiles() on shared storage paths like
     * /storage/emulated/0/Download. Without it, scoped storage hides every
     * pre-existing file (only subdirs and the calling app's own creations show
     * up). Granted via the system "Allow access to manage all files" toggle.
     * On API < 30 there's no scoped-storage gate to begin with, so we treat it
     * as always-granted there.
     */
    fun hasAllFilesAccess(@Suppress("UNUSED_PARAMETER") ctx: Context): Boolean =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            Environment.isExternalStorageManager()
        } else {
            true
        }

    fun allFilesAccessIntent(ctx: Context): Intent =
        Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION)
            .setData("package:${ctx.packageName}".toUri())
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
}
