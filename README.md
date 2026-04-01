# repomd

A CLI tool that analyzes any GitHub repo and generates a production-quality `CLAUDE.md` file using the Anthropic SDK.

[CLAUDE.md](https://docs.anthropic.com/en/docs/claude-code/memory) is read by Claude Code at the start of every session as persistent project memory — build commands, architecture decisions, gotchas, and workflows.

## Why?

Claude Code reads your codebase when you start a session — but it still has to discover things from scratch every time: which test command to use, which directories are generated and shouldn't be touched, which env vars are required, what the non-obvious architectural decisions are.

`CLAUDE.md` fixes this by giving Claude persistent, session-level memory. But writing it manually is tedious, and most repos — especially ones you didn't write — don't have one.

Three scenarios where this tool is useful:

**You cloned someone else's repo** and want to use Claude Code on it. No `CLAUDE.md` exists. Claude doesn't know the project uses `bun` instead of `npm`, that `generated/` is off-limits, or that tests require a running Postgres instance.

**You're inheriting a legacy codebase** at work. No AI config files. You need to onboard Claude Code without manually explaining the project every session.

**Your own repo, new machine.** You clone it fresh and open Claude Code — it has no memory of your agent architecture, your `.env` structure, or the non-obvious build steps.

`claudemd-gen` reads the repo via GitHub API (no clone needed) and generates a `CLAUDE.md` in one command.

## Install

```bash
pip install anthropic httpx
```

## Usage

```bash
# From GitHub URL
python main.py https://github.com/fastapi/fastapi

# From owner/repo shorthand
python main.py tiangolo/fastapi

# Save to file
python main.py django/django --output CLAUDE.md

# With tokens (higher rate limits)
export GITHUB_TOKEN=ghp_xxx
export ANTHROPIC_API_KEY=sk-ant-xxx
python main.py pallets/flask --output CLAUDE.md

# Debug: save raw signals
python main.py owner/repo --save-signals signals.json
```

## What it analyzes

| Signal | Source |
|--------|--------|
| Project metadata | GitHub API (language, topics, description) |
| Build/test commands | `package.json`, `Makefile`, `pyproject.toml`, CI workflows |
| Architecture | Directory structure, top-level dirs |
| Dependencies | `requirements.txt`, `go.mod`, `Cargo.toml`, etc. |
| Environment | `.env.example` |
| Docker setup | `docker-compose.yml` |
| Test setup | `pytest.ini`, `__tests__/`, test directories |

## Output format

Follows official [CLAUDE.md best practices](https://www.builder.io/blog/claude-md-guide):
- Concise (≤40 instructions — beyond ~150 LLM instruction-following degrades)
- Exact CLI commands, not vague descriptions
- Architecture decisions that affect code structure
- Project-specific gotchas only
- No linting rules (use actual linters)

## Example output

```markdown
# FastAPI

High-performance async Python web framework built on Starlette and Pydantic.

## Commands
- `pip install -e ".[all,dev,doc,test]"` — install with all extras
- `bash scripts/test.sh` — run test suite
- `bash scripts/lint.sh` — run mypy + ruff

## Architecture
- `fastapi/` — core framework code
- `docs/` — mkdocs documentation (do not edit generated files)
- `tests/` — pytest test suite

## Important
- All public API must be fully typed (mypy strict)
- Do not import from `starlette` directly in user-facing code — wrap in FastAPI equivalents
```

## Environment variables

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Required — Claude API key |
| `GITHUB_TOKEN` | Optional — increases GitHub rate limit from 60 to 5000 req/hr |

## Project structure

```
claudemd-gen/
├── main.py          # CLI entry point
└── src/
    ├── analyzer.py  # GitHub API repo signal collector
    └── generator.py # Anthropic SDK CLAUDE.md generator
```

## Architecture notes

**analyzer.py** fetches the repo file tree + priority config files via GitHub REST API. Files are truncated to 3000 chars to stay within reasonable token budgets.

**generator.py** builds a structured prompt from the signals and calls `claude-sonnet-4-6`. System prompt encodes CLAUDE.md best practices as constraints.

**main.py** is a thin CLI wrapper (argparse) with environment variable fallbacks.

## Limitations

- Private repos require `--github-token`
- Very large monorepos may miss some signals (tree truncation)
- Generated output is a starting point — review and add project-specific knowledge Claude couldn't infer
