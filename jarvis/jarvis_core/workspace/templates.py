"""Workspace content templates (T005).

All template strings live here as Python string constants.
Per spec FR-001 / FR-008 / FR-009 / FR-013 / US5.
"""

from __future__ import annotations


INSTRUCTION_MD_TEMPLATE = """# {NAME}

你是 {NAME}，一个乐于助人的智能体（人）。

## Identity
- 你的名字：{NAME}
- 创建时间：{TIMESTAMP}
- workspace 路径：{PATH}

## Personality
（TODO：描述语气、风格、价值观、说话方式）

## Boundaries
（TODO：能做什么、不能做什么、什么情况下拒绝）

## Tool 使用策略
（TODO：调用工具的一般流程、什么时候该用、什么时候不该用）

## Skills
（TODO：列出这个智能体擅长的领域，或指向 skills/ 下的特定 skill）
"""


PROVIDER_TOML_TEMPLATE = """# provider.toml — Jarvis Core 读取此文件来初始化模型
[provider]
protocol = "openai"
model_name = "gpt-4o"
temperature = 0.2
max_tokens = 128000
base_url = ""
secret_key = "YOUR_API_KEY_HERE"

[provider.extra]
reasoning_effort = "medium"
support_image = false
"""


MCP_JSON_EMPTY = '{"mcpServers": {}}'


MCP_README = """# MCP Server 配置指南

本目录下的 `mcp.json` 是 Jarvis 读取 MCP server 配置的入口，使用
`MCPConfig` dict 格式（与 Claude Desktop / Cursor / Cline 一致）。

`jarvis init` 默认生成 `{"mcpServers": {}}`（空配置），你可以按下面三种
transport 任选其一填入。

## 1) HTTP transport（远程 MCP server）

```json
{
  "mcpServers": {
    "langchainDocs": {
      "transport": "http",
      "url": "https://docs.langchain.com/mcp"
    }
  }
}
```

## 2) SSE transport（Server-Sent Events）

```json
{
  "mcpServers": {
    "legacyDocs": {
      "transport": "sse",
      "url": "https://example.com/mcp/sse"
    }
  }
}
```

## 3) stdio transport（本地子进程）

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "uvx",
      "args": ["mcp-server-filesystem", "--root", "/tmp"]
    }
  }
}
```

字段说明：

- `mcpServers`：对象，key 是 server 名（最终工具名前缀），value 是该 server 配置。
- `transport`：`"http"` 或 `"sse"`（远程）。
- `command` + `args`：stdio 模式（如 `uvx mcp-server-foo`）。
- 也支持 `headers`、`include_tools`、`exclude_tools`、`env` 等字段。
"""


SKILLS_README = """# Skills

本目录用于放置 Agent Skills。每个 skill 是一个**子目录**，里面必有
`SKILL.md`（含 YAML frontmatter），可附带附件。

## frontmatter 必填字段

```yaml
---
name: example-skill
description: 一句话描述这个 skill 干什么
when_to_use: 什么场景下应该使用它
---
```

Jarvis 自动生成了一个示例 skill，请打开
`example/SKILL.md` 参考完整结构。
"""


SKILLS_EXAMPLE_MD = """---
name: example-skill
description: 一个示例 skill，演示 frontmatter 字段怎么填
when_to_use: 任何时候你想看一下 SKILL.md 的最简形态，都可以参考此示例
---

# Example Skill

正文是 Markdown，描述这个 skill 做什么、怎么用、有什么注意事项。

## 用法

- 由 Jarvis 在合适的时机加载。
- 不需要手动注册。
"""


TOOLS_README = """# Tools

本目录用于放置手写的 `@tool` 函数。每个 `.py` 文件是一个模块。

## 命名规范

- 文件名使用 `snake_case`。
- 模块中的函数被 `from tools.xxx import yyy` 加载后自动注册为工具。

## Docstring 约定

函数 docstring 走 Google 风格（`Args:` / `Returns:`），LangChain 会自动
解析成 JSON Schema。

## MCP

MCP server 配置请放到 `../mcp/mcp.json`，**不要**在 `tools/` 写 MCP 客户端。
"""


MEMORY_README = """# Memory

本目录同时承载短期记忆与未来的长期记忆。两个 SQLite 文件**职责分离**，
禁止互相越界。

## checkpoint.sqlite3 — 短期记忆（Saver）

由 `SqliteSaver`（来自 `langgraph-checkpoint-sqlite`）写入。`init` 在
Core 阶段会创建此文件并建表（保存 0 行），用于：

- 单个 session 内的对话连续性。
- HITL、time travel、断点续跑。

重启 Core 不会丢对话；**手动删除此文件会丢全部短期对话历史**。

## store.sqlite3 — 长期记忆（Store）

由 Jarvis Scheduler 在跨 Session 长期记忆特性落地时自动创建并写入（使用
自研 SqliteStore，因为 LangGraph 官方没有 SQLite Store）。**当前 Core
阶段此文件不存在**，`jarvis init` 也不会创建它。

两个文件**职责分离**：

- ❌ Core 代码**禁止**读写 `store.sqlite3`。
- ❌ Scheduler 代码**禁止**读写 `checkpoint.sqlite3`。
"""


TOP_LEVEL_README = """# 本目录是你的 workspace，由 `jarvis init` 生成。

## 【可以改】

- `instruction.md`             你的智能体的灵魂
- `provider.toml`              你的智能体的大脑（模型）
- `tools/*.py`                 你的智能体的手脚（手写工具）
- `mcp/mcp.json`               你的智能体的外接器官（第三方 MCP server）
- `skills/*/SKILL.md`          你的智能体的工作手册（怎么做）
- `memory/checkpoint.sqlite3`  自动生成，可删除 → 丢短期记忆
- `memory/store.sqlite3`       自动生成（Core 阶段不生成）→ 删了丢长期记忆

## 【不要在这里新建】

- `agent.py`、`main.py` 等任何 Python 入口（不存在也不需要）
- `subagent` / 子智能体相关配置（Jarvis 没有"主-子"委派概念）
- `mcp/*.py` 自定义 MCP server 代码（自定义 MCP server 请放在项目仓库）

## 【需要帮助】

- `jarvis --help`

## ⚠️ 警告：不要并发跑 `jarvis init`

`jarvis init` 不做文件锁、不做原子写。如果同时跑两个 `jarvis init` 进程
在同一 workspace 上，它们会按 OS 调度交错写文件——**最后一个写入者赢**。
如果出现半成品，请再幂等跑一次 `jarvis init` 修复。
"""


GITIGNORE = """# SQLite (短期与未来长期记忆)
*.sqlite3
*.sqlite3-journal
*.sqlite3-wal
*.sqlite3-shm

# Python caches
__pycache__/
*.py[cod]
*$py.class

# Environments
.env
.venv/
venv/
env/

# Editor / OS noise
.DS_Store
"""