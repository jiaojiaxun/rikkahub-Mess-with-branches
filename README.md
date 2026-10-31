# RikkaHub — Mess with branches

这是一个基于 [RikkaHub](https://github.com/rikkahub/rikkahub) 的个人 Android 实验分支，应用显示名称为 **RikkaHub Agent**。仓库包含 AI 对话、工具调用和本地模型等相关代码，主要用于个人折腾与验证；功能可能变化或不完整，不代表上游项目，也不保证稳定性或提供正式发行支持。

## 项目内容

仓库以 Kotlin 编写，使用 Jetpack Compose 构建 Android 界面。当前代码包含以下方向的模块：

- AI 对话、模型提供商接入、流式生成与工具调用
- Agent 工具、Skills、插件、MCP 集成、应用内浏览器和工作区相关能力
- 本地模型运行时，包括 LiteRT-LM 与 llama.cpp 接入
- 网页搜索、语音、文档解析，以及应用内 Web 服务

具体功能是否可用，可能取决于设备、权限、模型或服务配置，以及当前分支的实现状态。请以源码和本仓库的构建配置为准。

## 项目结构

| 模块 | 用途概览 |
| --- | --- |
| `app` | Android 应用入口、Compose 界面、聊天与工具编排、数据层和应用服务 |
| `ai` | AI 模型/provider 抽象、消息与生成相关能力 |
| `local-llm`、`llama-cpp` | 本地模型运行时及 llama.cpp 接入 |
| `search`、`speech`、`document` | 搜索、语音与文档处理相关能力 |
| `workspace`、`web` | 工作区和应用内 Web 服务 |
| `common`、`highlight`、`material3` | 通用基础能力、代码高亮和 Material 组件扩展 |

## 构建

### 环境要求

- Android SDK Platform 37（项目当前配置的 `compileSdk` / `targetSdk`）
- Android 8.0（API 26）或更高版本的设备或模拟器
- JDK 17
- 仓库自带 Gradle Wrapper（Gradle 9.5.0）
- Android SDK 中与项目配置相匹配的 NDK，以及 CMake 3.22.1；首次构建时按 Gradle 提示安装
- Node.js、Bun 和 pnpm（Gradle 会安装并构建 `web-ui` 前端资源）

当前 `llama-cpp` 原生模块配置的 ABI 为 `arm64-v8a`；其他 ABI 尚未由此配置确认。

### 获取代码并构建 Debug APK

```bash
git clone --recurse-submodules https://github.com/jiaojiaxun/rikkahub-Mess-with-branches.git
cd rikkahub-Mess-with-branches
./gradlew :app:assembleDebug
```

如果克隆时没有初始化子模块，可补运行：

```bash
git submodule update --init --recursive
```

Windows 可将 `./gradlew` 替换为 `gradlew.bat`。构建产物通常位于 `app/build/outputs/apk/debug/`。

> 首次构建需要联网下载 Gradle、依赖和相应 SDK 组件。本 README 记录的是仓库配置；此处没有承诺特定机器上的构建一定成功。

### Release 构建提示

可使用 `./gradlew :app:assembleRelease` 生成 Release 变体。但当前构建脚本将 Release APK 配置为使用 debug signing config，并注明它只是临时本地制品签名，不是正式发行密钥。因此请勿把本地生成的 APK 当作上游或正式签名版本。

## 上游与许可

本仓库是独立衍生项目，与 RikkaHub 上游团队无隶属或官方发行关系。代码部分还衍生自 [ExTV/rikkahub-agent](https://github.com/ExTV/rikkahub-agent) 和 [AAAelina/rikkahub-agent](https://github.com/AAAelina/rikkahub-agent)。

许可与第三方组件说明请分别参阅 [`LICENSE`](LICENSE) 和 [`NOTICE`](NOTICE)。仓库包含不同来源与许可的组件，使用或再分发前请查看相应文件。
