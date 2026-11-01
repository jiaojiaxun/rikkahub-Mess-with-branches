# Web UI

`web-ui` 是 RikkaHub Android 应用 Web 界面的前端。它使用 React Router 与 Vite 构建为客户端 SPA（当前 `react-router.config.ts` 设置 `ssr: false`），静态文件随后由 Android `:web` 模块打包；它不是本仓库独立部署的 SSR 服务。

## 环境要求

- Node.js
- Bun（安装前端依赖）
- pnpm（运行前端脚本）

依赖版本由 `pnpm-lock.yaml` 管理。Android 工程中的 `:web` 构建任务会在需要时通过 Bun 安装依赖，再调用 `pnpm run build`。

## 本地开发

```bash
cd web-ui
bun install --frozen-lockfile
pnpm run dev
```

开发服务器默认位于 `http://localhost:5173`。Vite 会把 `/api` 请求代理到 `http://localhost:8080`；调试需要 API 的功能时，请确保相应的本地后端服务已在该地址运行。代理规则见 `vite.config.ts`。

## 构建与 Android 集成

```bash
cd web-ui
bun install --frozen-lockfile
pnpm run build
```

`pnpm run build` 会运行 React Router 构建，然后执行 `copy.ts`，将 `build/client/` 复制到 `../web/src/main/resources/static/`。复制脚本会先清理并重建目标目录，因此不要在该生成目录中手工维护需要保留的文件。

从仓库根目录构建 Android `:web` 模块时，Gradle 的 `preBuild` 会自动执行前端依赖安装和构建：

```bash
./gradlew :web:assembleDebug
```

Windows 可使用 `gradlew.bat :web:assembleDebug`。如需单独检查前端类型，可运行：

```bash
cd web-ui
pnpm run typecheck
```

本仓库的默认交付路径是将静态前端打包进 Android `:web` 模块；旧模板中提到的 Docker/独立 SSR 部署流程不适用于当前配置。
