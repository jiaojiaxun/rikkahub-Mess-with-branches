# locale-tui

用于查看、编辑和翻译 Android `strings.xml` 的终端界面（TUI）与命令行工具。它可以按配置扫描模块和语言资源、筛选缺失或无效条目，并通过 OpenAI-compatible Chat Completions API 翻译文本。

## 环境要求

- Python 3.12 或更高版本
- [uv](https://docs.astral.sh/uv/)
- 使用 AI 翻译时，需要可访问的 OpenAI-compatible API、API Key，以及该服务支持的模型

## 安装与配置

```bash
cd locale-tui
uv sync
```

`config.yml` 用于配置项目根目录、模块资源路径、语言和翻译模型。运行前请检查 `project_root` 与各模块路径是否符合你的 checkout。当前仓库附带的配置仍列有 `rag` 模块，但当前 checkout 中没有对应的 `rag/` 目录；使用前请删除或修正这条模块配置。

AI 翻译配置从 `.env` 读取。仓库没有 `.env.example`，可在 `locale-tui/` 下自行创建 `.env`：

```dotenv
OPENAI_API_KEY=你的服务密钥
OPENAI_BASE_URL=https://api.example.com/v1
```

`.env` 已由 `locale-tui/.gitignore` 忽略，请勿提交真实密钥。

注意：当前 `config.yml` 的默认模型名是 `deepseek-v4-flash`；若未设置 `OPENAI_BASE_URL`，程序默认使用 `https://api.openai.com/v1`。模型名、Base URL 和 API Key 必须对应同一个服务。使用 OpenAI endpoint 时，请将 `translation.model` 改为该账号/服务实际支持的模型；保留默认模型时，则配置能提供该模型的兼容 endpoint。

## 运行

在 `locale-tui/` 目录运行 TUI：

```bash
uv run python src/main.py
```

测试 API 连接与模型配置：

```bash
uv run python src/main.py test-connection
```

查看 CLI 命令：

```bash
uv run python src/main.py --help
```

## 常用命令

```bash
# 仅向 app 的源语言资源添加条目，不调用翻译 API
uv run python src/main.py add hello_world "Hello, world!" --module app --skip-translate

# 设置 app 的简体中文条目
uv run python src/main.py set hello_world "你好，世界！" --lang values-zh --module app

# 列出 app 模块的字符串键
uv run python src/main.py list-keys --module app
```

`add` 默认会尝试为配置中的目标语言调用 AI 翻译；可用 `--skip-translate` 只写入源语言。命令和 TUI 会修改项目中的 XML 资源文件，使用前建议确认 `git status`，完成后检查 diff。
