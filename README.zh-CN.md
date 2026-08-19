# llm-wiki

<p align="center">
  <img src="assets/logo.svg" alt="llm-wiki" width="480" /><br />
  <sub>基于 OKF 0.2 的个人知识库，与你共同成长</sub>
</p>

一个与你共同成长的 OKF 原生知识库。灵感来自 [Karpathy 的 LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)。**bundle 就是 wiki**——没有独立的"导出"步骤。

[English](README.md)

本仓库包含两部分：

| 组件 | 路径 | 用途 |
|------|------|---------|
| **Skill** | `skills/llm-wiki/` | Agent 技能（Claude Code / Cursor / Copilot）— INIT、INGEST、QUERY、UPDATE、LINT |
| **CLI** | `lwiki/` | Python 命令行工具 — 初始化 OKF bundle，跟踪 `raw/` 变更，校验，从旧版迁移 |

## 快速开始

```bash
# 1. 前置条件
uv --version || curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. 安装 CLI
uv tool install https://github.com/hsuanguo/llm-wiki.git

# 3. 创建一个新的 bundle
lwiki init ~/wikis/greek-history --domain "Greek history" --sources "articles, papers"

# 4. 在浏览器中浏览 / 编辑
lwiki serve --root ~/wikis
# 访问 http://127.0.0.1:8765

# 5. 校验 OKF 0.2 一致性
cd ~/wikis/greek-history && lwiki validate
```

## Bundle 结构

`lwiki init` 直接搭建一个 OKF 0.2 bundle——bundle 就是 wiki：

```
my-wiki/
├── index.md          # 声明 okf_version: "0.2"
├── log.md            # 仅追加的操作日志
├── overview.md       # 顶层概念（OKF frontmatter）
├── AGENTS.md         # 本地约定
├── CLAUDE.md         # 简短存根：@AGENTS.md，供 Claude Code 读取
├── README.md         # 指引文档
├── summaries/        # 来源摘要
├── concepts/         # 概念页
├── entities/         # 实体页（人物、工具、组织、产品）
├── insights/         # 综合分析与跨页分析
└── raw/              # 不可变来源，由 raw/files.log 跟踪
```

没有 `wiki/` 包装层。bundle 就是 wiki。

## OKF 0.2 Frontmatter

仅 `type` 是强制要求的，其他字段是建议性的。

| 层级 | 字段 |
|------|------|
| **必填** | `type`（`summary`、`concept`、`entity`、`insight`、`overview`、`attested-computation` 之一） |
| **建议** | `title`、`description`、`tags`、`generated: { by, at }`、`status` |
| **可选** | `resource`（规范 URI）、`sources`（可信度条目列表）、`verified`（审计记录）、`usage_window` |

OKF 的来源追溯取代了旧版 wiki 内部的 `updated:`、`sources: [paths]` 和 `cited:` 字段。

## 日常工作流

| 你做的 | AI 做的 |
|--------|---------|
| 把源文件丢进 `raw/` | 摄取、摘要、交叉引用 |
| 提问 | 从 bundle 回答；用 markdown 链接引用；可选保存为 insight |
| 说 "lint" | 一致性检查 + 启发式健康报告 |
| 在浏览器中浏览 | `lwiki serve` |
| 迁移旧的 Obsidian 风格 wiki | `lwiki migrate <old> --out <new>` |

## 从旧版 wiki 迁移（0.1.x → 2.0）

如果你还在使用带 `wiki/` 包装层和 `[[wikilinks]]` 的旧版 wiki：

```bash
lwiki migrate ~/old-wiki --out ~/new-bundle
# 源 wiki 保持原样；bundle 输出到新位置
# 所有 frontmatter 迁移到 OKF 0.2；[[wikilinks]] 被改写为 markdown 链接
```

迁移完成后，用 `lwiki validate ~/new-bundle` 确认 OKF 0.2 一致性。

## CLI 命令速查

| 命令 | 用途 |
|---------|---------|
| `lwiki init <dir> --domain "..."` | 搭建 OKF bundle |
| `lwiki structure` | 打印标准 bundle 结构 |
| `lwiki validate <dir>` | 校验 OKF 0.2 一致性 |
| `lwiki serve --root <parent>` | Web UI，浏览 `<parent>` 下所有 bundle |
| `lwiki raw sync` / `lwiki raw status` | 跟踪 `raw/files.log` |
| `lwiki migrate <old> --out <new>` | 从旧 wiki 转换为 OKF bundle |
| `lwiki export okf <bundle>` | 校验一致性（`lwiki validate` 的别名） |

## 许可证

[MIT](LICENSE)