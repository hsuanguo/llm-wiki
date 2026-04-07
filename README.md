# llm-wiki

<p align="center">
  <img src="assets/logo.svg" alt="llm-wiki" width="480" /><br />
  <sub>LLM-powered personal knowledge base</sub>
</p>

An LLM wiki that evolves with you. Based on [Karpathy's LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).

This repo ships two things:

| What | Path | Purpose |
|------|------|---------|
| **Skill** | `skills/llm-wiki/` | Agent skill (Claude Code / Cursor / Copilot) — INIT, INGEST, QUERY, UPDATE, LINT |
| **CLI** | `lwiki/` | Python CLI — scaffold wiki trees and track `raw/` drift |

## Quick Start

### 1. Install the CLI

```bash
pip install .
# or with uv:
uv tool install .
```

### 2. Create a wiki

```bash
lwiki init ./my-wiki --domain "My topic"
cd my-wiki
```

### 3. Install the skill

Copy `skills/llm-wiki/` into your project's `.claude/skills/` (or use [act-cli](https://github.com/hsuanguo/act-cli)):

```bash
cp -r skills/llm-wiki /path/to/project/.claude/skills/llm-wiki
```

Or in `act.toml`:

```toml
[skills]
llm-wiki = "hsuanguo/llm-wiki/skills/llm-wiki"
```

## Skill

The `skills/llm-wiki/` directory is a self-contained agent skill with:

- **`SKILL.md`** — main instructions (gather context, route to operation, execute)
- **`references/`** — per-operation playbooks: `init.md`, `ingest.md`, `query.md`, `update.md`, `lint.md`
- **`templates/`** — starter page templates: `index.md`, `concept.md`, `entity.md`, `insight.md`, `summary.md`

Works with any agent that reads `SKILL.md` from `.claude/skills/` or similar conventions.

## CLI (`lwiki`)

### Requirements

- Python 3.11+
- Git on PATH (for wiki operations)

### Commands

| Command | Purpose |
|---------|---------|
| `lwiki structure` | Print canonical wiki tree (what `init` creates) |
| `lwiki init [PATH]` | Scaffold `AGENTS.md`, `raw/`, `wiki/`, templates, etc. |
| `lwiki raw status` | Report drift between `raw/` and `files.log`; exit 1 on drift |
| `lwiki raw sync` | Refresh `raw/files.log` to match disk |
| `lwiki checkout` | Alias for `raw sync` |

### Day-to-day workflow

```bash
cd /path/to/wiki-root
lwiki raw status          # check for new/changed raw files
# ... run wiki ingest via your agent ...
lwiki raw sync            # update files.log
```

### Development

```bash
uv sync --all-extras
uv run lwiki --help
uv run pytest
```

## License

[MIT](LICENSE)
