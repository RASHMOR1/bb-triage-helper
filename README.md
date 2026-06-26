# BB Triage Helper

BB Triage Helper is a reusable AI-agent workflow for bug-bounty finding triage.

It is meant for audit folders shaped roughly like this:

```text
folder1/
├── repo/
└── findings.md
```

The helper sets up a local triage workspace, searches repo and official internet sources for deployment context, groups related findings, indexes docs and code comments, and then helps analyze individual findings against current on-chain state.

## What It Does

During setup, it:

- asks for the findings markdown file
- asks for the repo path
- identifies the protocol name when possible
- searches repo docs, NatSpec, comments, and deployment/config files
- uses official internet sources supplied as external docs, such as program pages, deployment docs, block explorer pages, and official GitHub configs
- extracts candidate chains and contract/program addresses
- groups duplicate-like or related findings
- writes setup artifacts into `bb-triage-helper-output/`

For single-finding triage, it helps produce:

- duplicate status first
- simple finding explanation
- docs/spec/prior-finding/known-issue check
- current on-chain state assessment
- human-understandable numerical example
- protocol analysis and verdict in one section
- caveats, assumptions, confidence, severity, and submission notes

## Setup Output

The setup script writes:

```text
bb-triage-helper-output/
├── triage-context.json
├── related-findings.md
├── docs-index.md
└── deployment-context.md
```

`deployment-context.md` shows candidate chains, addresses, URLs, source excerpts, and verification reminders.

`related-findings.md` is the main human-readable grouping file.

`docs-index.md` shows indexed docs and likely docs hits per finding.

`triage-context.json` is used by the lookup script and AI agent workflow.

## Manual Usage

Run setup:

```bash
python3 /your-folder/bb-triage-helper/scripts/setup_triage.py \
  --repo ./repo \
  --findings ./findings.md \
  --protocol-name "Protocol Name"
```

With external docs:

```bash
python3 /your-folder/bb-triage-helper/scripts/setup_triage.py \
  --repo ./repo \
  --findings ./findings.md \
  --protocol-name "Protocol Name" \
  --external-doc ./docs \
  --external-doc https://example.com/protocol-docs
```

Look up one finding:

```bash
python3 /your-folder/bb-triage-helper/scripts/lookup_finding.py M-24 \
  --context ./bb-triage-helper-output/triage-context.json
```

The lookup output is not the final triage answer. It is a focused packet the AI agent uses before reading the actual code, docs, deployment context, and finding text directly.

## Codex Usage

Copy or symlink this folder into your Codex skills directory:

```bash
mkdir -p ~/.codex/skills
cp -r /your-folder/bb-triage-helper ~/.codex/skills/bb-triage-helper
```

Then invoke it from Codex:

```text
Use $bb-triage-helper to set up bug bounty triage.
```

After setup:

```text
/triage M-24
```

## Claude Code Usage

Install Claude Code support into one audit folder:

```bash
python3 /your-folder/bb-triage-helper/scripts/install_claude_support.py \
  --scope project \
  --project-dir /path/to/folder1
```

Or install for the current user:

```bash
python3 /your-folder/bb-triage-helper/scripts/install_claude_support.py --scope user
```

Claude Code commands:

```text
/triage-setup
/triage M-24
```

## Expected Triage Answer Format

Single-finding answers should use this order:

1. Duplicate Status
2. Finding Explanation
3. Docs/Spec/Known-Issue Check
4. Current On-chain State Assessment
5. Numerical Example
6. Protocol Analysis And Verdict

The current on-chain state section should decide whether the finding is exploitable against the live scoped deployment. If current state does not support a real bug, the helper should recommend skipping submission or classify it as invalid/needs more information.
