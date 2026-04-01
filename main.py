#!/usr/bin/env python3
"""
claudemd-gen — Generate CLAUDE.md for any GitHub repo

Usage:
    python main.py <github_url_or_owner/repo> [options]

Examples:
    python main.py https://github.com/fastapi/fastapi
    python main.py tiangolo/fastapi
    python main.py MeghanBao/freelancer-visa-agent-de --output ./CLAUDE.md
    python main.py django/django --github-token ghp_xxx
"""

import argparse
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from analyzer import collect_repo_signals, parse_repo_url
from generator import generate_claude_md


def main():
    parser = argparse.ArgumentParser(
        description="Generate CLAUDE.md for any GitHub repo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("repo", help="GitHub URL or owner/repo shorthand")
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output file path (default: print to stdout)"
    )
    parser.add_argument(
        "--github-token", "-t",
        default=os.environ.get("GITHUB_TOKEN"),
        help="GitHub token for private repos / higher rate limits (or set GITHUB_TOKEN env)"
    )
    parser.add_argument(
        "--anthropic-key", "-k",
        default=os.environ.get("ANTHROPIC_API_KEY"),
        help="Anthropic API key (or set ANTHROPIC_API_KEY env)"
    )
    parser.add_argument(
        "--model", "-m",
        default="claude-sonnet-4-6",
        help="Claude model to use (default: claude-sonnet-4-6)"
    )
    parser.add_argument(
        "--save-signals",
        default=None,
        metavar="FILE",
        help="Save raw repo signals to JSON file (useful for debugging)"
    )

    args = parser.parse_args()

    # Parse repo
    try:
        owner, repo = parse_repo_url(args.repo)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"[claudemd-gen] Analyzing {owner}/{repo}")

    # Step 1: Collect signals
    try:
        signals = collect_repo_signals(owner, repo, token=args.github_token)
    except Exception as e:
        print(f"Error fetching repo: {e}", file=sys.stderr)
        sys.exit(1)

    # Optionally save signals
    if args.save_signals:
        import json
        with open(args.save_signals, "w") as f:
            # Exclude full file list for readability
            debug = {k: v for k, v in signals.items() if k != "all_files"}
            json.dump(debug, f, indent=2, ensure_ascii=False)
        print(f"  Signals saved to {args.save_signals}")

    # Step 2: Generate CLAUDE.md
    if not args.anthropic_key:
        print(
            "Error: ANTHROPIC_API_KEY not set. Use --anthropic-key or set env var.",
            file=sys.stderr
        )
        sys.exit(1)

    try:
        claude_md = generate_claude_md(
            signals,
            api_key=args.anthropic_key,
            model=args.model
        )
    except Exception as e:
        print(f"Error generating CLAUDE.md: {e}", file=sys.stderr)
        sys.exit(1)

    # Step 3: Output
    if args.output:
        Path(args.output).write_text(claude_md, encoding="utf-8")
        print(f"\n[claudemd-gen] Written to {args.output}")
    else:
        print(f"\n{'='*60}")
        print(claude_md)
        print(f"{'='*60}")
        print(f"\n[claudemd-gen] Done. Use --output CLAUDE.md to save.")


if __name__ == "__main__":
    main()
