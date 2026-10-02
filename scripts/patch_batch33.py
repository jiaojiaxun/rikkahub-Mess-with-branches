from pathlib import Path
import re
import sys

ROOT = Path.cwd()


def fail(path, msg):
    print(f"::error file={path}::batch33 {msg[:1400]}")
    raise SystemExit(1)


# ============================================================
# 定时任务接线 v3（#96 修复）
# v2 失败：sub_agents 锚点正则没错，但 batch31 v2 在它之前就挂了。
# v3：sub_agents 行锚点照抄 patch_chat_ui_tools.py 的 ENUM_RE 模式
# （匹配行本身，插入点在行尾 m.end()），与 batch31 v3 插入格式一致。
# ============================================================

# ---------- 1) app/build.gradle.kts：WorkManager 依赖 ----------
P1 = "app/build.gradle.kts"
t1 = (ROOT / P1).read_text(encoding="utf-8")

if "androidx.work:work-runtime-ktx" in t1:
    print("batch33: gradle already patched")
else:
    A = (
        "    // AndroidX DocumentFile — Phase 25 SAF tree traversal for the ExternalStorage tools\n"
        "    // (USB / SD / Downloads / cloud DocumentsProvider access via persisted tree grants).\n"
        "    implementation(libs.androidx.documentfile)\n"
    )
    B = (
        "    // AndroidX DocumentFile — Phase 25 SAF tree traversal for the ExternalStorage tools\n"
        "    // (USB / SD / Downloads / cloud DocumentsProvider access via persisted tree grants).\n"
        "    implementation(libs.androidx.documentfile)\n"
        "\n"
        "    // AndroidX WorkManager — CronJobWorker (scheduled jobs, batch33)\n"
        '    implementation("androidx.work:work-runtime-ktx:2.9.1")\n'
    )
    if t1.count(A) != 1:
        fail(P1, f"DocumentFile anchor count={t1.count(A)}")
    t1 = t1.replace(A, B, 1)
    (ROOT / P1).write_text(t1, encoding="utf-8")
    print("batch33: WorkManager dependency added")

# ---------- 2) AndroidManifest.xml：权限 + Receiver ----------
P2 = "app/src/main/AndroidManifest.xml"
t2 = (ROOT / P2).read_text(encoding="utf-8")

if "CronBootReceiver" in t2:
    print("batch33: manifest already patched")
else:
    A = '  <uses-permission android:name="android.permission.NFC" />\n'
    B = (
        '  <uses-permission android:name="android.permission.NFC" />\n'
        "  <!-- Scheduled jobs (batch33): rebuild WorkManager schedules after reboot/update. -->\n"
        '  <uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED" />\n'
    )
    if t2.count(A) != 1:
        fail(P2, f"NFC permission anchor count={t2.count(A)}")
    t2 = t2.replace(A, B, 1)

    A = (
        "    <activity\n"
        "      android:name=\".ui.activity.SafeModeActivity\"\n"
        "      android:exported=\"false\"\n"
        "      android:label=\"@string/title_activity_safe_mode\"\n"
        "      android:theme=\"@style/Theme.Rikkahub\" />\n"
    )
    B = (
        "    <activity\n"
        "      android:name=\".ui.activity.SafeModeActivity\"\n"
        "      android:exported=\"false\"\n"
        "      android:label=\"@string/title_activity_safe_mode\"\n"
        "      android:theme=\"@style/Theme.Rikkahub\" />\n"
        "    <!-- Scheduled jobs (batch33): reschedule all enabled cron jobs after boot/update. -->\n"
        "    <receiver\n"
        "      android:name=\".service.CronBootReceiver\"\n"
        "      android:exported=\"true\">\n"
        "      <intent-filter>\n"
        "        <action android:name=\"android.intent.action.BOOT_COMPLETED\" />\n"
        "        <action android:name=\"android.intent.action.MY_PACKAGE_REPLACED\" />\n"
        "      </intent-filter>\n"
        "    </receiver>\n"
    )
    if t2.count(A) != 1:
        fail(P2, f"SafeModeActivity anchor count={t2.count(A)}")
    t2 = t2.replace(A, B, 1)

    (ROOT / P2).write_text(t2, encoding="utf-8")
    print("batch33: manifest permission + receiver added")

# ---------- 3) AppModule.kt：DI ----------
P3 = "app/src/main/java/me/rerere/rikkahub/di/AppModule.kt"
t3 = (ROOT / P3).read_text(encoding="utf-8")

if "CronJobStore" in t3:
    print("batch33: AppModule already patched")
else:
    A = (
        "    single {\n"
        "        ChatService(\n"
        "            context = get(),\n"
        "            appScope = get(),\n"
    )
    B = (
        "    // Scheduled jobs (batch33): DataStore-backed store + WorkManager scheduler.\n"
        "    // Worker resolves dependencies lazily from Koin (WorkManager creates it itself).\n"
        "    single { me.rerere.rikkahub.data.cron.CronJobStore(context = get()) }\n"
        "    single { me.rerere.rikkahub.service.CronJobScheduler(context = get(), store = get()) }\n"
        "\n"
        "    single {\n"
        "        ChatService(\n"
        "            context = get(),\n"
        "            appScope = get(),\n"
    )
    if t3.count(A) != 1:
        fail(P3, f"ChatService single anchor count={t3.count(A)}")
    t3 = t3.replace(A, B, 1)
    (ROOT / P3).write_text(t3, encoding="utf-8")
    print("batch33: AppModule DI registered")

# ---------- 4) LocalTools.kt：选项 + 工具 ----------
P4 = "app/src/main/java/me/rerere/rikkahub/data/ai/tools/LocalTools.kt"
t4 = (ROOT / P4).read_text(encoding="utf-8")

if "LocalToolOption.CronJobs" not in t4:
    # 4a. 封闭类加 CronJobs 选项（照抄 ENUM_RE 模式匹配 sub_agents 行，插在行尾）
    SUB_AGENTS_RE = re.compile(
        r'(?P<indent>[ \t]*)@Serializable[ \t]+@SerialName\("sub_agents"\)[ \t]+'
        r'data object SubAgents[ \t]*:[ \t]*LocalToolOption\(\)'
    )
    m = SUB_AGENTS_RE.search(t4)
    if not m:
        fail(P4, "sub_agents option line (ENUM_RE) not found — batch31 must run first")
    ind = m.group("indent")
    cronjobs_line = (
        '\n{ind}// Scheduled jobs (batch33): schedule_job / list_jobs / delete_job / pause_job /'
        '\n{ind}// resume_job / trigger_job_now / job_history'
        '\n{ind}@Serializable @SerialName("cron_jobs") data object CronJobs : LocalToolOption()'
    ).format(ind=ind)
    t4 = t4[: m.end()] + cronjobs_line + t4[m.end():]

    # 4b. getTools 挂 7 工具（CostGuards 块锚点，逐字实测）
    A = (
        "        if (options.contains(LocalToolOption.CostGuards)) {\n"
        "            tools.add(me.rerere.rikkahub.costguards.checkTokenUsageTool(settingsStore, conversationRepo))\n"
        "        }\n"
    )
    B = (
        "        if (options.contains(LocalToolOption.CostGuards)) {\n"
        "            tools.add(me.rerere.rikkahub.costguards.checkTokenUsageTool(settingsStore, conversationRepo))\n"
        "        }\n"
        "        if (options.contains(LocalToolOption.CronJobs)) {\n"
        "            // Scheduled jobs (batch33). Engine + storage are app-level singles;\n"
        "            // resolved lazily here so LocalTools keeps no cron constructor deps.\n"
        "            runCatching {\n"
        "                val koin = org.koin.core.context.GlobalContext.get()\n"
        "                val cronStore = koin.get<me.rerere.rikkahub.data.cron.CronJobStore>()\n"
        "                val cronScheduler = koin.get<me.rerere.rikkahub.service.CronJobScheduler>()\n"
        "                tools.addAll(\n"
        "                    me.rerere.rikkahub.data.ai.tools.createCronTools(\n"
        "                        store = cronStore,\n"
        "                        scheduler = cronScheduler,\n"
        "                        callerContext = invocationContext,\n"
        "                    )\n"
        "                )\n"
        "            }\n"
        "        }\n"
    )
    if t4.count(A) != 1:
        fail(P4, f"CostGuards anchor count={t4.count(A)}")
    t4 = t4.replace(A, B, 1)

    (ROOT / P4).write_text(t4, encoding="utf-8")
    print("batch33 v3: LocalTools option + cron tools wired")
else:
    print("batch33: LocalTools already patched")

# ---------- 5) AssistantLocalToolPage.kt：开关 ----------
P5 = "app/src/main/java/me/rerere/rikkahub/ui/pages/assistant/detail/AssistantLocalToolPage.kt"
if not (ROOT / P5).exists():
    print("batch33: local tool page missing, skipping switch")
else:
    src = (ROOT / P5).read_text(encoding="utf-8")
    if "LocalToolOption.CronJobs" in src:
        print("batch33: switch already patched")
    else:
        ANCHOR_RE = re.compile(
            r"(?P<indent>[ \t]*)item\(\s*headlineContent = \{\s*"
            r"Text\(stringResource\(R\.string\.assistant_page_local_tools_javascript_engine_title\)\)"
        )
        m = ANCHOR_RE.search(src)
        if not m:
            fail(P5, "anchor (javascript_engine item) not found")
        ind = m.group("indent")
        block = (
            f"{ind}item(\n"
            f"{ind}    headlineContent = {{ Text(\"定时任务（Cron Jobs）\") }},\n"
            f"{ind}    supportingContent = {{ Text(\"允许 AI 创建/暂停/删除定时任务，触发时把提示词发到指定会话；每次变更都需要你批准\") }},\n"
            f"{ind}    trailingContent = {{\n"
            f"{ind}        Switch(\n"
            f"{ind}            checked = assistant.localTools.contains(LocalToolOption.CronJobs),\n"
            f"{ind}            onCheckedChange = {{ toggleLocalTool(LocalToolOption.CronJobs, it) }}\n"
            f"{ind}        )\n"
            f"{ind}    }}\n"
            f"{ind}})\n"
        )
        src = src[: m.start()] + block + src[m.start():]
        (ROOT / P5).write_text(src, encoding="utf-8")
        print("batch33: CronJobs switch added")
