package me.rerere.rikkahub.data.ai.tools

/**
 * Stable names for model-facing tools contributed by installed plugins.
 * The raw plugin id is not used verbatim because dots and long ids can violate provider limits.
 */
object ToolNaming {
    private const val PREFIX = "plugin_"

    fun buildPluginToolName(pluginId: String, toolName: String): String {
        val pluginKey = pluginId.hashCode().toUInt().toString(16).padStart(8, '0')
        val safeTool = toolName
            .replace(Regex("[^A-Za-z0-9_-]"), "_")
            .trim('_')
            .ifBlank { "tool" }
            .take(48)
        return "$PREFIX${pluginKey}_${safeTool}".take(64)
    }
}
