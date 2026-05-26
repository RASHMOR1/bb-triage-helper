#!/usr/bin/env python3
"""Install Claude Code commands and subagent for bb-triage-helper."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PLACEHOLDER = "{{BB_TRIAGE_HELPER_DIR}}"


def render_template(source: Path, skill_dir: Path) -> str:
    return source.read_text(encoding="utf-8").replace(PLACEHOLDER, str(skill_dir))


def install_file(source: Path, target: Path, skill_dir: Path, force: bool) -> str:
    if target.exists() and not force:
        return f"skipped existing {target} (use --force to overwrite)"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_template(source, skill_dir), encoding="utf-8")
    return f"installed {target}"


def install(scope_root: Path, skill_dir: Path, force: bool) -> list[str]:
    template_root = skill_dir / "claude"
    if not template_root.is_dir():
        raise SystemExit(f"Claude templates not found: {template_root}")

    operations: list[str] = []
    for source in sorted((template_root / "commands").glob("*.md")):
        target = scope_root / "commands" / source.name
        operations.append(install_file(source, target, skill_dir, force))

    for source in sorted((template_root / "agents").glob("*.md")):
        target = scope_root / "agents" / source.name
        operations.append(install_file(source, target, skill_dir, force))

    return operations


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install bb-triage-helper support for Claude Code.")
    parser.add_argument(
        "--scope",
        choices=("project", "user"),
        default="project",
        help="Install into project .claude/ or user ~/.claude/. Defaults to project.",
    )
    parser.add_argument(
        "--project-dir",
        default=".",
        help="Project/audit folder for --scope project. Defaults to current directory.",
    )
    parser.add_argument(
        "--skill-dir",
        default=str(Path(__file__).resolve().parents[1]),
        help="Path to this bb-triage-helper directory.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing Claude Code files.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    skill_dir = Path(args.skill_dir).expanduser().resolve()
    if not (skill_dir / "SKILL.md").is_file():
        raise SystemExit(f"Invalid bb-triage-helper directory: {skill_dir}")

    if args.scope == "project":
        scope_root = Path(args.project_dir).expanduser().resolve() / ".claude"
    else:
        scope_root = Path.home() / ".claude"

    print("Installing Claude Code support for bb-triage-helper")
    print(f"Skill directory: {skill_dir}")
    print(f"Target scope: {scope_root}")

    for operation in install(scope_root, skill_dir, args.force):
        print(f"- {operation}")

    print()
    print("Available in Claude Code after install:")
    print("- /triage-setup")
    print("- /triage <finding-id>")
    print("- bb-triage-helper subagent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
