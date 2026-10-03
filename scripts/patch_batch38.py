#!/usr/bin/env python3
"""batch38: 补 CronJobStore / CronJobScheduler 的 Koin 注册（修致命缺陷）

问题（对抗性检查发现）：
  CronJobStore 与 CronJobScheduler 在 5 个 DI 模块里全无注册：
    AppModule / DataSourceModule / RepositoryModule / ViewModelModule / PluginModule
  但 CronJobWorker.doWork() 里写了 koin.get<CronJobStore>()，
  新设置页也用了 koinInject<CronJobStore>() / koinInject<CronJobScheduler>()。
  → 一打开“设置→定时任务”立刻抛 NoDefinitionFoundException；
    定时任务真的触发时 Worker 也崩。
  （batch33 移植时漏了这一步，之前的“能存进去”只是没触发到 DI）

前车之鉴（AAAelina/rikkahub-agent 的 AppModule）：
    single { CronJobScheduler(get(), get()) }
  它那边第二个参数是 ScheduledJobRepository，fork 用的是 CronJobStore，
  所以对应改写为两个 single。

锚点：appModule 里 `single { SoundEffectPlayer(get()) }` 之后。
铁律：不用 f-string；含 Kotlin 双引号块用 Python 单引号；幂等标记 rhCronJobDi
"""
from pathlib import Path

ROOT = Path.cwd()
MARK = "rhCronJobDi"


def fail(path, msg):
    print('::error file=' + path + '::batch38 ' + msg[:1400])
    raise SystemExit(1)


P = "app/src/main/java/me/rerere/rikkahub/di/AppModule.kt"
t = (ROOT / P).read_text(encoding="utf-8")

if MARK in t:
    print("batch38: CronJob DI already registered")
else:
    ANCHOR = (
        '    single {\n'
        '        SoundEffectPlayer(get())\n'
        '    }\n'
    )
    idx = t.find(ANCHOR)
    if idx < 0:
        fail(P, "SoundEffectPlayer single anchor not found")

    addition = ANCHOR + (
        '\n'
        '    /* rhCronJobDi: batch33 移植定时任务时漏掉的 DI 注册。\n'
        '       缺了它们，CronJobWorker 与设置页的 koinInject 会抛\n'
        '       NoDefinitionFoundException。前车之鉴：AAAelina 的 AppModule。 */\n'
        '    single {\n'
        '        me.rerere.rikkahub.data.cron.CronJobStore(get())\n'
        '    }\n'
        '\n'
        '    single {\n'
        '        me.rerere.rikkahub.service.CronJobScheduler(get(), get())\n'
        '    }\n'
    )
    t = t[:idx] + addition + t[idx + len(ANCHOR):]
    (ROOT / P).write_text(t, encoding="utf-8")
    print("batch38: CronJobStore + CronJobScheduler registered")

print("batch38: OK")
