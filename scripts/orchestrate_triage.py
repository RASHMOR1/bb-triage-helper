#!/usr/bin/env python3
"""Run isolated AI triage jobs for many findings.

The orchestrator creates one prompt and one CLI process per finding. This keeps
long multi-finding triage from blending context across unrelated reports.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import json
import os
import re
import shlex
import subprocess
import sys
import threading
from pathlib import Path


DEFAULT_MODEL = "gpt-5.5"
DEFAULT_REASONING_EFFORT = "xhigh"
MANIFEST_NAME = "manifest.jsonl"


def utc_now() -> str:
    return dt.datetime.now(dt.UTC).isoformat(timespec="seconds")


def canonical_id(value: str) -> str:
    match = re.match(r"^([A-Za-z]+)-?0*(\d+)$", value.strip())
    if not match:
        return value.strip().upper()
    return f"{match.group(1).upper()}-{int(match.group(2))}"


def safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())


def load_context(path: Path) -> dict:
    if not path.is_file():
        raise SystemExit(f"Context file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def find_helper_dir(script_path: Path, override: str | None) -> Path:
    if override:
        helper_dir = Path(override).expanduser().resolve()
    else:
        helper_dir = script_path.resolve().parents[1]
    if not (helper_dir / "SKILL.md").is_file():
        raise SystemExit(f"Helper directory does not contain SKILL.md: {helper_dir}")
    if not (helper_dir / "scripts" / "lookup_finding.py").is_file():
        raise SystemExit(f"Helper directory does not contain scripts/lookup_finding.py: {helper_dir}")
    return helper_dir


def resolve_findings(context: dict, args: argparse.Namespace) -> list[dict]:
    findings = context.get("findings", [])
    if not findings:
        raise SystemExit("No findings in triage context.")

    by_id = {}
    for finding in findings:
        for key in (finding.get("id"), finding.get("canonical_id"), finding.get("unique_id")):
            if key:
                by_id[canonical_id(key)] = finding

    selected = findings
    if args.ids:
        selected = []
        missing = []
        for finding_id in args.ids:
            finding = by_id.get(canonical_id(finding_id))
            if finding:
                selected.append(finding)
            else:
                missing.append(finding_id)
        if missing:
            raise SystemExit(f"Finding IDs not found: {', '.join(missing)}")

    if args.from_id:
        wanted = canonical_id(args.from_id)
        start = next((idx for idx, finding in enumerate(selected) if canonical_id(finding.get("id", "")) == wanted), None)
        if start is None:
            raise SystemExit(f"--from-id not found in selected findings: {args.from_id}")
        selected = selected[start:]

    if args.to_id:
        wanted = canonical_id(args.to_id)
        end = next((idx for idx, finding in enumerate(selected) if canonical_id(finding.get("id", "")) == wanted), None)
        if end is None:
            raise SystemExit(f"--to-id not found in selected findings: {args.to_id}")
        selected = selected[: end + 1]

    if args.limit is not None:
        selected = selected[: args.limit]
    return selected


def run_lookup(helper_dir: Path, context_path: Path, finding_id: str, max_content_chars: int) -> str:
    command = [
        sys.executable,
        str(helper_dir / "scripts" / "lookup_finding.py"),
        finding_id,
        "--context",
        str(context_path),
        "--max-content-chars",
        str(max_content_chars),
    ]
    result = subprocess.run(command, check=False, text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"lookup_finding.py failed for {finding_id}:\n{result.stderr or result.stdout}")
    return result.stdout


def build_prompt(
    *,
    context: dict,
    context_path: Path,
    helper_dir: Path,
    finding: dict,
    packet: str,
    output_file: Path,
) -> str:
    finding_id = finding.get("id", finding.get("unique_id", "unknown"))
    repo_root = Path(context["repo_root"]).resolve()
    output_dir = Path(context.get("output_dir", context_path.parent)).resolve()
    triage_method = helper_dir / "references" / "triage-method.md"

    return f"""You are an isolated bb-triage-helper worker. Triage exactly one bug-bounty finding and produce a final markdown triage record.

Finding ID: {finding_id}
Finding title: {finding.get("title", "")}
Current UTC date: {utc_now()}

Read these instruction files before deciding:
- {helper_dir / "SKILL.md"}
- {triage_method}

Workspace and context:
- Repo root: {repo_root}
- Triage context: {context_path}
- Setup output directory: {output_dir}
- Related findings: {output_dir / "related-findings.md"}
- Docs index: {output_dir / "docs-index.md"}
- Deployment context: {output_dir / "deployment-context.md"}
- Target output file for this run: {output_file}

Hard constraints:
- Analyze only {finding_id} as the primary finding. Discuss other findings only for duplicate or related status.
- Do not edit the repo, findings file, or setup artifacts. Return the final triage as your final answer only.
- Directly inspect relevant code, docs, comments, prior audits, known-issue notes, GitHub issues/PRs, and deployment context.
- Verify current/live facts when relevant. If live verification is unavailable, state the gap and its effect on the verdict.
- Treat previous audits and audit contests as mandatory known-issue sources.
- Treat automated duplicate clusters as hints only. Prefer the human grouping notes in related-findings.md when they exist.
- Be neutral: try to prove the finding valid and try to disprove it before deciding.

Required final response sections, in this exact order:

## Duplicate Status

State `Duplicate`, `Near-duplicate`, `Related`, or `No duplicate detected`. Name matching finding IDs and explain the root-cause relationship.

## Finding Explanation

Explain the issue in simple terms for a smart reader who may not know the protocol.

## Docs/Spec/Known-Issue Check

Check external docs, repo docs, NatSpec/comments, previous audits, audit contest findings, Immunefi scope, known issues, GitHub issues/PRs, governance/forum posts, and public discussions.

## Current On-chain State Assessment

Answer which chain/contracts are relevant, how verified, amount at risk, one-shot vs recurring, admin/config assumptions, current configurability, historical preconditions, intentional behavior, known-issue chance, and whether current state supports submission.

## Numerical Example

Start with context, then walk through concrete numbers and roles.

## Protocol Analysis And Verdict

Trace entrypoints, state changes, invariants, guards, rounding, permissions, edge cases, tests, counterpoints, caveats, current deployment constraints, and submission notes.

End this final section with:

Preliminary decision: Valid/Invalid/Partially valid/Needs more information
Confidence: Low/Medium/High
Why: <main reason from code/spec/current state>
Assumptions: <deployment/user/role/oracle/token assumptions>
Notes: <duplicates, severity adjustment, caveats, tests, current-state blockers, or submission recommendation>

Lookup packet follows. Use it as a starting point only; verify directly.

---

{packet}
"""


def format_template(template: str, values: dict[str, str]) -> str:
    return template.format(**{key: shlex.quote(value) for key, value in values.items()})


def default_codex_command(args: argparse.Namespace, context: dict, output_file: Path) -> list[str]:
    repo_root = Path(args.codex_cd or context["repo_root"]).resolve()
    context_output_dir = Path(context.get("output_dir", output_file.parent)).resolve()
    command = [
        args.codex_bin,
        "exec",
        "--model",
        args.model,
        "-c",
        f'model_reasoning_effort="{args.reasoning_effort}"',
        "--sandbox",
        args.sandbox,
        "--ask-for-approval",
        args.approval,
        "--skip-git-repo-check",
        "--cd",
        str(repo_root),
        "--add-dir",
        str(context_output_dir),
        "--output-last-message",
        str(output_file),
    ]
    if args.search:
        command.append("--search")
    for extra in args.extra_codex_arg:
        command.append(extra)
    command.append("-")
    return command


def append_manifest(path: Path, lock: threading.Lock, record: dict) -> None:
    with lock:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def write_index(output_dir: Path, records: list[dict]) -> None:
    lines = [
        "# Triage Orchestration Index",
        "",
        f"Generated UTC: {utc_now()}",
        "",
        "| Finding | Status | Result | Log |",
        "| --- | --- | --- | --- |",
    ]
    for record in records:
        result = Path(record["output_file"]).name if record.get("output_file") else ""
        log = Path(record["log_file"]).name if record.get("log_file") else ""
        result_link = f"[{result}](results/{result})" if result else ""
        log_link = f"[{log}](logs/{log})" if log else ""
        lines.append(f"| `{record['finding_id']}` | {record['status']} | {result_link} | {log_link} |")
    (output_dir / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_one(
    *,
    args: argparse.Namespace,
    context: dict,
    context_path: Path,
    helper_dir: Path,
    output_dir: Path,
    manifest_path: Path,
    manifest_lock: threading.Lock,
    finding: dict,
) -> dict:
    finding_id = finding.get("id", finding.get("unique_id", "unknown"))
    stem = safe_filename(finding_id)
    prompt_file = output_dir / "prompts" / f"{stem}.prompt.md"
    output_file = output_dir / "results" / f"{stem}.md"
    log_file = output_dir / "logs" / f"{stem}.log"

    record = {
        "finding_id": finding_id,
        "title": finding.get("title", ""),
        "prompt_file": str(prompt_file),
        "output_file": str(output_file),
        "log_file": str(log_file),
        "started_at": utc_now(),
    }

    if output_file.exists() and not args.force:
        record.update({"status": "skipped", "reason": "output exists", "completed_at": utc_now(), "returncode": 0})
        append_manifest(manifest_path, manifest_lock, record)
        return record

    packet = run_lookup(helper_dir, context_path, finding_id, args.lookup_max_content_chars)
    prompt = build_prompt(
        context=context,
        context_path=context_path,
        helper_dir=helper_dir,
        finding=finding,
        packet=packet,
        output_file=output_file,
    )
    prompt_file.write_text(prompt, encoding="utf-8")

    if args.dry_run:
        record.update({"status": "planned", "completed_at": utc_now(), "returncode": 0})
        append_manifest(manifest_path, manifest_lock, record)
        return record

    if args.runner_command:
        values = {
            "finding_id": finding_id,
            "prompt_file": str(prompt_file),
            "output_file": str(output_file),
            "log_file": str(log_file),
            "context": str(context_path),
            "repo": str(Path(context["repo_root"]).resolve()),
            "helper": str(helper_dir),
            "model": args.model,
            "reasoning_effort": args.reasoning_effort,
        }
        command_display = args.runner_command
        command = format_template(args.runner_command, values)
        result = subprocess.run(
            command,
            shell=True,
            input=prompt,
            text=True,
            capture_output=True,
            timeout=args.timeout_seconds or None,
        )
        log_file.write_text((result.stdout or "") + (result.stderr or ""), encoding="utf-8")
        if not output_file.exists() and result.stdout:
            output_file.write_text(result.stdout, encoding="utf-8")
    else:
        command_list = default_codex_command(args, context, output_file)
        command_display = " ".join(shlex.quote(item) for item in command_list)
        with log_file.open("w", encoding="utf-8") as log_handle:
            result = subprocess.run(
                command_list,
                input=prompt,
                text=True,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                timeout=args.timeout_seconds or None,
            )

    status = "completed" if result.returncode == 0 and output_file.exists() else "failed"
    record.update(
        {
            "status": status,
            "completed_at": utc_now(),
            "returncode": result.returncode,
            "command": command_display,
        }
    )
    append_manifest(manifest_path, manifest_lock, record)
    return record


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Spawn isolated CLI triage jobs for findings.")
    parser.add_argument("--context", default="bb-triage-helper-output/triage-context.json", help="Path to triage-context.json.")
    parser.add_argument("--helper-dir", help="Path to the bb-triage-helper directory. Defaults to this script's parent repo.")
    parser.add_argument("--output-dir", help="Directory for prompts, logs, results, and manifest. Defaults to <context output>/triaged.")
    parser.add_argument("--ids", nargs="*", help="Specific finding IDs to run.")
    parser.add_argument("--from-id", help="Start at this finding ID after any --ids selection.")
    parser.add_argument("--to-id", help="Stop at this finding ID after any --ids/--from-id selection.")
    parser.add_argument("--limit", type=int, help="Maximum number of selected findings to run.")
    parser.add_argument("--jobs", type=int, default=1, help="Number of concurrent CLI workers. Default: 1.")
    parser.add_argument("--force", action="store_true", help="Re-run findings even if result files already exist.")
    parser.add_argument("--dry-run", action="store_true", help="Write prompts and manifest records without invoking the CLI.")
    parser.add_argument("--lookup-max-content-chars", type=int, default=14_000)
    parser.add_argument("--timeout-seconds", type=int, default=0, help="Per-finding subprocess timeout. 0 means no timeout.")

    parser.add_argument("--codex-bin", default=os.environ.get("CODEX_BIN", "codex"))
    parser.add_argument("--model", default=os.environ.get("BB_TRIAGE_MODEL", DEFAULT_MODEL))
    parser.add_argument("--reasoning-effort", default=os.environ.get("BB_TRIAGE_REASONING_EFFORT", DEFAULT_REASONING_EFFORT))
    parser.add_argument("--codex-cd", help="Directory passed to codex exec --cd. Defaults to context repo_root.")
    parser.add_argument("--sandbox", default="danger-full-access", choices=["read-only", "workspace-write", "danger-full-access"])
    parser.add_argument("--approval", default="never", choices=["untrusted", "on-failure", "on-request", "never"])
    parser.add_argument("--search", dest="search", action="store_true", default=True, help="Pass --search to Codex. Default: enabled.")
    parser.add_argument("--no-search", dest="search", action="store_false", help="Do not pass --search to Codex.")
    parser.add_argument("--extra-codex-arg", action="append", default=[], help="Additional raw argument to append to codex exec. Repeat as needed.")
    parser.add_argument(
        "--runner-command",
        help=(
            "Custom shell command. Prompt is sent on stdin. Placeholders: {finding_id}, {prompt_file}, "
            "{output_file}, {log_file}, {context}, {repo}, {helper}, {model}, {reasoning_effort}."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.jobs < 1:
        raise SystemExit("--jobs must be at least 1")

    script_path = Path(__file__)
    helper_dir = find_helper_dir(script_path, args.helper_dir)
    context_path = Path(args.context).expanduser().resolve()
    context = load_context(context_path)
    findings = resolve_findings(context, args)

    base_output = Path(args.output_dir).expanduser().resolve() if args.output_dir else Path(context.get("output_dir", context_path.parent)).resolve() / "triaged"
    for child in ("prompts", "results", "logs"):
        (base_output / child).mkdir(parents=True, exist_ok=True)
    manifest_path = base_output / MANIFEST_NAME
    manifest_lock = threading.Lock()

    records: list[dict] = []
    if args.jobs == 1:
        for finding in findings:
            records.append(
                run_one(
                    args=args,
                    context=context,
                    context_path=context_path,
                    helper_dir=helper_dir,
                    output_dir=base_output,
                    manifest_path=manifest_path,
                    manifest_lock=manifest_lock,
                    finding=finding,
                )
            )
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
            future_to_id = {
                executor.submit(
                    run_one,
                    args=args,
                    context=context,
                    context_path=context_path,
                    helper_dir=helper_dir,
                    output_dir=base_output,
                    manifest_path=manifest_path,
                    manifest_lock=manifest_lock,
                    finding=finding,
                ): finding.get("id", finding.get("unique_id", "unknown"))
                for finding in findings
            }
            for future in concurrent.futures.as_completed(future_to_id):
                try:
                    records.append(future.result())
                except Exception as exc:
                    finding_id = future_to_id[future]
                    record = {
                        "finding_id": finding_id,
                        "status": "failed",
                        "reason": str(exc),
                        "started_at": utc_now(),
                        "completed_at": utc_now(),
                    }
                    append_manifest(manifest_path, manifest_lock, record)
                    records.append(record)

    records.sort(key=lambda item: canonical_id(item.get("finding_id", "")))
    write_index(base_output, records)

    counts: dict[str, int] = {}
    for record in records:
        counts[record["status"]] = counts.get(record["status"], 0) + 1
    print(json.dumps({"output_dir": str(base_output), "selected": len(findings), "counts": counts}, indent=2))
    return 1 if counts.get("failed") else 0


if __name__ == "__main__":
    raise SystemExit(main())
