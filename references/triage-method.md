# Triage Method

Use this reference when making a single-finding validity call.

## Validity Categories

- `Valid`: the described behavior is reachable under realistic assumptions and produces the claimed impact or a materially similar impact.
- `Invalid`: the described behavior is not reachable, is prevented by code/spec constraints, depends on impossible assumptions, or has no meaningful impact.
- `Partially valid`: a real issue exists, but severity, affected flow, preconditions, or impact differ from the finding.
- `Needs more information`: the decision depends on missing deployment parameters, privileged role assumptions, oracle behavior, governance choices, undocumented integrations, or unavailable external docs.

## Analysis Checklist

1. Identify the exact claim: attacker/user action, affected asset/state, expected behavior, actual behavior, and impact.
2. Map the path: external entrypoint, internal calls, modifiers/guards, state reads/writes, emitted accounting, and downstream effects.
3. Verify deployment context: live chain(s), contract address(es), bug bounty scope, current configuration, balances/TVL, paused state, role holders, enabled markets/assets, caps, oracle settings, and relevant historical transactions.
4. Check preconditions: roles, initialization, paused states, caps, whitelists, oracle freshness, timing windows, decimals, rounding, token behavior, and whether those preconditions exist today.
5. Compare specification sources and prior-report sources: external docs first if provided, then previous audit reports, audit contest findings, bug bounty/program pages, repo docs, GitHub issues/PRs, prior audit notes, known-issue files, uncovered-attack-vector docs, NatSpec, comments, and inferred intent.
6. Build a numerical example: first explain the scenario and what the protocol is supposed to measure, then choose small numbers, use simple roles or names only where helpful, show before/after state, and make the loss/gain/invariant break visible in a natural walkthrough with arithmetic on separate lines.
7. Try to invalidate: search for current-state blockers, guards, clamps, reverts, invariant restoration, impossible caller paths, dormant configs, admin-only misconfiguration assumptions, or missing permissions.
8. Try to validate: search for alternate entrypoints, live enabled configurations, stale state, rounding accumulation, integration flows, hooks, callbacks, cross-contract effects, and previous on-chain precondition occurrences.
9. Decide preliminarily with confidence, assumptions, and whether the issue is worth submitting.

## Plain-Language Explanations

Explain the finding for a smart reader who may not know the protocol yet.

Prefer:

- A short setup of the relevant mechanism.
- Plain words for protocol jargon, followed by the exact term in parentheses if needed.
- "Normally..." and "The problem is..." phrasing when it helps.
- A sentence that says why users, LPs, keepers, or the protocol care.

Avoid:

- One-paragraph compressed auditor shorthand.
- Starting with raw function names before explaining the behavior.
- Long lists of variables without saying what they represent.

## Numerical Examples

Keep the example tied to the implementation and write it like a human-readable walkthrough. Before listing numbers, add a short context paragraph that answers:

- What is this module/check trying to measure?
- What should be included or excluded?
- What mistake does the finding claim?
- Why does that mistake matter to a user, LP, keeper, trader, or the protocol?

Use simple roles such as `user`, `depositor`, `withdrawer`, `attacker`, `keeper`, `pool`, or `protocol`. Use names like Alice/Bob only when multiple people would otherwise be confusing. Do not repeat names in every sentence. Put important arithmetic on its own lines so the reader can scan the numbers:

```text
Context:
The fee module is supposed to charge higher fees when a trade uses too much of the pool's real active risk capacity. Queued withdrawal reserves are already owed to withdrawing LPs, so they should not make the pool look safer than it is.

Initial state:
- Pool has <value>.
- User/depositor/withdrawer has <value>.
- One share/token/unit means <plain-language meaning>.

What the protocol should count:
- <state included/excluded in plain language>.
- Calculation:
  <value> * <value> / <value> = <expected result>

What the code counts:
- <wrong or broader state included in plain language>.
- Contract calculation:
  <value> * <value> / <value> = <actual result>

Why it matters:
- <trade/deposit/withdrawal/action> looks <safer/cheaper/larger/smaller> than it really is.
- Difference:
  <actual result> - <expected result> = <excess, shortfall, or undercharge>

Final state:
- User/depositor/withdrawer has <value>.
- The protocol/pool has <value>.
- The expected result would have been <value>.

Important nuance:
- <who is actually harmed, who is not harmed, bounded impact, or overstatement>
```

Do not paste PoC variables as the whole example. If a PoC uses names like `totalSupplyAtQueue`, `queued shares`, or `gross value`, translate them into user-facing state first. For example, explain "the user queued almost 5,000 LP for withdrawal, so those shares should no longer be priced as live LP for the later deposit."

If a draft example only shows formulas, rewrite it until a reader can answer: "what is supposed to happen, what actually happens, and who cares?"

If the finding is about:

- Share/accounting bugs: show assets, shares, exchange rate, deposit/withdraw result, and who gains or loses.
- Rounding: choose values that produce truncation or ceiling behavior and show the exact delta.
- Oracle/price bugs: show price, decimals, conversion, collateral value, debt limit, and liquidation or borrowing effect.
- Time/rate bugs: show timestamps, elapsed time, accrued amount, and state before/after.
- Access control: show role/caller, allowed action, forbidden action, and resulting state mutation.
- Liquidation/incentives: show collateral, debt, health factor, discount/bonus, and net transfer.

Avoid examples that depend on arbitrary huge numbers unless the exploit actually requires size.

## Documentation Check

Docs Check must look for both specification intent and prior identification of the same or similar issue. Search external docs, repo docs, previous audit reports, audit contest findings, prior audit notes, issue lists, `ALL_FINDINGS`-style files, `UNCOVERED_ATTACK_VECTORS`-style files, TODO/security notes, NatSpec, and comments.

When docs mention the behavior or issue, classify the relationship:

- Direct support: docs explicitly require or forbid the behavior in the finding.
- Related invariant: docs describe a broader invariant that the finding may affect.
- Prior/similar finding: previous audits, audit contest findings, docs, or audit notes already identify the same bug, a duplicate, a broader issue, or a neighboring edge case.
- Conflicting behavior: docs contradict the implementation or report assumption.
- Operational caveat: docs weaken or qualify the practical exploit path, such as no public mempool, restricted keepers, limited token set, or configuration constraints.
- Silent: docs do not address the behavior.

Do not over-weight silence. Many valid findings are undocumented edge cases. If the docs partially mention the issue, say exactly what is covered and what is missing.

## Current On-chain State Assessment

Bug-bounty triage must answer whether the reported issue is exploitable against current deployed state, not only whether the code contains a theoretical weakness.

Use `deployment-context.md` as a starting point, then verify with official docs/program pages, block explorers, read-only contract calls, public dashboards, and historical transactions. Record uncertainty directly when current-state evidence is missing.

Answer these points in a separate section:

- Relevant chain(s), contract address(es), proxy/implementation relationship when relevant, and how they were verified.
- Current amount at risk: contract balances, TVL, market size, enabled asset exposure, caps, or a reasoned estimate. If the bug mainly affects future deposits/borrows/trades, estimate reasonable future value at risk from caps, current usage, or recent volume.
- Repeatability: recurring drain/grief/accounting issue, single one-shot action, bounded per epoch/market, or only future-triggered.
- Admin/config dependency: whether the exploit requires privileged actors to make a bad setting. If yes, most platforms treat it as out of scope unless that configuration exists today and the program includes it.
- Current configuration: whether the live contract is configured so the attack can happen now, or whether the bug is dormant behind disabled assets, zero caps, paused state, unset routes, missing approvals, stale deployments, or uninitialized modules.
- Historical preconditions: whether needed states or events have appeared before, such as queued withdrawals, stale oracle updates, liquidation windows, empty markets, role actions, or matching transaction patterns.
- Intent: whether docs, naming, tests, or product behavior suggest the described behavior is intentional.
- Known issue status: whether previous audit reports, audit contest findings, the repo, docs, program page, issues, PRs, governance posts, or public discussions already mention the issue or a close variant.
- Submission recommendation: if current-state answers do not support a real exploitable bug, recommend skipping submission or classify as invalid/needs more information.

## Protocol Analysis And Verdict

The final response section must combine the implementation trace and verdict. Do not split verdict into a separate section. Include caveats before the final decision whenever they materially affect triage.

Useful caveat types:

- Bounded impact: no direct theft, capped loss, limited griefing, or only accounting/policy impact.
- Deployment assumptions: only applies to specific tokens, oracle settings, roles, chains, integrations, contract addresses, or configuration values.
- Existing mitigations: caps, delays, whitelists, pausing, permission checks, slippage checks, or fallback paths that reduce exploitability.
- Current-state blockers: paused modules, disabled markets, zero balances, zero caps, inactive deployments, missing routes, or bug bounty scope exclusions.
- Admin-only assumptions: requires governance/admin to configure the system into a vulnerable state.
- Overstatement: the finding is directionally correct but the report exaggerates severity, reachability, affected users, or repeatability.
- Non-applicable cases: deployments or flows where the issue cannot occur.

After the code trace, counterpoints, caveats, and tests, end with:

```text
Preliminary decision: Valid
Confidence: Medium
Why: <main reason from code/spec>
Assumptions: <deployment/user/role/oracle assumptions>
Notes: <duplicates, severity adjustment, test gap, or docs mismatch>
```

Use `preliminary` unless the user asks for a final adjudication and the evidence is strong.
