---
description: Triage one bug-bounty finding by ID
allowed-tools: Bash(python3:*), Bash(find:*), Bash(rg:*), Bash(npx hardhat test:*), Bash(forge test:*), Read, Glob, Grep, WebSearch, WebFetch
---

Triage one audit/security finding using BB Triage Helper.

Finding ID and optional extra instructions:

`$ARGUMENTS`

BB Triage Helper directory:

`{{BB_TRIAGE_HELPER_DIR}}`

Instructions:

1. Read `{{BB_TRIAGE_HELPER_DIR}}/SKILL.md`.
2. Read `{{BB_TRIAGE_HELPER_DIR}}/references/triage-method.md`.
3. Locate `bb-triage-helper-output/triage-context.json`. If setup has not been run, switch to setup behavior from `{{BB_TRIAGE_HELPER_DIR}}/claude/commands/triage-setup.md`.
4. Run:

```bash
python3 {{BB_TRIAGE_HELPER_DIR}}/scripts/lookup_finding.py <finding-id> --context <triage-context.json>
```

5. Use the lookup packet only as a starting point. Directly inspect the relevant finding text, docs, prior audit/known-issue notes, NatSpec/comments, deployment context, and implementation.
6. Verify current on-chain state from `deployment-context.md`, official docs/program pages, block explorers, read-only calls, dashboards, and historical transactions when available.
7. Give the final triage response in exactly this order:

## Duplicate Status

State `Duplicate`, `Near-duplicate`, `Related`, or `No duplicate detected`. Name matching finding IDs and explain the root-cause relationship. If setup missed a duplicate but direct review finds one, say so.

## Finding Explanation

Explain the issue in simple terms for a smart reader who may not know this protocol yet. Define the moving parts, explain what normally should happen, what goes wrong, and why it matters.

## Docs/Spec/Known-Issue Check

Check external docs, repo docs, prior audit reports, bug bounty scope, known-issue files, GitHub issues/PRs, uncovered-attack-vector docs, NatSpec, and comments for the same issue, similar issues, intended behavior, related invariants, and scope caveats. Say clearly whether docs are silent, ambiguous, partially mention it, identify a broader related issue, or mark it out of scope.

## Current On-chain State Assessment

Check current deployed state and answer:

- Which chain(s) and contract address(es) are relevant, and how were they verified?
- What amount is currently at risk? If the attack targets future amounts, what is a reasonable estimate of value at risk?
- Is the attack recurring or one-shot?
- Does the attack depend on admins setting misconfigurations? If yes, flag likely out-of-scope risk unless the configuration exists today and is in scope.
- If the attack requires a configuration, is the contract currently configured so the attack is possible on-chain, or is it dormant?
- Have the preconditions for the attack occurred previously?
- Is there a chance the described behavior is intentional?
- Is there a chance the bug is known from the GitHub repo, program page, docs, issues, audits, or public discussions?
- If current-state answers do not support a real, exploitable bug, recommend skipping submission or classify as invalid/needs more information.

## Numerical Example

Start with a short context paragraph that explains what the example is demonstrating, what the protocol/module is supposed to measure, and what goes wrong. Then use concrete numbers and a human-readable walkthrough with simple roles such as `user`, `depositor`, `withdrawer`, `attacker`, or `keeper`. Put important arithmetic on its own lines and explain what each number means.

## Protocol Analysis And Verdict

Trace the implementation and decision together in one section. Cover entrypoints, state changes, invariants, guards, rounding, permissions, edge cases, tests, counterpoints, current deployment constraints, and submission caveats.

End with:

```text
Preliminary decision: Valid/Invalid/Partially valid/Needs more information
Confidence: Low/Medium/High
Why: <main reason from code/spec/current state>
Assumptions: <deployment/user/role/oracle/token assumptions>
Notes: <duplicates, severity adjustment, caveats, tests, current-state blockers, or submission recommendation>
```

Be unbiased. Try to prove and disprove the finding before deciding.
