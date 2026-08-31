package me.rerere.rikkahub.data.ai.tools

/**
 * Single source of truth for which tools require user approval before they execute.
 *
 * The matching policy is "tool name in the set" — there's no per-arg gating yet. When the
 * runtime decides whether to ask the user, it consults this set, then the per-conversation
 * "Allow for this chat" allow-list, then the persistent "Always Allow" allow-list (in that
 * order); the prompt only fires when none of those let it through.
 *
 * MCP-relayed tools (any name starting with `mcp__`) are gated separately at the
 * GenerationHandler level — this set covers only locally-defined tools. See
 * [requiresApproval] for the combined logic.
 *
 * If you add a new LLM-callable tool, decide:
 *   - Is it side-effecting (writes to disk, runs shell, controls hardware, posts to a
 *     remote service, manipulates UI)? → add it here.
 *   - Is it a pure read (battery, location, screenshot, list-installed-apps)? → leave it
 *     out; the user doesn't need to be interrupted for "what's the brightness".
 *
 * Privacy-sensitive READS (contacts, sms, call log) ARE in here: reading PII off the
 * device into an LLM context deserves the same friction as a write does — the secret
 * is leaving the device either way.
 */
object ToolApprovalDefaults {

    /** Tool names that ALWAYS require approval unless the user has granted an exception. */
    val ALWAYS_ASK: Set<String> = setOf(
        // Arbitrary code execution
        "eval_javascript",

        // Filesystem / network writes
        "write_text_file",
        "download_file",
        "scan_media",

        // Privacy / hardware actuation
        "take_photo",
        "record_audio",
        "speech_to_text",    // activates the microphone + uploads audio to recognizer
        "verify_fingerprint",
        "share",
        "set_torch",
        "vibrate",
        "set_brightness",
        "set_volume",
        "play_media",
        "stop_media",
        "pause_media",
        "resume_media",
        "seek_media",
        // get_media_status is read-only — no approval needed
        // Privacy reads — PII leaves the device into the model's context
        "list_call_log",
        "list_contacts",
        "search_contacts",
        "list_sms_inbox",
        "search_sms",

        // File manager — all ops are side-effecting or read PII from arbitrary paths
        "list_files",
        "read_file",
        "write_binary_file",
        "delete_file",
        "move_file",
        "copy_file",
        "create_directory",
        "file_info",
        "find_files",
        // Batch file ops (item 5.5) — list-or-glob copy / move / delete. Side-effecting
        // over potentially many paths in one call, so each gets the same approval gate as
        // the single-path file tools.
        "batch_copy",
        "batch_move",
        "batch_delete",

        // MCP control — all side-effecting MCP tools require approval.
        // mcp_add and mcp_update are also flagged with "no always-allow" below because a
        // hostile MCP server can exfiltrate everything the LLM has access to and we want
        // a per-call confirmation each time, not a one-shot blanket grant.
        "mcp_add",
        "mcp_update",
        "mcp_delete",
        "mcp_set_enabled",
        "mcp_set_tool_approval",

        // Skill import (Phase 16) — pulls a markdown / JSON skill from an arbitrary URL
        // (or from raw text) and installs
        // it. Whatever is in the skill rides along with the assistant's tool surface,
        // so this is privilege-escalation-adjacent. NO_ALWAYS_ALLOW below.
        "skill_install_from_url",
        "skill_install_from_text",

        // JS skills (Phase 18) — run a skill's JavaScript inside a hidden WebView.
        // The script can issue arbitrary network requests on behalf of the user, so
        // every invocation gets per-call approval. Eligible for "Always allow" once a
        // particular skill is trusted (NOT in NO_ALWAYS_ALLOW — the skill's body has
        // already been reviewed at install time).
        "run_js",

        // Native intent tools (Phase 18) — open the system Calendar / Contacts / SMS /
        // Email composer / WiFi settings / Maps app. Each fires a system intent the user
        // finalises in the destination app. Approval gate ensures the user reviews the
        // pre-filled fields before the LLM hands the action off.
        "create_calendar_event",
        "create_contact",
        "send_email_intent",
        "send_sms_intent",
        "open_wifi_settings",
        "show_location_on_map",

        // In-app browser write tools (Phase 21 / Pass 2). The browser can carry auth tokens
        // in cookies, so anything that mutates page state OR runs JS is approval-gated. Read
        // tools (open, current_url, screenshot, get_text, get_dom, get_links, back, forward,
        // wait_for) are NOT in this set — reading text out of a page is the same trust level
        // as taking a screenshot or reading any other LLM context. browser_done is the
        // loop-control sentinel and never side-effects.
        "browser_click",
        "browser_type",
        "browser_scroll",
        "browser_submit",
        "browser_select",
        "browser_press_key",
        "browser_eval_js",
        // Composite click+read added in the token-cost optimisation pass — its click
        // side carries the same trust footprint as plain browser_click, so it
        // inherits the same approval gate.
        "browser_click_and_read",

        // web_fetch (item 1.2) — network egress. A bare HTTP GET/POST can exfiltrate
        // anything the LLM puts in the URL / body / headers, so it gets the same
        // approval gate as every other outbound call.
        "web_fetch",
        // web_extract performs the same outbound GET as web_fetch, so it carries the same
        // trust footprint and inherits the same approval gate.
        "web_extract",

        // Phase 25 — Phase 3 second cut. Every mutating tool is approval-gated; the
        // read-only tools (keystore_verify, keystore_list_keys, list_storage_volumes,
        // list_granted_directories, list_zip_contents) are deliberately NOT in this set.
        "send_sms",                 // sends a real SMS — costs money / leaves the device
        "set_wallpaper",            // changes a visible device setting
        "keystore_generate_key",    // creates a hardware key (NO_ALWAYS_ALLOW below)
        "keystore_sign",            // signs arbitrary data with the user's key
        "keystore_encrypt",         // encrypts with the user's key
        "keystore_decrypt",         // decrypts ciphertext (NO_ALWAYS_ALLOW below)
        "keystore_delete_key",      // destroys a key
        "nfc_read_tag",             // opens a foreground reader session
        "nfc_write_tag",            // writes NDEF to a physical tag (NO_ALWAYS_ALLOW below)
        "grant_directory_access",   // persistent read+write to a whole tree (NO_ALWAYS_ALLOW below)
        "zip_files",                // writes an archive to disk / a granted tree
        "unzip_file",               // writes extracted files to disk / a granted tree

    )

    /**
     * Tools whose approval prompt MUST drop the "Always Allow" button so the user has to
     * confirm every single call. Reserved for tools that are inherently privilege-escalation
     * surfaces — adding an MCP server is exactly that, since a hostile server can exfiltrate
     * anything reachable through the assistant's tool set. The in-app surface reads this set
     * when rendering the approval card.
     */
    val NO_ALWAYS_ALLOW: Set<String> = setOf(
        "mcp_add",
        "mcp_update",
        // eval_javascript runs arbitrary code in the QuickJS engine. Even with a wall-clock
        // timeout + a bounded native heap/stack, the code itself is attacker-controllable, so
        // it always requires a per-call confirmation.
        "eval_javascript",
        // Skill installation can add executable behavior to the assistant's tool surface.
        // We require per-call approval every single time so
        // the user reviews the URL / source-label + skill name.
        "skill_install_from_url",
        "skill_install_from_text",
        // Phase 21 / Pass 2 — browser_eval_js runs arbitrary JavaScript in a real WebView
        // with the user's cookies, localStorage, and authenticated fetch surface. Even
        // after HARDLINE filters out shell-shaped strings + obvious dynamic-eval patterns,
        // the residual surface is too broad to ever blanket-allow. Every invocation gets
        // an explicit per-call approval card, no exceptions.
        "browser_eval_js",
        // Phase 25 — privilege-escalation surfaces that must confirm every single call:
        //  - keystore_generate_key: mints a hardware key that later sign/encrypt calls trust
        //  - keystore_decrypt: turns ciphertext back into plaintext the model then reads
        //  - nfc_write_tag: permanently rewrites a physical tag's contents
        //  - grant_directory_access: persistent read+write to an entire storage tree,
        //    possibly cloud / Downloads / Pictures
        "keystore_generate_key",
        "keystore_decrypt",
        "nfc_write_tag",
        "grant_directory_access",
    )

    fun allowsAlwaysAllow(toolName: String): Boolean = toolName !in NO_ALWAYS_ALLOW

    /**
     * True if [toolName] requires approval. Local tools are looked up in [ALWAYS_ASK];
     * MCP-relayed tools (`mcp__*`) are always gated because the MCP server's tool surface
     * is opaque to us — we can't know which calls are destructive. An MCP server that
     * exposes purely-read tools costs the user one approval per session via "Always
     * Allow", which is a fair trade for the floor.
     */
    fun requiresApproval(toolName: String): Boolean =
        toolName in ALWAYS_ASK || toolName.startsWith("mcp__")
}
