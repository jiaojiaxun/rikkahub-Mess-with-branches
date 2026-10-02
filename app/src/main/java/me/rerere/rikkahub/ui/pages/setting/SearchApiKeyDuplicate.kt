package me.rerere.rikkahub.ui.pages.setting

import me.rerere.search.SearchServiceOptions
import kotlin.uuid.Uuid

/** Returns the configured credential without ever exposing it to UI/logging. */
internal fun SearchServiceOptions.apiKeyForDuplicateCheck(): String? = when (this) {
    is SearchServiceOptions.ZhipuOptions -> apiKey
    is SearchServiceOptions.DoubaoOptions -> apiKey
    is SearchServiceOptions.TavilyOptions -> apiKey
    is SearchServiceOptions.ExaOptions -> apiKey
    is SearchServiceOptions.LinkUpOptions -> apiKey
    is SearchServiceOptions.BraveOptions -> apiKey
    is SearchServiceOptions.MetasoOptions -> apiKey
    is SearchServiceOptions.OllamaOptions -> apiKey
    is SearchServiceOptions.PerplexityOptions -> apiKey
    is SearchServiceOptions.FirecrawlOptions -> apiKey
    is SearchServiceOptions.JinaOptions -> apiKey
    is SearchServiceOptions.BochaOptions -> apiKey
    is SearchServiceOptions.RikkaHubOptions -> apiKey
    is SearchServiceOptions.GrokOptions -> apiKey
    is SearchServiceOptions.TinyfishOptions -> apiKey
    is SearchServiceOptions.SerperOptions -> apiKey
    is SearchServiceOptions.BingLocalOptions,
    is SearchServiceOptions.DuckDuckGoOptions,
    is SearchServiceOptions.SearXNGOptions,
    is SearchServiceOptions.CustomJsOptions -> null
}

internal fun SearchServiceOptions.normalizedApiKey(): String? =
    apiKeyForDuplicateCheck()?.trim()?.takeIf { it.isNotEmpty() }

/** Returns the existing provider id whose key matches, excluding the provider being edited. */
internal fun findDuplicateSearchApiKey(
    candidate: SearchServiceOptions,
    existing: List<SearchServiceOptions>,
): Uuid? {
    val key = candidate.normalizedApiKey() ?: return null
    return existing.firstOrNull { it.id != candidate.id && it.normalizedApiKey() == key }?.id
}
