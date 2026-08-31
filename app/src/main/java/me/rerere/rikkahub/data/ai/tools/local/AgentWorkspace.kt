package me.rerere.rikkahub.data.ai.tools.local

import android.content.Context
import java.io.File

/**
 * Private file workspace for the on-device assistant.
 *
 * The workspace root lives in `${context.filesDir}/workspace/`. Tools that take a path
 * argument expand `~` and `~/foo` to that directory before validation, so the LLM can
 * write to a stable, OS-blessed location without knowing the absolute path:
 *
 *   write_text_file(path = "~/learnings/ERRORS.md", content = "...")
 *   list_files(path = "~/skill-cache/")
 *
 * Why this directory:
 *  - `/data/data/<own-package>/files/` has stayed open for app-private writes since
 *    Android 1; immune to scoped-storage tightening across releases.
 *  - PathSafetyGuard's OWN_APP_PREFIXES already allows it; no policy change needed.
 *  - It is app-private and needs no shared-storage permission.
 *  - Workspace contents are included by the backup/export path so device migration can restore
 *    them; sensitive skill material remains subject to the existing file safety rules.
 *  - Files the user explicitly exports still belong in the user-visible export location.
 */
object AgentWorkspace {
    private const val DIR_NAME = "workspace"

    @Volatile
    private var workspaceDir: File? = null

    /** Wire up at app start (RikkaHubApp.onCreate) — idempotent. */
    fun init(context: Context) {
        val dir = File(context.filesDir, DIR_NAME)
        if (!dir.exists()) dir.mkdirs()
        workspaceDir = dir
    }

    /** Absolute path of `~`. Throws if [init] hasn't been called yet. */
    fun rootPath(): String = workspaceDir?.absolutePath
        ?: error("AgentWorkspace not initialised — call AgentWorkspace.init(context) first")

    /**
     * Expand a tilde-prefixed path to the workspace dir. No-op for everything else.
     *   "~"            → "/data/data/<pkg>/files/workspace"
     *   "~/learnings/" → "/data/data/<pkg>/files/workspace/learnings/"
     *   "/sdcard/x"    → "/sdcard/x"   (unchanged)
     */
    fun expand(raw: String): String {
        if (raw.isEmpty()) return raw
        if (raw == "~") return rootPath()
        if (raw.startsWith("~/")) return rootPath() + raw.removePrefix("~")
        return raw
    }
}
