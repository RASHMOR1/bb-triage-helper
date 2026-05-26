---
name: bb-triage-helper
description: Bug-bounty audit finding triage workflow for repositories with a findings markdown file. Use when Codex needs to set up triage from repo plus findings.md, search official docs and the internet for deployed chains and contract addresses, group duplicate or related findings, or answer commands like /triage M-24, "triage finding M-24", or "assess H-01" with duplicate status, docs/known-issue checks, current on-chain state assessment, numerical example, and unbiased verdict.
---

# BB Triage Helper

## Overview

Use this skill to set up and run a bug-bounty-oriented triage workflow for a code repository plus a markdown findings file.

- Setup mode: identify inputs, search repo docs/NatSpec/comments plus official internet sources, discover deployed chains and contract addresses, index documentation, group duplicate or related findings, and write setup artifacts.
- Single-finding mode: handle `/triage <finding-id>` by stating duplicate status first, explaining the finding, checking docs/specs/known issues, assessing current on-chain exploitability in detail, giving a numerical example, and combining implementation analysis with a preliminary verdict.

For detailed triage standards and decision criteria, read `references/triage-method.md` when starting single-finding analysis or when the validity call is subtle.

## Setup Mode

Run setup when the user invokes the skill for a repo that does not already have `bb-triage-helper-output/triage-context.json`, or when they explicitly ask to re-run setup.

1. Identify the markdown findings file. Common layouts are `folder/findings.md` and `folder/repo/`.
2. Identify the repo root. If there is one obvious repository directory next to the findings file, use it; otherwise ask for the repo path.
3. Identify the protocol/project name from the repo, findings file, package metadata, README, or user prompt.
4. Search repo docs, deployment files, NatSpec/comments, and code for deployment evidence.
5. Search the internet for official or high-confidence deployment sources: bug bounty/program page, official docs, official GitHub/deployment configs, verified block explorer pages, governance/forum deployment posts, and public app/config pages. Prefer official sources; use third-party pages only as leads to official addresses.
6. Pass discovered official docs and deployment URLs to the setup script as `--external-doc` inputs. If the runtime has no browser/search tool, ask the user for official docs, program scope, and deployment URLs before setup.
7. Run the setup script from this skill directory:

```bash
python3 /path/to/bb-triage-helper/scripts/setup_triage.py \
  --repo /path/to/repo \
  --findings /path/to/findings.md \
  --protocol-name "Protocol Name" \
  --external-doc /optional/doc/or/dir/or/url
```

Omit `--protocol-name` only if unknown. Omit `--external-doc` only if no docs or URLs are available. Repeat `--external-doc` for multiple docs. Add `--output /path/to/output` only if the user wants a custom output location; otherwise the script writes next to the findings file under `bb-triage-helper-output/`.

The setup script writes:

- `triage-context.json`: parsed findings, docs index, deployment discovery, and machine-readable grouping hints.
- `related-findings.md`: duplicate-like and related finding groups.
- `docs-index.md`: indexed docs/NatSpec/comment sources and top doc hits by finding.
- `deployment-context.md`: candidate chains, contract/program addresses, deployment URLs, source excerpts, and manual verification reminders.

After setup, open `deployment-context.md`, `related-findings.md`, and `docs-index.md`. The script uses heuristics; refine conclusions with code-aware and source-aware judgment. If official internet sources identify chains or addresses that the script missed, rerun setup with those URLs or add a note in the output directory.

## Single-Finding Mode

Use this mode when the user says `/triage M-24`, `triage M-24`, or gives any similar request with a finding ID.

1. Locate `triage-context.json`. Default to `<findings-dir>/bb-triage-helper-output/triage-context.json`. If setup has not been run, run Setup Mode first.
2. Run the lookup script:

```bash
python3 /path/to/bb-triage-helper/scripts/lookup_finding.py M-24 \
  --context /path/to/bb-triage-helper-output/triage-context.json
```

3. Use the lookup packet as a starting point, not as the final answer. Open relevant finding text, docs, NatSpec/comments, prior audit notes, known-issue files, `deployment-context.md`, and code references directly when needed.
4. For current on-chain checks, use official deployment sources, block explorers, read-only RPC calls, public dashboards, and program scope pages when available. Current state is time-sensitive; verify live facts rather than relying only on setup-time notes.
5. If the finding belongs to a duplicate or related group, make that the first section of the response and consider whether the same root cause affects the decision.
6. Analyze neutrally. Try to prove the finding valid and try to disprove it before deciding.

## Required Single-Finding Answer

Structure each triage response with these sections, in this order:

- Duplicate status: first line/section. State `Duplicate`, `Near-duplicate`, `Related`, or `No duplicate detected`. Name the matching finding IDs and the root-cause relationship. If setup did not auto-cluster something but code/finding review shows a match, say that explicitly.
- Finding explanation: explain the issue in simple terms for a smart reader who may not know this protocol yet. Define the moving parts, explain what normally should happen, what goes wrong, and why it matters.
- Docs/spec/known-issue check: state whether external docs, repo docs, NatSpec, comments, prior audit reports, bug bounty scope, known-issue notes, uncovered-attack-vector docs, GitHub issues/PRs, or public program pages mention this finding, a similar finding, the intended behavior, or a related invariant. Say clearly when docs are silent, ambiguous, partially mention the issue, identify a broader related issue, or mark the behavior out of scope.
- Current on-chain state assessment: separate detailed section. Check the current deployed state and answer:
  - Which chain(s) and contract address(es) are relevant, and how were they verified?
  - What amount is currently at risk? If the attack targets future amounts, what is a reasonable value-at-risk estimate and basis?
  - Is the attack recurring or one-shot?
  - Does the attack depend on admins setting misconfigurations? If yes, note that this is likely out of scope on many platforms unless the misconfiguration exists today and is in scope.
  - If the attack requires a configuration, is the contract currently configured so the attack is possible on-chain, or is it a dormant bug?
  - Have the attack preconditions occurred previously on-chain?
  - Is there a reasonable chance the described behavior is intentional?
  - Is there a reasonable chance the bug is already known from the GitHub repo, program page, docs, issues, audits, or public discussions?
  - If the answers do not support a real, exploitable bug against current state, recommend skipping submission or mark the finding invalid/needs more information.
- Numerical example: start with a short context paragraph that explains what the example is demonstrating, what the protocol/module is supposed to measure, and what goes wrong. Then use a human-readable walkthrough with concrete roles such as `user`, `depositor`, `withdrawer`, `attacker`, or `keeper`. Put important arithmetic on its own lines.
- Protocol analysis and verdict: combine the code trace and decision in one final section. Trace entrypoints, state changes, invariants, guards, rounding, permissions, edge cases, tests, and counterpoints. Include caveats before the final decision, especially current deployment constraints, bounded value at risk, dormant configurations, admin assumptions, mitigations already present, non-applicable chains/contracts, severity limits, or ways the report overstates the issue. End with `Preliminary decision: Valid/Invalid/Partially valid/Needs more information`, confidence, assumptions, and severity/duplicate/submission notes.

Do not create a standalone `Preliminary Decision` section. The verdict belongs at the end of `Protocol analysis and verdict`.

## Decision Discipline

Do not anchor on the report's conclusion. A finding is not valid merely because it is plausible, and it is not invalid merely because docs are silent.

Use this rough evidence hierarchy:

1. Current deployed state: verified contract addresses, read-only calls, block explorer state, live balances/TVL, program scope, and relevant historical transactions.
2. Executable behavior: tests, reproductions, direct code traces.
3. Official external docs, specs, program pages, and deployment pages.
4. Repo docs and design docs.
5. NatSpec and code comments.
6. Naming conventions and inferred intent.

Prefer precise conditional language when the evidence is mixed. For example: "Valid if deposits can be made through X on the live Arbitrum deployment; invalid for the current Base deployment because Z is paused and the vulnerable asset is not enabled."

## Output Artifacts

During setup, write grouping and deployment artifacts in the output directory instead of inside the skill directory. During single-finding triage, do not edit the original findings file unless the user explicitly asks. If you create notes, place them in the setup output directory.

## Claude Code Support

Claude Code does not discover Codex `SKILL.md` files directly. Use the bundled installer to copy equivalent Claude Code slash commands and a subagent into Claude's supported `.claude/` layout.

For one audit/project folder:

```bash
python3 /path/to/bb-triage-helper/scripts/install_claude_support.py \
  --scope project \
  --project-dir /path/to/audit-folder
```

For all Claude Code sessions for the current user:

```bash
python3 /path/to/bb-triage-helper/scripts/install_claude_support.py --scope user
```

Use `--force` to overwrite existing command or agent files.

Installed Claude Code features:

- `.claude/commands/triage-setup.md` provides `/triage-setup`.
- `.claude/commands/triage.md` provides `/triage <finding-id>`.
- `.claude/agents/bb-triage-helper.md` provides a specialized `bb-triage-helper` subagent.

The installer replaces template paths with the absolute path to this helper folder so Claude Code can run the same setup and lookup scripts.
