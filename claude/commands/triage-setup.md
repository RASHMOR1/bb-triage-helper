---
description: Set up bug-bounty finding triage for this repo
allowed-tools: Bash(python3:*), Bash(find:*), Bash(rg:*), Read, Glob, Grep, WebSearch, WebFetch
---

Set up the BB Triage Helper workflow for bug-bounty findings.

BB Triage Helper directory:

`{{BB_TRIAGE_HELPER_DIR}}`

User arguments:

`$ARGUMENTS`

Instructions:

1. Read `{{BB_TRIAGE_HELPER_DIR}}/SKILL.md`.
2. Identify the findings markdown file. If the user did not provide it and it is not obvious, ask for it.
3. Identify the repo root. Common layout is `<audit-folder>/repo` plus `<audit-folder>/findings.md`. If ambiguous, ask for the repo path.
4. Identify the protocol/project name from the repo, findings, README, package metadata, or user prompt.
5. Search repo docs, deployment/config files, NatSpec, comments, and code for chain/address evidence.
6. If web access is available, search official internet sources for the bug bounty scope, previous audit reports, audit contest findings, deployed chains, contract addresses, official deployment docs, verified block explorer pages, and official GitHub deployment configs. If web access is unavailable, ask the user for official docs/program/deployment URLs plus prior audit/audit contest links.
7. Run:

```bash
python3 {{BB_TRIAGE_HELPER_DIR}}/scripts/setup_triage.py --repo <repo> --findings <findings.md> --protocol-name "<protocol-name>"
```

Add one `--external-doc <path-or-url>` for each external official doc, previous audit report, audit contest finding source, deployment URL, program page, or block explorer/source URL.

8. After setup, open and briefly summarize:

- `bb-triage-helper-output/deployment-context.md`
- `bb-triage-helper-output/related-findings.md`
- `bb-triage-helper-output/docs-index.md`

9. Tell the user the exact `triage-context.json` path and that they can now run `/triage M-24`.
