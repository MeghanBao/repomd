"""
Uses Anthropic SDK to generate a structured CLAUDE.md
from repo signals collected by analyzer.py.

System prompt is modeled after Anthropic's own internal CLAUDE.md creation
agent prompt (as extracted by Piebald-AI/claude-code-system-prompts).
"""

import anthropic
import json
from typing import Optional


# Modeled after Claude Code's internal "Agent Prompt: CLAUDE.md creation" (384 tks)
# Source: github.com/Piebald-AI/claude-code-system-prompts
# Key principles extracted from that prompt + official Claude Code /init skill:
#   - Explore first, write second
#   - Only document what would cause mistakes if missing
#   - Prefer @ includes over inlining large docs
#   - Commands must be exact and runnable
#   - Architecture section only for non-obvious decisions
SYSTEM_PROMPT = """Your task is to analyze a codebase and produce a CLAUDE.md file.

CLAUDE.md is read by Claude Code at the start of every session as persistent project memory. It replaces the need to repeat project context in every prompt.

## Your process

1. **Explore** the provided codebase signals thoroughly before writing anything.
2. **Identify** what would cause mistakes if Claude didn't know it — focus on things that are non-obvious or project-specific.
3. **Write** a concise, accurate CLAUDE.md.

## What to include

Include a section only when you have clear evidence from the codebase signals:

- **Project overview** — one sentence: what it does and the primary tech stack
- **Build / test / lint / run commands** — exact CLI invocations, not tool names alone
  - Bad: "use pytest"  Good: `pytest tests/ -v --tb=short`
- **Architecture** — only directories or patterns that are non-obvious or that violate typical conventions
  - Skip: standard `src/`, `tests/`, `docs/` explanations
  - Include: monorepo package ownership, unusual module boundaries, generated-file directories to never edit
- **Environment setup** — required env vars, external services, non-obvious install steps
- **Critical gotchas** — things that would cause bugs or broken builds if ignored
  - Examples: "never edit files in `generated/`", "always run migrations before tests", "use `bun` not `npm`"
- **Development workflow** — only if there's a non-standard flow (e.g. worktree strategy, PR conventions)

## What to exclude

- Generic advice ("write clean code", "add comments", "handle errors")
- Things Claude already knows: standard library APIs, common framework patterns
- Linting/formatting rules — those belong in config files and tool hooks, not CLAUDE.md
- Placeholder sections with no real content
- Anything that doesn't affect how code should be written or tasks executed

## Format rules

- Valid markdown, human-readable
- Use `@./path/to/file` includes for large external docs instead of inlining them
- Maximum ~40 substantive instructions — beyond ~150 total instructions, LLM instruction-following degrades
- Start with `# ProjectName`
- Output ONLY the CLAUDE.md content, no preamble or explanation"""


def build_analysis_prompt(signals: dict) -> str:
    """Build the user-turn prompt from collected repo signals."""
    meta = signals["meta"]
    contents = signals["file_contents"]

    sections = [
        f"# Codebase: {meta['owner']}/{meta['repo']}",
        f"**Description:** {meta['description'] or 'N/A'}",
        f"**Primary language:** {meta['language']}",
        f"**Topics:** {', '.join(meta['topics']) or 'none'}",
        f"\n## Top-level directory structure\n`{', '.join(signals['top_dirs'][:30])}`",
        f"\n## Config / build files present\n`{', '.join(signals['found_config_files'])}`",
        f"\n## Test setup\n```json\n{json.dumps(signals['test_signals'], indent=2)}\n```",
    ]

    # Append fetched file contents
    for fname, content in contents.items():
        display_name = fname.lstrip("_").replace("_", " ")
        sections.append(f"\n## {display_name}\n```\n{content}\n```")

    sections.append("""
---
Based on the codebase signals above, produce the CLAUDE.md file now.
Output only the file content.""")

    return "\n".join(sections)


def generate_claude_md(
    signals: dict,
    api_key: Optional[str] = None,
    model: str = "claude-sonnet-4-6",
) -> str:
    """Call Claude API to generate CLAUDE.md from signals."""
    client = anthropic.Anthropic(api_key=api_key)  # uses ANTHROPIC_API_KEY if None

    prompt = build_analysis_prompt(signals)

    print("  Generating CLAUDE.md with Claude API...")
    message = client.messages.create(
        model=model,
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )

    return message.content[0].text
