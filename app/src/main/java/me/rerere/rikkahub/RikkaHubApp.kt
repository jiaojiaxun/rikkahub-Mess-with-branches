package me.rerere.rikkahub

import android.app.Application
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.util.Log
import androidx.compose.foundation.ComposeFoundationFlags
import androidx.compose.runtime.Composer
import androidx.compose.runtime.tooling.ComposeStackTraceMode
import androidx.core.app.NotificationChannelCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import kotlinx.coroutines.CoroutineExceptionHandler
import kotlinx.coroutines.CoroutineName
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import me.rerere.common.android.Logging
import me.rerere.common.android.appTempFolder
import com.whl.quickjs.android.QuickJSLoader
import me.rerere.rikkahub.di.appModule
import me.rerere.rikkahub.di.dataSourceModule
import me.rerere.rikkahub.di.repositoryModule
import me.rerere.rikkahub.plugin.di.pluginModule
import me.rerere.rikkahub.di.viewModelModule
import me.rerere.rikkahub.data.files.FilesManager
import me.rerere.rikkahub.data.datastore.SettingsStore
import me.rerere.rikkahub.service.WebServerService
import me.rerere.rikkahub.utils.CrashHandler
import me.rerere.rikkahub.utils.DatabaseUtil
import me.rerere.rikkahub.data.repository.WorkspaceRepository
import me.rerere.workspace.WorkspaceManager
import org.koin.android.ext.android.get
import org.koin.android.ext.koin.androidContext
import org.koin.android.ext.koin.androidLogger
import org.koin.core.context.startKoin

private const val TAG = "RikkaHubApp"

enum class AppStartupStage {
    Starting,
    LoadingCore,
    PreparingData,
    LoadingServices,
    Finalizing,
    Ready,
}

data class AppStartupProgress(
    val percent: Int = 0,
    val stage: AppStartupStage = AppStartupStage.Starting,
    val ready: Boolean = false,
)

object AppStartupProgressTracker {
    private val _state = MutableStateFlow(AppStartupProgress())
    val state: StateFlow<AppStartupProgress> = _state.asStateFlow()

    fun update(percent: Int, stage: AppStartupStage, ready: Boolean = false) {
        _state.value = AppStartupProgress(percent.coerceIn(0, 100), stage, ready)
    }
}

const val CHAT_LIVE_UPDATE_NOTIFICATION_CHANNEL_ID = "chat_live_update"
const val WEB_SERVER_NOTIFICATION_CHANNEL_ID = "web_server"
const val MUSIC_PLAYER_NOTIFICATION_CHANNEL_ID = "plugin_music"
const val POMODORO_NOTIFICATION_CHANNEL_ID = "plugin_pomodoro"

class RikkaHubApp : Application() {
    override fun onCreate() {
        super.onCreate()
        AppStartupProgressTracker.update(5, AppStartupStage.Starting)
        // :ai (and other sub-:app modules) have no BuildConfig of their own, so this is
        // how their provider code learns whether it's running a debug build — needed to
        // gate full request/response body logging the same way HttpLoggingInterceptor
        // is already gated behind BuildConfig.DEBUG in DataSourceModule.
        Logging.setDebugLoggingEnabled(BuildConfig.DEBUG)
        startKoin {
            androidLogger()
            androidContext(this@RikkaHubApp)
            modules(appModule, viewModelModule, dataSourceModule, repositoryModule, pluginModule)
        }
        AppStartupProgressTracker.update(15, AppStartupStage.LoadingCore)
        this.createNotificationChannel()

        // set cursor window size to 32MB
        DatabaseUtil.setCursorWindowSize(32 * 1024 * 1024)
        AppStartupProgressTracker.update(25, AppStartupStage.PreparingData)

        // install crash handler
        CrashHandler.install(this)

        // Init QuickJS native library
        QuickJSLoader.init()
        AppStartupProgressTracker.update(40, AppStartupStage.PreparingData)

        // delete temp files
        deleteTempFiles()



        // check workspace integrity (mark workspaces with missing files as broken after backup restore)
        checkWorkspaceIntegrity()

        // sync upload files to DB
        syncManagedFiles()
        AppStartupProgressTracker.update(60, AppStartupStage.LoadingServices)

        // Start WebServer if enabled in settings
        startWebServerIfEnabled()

        // Eagerly construct ChatService on the main thread. Its constructor calls
        // LifecycleRegistry.addObserver, which must run on the main thread; without this
        // priming, a background caller can make Koin build ChatService on an IO thread.
        eagerlyInitChatService()

        AppStartupProgressTracker.update(75, AppStartupStage.LoadingServices)

        // Initialise the agent's `~` workspace at /data/data/<pkg>/files/workspace/.
        // Tools resolve `~` and `~/foo` paths to this dir, giving the LLM a stable
        // sandbox for `.learnings/`, scratch files, and skill state without scoped-
        // storage friction. The directory is private and persistent inside app storage.
        me.rerere.rikkahub.data.ai.tools.local.AgentWorkspace.init(this)

        // Copy any default skills bundled in assets/default-skills/* into the user's skills
        // dir on first launch. SkillManager guards via a per-skill .seeded sentinel so this
        // is a one-time install — user edits / deletes are respected on subsequent launches.
        seedDefaultSkillsIfNeeded()

        // Increment launch count
        incrementLaunchCount()

        // Register a network-change monitor that evicts OkHttp's connection pool on
        // default-network transitions. The next request then performs a fresh DNS lookup
        // and opens a new socket after connectivity changes.
        startNetworkChangeMonitor()

        // Auto-recover from a prior native crash inside a local-runtime JNI lib
        // (LiteRT-LM 0.11.0 has known SIGSEGVs on the GPU/NNAPI backend during
        // inference on Pixel Tensor-G). If we detect one, force the runtime to
        // CPU on the next load and stamp a recovery banner the LiteRT settings
        // page picks up — so users see "Recovered: switched to CPU" instead of
        // a silent re-crash.
        sweepLocalLlmNativeCrashes()

        // Clear stale per-device decisions (cached accelerator, vision-unavailable set,
        // crash-recovery banner) when the bundled LiteRT-LM SDK has been bumped since
        // the last app start. An older SDK's "GPU is broken on Adreno 7xx" / "vision
        // encoder unavailable" decisions can mask a fix shipped in the new SDK; without
        // this sweep, a 0.11→0.12 bump would silently stay on CPU even though 0.12 may
        // have fixed the GPU path. Decisions are re-inferred from a fresh probe on the
        // next inference / re-detect tap. User-set knobs (force-CPU toggle, max-context
        // override) are NOT touched.
        invalidateLocalLlmDecisionsOnSdkUpgrade()
        AppStartupProgressTracker.update(95, AppStartupStage.Finalizing)
        AppStartupProgressTracker.update(100, AppStartupStage.Ready, ready = true)

        // Composer.setDiagnosticStackTraceMode(ComposeStackTraceMode.Auto)
    }

    /**
     * Inspect the package's recent ApplicationExitInfo records for a native crash whose
     * stack/description points at a local-runtime JNI library. When one is found, set the
     * matching runtime's force-CPU flag so the next inference runs on CPU, and record the
     * crashed accelerator label so the settings UI can surface a "switched to CPU" notice.
     *
     * Best-effort: errors are logged, never thrown — a stuck app start is worse than a
     * skipped recovery sweep.
     */
    private fun sweepLocalLlmNativeCrashes() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) return  // ApplicationExitInfo is API 30+
        get<AppScope>().launch(Dispatchers.IO) {
            runCatching {
                val am = getSystemService(android.app.ActivityManager::class.java) ?: return@runCatching
                // Look at the last ~5 exits: more than enough to spot a recent crash even if
                // the user opened the app a few times since (each open = one exit record).
                val recentExits = am.getHistoricalProcessExitReasons(packageName, 0, 5)
                val nativeCrash = recentExits.firstOrNull { exit ->
                    exit.reason == android.app.ApplicationExitInfo.REASON_CRASH_NATIVE &&
                        // ApplicationExitInfo.description includes the offending shared library
                        // for native crashes. Match the JNI sidekick of each runtime.
                        (exit.description?.contains("liblitertlm", ignoreCase = true) == true)
                } ?: return@runCatching
                val prefs = get<me.rerere.locallm.LocalRuntimePreferences>()
                val runtime = me.rerere.locallm.LocalRuntime.LiteRT
                // Don't double-stamp if the user has already seen and dismissed an earlier
                // crash banner — the prior dismiss cleared the recovery key, but if a NEW
                // crash happened after, we want a fresh notice.
                val crashedAccel = prefs.acceleratorFlow(runtime).first() ?: "GPU/NPU"
                if (!prefs.forceCpu(runtime)) {
                    prefs.setForceCpu(runtime, true)
                    prefs.clearAccelerator(runtime)
                }
                prefs.setCrashRecovery(runtime, crashedAccel)
                Log.w(
                    TAG,
                    "sweepLocalLlmNativeCrashes: detected native crash in liblitertlm at " +
                        "${nativeCrash.timestamp} (accel=$crashedAccel) — forcing CPU + stamping recovery banner"
                )
            }.onFailure {
                Log.w(TAG, "sweepLocalLlmNativeCrashes failed", it)
            }
        }
    }

    /**
     * Fire-and-forget: clear stale SDK-coupled decisions (accelerator, vision-unavailable
     * set, crash-recovery banner) whenever the compiled-in LiteRT-LM version differs from
     * the last-persisted one. Best-effort — failure is logged and ignored so a slow or
     * broken DataStore read can never block app start. Idempotent across multiple calls
     * within the same process (the version write makes the second call a no-op).
     */
    private fun invalidateLocalLlmDecisionsOnSdkUpgrade() {
        get<AppScope>().launch(Dispatchers.IO) {
            runCatching {
                val prefs = get<me.rerere.locallm.LocalRuntimePreferences>()
                val invalidated = prefs.maybeInvalidateOnSdkUpgrade(me.rerere.locallm.LocalRuntime.LiteRT)
                if (invalidated) {
                    Log.i(
                        TAG,
                        "invalidateLocalLlmDecisionsOnSdkUpgrade: SDK version changed — cleared " +
                            "accelerator + vision-unavailable + crash-recovery for LiteRT (new=${prefs.currentSdkVersion})",
                    )
                }
                // Unconditionally wipe the visionUnavailable set on every app start. Stale
                // flags can be left behind by transient failures the SDK has since
                // recovered from (most notably the 0.12.0 -> 0.11.0 downgrade where the
                // SDK-version key may already match because the device ran 0.11.0 first).
                // If GPU vision really is broken on this device, [LiteRtRuntime.ensureLoaded]
                // re-stamps the flag the moment it observes a fresh failure — so the wipe
                // never strands the app in a crash loop, it just ensures we re-test on
                // every launch.
                val wipedVision = prefs.clearAllVisionUnavailable(me.rerere.locallm.LocalRuntime.LiteRT)
                if (wipedVision > 0) {
                    Log.i(
                        TAG,
                        "invalidateLocalLlmDecisionsOnSdkUpgrade: wiped $wipedVision stale " +
                            "visionUnavailable entries (forcing fresh attempt next inference)",
                    )
                }
            }.onFailure {
                Log.w(TAG, "invalidateLocalLlmDecisionsOnSdkUpgrade failed", it)
            }
        }
    }

    private fun startNetworkChangeMonitor() {
        runCatching {
            val client = get<okhttp3.OkHttpClient>()
            me.rerere.rikkahub.utils.NetworkChangeMonitor.start(this, client)
        }.onFailure {
            Log.w(TAG, "startNetworkChangeMonitor failed", it)
        }
    }

    private fun incrementLaunchCount() {
        get<AppScope>().launch {
            runCatching {
                val store = get<SettingsStore>()
                val current = store.settingsFlowRaw.first()
                store.update(current.copy(launchCount = current.launchCount + 1))
                Log.i(TAG, "incrementLaunchCount: ${store.settingsFlowRaw.first().launchCount}")
            }.onFailure {
                Log.e(TAG, "incrementLaunchCount failed", it)
            }
        }
    }

    private fun eagerlyInitChatService() {
        try {
            // Just resolving the singleton triggers Koin's factory; the side effect we care
            // about is the LifecycleRegistry.addObserver call inside ChatService.<init>,
            // which Android requires to happen on the main thread.
            get<me.rerere.rikkahub.service.ChatService>()
        } catch (t: Throwable) {
            Log.e(TAG, "eagerlyInitChatService failed", t)
        }
    }

    private fun seedDefaultSkillsIfNeeded() {
        get<AppScope>().launch(Dispatchers.IO) {
            runCatching {
                get<me.rerere.rikkahub.data.files.SkillManager>().seedDefaultSkillsIfNeeded()
            }.onFailure {
                Log.e(TAG, "seedDefaultSkillsIfNeeded failed", it)
            }
        }
    }

    private fun checkWorkspaceIntegrity() {
        get<AppScope>().launch(Dispatchers.IO) {
            runCatching {
                get<WorkspaceRepository>().checkIntegrity()
            }.onFailure {
                Log.e(TAG, "checkWorkspaceIntegrity failed", it)
            }
        }
    }

    private fun deleteTempFiles() {
        get<AppScope>().launch(Dispatchers.IO) {
            val dir = appTempFolder
            if (dir.exists()) {
                dir.deleteRecursively()
            }
        }
    }


    private fun syncManagedFiles() {
        get<AppScope>().launch(Dispatchers.IO) {
            runCatching {
                get<FilesManager>().syncFolder()
            }.onFailure {
                Log.e(TAG, "syncManagedFiles failed", it)
            }
        }
    }

    private fun startWebServerIfEnabled() {
        get<AppScope>().launch {
            runCatching {
                delay(500)
                val settings = get<SettingsStore>().settingsFlowRaw.first()
                if (settings.webServerEnabled) {
                    // Android 17 (API 37) requires ACCESS_LOCAL_NETWORK to bind to LAN
                    // interfaces. localhost-only mode does not need it because traffic stays
                    // within the app's UID. Cherry-picked from upstream 80186f5d.
                    if (Build.VERSION.SDK_INT >= 37 &&
                        !settings.webServerLocalhostOnly &&
                        ContextCompat.checkSelfPermission(
                            this@RikkaHubApp,
                            android.Manifest.permission.ACCESS_LOCAL_NETWORK
                        ) != PackageManager.PERMISSION_GRANTED
                    ) {
                        Log.w(TAG, "startWebServerIfEnabled: local network permission not granted, skipping")
                        return@launch
                    }
                    val intent = Intent(this@RikkaHubApp, WebServerService::class.java).apply {
                        action = WebServerService.ACTION_START
                        putExtra(WebServerService.EXTRA_PORT, settings.webServerPort)
                        putExtra(WebServerService.EXTRA_LOCALHOST_ONLY, settings.webServerLocalhostOnly)
                    }
                    startForegroundService(intent)
                }
            }.onFailure {
                Log.e(TAG, "startWebServerIfEnabled failed", it)
            }
        }
    }

    private fun createNotificationChannel() {
        val notificationManager = NotificationManagerCompat.from(this)
        val chatLiveUpdateChannel = NotificationChannelCompat
            .Builder(
                CHAT_LIVE_UPDATE_NOTIFICATION_CHANNEL_ID,
                NotificationManagerCompat.IMPORTANCE_LOW
            )
            .setName(getString(R.string.notification_channel_chat_live_update))
            .setVibrationEnabled(false)
            .build()
        notificationManager.createNotificationChannel(chatLiveUpdateChannel)

        val webServerChannel = NotificationChannelCompat
            .Builder(WEB_SERVER_NOTIFICATION_CHANNEL_ID, NotificationManagerCompat.IMPORTANCE_LOW)
            .setName(getString(R.string.notification_channel_web_server))
            .setVibrationEnabled(false)
            .setShowBadge(false)
            .build()
        notificationManager.createNotificationChannel(webServerChannel)

        val pluginMusicChannel = NotificationChannelCompat
            .Builder(MUSIC_PLAYER_NOTIFICATION_CHANNEL_ID, NotificationManagerCompat.IMPORTANCE_LOW)
            .setName("Plugin media")
            .setVibrationEnabled(false)
            .setShowBadge(false)
            .build()
        notificationManager.createNotificationChannel(pluginMusicChannel)

        val pluginPomodoroChannel = NotificationChannelCompat
            .Builder(POMODORO_NOTIFICATION_CHANNEL_ID, NotificationManagerCompat.IMPORTANCE_LOW)
            .setName("Plugin focus timer")
            .setVibrationEnabled(false)
            .setShowBadge(false)
            .build()
        notificationManager.createNotificationChannel(pluginPomodoroChannel)
    }

    override fun onTerminate() {
        super.onTerminate()
        get<AppScope>().cancel()
        stopService(Intent(this, WebServerService::class.java))
    }
}

class AppScope : CoroutineScope by CoroutineScope(
    SupervisorJob()
        + Dispatchers.Main
        + CoroutineName("AppScope")
        + CoroutineExceptionHandler { _, e ->
        Log.e(TAG, "AppScope exception", e)
    }
)
