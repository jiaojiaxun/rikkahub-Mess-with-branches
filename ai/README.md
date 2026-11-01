# `ai` 模块

`ai` 是 RikkaHub Android 应用中的 Kotlin/Android 库模块，提供 AI 消息与模型接口、provider 请求/响应转换、流式响应处理及相关测试。模块由根目录的 Gradle 工程管理，并依赖 `:common`。

当前模块构建脚本没有启用 MNN 或其他 CMake native build；本目录也没有 `src/main/cpp/mnn`。本页只说明 `:ai` 模块，不代表整个 Android 应用的所有 native 构建要求。

## 环境要求

- JDK 17
- 根工程配置的 Android SDK Platform 37
- 从仓库根目录运行 Gradle Wrapper

## 构建与测试

```bash
# 在仓库根目录执行
./gradlew :ai:assembleDebug
./gradlew :ai:testDebugUnitTest
```

Windows 可使用：

```bat
gradlew.bat :ai:assembleDebug
gradlew.bat :ai:testDebugUnitTest
```

`assembleDebug` 编译该 Android library 模块；`testDebugUnitTest` 运行 `ai/src/test` 中的 JVM 单元测试。首次构建需要联网下载 Gradle 和依赖。

## 相关目录

- `src/main/java/`：AI 类型、provider、消息转换和流式处理实现
- `src/test/`：provider 请求/响应与流式解析等单元测试
- `src/test/resources/stream-traces/`：用于回放测试的 SSE 事件样例
