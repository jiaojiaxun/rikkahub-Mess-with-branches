#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rhCron341 -- 定时任务「立即执行也不执行」的对抗性检查结论 + 修复。

━━ 全链路读过的文件（不是猜） ━━
CronTools.kt            trigger_job_now → scheduler.triggerNow(jobId)
CronJobScheduler.kt     triggerNow → WorkManager.enqueueUniqueWork(manual名, REPLACE, OneTimeWorkRequest(delay=0))
CronJobWorker.kt        doWork：找 job → resolveConversationId → chatService.sendMessage → 等 generationDoneFlow
CronJobStore.kt         DataStore JSON，jobs/history 各一个 key
CronJob.kt              CronParser.parseNextRun + isValid
ChatGenerationForegroundService.kt  startForegroundCompat() 被拒时 markUnavailable()
AppControlService.kt    scheduleCronJob/triggerCronJob 与 CronTools 同源
ForegroundServiceReadiness.kt       awaitReady 超时返回 false

━━ 排除的假设（逐条核对过，不是想当然） ━━
1. job 没写进 store？—— 排除。list_cron_jobs 能列出 ab32a86f，upsert 与 schedule 都在。
2. CronParser 解析失败导致不调度？—— 只影响 schedule_job 的 isValid，不影响 triggerNow。
3. `settingsFlow.first { !it.init }` 永久挂起？—— 排除。Settings.init 是
   `@Transient val init: Boolean = false`，恒为 false，first 立即返回。
4. sendMessage 签名不匹配？—— 排除。`fun sendMessage(Uuid, List<UIMessagePart>, answer: Boolean = true)`，
   Worker 传的三参正好对上。
5. 手动触发被 enabled 门控？—— 排除。`if (!manual && !job.enabled)`，manual 直接跳过。

━━ 真正的问题（三个，都不是"机制没接上"，而是"失败不可见"） ━━
A. triggerNow 只 enqueue 就返回。工具/网关立刻回 `{"triggered": id}`，用户看到"成功"，
   但 Worker 可能还没被 WorkManager 调度（Doze / 电池优化 / 刚 force-stop 过）。
B. Worker 里任何失败都只写 history，不通知。而且 `resolveConversationId` 里的
   `chatService.sendMessage` 是**非 suspend**，失败会走 catch → outcome=failure，
   用户不翻「历史」永远看不到。
C. Worker 卡在 await（比如 FGS 被拒、生成事件没到）时，**history 一个字都没有**——
   要等 600 秒超时才落一条 timeout，用户早就以为"没执行"了。

━━ 本批改三处 ━━
1. CronJobScheduler.triggerNow 加 setExpedited(RUN_AS_NON_EXPEDITED_WORK_REQUEST)：
   提高后台立即执行的优先级；配额超了自动降级为普通 work，不会失败。
2. CronJobWorker 在 doWork 一开始就落一条 `started` / `manual_started` 历史：
   卡住也有痕迹，用户能立刻在历史里看到"跑了"。
3. trigger 的返回文案改成"已排队，结果看历史"：CronTools + AppControlService 两侧同改。

不改 sendMessage 语义、不改 CronJob 数据结构、不动 DataStore key。
"""
import os
import sys

MARK = "rhCron341"
DIAG = "ci_diag_batch341_cron.txt"
Q = chr(34)
ROOT = os.path.abspath(os.getcwd())
rows = []

SCHED = "app/src/main/java/me/rerere/rikkahub/service/CronJobScheduler.kt"
WORKER = "app/src/main/java/me/rerere/rikkahub/service/CronJobWorker.kt"
TOOLS = "app/src/main/java/me/rerere/rikkahub/data/ai/tools/CronTools.kt"
CTRL = "app/src/main/java/me/rerere/rikkahub/data/ai/tools/appcontrol/AppControlService.kt"


def note(msg):
    line = "[batch341] " + str(msg)
    print(line)
    rows.append(line)


def fail(msg):
    note("FAIL " + str(msg))
    flush()
    sys.exit(0)


def flush():
    try:
        with open(os.path.join(ROOT, DIAG), "w", encoding="utf-8") as f:
            f.write("\n".join(rows) + "\n")
    except Exception:
        pass


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def write(rel, text):
    with open(os.path.join(ROOT, rel), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def parens(t):
    return (t.count("(") - t.count(")"), t.count("{") - t.count("}"), t.count("[") - t.count("]"))


def step_expedited():
    text = read(SCHED)
    if MARK in text:
        note("skip scheduler (already applied)")
        return
    needle = "        val req = OneTimeWorkRequestBuilder<CronJobWorker>()\n            .setInitialDelay(0L, TimeUnit.MILLISECONDS)"
    if text.count(needle) != 1:
        fail("scheduler anchor count=" + str(text.count(needle)))
    repl = (
        "        val req = OneTimeWorkRequestBuilder<CronJobWorker>()\n"
        "            .setInitialDelay(0L, TimeUnit.MILLISECONDS)\n"
        "            // " + MARK + ": 立即执行提高优先级；配额超了会自动降级为普通 work，不会失败\n"
        "            .setExpedited(androidx.work.OutOfQuotaPolicy.RUN_AS_NON_EXPEDITED_WORK_REQUEST)"
    )
    before = parens(text)
    text = text.replace(needle, repl, 1)
    after = parens(text)
    if after != before:
        fail("scheduler balance " + str(before) + " -> " + str(after))
    write(SCHED, text)
    note("scheduler: setExpedited added")


def step_worker_marker():
    text = read(WORKER)
    if MARK in text:
        note("skip worker (already applied)")
        return
    needle = "        var outcome = " + Q + "success" + Q
    if text.count(needle) != 1:
        fail("worker anchor count=" + str(text.count(needle)))
    block = (
        "        // " + MARK + ": 先落一条「已开始」，卡住也有痕迹；用户能在历史里看到到底跑没跑\n"
        "        runCatching {\n"
        "            store.addHistory(\n"
        "                ScheduledJobRunRecord(\n"
        "                    id = Uuid.random().toString(),\n"
        "                    jobId = job.id,\n"
        "                    jobName = job.name,\n"
        "                    scheduledAtMs = now,\n"
        "                    startedAtMs = now,\n"
        "                    outcome = if (manual) " + Q + "manual_started" + Q + " else " + Q + "started" + Q + ",\n"
        "                )\n"
        "            )\n"
        "        }\n"
        "\n"
    )
    before = parens(text)
    text = text.replace(needle, block + needle, 1)
    after = parens(text)
    if after != before:
        fail("worker balance " + str(before) + " -> " + str(after))
    write(WORKER, text)
    note("worker: started history added")


def step_tool_note():
    text = read(TOOLS)
    if MARK in text:
        note("skip CronTools (already applied)")
        return
    needle = "            put(" + Q + "triggered" + Q + ", jobId)"
    if text.count(needle) != 1:
        fail("CronTools anchor count=" + str(text.count(needle)))
    repl = (
        needle + "\n"
        "            put(" + Q + "note" + Q + ", " + Q +
        "已提交到后台队列；几秒后开始，结果看 job_history（卡住也会有 *_started 记录）" + Q + ") // " + MARK
    )
    text = text.replace(needle, repl, 1)
    write(TOOLS, text)
    note("CronTools: trigger note added")


def step_control_note():
    text = read(CTRL)
    if MARK in text:
        note("skip AppControlService (already applied)")
        return
    needle = "        return successJson(" + Q + "triggered job $jobId" + Q + ")"
    if text.count(needle) != 1:
        fail("AppControl anchor count=" + str(text.count(needle)))
    repl = (
        "        return successJson(" + Q +
        "triggered job $jobId (queued; see job history; stuck runs also log *_started)" + Q + ") // " + MARK
    )
    text = text.replace(needle, repl, 1)
    write(CTRL, text)
    note("AppControlService: trigger note added")


def main():
    steps = [
        ("expedited", step_expedited),
        ("worker", step_worker_marker),
        ("tool", step_tool_note),
        ("control", step_control_note),
    ]
    ok = 0
    for name, fn in steps:
        try:
            fn()
            ok += 1
        except SystemExit:
            pass
        except Exception as exc:  # noqa: BLE001
            note("EXCEPTION " + name + " " + type(exc).__name__ + " " + str(exc)[:240])
    note("steps ok=" + str(ok) + "/" + str(len(steps)))
    flush()
    print("::error::batch341 END lines=" + str(len(rows)))
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        note("FATAL " + type(exc).__name__ + " " + str(exc)[:240])
        flush()
        sys.exit(0)