from pathlib import Path
import re
import sys

ROOT = Path.cwd()


def fail(path, msg):
    print(f"::error file={path}::batch33 {msg[:1400]}")
    raise SystemExit(1)


# ============================================================
# 定时任务接线 v2（#95 修复）
# v1 失败：batch31 的 archive 锚点空格数不匹配（count=0）导致整个 patch 步骤挂。
# v2：sub_agents 选项行锚点改为「正则」，匹配 batch31 v2 插入的单空格格式行。
# 其余锚点（注释行/代码块）逐字实测无对齐风险，保持不变。
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
    # 4a. 封闭类加 CronJobs 选项（正则锚，匹配 batch31 v2 插入的单空格 sub_agents 行）
    SUB_AGENTS_RE = re.compile(
        r'(?P<line>[ \t]*@Serializable[ \t]+@SerialName\("sub_agents"\)[ \t]+data[ \t]+object[ \t]+SubAgents[ \t]*:[ \t]*LocalToolOption\(\)[ \t]*\n)'
    )
    m = SUB_AGENTS_RE.search(t4)
    if not m:
        fail(P4, "sub_agents option line (regex) not found — batch31 must run first")
    cronjobs_block = (
        "    // Scheduled jobs (batch33): schedule_job / list_jobs / delete_job / pause_job /\n"
        "    // resume_job / trigger_job_now / job_history\n"
        '    @Serializable @SerialName("cron_jobs") data object CronJobs : LocalToolOption()\n'
    )
    t4 = t4[: m.end("line")] + cronjobs_block + t4[m.end("line"):]

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
    print("batch33 v2: LocalTools option + cron tools wired")
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
