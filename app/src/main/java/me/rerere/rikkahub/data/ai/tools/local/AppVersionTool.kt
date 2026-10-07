package me.rerere.rikkahub.data.ai.tools.local

import android.content.Context
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import me.rerere.ai.core.InputSchema
import me.rerere.ai.core.Tool
import me.rerere.ai.ui.UIMessagePart
import me.rerere.rikkahub.BuildConfig

/**
 * rhAppVersion: 让模型能自报家门 —— 当前跑的是哪一次 CI 构建。
 *
 * CI 会把 versionName 盖成 "<base>+run<N>"(见 scripts/patch_batch132.py),N 与 Release
 * 标签 fix-batch1-run<N> 一一对应。用户问"我装的是哪个版本/这个 bug 在哪个构建上",
 * 模型直接调本工具报 run 号,不用猜,也不用用户去翻设置页。
 *
 * 常驻注册(不挂 LocalToolOption 开关):它只读自己的 BuildConfig 与自己的包信息,
 * 无任何副作用;而它存在的意义就是"任何会话里都能查到版本",挂开关等于经常查不到。
 * 注册点在 ChatService 的 tools buildList 内、酒馆模式提前返回之后,所以酒馆模式
 * 仍然只有 人设 + 记忆 + 搜索 + 文件。
 */
fun appVersionTool(context: Context): Tool = Tool(
    name = "get_app_version",
    description = """
        Get the running app build: version name, version code, CI run number, package name,
        build type and install/update timestamps. Use this when the user asks which version
        or build they are running, or when a bug needs the exact build pinned down.
    """.trimIndent().replace("\n", " "),
    parameters = {
        InputSchema.Obj(properties = buildJsonObject { })
    },
    execute = {
        val versionName = BuildConfig.VERSION_NAME
        // "2.4.14+run305" -> 305;本地构建没有 +run 后缀时为 null
        val runDigits = versionName.substringAfter("+run", "").takeWhile { ch -> ch.isDigit() }
        val runNumber = runDigits.toIntOrNull()
        val pkgInfo = runCatching {
            context.packageManager.getPackageInfo(context.packageName, 0)
        }.getOrNull()
        val payload = buildJsonObject {
            put("version_name", versionName)
            put("version_code", BuildConfig.VERSION_CODE)
            if (runNumber != null) {
                put("ci_run_number", runNumber)
            } else {
                put("ci_run_number", JsonNull)
            }
            put("is_ci_build", runNumber != null)
            put("package_name", context.packageName)
            put("build_type", if (BuildConfig.DEBUG) "debug" else "release")
            if (pkgInfo != null) {
                put("first_install_time_ms", pkgInfo.firstInstallTime)
                put("last_update_time_ms", pkgInfo.lastUpdateTime)
            } else {
                put("first_install_time_ms", JsonNull)
                put("last_update_time_ms", JsonNull)
            }
        }
        listOf(UIMessagePart.Text(payload.toString()))
    }
)
