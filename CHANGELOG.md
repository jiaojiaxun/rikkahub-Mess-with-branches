# RikkaHub（分支审阅版）更新日志

## 范围与说明

- **功能历史主线：**`origin/fix/batch1`，共 621 commits；审阅覆盖 2026-08-31 至 2026-11-01（含首尾），截至 11/1。末端 HEAD 为 `f086776dd43ab7d545d6c45f6c02e94e01d2a32a`（phone(332) 修复）。
- **其他核对线：**`origin/snapshot` 是功能主线之后的一个提交，共 622 commits；快照末端 HEAD 为 `a767b371a596abd7e12ef7a46c44356f0e6be614`（snapshot: run 574），用于核对最终源码接线。默认分支 `agent-2.4.14-final-public` 仅 6 commits，HEAD `103365d848ad4d4b85e02e78e1b1f272cbfc3cef`，是独立公开文档短线，不替代功能历史主线；文档线更新不作为产品功能记载。
- **版本事实：**审阅材料未发现可据以发布正式 SemVer 的 tag。文中 2.4.15–2.5.6 是提交明确标注的**上游来源版本**，不是本仓库版本；`batchN`、`phone(N)` 均为内部工作标记，不是软件版本号。本日志不推定任何发行版本。
- **历史起点：**仓库可见历史最早始于 2026-08-31 的 public-safe source snapshot；因此更早的项目/上游变更无法从该仓库核实。该初始提交为 [`1128991360fa22485ce13951343fadbe13bf1718`](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/1128991360fa22485ce13951343fadbe13bf1718)。各项按提交日期及可核验功能合并去重；中间编译修补、补丁锚点重试、诊断、CI、回滚和已被修正的失败尝试不作为独立产品更新。
- **证据范围：**提交链接均指向此仓库的完整 SHA。较多功能通过构建期 patch 脚本表达；审阅依据为提交差异、脚本内容及提供的快照核验，并非完整构建或运行测试。

## 更新日志

### 2026-11-01

#### Added
- **手机无障碍操控基础能力：**新增屏幕树捕获与文本化、敏感输入遮罩及银行卡/身份证号脱敏、动作执行、安全规则与 PhoneCore 调度；提供读屏/收集、点击/输入/滚动/按键、打开应用、handoff 和 intent 等工具，并加入助手开关。默认安全门对系统页、敏感输入及支付/银行等场景保护或要求确认。phone(331) 补入设置页、拨号、短信草稿、分享、导航、日历等 intent 处理。来源：[phone(326) 数据层与安全规则](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/c24e80b2192268a7303227d544d683a5c5d8004d)、[phone(327) 屏幕捕获](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/b58ddebf056e83c9221286426ae339b8de487338)、[phone(328) 执行层与无障碍服务](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/ad7cabc049a5c22bfa625c2bde143ce22ca0c890)、[phone(329) 调度核心](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/8034d4505bada3820561b5c06467bb86a87d4c69)、[phone(330) 工具接入](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/a8c41469888419e2e0a55716fd69b8cb68a03a88)。
- **聊天页 DSH 风格界面：**加入顶栏、输入区快捷键、上下文使用环及用量面板；composer 整理附件入口，按助手名称生成占位文案。上下文容量优先按当前对话固定模型解析，HTML 皮肤顶栏高度同步调整。来源：[batch318](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/1f85f65325b8172574407e79d5bec78225a268b7)、[batch319](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/b9b9364bb62c69d9b287fe24145781ce6f0ae7aa)、[batch324](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/78cb16ec591aec0b7a9596890b69645533f1575f)、[batch325](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/6c0d932e35510cb5f24d4faf48608a76e6cc503e)。
- **DeepSeek 搜索服务：**接入 Search 与 Fetch、API Key 配置、结果映射及错误处理；这是适配 DeepSeek API，不是应用上游版本移植。来源：[batch316](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/803f16b235b26f55e8f99668ccfa1d2310defa6d)。

#### Changed
- 文件与工具面板取消重复的拍照、图片、文件入口，改为提供联网搜索和思考深度控制。来源：[batch326](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/f3825b3fc130355424df9add7689bb34fbb8b29d)。
- 思考区优先显示 AI 提供的任务说明或最新推理片段；工具行复用任务说明。来源：[batch317](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/908f2538650099f721926b725f125a680d677894)。

#### Fixed
- 修复 WebDAV/S3 备份与覆盖恢复在后台任务尚未结束时就报告成功的问题，并正确传播取消信号。来源：[batch317](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/e5967a02606d2c9d1f36b8e158692b3faacda0f3)。
- 修正无障碍工具的 suspend 调用、intent 分发与角色信息读取，避免调用不存在的 API。来源：[phone(331)](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/015d286e659223193939b3b0e445d554dd6b2232)、[phone(332)](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/f086776dd43ab7d545d6c45f6c02e94e01d2a32a)。

### 2026-10-27

#### Added
- 思考抽屉顶部实时显示当前活动步骤；推理显示计时，工具步骤复用工具标题，服务端工具显示工具名。来源：[batch295](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/d711e5af20a989f9770e9f218365528edbb5af3b)。

### 2026-10-23 至 2026-10-25

#### Added
- **工作区执行与 rootfs：**恢复 Linux shell/rootfs 安装链路，加入 proot、shell runner、后台进程和工作区工具；后续补入静态 busybox/applet、nativeLibraryDir 执行入口、bind mount 占位路径及 rootfs staging/原子提交。来源：[工作区管线](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/d93e4483f98783c339e3e419786fd3f4e7542924)、[工具与安装接线](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/dc02c19f90fc5a3c91a80ebbf12c27fbb52f42c6)、[busybox 执行入口](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/23dc396f22a0671a3907db947ebf1445020a3558)、[原子安装器](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/35c0026a856e6f9598dd72cfbd6768e750d13bd0)。
- **工具与思考链：**加入逐层展开的思考链抽屉、工具时间线/入参结果、按活跃步骤计时；工具步骤改为就地展开，默认折叠且生成时不自动展开。流式输出加入匀速呈现、块冻结与淡入。来源：[思考链抽屉](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/ad7dd67a32780ba943d8e8e043668f64669a5921)、[流式平滑](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/30f301216f679744e11493d480677e11c47da7c2)、[就地展开及备份合并界面](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/9ea4c07ab18c2dbf53af4dee6c1c151d100b3eeb)。
- **MCP 头像与授权：**设置页支持 MCP 服务器头像，助手选择器及聊天工具行展示服务器头像；建立审批身份，并支持 AppControl 动作级、MCP 服务器级授权及 Cron 预设。来源：[MCP 头像](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/7c506ed2b6fae7fbfd628059ab0633784016ff94)、[细粒度授权](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/5158c90e429bd1252ce6e75f2e3275b0f8265d8a)。
- **工具调用体验：**加入 AI 工具调用行展示文案；新增本地持久化 JavaScript 自定义工具。来源：[batch229](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/85e6de775e927162fa57dba7ade84e8633a3fbec)、[自定义工具](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/bb7acc6643b3b290ed84c6098dbfb9128addb91e)。
- **备份与记忆：**备份可包含 scripts 并在恢复时还原；备份合并支持差异分析、确认及批量选择；恢复后可选择删除本地备份包。修复旧备份孤儿记忆的查询/归属兼容。来源：[scripts 进备份](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/252ecf5b819a738334154fa39338debd4c9fb24b)、[备份合并流程](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/957db361572f4ec3f6e10eb4ba038780974c9dc0)、[记忆兼容](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/4f6735d956575a91579a35d4d7c33c11c9457c06)。
- **聊天和工作区交互：**支持 MCP 能力状态展示、引用隐私过滤、预览搜索入口恢复；优化工作区 shell 选择、AI 文件卡片及思考链摘要。来源：[会话模型显示修正](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/7084043b6c540c43c24f0c4a56f158b7512f457a)、[引用隐私过滤](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/253c67674b984c8d776faa741729f4cdc6fdd144)、[预览搜索恢复](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/05109455e10669e6994df3ed9a19a6bba36a79dd)。
- **Release 构建：**增加固定 release 签名配置，支持同签名 APK 覆盖安装。来源：[签名构建](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/295da6f1c38191ee22a7413a422a90a3e005b2ef)。

#### Changed
- 聊天模型选择、输入栏选择器及顶部模型名统一跟随助手/当前会话模型来源；顶部改为展示数据而非重复计算。来源：[batch255](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/1e365edcbbe4b0ff7743a6ba491b71f3344d990f)、[batch260](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/a5b30a878759c119ef5d3896f8cb968105e37f34)。
- 增加中文/英文资源打包审计；补齐部分工具及 OAuth 界面中文资源。来源：[batch301](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/335dda6b91633142231bdb44c241bcba7e0b5833)、[中文资源](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/3072ecf4ed222e2b7081c7db82f0528688b0efa6)。

#### Fixed
- 修复工作区 shell 硬编码 `/bin/bash` 导致的失效，并按 rootfs 选择可用 shell。来源：[batch252](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/ef581a67fc9af350b02089554e3536ef1d1f2f75)。
- 修复模型切换后聊天页仍显示全局模型、引用队列丢失 `quotedMessageId`、隐藏段泄露、流式重进时整篇消息重放，以及 Rootfs 下载/安装问题。来源：[引用链修复](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/7fa866e206018f4f50dd285475f827f0754c71cf)、[Rootfs 多镜像回退](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/e1f7d7b9d7b348712780694300ced4370da367df)、[流式重放修复](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/14f3479a914785734f18460e8055abe84621e4ea)。

#### Removed
- 会话独立模型总开关曾在 batch285 实验性引入，随后 batch287 明确整体回退；预览模式搜索条的移除也在 batch315 恢复。因此这两项不作为期末仍保留的移除/新增功能。相关记录：[模型行为回退](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/7338d35864e2125739a04d3a2bf2615e3ab41a1c)。

### 2026-10-16 至 2026-10-18

#### Added
- 新增 AI 持久化 JavaScript 自定义工具、models.dev 上下文目录查询、备份合并快捷决策；增加 Rootfs 安装卡片崩溃修复和榨干 token 开关接线。来源：[自定义工具](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/bb7acc6643b3b290ed84c6098dbfb9128addb91e)、[models.dev](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/8f48d51d6277f4eba34d6565eb7b4e1a5f9452df)、[备份快捷操作](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/eaf2fc8cd476a8f2b6d91d223e3b6878e2817d80)。
- 榨干 token 会话级自动续跑支持用户停止与轮次上限；加入 proot 二进制及 x86_64 支持。另新增 BLE 心率广播设备入口、todo_write 计划工具及计划条。来源：[自动续跑与 proot](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/dd0664318941f7f631ce25f8322afbfb20ca2b72)、[计划工具](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/35cfb76dd626d8db761e8526dfab4a9bf3a5c79c)。
- 建立会话级助手/模型配置和会话私有短期记忆；Rootfs 下载加入多镜像回退及龟速检测。来源：[会话配置](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/baa10693b8cba5d22bb88eadd91b99abb33d4874)、[Rootfs 回退](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/e1f7d7b9d7b348712780694300ced4370da367df)。
- 新增 NOTICE 与 README 衍生来源/许可证说明；备份可在恢复后安排删除本地备份包。来源：[NOTICE](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/d11686614d5bfe7abe00d0aa113a4921ca8ce006)、[README 来源说明](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/33da62cdf196826febd4d8669275ef7c2748fb4b)、[恢复后删除备份](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/cbe450a1cc9b523d918aeb0a6cd840db19d49a3f)。

#### Changed
- 将生成管线移出主线程；自定义聊天字体应用到全局排版；流式输出优化为降低重复上下文估算、冻结闭合 Markdown 块及缓存 reasoning 文本转换。来源：[后台生成管线](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/3ebf2ea11f20066f167cc1619ff0735f8c213832)、[流式优化](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/623a70fcfa72c5f7c933f5140a7d79cdcdce4e7f)。
- 备份 ID 匹配失败时按去掉末尾 `+N` 的原名回退；工具调用行优先展示 `_display` 文案。来源：[备份对话匹配](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/6f9f7754b90d2166d7354cbb30d7defbebd7dc27)、[工具行文案](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/85e6de775e927162fa57dba7ade84e8633a3fbec)。

#### Fixed
- 修复会话配置迁移缺列、模型写入编译问题、Rootfs tar 的 `./` 根条目安装崩溃，以及模型弹窗分组折叠失效。来源：[配置迁移](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/12c1f12ac3a0676347612aed1f487f5a09149e53)、[Rootfs 修复](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/3ab0517a9b609dc488773d453527fc7d042d89a4)、[模型弹窗修复](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/99cf8bc8d7d5b6edbb16b11244cbdc2b0d0b7cdd)。

### 2026-10-11

#### Added / Changed / Fixed
- 新增工作区 Rootfs 安装入口、工具思考摘要；移植上游 RikkaHub 2.5.6 的 JsonTree 长按崩溃修复和 MCP schema `$ref` 内联修复。上游版本仅说明来源，不代表 fork 版本。来源：[Rootfs 卡片](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/e9d7e050538f0f95aef635a9eafc4e6dc8d502af)、[JsonTree 上游 2.5.6 修复](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/699531395d17aea283d07145868e67f7cc8f279b)、[MCP `$ref` 上游 2.5.6 修复](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/24ab1b699f94ae6e3880462ea0fd1f48df6e9d88)。
- 加入会话级榨干 token 开关、Responses API 流式重试、字体全局应用和中文文案调整；调整定时任务重复行及酒馆模式开关位置。注意：该日证据确认了开关/存储/接线，未确认自动续跑循环；续跑实现见 10 月 16–17 日。来源：[开关](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/8850d5c9a8cfa2196cfeed4237d70ac7bd2245fe)、[Responses 重试](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/7eb501cbf3eaf2290ef68e0b33eb789098ac8920)、[全局字体](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/0d5b992d0c64e2f5d2355fbedcd0deef0c284169)。

### 2026-10-10

#### Added / Changed / Fixed
- 加入鲸鱼主题预设、聊天页吉祥物、关于页鲸鱼肖像及鲸鱼加载动画；工作区 shell 数据库迁移兼容 v36 字段。来源：[鲸鱼渲染/角色](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/81b001faf88cd07f16877a6820bb2680f9fd9301)、[聊天页吉祥物](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/2d6e1d61b3e0e02a1464c0b9bd80a71387786283)、[v36 数据库兼容](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/2b21896d030887f690550be526f82837e198daad)。
- 定时任务设置页支持查看/手动触发，AppControl 增加 6 个定时任务操作；子代理工具正式接入注册/依赖注入并增加 `parentChatId` 及 schema v35 父子关联。来源：[定时任务入口](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/bc08ca05910372e0039e73fb3a6afdc6b83e78dd)、[AppControl cron 操作](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/fc3a7cafa3f7bd27a3eab4360a974c0d1d4876f1)、[子代理会话关联](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/c6f08b9095eb44e458249df5a1f845d1a43b9a16)。
- 提供商搜索支持 API Key/Base URL，工具链显示 N/M 进度；折叠思考链恢复原地展开，并加入 RP 自定义文本样式及 AI 工作区文件大卡片。来源：[提供商搜索](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/fbe2d656563d0aef4a13c737801c3b7832aa29f6)、[N/M 进度](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/dae196a15d78d7f8035b53e8e85a8c17f6c28cf5)、[工作区卡片](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/f2c5f50bfa88f852934776f0c70a11d7897d0138)。
- 按用户反馈回滚未达到预期的 batch41 压缩重试/取消实验，恢复原有压缩实现；不是保留新增能力。来源：[回滚与反馈修复](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/f5bbb6aea30a0c3fa3424004d5ee95141693b385)。

### 2026-10-07

#### Added / Changed / Fixed / Removed
- 恢复 Linux 工作区 shell、proot/rootfs 安装、后台进程和 9 个工作区工具；补充 JNI 库、镜像检查、依赖和数据库迁移。来源：[shell 管线](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/af5050530767781b302665d5c00574bcf9640e3e)、[Rootfs 安装器](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/f10f1851195b3f93c4c22fc8852091efd5ca2835)、[工作区工具](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/15852ada0b038f1f1766752e5b568f2d4f0e9abe)。
- 供应商配置支持多组 API Key；聊天页模型选择器搜索模型/供应商/API Key/Base URL。新增应用版本戳及 `get_app_version` 本地工具。来源：[多 API Key](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/189d5d267356ee5c80095d1a090ba15fc18d92c6)、[模型搜索](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/98e595952a4accc501f354f7374dedf8937468a9)、[版本工具](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/765547349fc5da4e10c4da3d309f1b46e8c18ab4)。
- 备份导出支持选择项目及轻量附件筛选；WebDAV/S3 上传转入 AppScope 后台任务；文档/音频附件卡片放大。来源：[备份项目选择器](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/d7572a15ab4cab038adc00b9e53def67c0a2ddeb)、[后台上传](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/449b79bf47d122cd434cff12021a006a45935008)、[附件样式](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/1e3642906fdd86671c01eacfeb55154ae70b8a17)。
- 新建供应商时按 URL/API Key 查重并可确认合并；非新会话隐藏导入共享会话按钮。移除推荐供应商和二维码导入入口。来源：[供应商查重](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/848a63ddaf87d341b71c80ce3ec80ff4aa5a046c)、[共享会话按钮](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/113c42e8a3dc6fa9d9658d05b0df0da8bb5f7d74)、[移除供应商入口](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/765547349fc5da4e10c4da3d309f1b46e8c18ab4)。

### 2026-10-06

#### Added / Changed / Fixed
- 聊天生成可切换流式输出；新增酒馆模式会话开关、截断后自动续写；侧栏助手卡片可切换助手。来源：[流式开关](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/3056277c55874ec903e173ce500e4d3f134162aa)、[酒馆模式](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/92c2aebc2d4a583886597479a35f9dec850d09e4)、[自动续写](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/48d155ecfd238a1e1c489c721f3170fb9a4c0dfe)。
- 定时任务支持手动创建/编辑及 cron 预设；LITE 备份阈值从 10/5 历史版本的 5 MiB 调整为 3 MiB，并加入文本/图片筛选及按配置筛选图片。来源：[任务编辑](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/bc9bf4fbb4e8967a23de0a4fe198ac44a3a507bc)、[3 MiB 阈值与筛选](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/6f30a51b1f28bc81b602d01add76c2ec3cbe311b)、[配置图片筛选](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/d0de593e382c84353f7af9b955f62d6687f7a3a8)。

### 2026-10-04 至 2026-10-05

#### Added
- **引用回复：**接通 `quotedMessageId`、引用块、菜单入口、消息列表显示与发送链；batch95 修复真实引用文本注入。batch57 系列早期草稿实现有误并已删除，不视为交付。来源：[引用数据链 batch65](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/0e801e31f5ef485f3dba53855b0400aa3b7e483a)、[引用 UI batch66](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/13c2e96465f3fb300f94b5148275251513e251d4)、[引用链路 batch68–70](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/8777dfa478e03b67728bd3a141f62dd0a8020379)、[注入修复 batch95](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/ba4aeb4de406bf87031a581d7855a972cadf7370)。
- **子代理交互：**审批身份/权限继承、父子会话折叠树与嵌套展示、审批横幅及可选子代理模型。来源：[审批身份 batch55-4b](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/473f9920cb70b9f6d50220c0e03c1e2c13089336)、[嵌套会话 batch83](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/d6cadf10245a74a6e25ec99c97877682fc0187ad)、[可选模型 batch91](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/1264bb0909ee93992dadf7c5e29c414c928c0b6f)。
- **工具与模型体验：**增加工具 Summary 面板内容及语义映射、清爽单行工具步骤和 `m/n` 进度；补充供应商一键整理/最近使用时间、模型名前缀规范化及上下文长度规则。来源：[工具摘要 batch76](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/6f3a5ec1b1a9e6e70d184a4106d95acb16c23617)、[面板内容 batch88](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/c8dcea393313d84b5f656f05d6bb1d8e6f67a5d9)、[单行工具步骤 batch81](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/308d56c6e5a23343509a42a005e67dba40cfc169)、[工具步骤进度 batch78](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/fc251f550a4c62cd007ffe76aba99fdbc3be9ec0)、[Summary 语义 batch102](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/eda7868af66a1a0668aca65dcae77fb001a33160)、[供应商整理 batch92](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/20b2df1e9dab80a5d391a7b42a9d84a7cf023d6e)、[上下文解析 batch56](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/a0aff9698364b7fa11145efb2e94a048ec90d8cb)、[Kimi 规则 batch94](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/256a1e44d4aa23b6274b5792e0428a775ff88d27)、[MiMo 规则 batch98](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/1992916aec3376ab0162ed6c38aced84c58d11f9)。
- **聊天界面与设置：**加入顶栏 haze/玻璃效果、卡片淡入、抽屉美化及 Yuihub 四宫格；增加高级设置中的定时任务入口。用户头像/昵称编辑属于尝试：batch86c 提交注明“准备好，待推”，不能记作 10/5 当天已推送；后续 snapshot 源码可见接线证据。来源：[Yuihub 四宫格 batch85](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/2511a3a98fad93c648d9abaced838d690818d12b)、[定时任务入口 batch105](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/6ebf71423dcbfa78e679ad0769fba1517b2e4d68)、[头像/昵称入口尝试 batch86c](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/688848982fbb3346a7e72378f089d2f686217887)。
- **通知与备份：**加入 `send_notification` 工具、独立开关、Android 13+ 运行时通知权限；ChatService 发出生成更新/结束事件，由 `ChatNotificationManager` 消费。LITE 取代 `PURE_OFFICIAL`；10/5 的 5 MiB 附件阈值及 totalBytes 修正是历史版本，10/6 演进为 3 MiB 和文本/图片筛选（见 10/6）。来源：[工具注册 batch87](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/2f41b5b1690a0734602f0f8ec30fc950b6a031f4)、[可达性/独立开关 batch96](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/9f8eada19a6640f694493d994adf349fd9cbb182)、[运行时权限 batch97](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/d55b93ca249f4a85f2cf0054ee38de328659c979)、[事件接线 batch101](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/10ed5586ffa2ee9c35a5342a6d383d4efeabd9a9)、[10/5 LITE 5 MiB 历史实现](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/79b10cf0ec74466c7c7ad21d6d8aabcbcb9c1d37)。设备需由用户授予通知权限。

#### Changed
- 模型上下文解析规则扩展（含 Kimi K2、MiMo 1M）；供应商名规范化。OFFICIAL 备份恢复兼容 `parent_chat_id`，设置页清理 QQ/Discord 与工作区文件入口（仅移除入口）。来源：[模型名前缀 batch79](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/4ec0186dc71e24f9acebe29ff0d7f5b83c202026)、[MiMo 规则 batch98](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/1992916aec3376ab0162ed6c38aced84c58d11f9)、[OFFICIAL 备份兼容 batch104](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/0b06ddefddb32884eb14a9f9e72742b3a79d7e7f)、[设置入口清理 batch100](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/99351999bfea4fc96661428914fed6840a048766)。

#### Fixed
- 修复“已是最新”备份恢复校验不应依赖 fork 专属字段的问题。来源：[batch89](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/95d78cbae2fa025a6a9665d5700fe33d5e69f857)。

#### Removed
- 移除赞助弹窗及设置页中的 QQ/Discord、工作区文件入口；仅移除这些入口，不据此推断底层功能删除。来源：[赞助弹窗](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/a00d1909c203a6c7063e30e3379254e05bce4b97)、[设置入口清理](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/99351999bfea4fc96661428914fed6840a048766)。

### 2026-10-02 至 2026-10-03

#### Added / Changed / Fixed
- 扩充模型上下文长度规则；自动压缩增加“只保留最近 N 条”模式及冷却机制，并改进工具/系统提示开销估算。来源：[上下文规则](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/0b3942ba51490be93e85da892965879c6c2f08fc)、[压缩模式](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/a76bd65aa9abbb7aa87c9d1e44d85788abcea787)。
- 新增 Claude Opus/Sonnet 5.5、Gemini 4 等模型支持；模型列表可按供应商折叠；导出对话可排除思考过程，重复 API Key 有确认提示。来源：[模型识别](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/5dc7acf4db4be77b913c727665ca13b0a8246ba3)、[模型列表](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/705ef06105324eddc3881604092e1a6b73e75bc9)、[导出选项](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/12cc4ff2148869b9fa078221dfeeb77b52948a98)。
- 工作区支持多选批量导出；jieba 词典注册移出数据库打开关键路径并异步预热；加入鲸鱼主题与上下文使用环，后续增加完整鲸鱼吉祥物渲染、聊天叠加及加载动画。来源：[工作区导出](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/80fabe8b27dc740092267822ca9c535584b899cf)、[启动性能](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/912b19e9e9c9a1ac51f9788847cf288542fa4349)、[吉祥物](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/2d6e1d61b3e0e02a1464c0b9bd80a71387786283)。
- 新增 CronJob 定时任务与 SubAgent 基础引擎；后续完成工具接线、持久化调度、设置页、手动触发和父子会话关联。来源：[CronJob](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/90070ead410c85f5f822f43ae6ff74e57fa97ebe)、[子代理引擎](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/a8690bee185bb5a32f947c5ce66f1ff2d599166e)、[调度任务](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/3a0e87efcaee2a2fc14f6060610629f4529e7ca3)。
- 扩展本地工具 AppControl/Chat UI、图像生成 `generate_image`、any-file/workspace 导入；改进备份兼容与 WebDAV/S3 列表。来源：[图像生成](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/d5602b03e9028d32783dcb327c0a11680695a570)、[AppControl 工具](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/908e7b4ae0eda629b7cb3e185eac2f6a27c1d557)、[FULL 备份兼容](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/f21a719ac7d1bdc5993b308edfe946de6be32515)。
- 改进提供商搜索、工具步骤折叠、对话队列、引用块、流式 TPS/跟随滚动、统计成本与上下文估算；新增自定义文本样式、轻量流式渲染及中文 cron 解释。来源：[轻量渲染](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/d6c46138af65964c0b2d71e8ffb7d3c058b373af)、[cron 中文解释](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/fe0b75b979c230b17c71eab2ca9f1f3c1b772608)、[统计修复](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/c97cdae84a530b437a5a0457264970265bd22832)。
- 技能导入改为字节下载以保留二进制文件，并补充 Android 翻译快捷入口；新增 Responses API 重试、工具调用进度及供应商模型目录缓存尝试。来源：[技能导入/翻译入口](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/e37688232f5960ad4c1b0d791137d7ae1ef0e78e)、[Responses 重试](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/7eb501cbf3eaf2290ef68e0b33eb789098ac8920)。

### 2026-10-01

#### Upstream 移植（不是本仓库版本）
- 该日移植提交标注来源 RikkaHub 2.4.15–2.5.5，覆盖模型/供应商注册、GPT-6 与 MiMo v2.6、火山引擎 TTS/语音识别、服务端 VAD、Exa 搜索参数、网页聊天、附件选择、收藏/代码显示、MCP OAuth/SDK、DashScope 参数、OpenCode/X-Session-ID 兼容，以及多项崩溃、输入与 Responses API 修复。上游版本仅作来源标签；此仓库按具体移植提交吸收，不等同上游发行。代表性来源：[2.5.5 依赖与组件](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/aef279a3d09900d523b5bf3fe6962bfa159db110)、[2.5.5 MCP 空请求头修复](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/d0292d979617126d559e3da0f7e6ee5c60fb1031)、[2.5.4 MiMo v2.6](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/83ed098dd013beda055a1e1bb63e176f234d8e7e)、[2.5.3 移除小马默认供应商](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/a1a8890b4738f2e63cfa430c804868c831094007)、[2.5.2 火山语音朗读](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/adbb1f48d4eba1e2779291af29080417e379add3)、2.5.1 网页提问多选（原引用 SHA 无法核实，故不保留无效链接）、[2.5.0 服务端 VAD](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/cc8272360aefa7d47209d4f6f4ffc352d60636f2)、[2.4.17 GPT-6 识别](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/e15534874e2d3f5241eadb2165138aeeee40bdad)、[2.4.16 图片选择](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/843572faf2332ceb938d4a80d7fb56f3bd928b80)、[2.4.15 工具操作消息按钮修复](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/7bb8d03cc48d7b2243db74fe05f3da87ff538c0b)。

#### Added
- 长用户消息折叠；上下文压缩时流式呈现模型输出；附件可选择任意文件，文本/文档可直接附加，其他文件可导入助手 workspace。来源：[batch3](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/c252370d9b35ff78b869c55566f12f40eedfffcc)。
- 新增后台图像生成服务及 AI `generate_image` 工具，结果保存到图库；增加本地 Chat UI、AppControl 与 HTML 模式开关。来源：[图像生成](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/d5602b03e9028d32783dcb327c0a11680695a570)、[本地工具开关](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/c2c9257c7f5496f5393348b085fec18ae80125d4)。
- 模型注册表增加/合并 HY4、Qwen 3.8、Step 5、GLM 5.3 及 DeepSeek V4/V4.1 等条目；相关 DeepSeek Flash/V4 模型支持图像输入。来源：[注册表冲突解决](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/aa6ed198c3ab74eba1f348166d97df5a4201966f)、[DeepSeek 图像输入](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/7738bf229ace6f22780fa99034671ea3d8797f42)。

#### Changed / Fixed
- HTML 聊天皮肤增加安全区域/对比度和原生退出入口、布局限制；审批使用明确双按钮。加入 Responses API 路径配置及 reasoning OFF 处理；改善流式滚动、TPS 与皮肤/原生文本显示。来源：[batch1](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/f1c05cf8d330f6d6bfdc2a2f4803e15537dee919)、[batch2](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/ade8a28b4034a88241f54fadabc3bbd7e28d9336)。
- FULL 备份同时保留官方 RikkaHub 2.4.14 可导入数据及 fork 专属数据，另提供剔除官方版本不识别数据的兼容导出；修复上传备份未出现在 WebDAV/S3 列表的问题。来源：[FULL 备份](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/f21a719ac7d1bdc5993b308edfe946de6be32515)、[官方兼容导出](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/30e5d829fc32d1edba74c759dd0defbf474a4f73)、[列表修复](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/0c28de5f431e4ff3e7c5f9e9f85633b64d60ed65)。
- 用量统计按流合并 token、跨步骤累计费用并修正缓存字段/上下文重复计数；网络翻译改用 Microsoft Edge 非官方端点并处理长文本分块。来源：[统计审计](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/c97cdae84a530b437a5a0457264970265bd22832)、[翻译端点](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/d7c06f8d19df1a2145b6cd8384a0a5fa8c3cc073)。

### 2026-09-13

#### Added
- **AI 编写 HTML 聊天皮肤：**新增 `chat_ui_write`、`chat_ui_set_mode`、`chat_ui_list_skins`、`chat_ui_delete_skin` 工具，可创建、启停、列出和删除皮肤；写入、切换、删除需用户审批。新增独立皮肤状态存储与全屏 WebView 层，通过 JS bridge 接收事件，原生消息区与输入栏保留。实现限制 HTML 大小及外部脚本、样式导入和 `file://` 引用。来源：[工具初版](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/0eddd3207c1b96252ce45760910a65bb013f306d)、[独立状态存储](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/d18482be3a8fd0d848c796e2e2c5f055cd983c61)、[全屏皮肤层与 JS bridge](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/f67380bcfa0d62ec4c65f70a5a5f2421d842d295)。
- **AppControl 本地工具：**新增 `rikkahub_capabilities`、`rikkahub_query`、`rikkahub_apply_change`，支持查询脱敏应用状态，并在每次用户审批后执行白名单操作，包括助手/模型切换、助手配置、provider、MCP server 及 Web server 管理。查询会排除密钥、令牌、密码和自定义 headers。来源：[AppControl 工具](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/908e7b4ae0eda629b7cb3e185eac2f6a27c1d557)、[provider 重命名操作](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/6e2deeb5a394174909fd0ab4addbb6a54d51e802)。

#### Changed
- 通过构建期补丁注册本地工具、初始化皮肤状态并将皮肤层接入 ChatPage；工作流提供双模式分支 APK 构建。来源：[皮肤单例/工具工厂](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/1a1e0acda489fc72ad07af6396c2f7d3f920c59d)、[皮肤层接线](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/cbb8e5fb7265610815e7c5218ba1900750e1dae9)。AppControl 的 Chat UI 选项和工具组亦经构建期补丁接线。来源：[AppControl 构建接线](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/908e7b4ae0eda629b7cb3e185eac2f6a27c1d557)。

### 2026-08-31

#### Added
- 公开安全源码快照（RikkaHub Agent 2.4.14 public-safe source snapshot）；这是可见仓库历史起点，不是本日日常功能更新。来源：[初始提交 `1128991360fa22485ce13951343fadbe13bf1718`](https://github.com/jiaojiaxun/rikkahub-Mess-with-branches/commit/1128991360fa22485ce13951343fadbe13bf1718)。

## 已知问题与证据边界

- **未确认的补丁落地：**batch7 模型目录缓存有 SettingVM 实现提交，但 UI 接线只见 patch 脚本；审阅记录指出一次运行在编译前停止，之后仅修补脚本锚点，未找到成功构建证据。故不将其写成已验证交付功能。
- **验证限制：**全程未运行完整 build、patch scripts 或应用运行测试。大量功能由 `scripts/patch_batchN.py` 定义，尤其 10/4–5 的多项 app 改动；因此按脚本/源码证据描述，不声称 APK 构建成功。未独立验证不等于功能损坏。通知链路在 `origin/snapshot` 最终源码可见工具注册、Android 13+ 权限请求、ChatService 事件和管理器消费；使用时设备仍需用户授权。LITE 备份最终快照已演进至 3 MiB 阈值及筛选实现，不列为期末问题：`origin/fix/batch1:scripts/patch_batch106.py` 与 `origin/snapshot` 最终脚本均为 3 MiB；快照源码 `app/src/main/java/me/rerere/rikkahub/data/sync/webdav/WebDavSync.kt` 也将 3 MiB 阈值接入，并读取图片类型设置筛选。
- **批次/分支缺史：**批次号有跳号、变体及重复主题（例如不同的 batch317）；只记录资料中实际可核实内容，不推断缺失批次的功能。没有独立功能记录的日期/分支内容不补写。
- **历史起点限制：**仓库在 2026-08-31 public-safe source snapshot 之前的项目/上游历史不可得；没有正式 tags 时无法确认传统发行版边界。分段审阅失败：**无**（输入为 `[]`）。
