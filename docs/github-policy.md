# GitHub Domain Policy Evaluation

The read-only status collector evaluates active branch rules through a registry
in `tools/github_policy.py`. Transport, credential handling, response capture,
pagination, time/request limits and publication remain in the existing common
layers. New domain adapters must return evidence identities, a scoped status and
completeness, not mutate provider policy or authorize native completion.

## Contracts

| Rule | Evidence and decision | Explicit non-PASS boundaries |
| --- | --- | --- |
| `workflows` | GitHub rule-suite evaluation for the exact commit/ref, active ruleset ID and workflow rule; current parameters and ruleset update time checked before/after | Missing/expired evaluation, bypass, evaluate-only rule, newer policy, timestamp tie, changed evidence, creation exemption, mutable definition revision |
| `code_scanning` | Successful latest analysis per tool GUID, analysis key, category and environment; exact branch-head SHA; ref-scoped alert instances with severity thresholds | Missing/failed/warning analysis, stale category, unknown severity, denied access, changed uploads/alerts, candidate SHA without PR/reference context |
| `required_deployments` | Latest deployment attempt for each required environment and exact target SHA, then latest status, both rechecked | Missing/pending/failed/inactive attempt, wrong SHA/environment/resource URL, timestamp tie, changed inventory/status, incomplete pagination |

### Required Workflows

Matching job names, workflow filenames or `referenced_workflows` is insufficient:
a reusable workflow execution is not necessarily the organizational required
workflow. The adapter instead reads GitHub's per-rule evaluation, preserving
ruleset identity and active enforcement. It rejects current ruleset parameters
that differ from discovered policy. An evaluation must be strictly later than the
current ruleset update timestamp; same-second ambiguity is not resolved by IDs.
Ruleset update timestamps accept timezone-aware RFC3339 offsets and fractional
seconds observed in actual API responses, not only second-resolution UTC examples.
Naive timestamps, invalid dates/offsets and excess precision fail closed.
The unique latest exact-ref/commit suite is used, including failures and bypasses,
not the latest successful suite. Suite detail and ruleset are re-read before use.

GitHub exposes a bounded rule-suite history (`month` at most here), not an archive
or a signature. No retained evaluation is `EVALUATION_NOT_OBSERVED`. A PASS applies
only to the provider's push evaluation of that commit, **not** present merge
authorization. Definitions pinned by commit SHA can support this scoped PASS.
When only a movable branch/tag is configured, even a provider pass remains
`DEFINITION_REVISION_UNVERIFIED`: the suite response does not identify the resolved
workflow-source SHA. This is an evidence limitation, not an unimplemented dispatch
branch, and is not hidden with a filename heuristic. Creation exemptions cannot
be mistaken for execution. Ruleset updates, disabled enforcement and missing
administration access cannot reuse an old successful evaluation.

### Code Scanning

All documented ordinary thresholds (`none`, `errors`, `errors_and_warnings`,
`all`) and security thresholds (`none`, `critical`, `high_or_higher`,
`medium_or_higher`, `all`) are supported. Security findings use security severity;
non-security findings use ordinary severity. An explicitly security-tagged alert
without a security severity cannot be silently classified as safe. An open
ref-specific instance is not hidden by a repository-wide fixed/dismissed state.
Closed instances may legitimately retain an older commit and do not block.

Empty alert results alone never pass: successful analysis must exist. Every
observed analysis category must have a successful latest result for the target
SHA. Analysis warnings are conservatively non-PASS rather than proof of complete
coverage. Histories and alert lists are queried completely within shared limits,
then re-read to detect changes; they are not an atomic provider transaction.
The collector also reads all check attempts, not only the latest completed ones.
Any observed queued/in-progress/waiting/requested/pending attempt conservatively
holds a domain PASS at `EXECUTION_PENDING`. This may include unrelated checks:
job names cannot reliably identify which job belongs to a scanner. Undisclosed
external provider work with no GitHub check/analysis record is not discoverable.

This collector targets a policy branch. When the target SHA is not its current
head, the adapter returns `REFERENCE_CONTEXT_REQUIRED`, rather than interpreting
base-branch alerts as PR-diff or merge-queue results. PR/merge-group context is a
separate future adapter input. A scoped branch-head PASS covers the observed
reference analysis categories, **not** a proof that every possible language or
scanner configuration has run, or that the source has no vulnerabilities.

### Required Deployments

Policy evaluation differs intentionally from the common deployment inventory.
The policy adapter filters by the exact target SHA and each required environment;
the inventory observes the latest deployment across SHAs to avoid presenting old
code as currently deployed. A newer failed/pending retry for the target SHA blocks
an older successful attempt. Other-SHA deployment records cannot satisfy this
commit's requirement. Success is a GitHub deployment record, not serving health,
deployment authorization, runtime attestation or proof that tests ran there.

## Extension And Failure Model

`EVALUATORS` is the supported-rule registry. `collect` isolates per-rule controlled
errors and preserves successful sibling observations without converting the
overall result to PASS. Unknown rule types remain explicitly unsupported. Domain
results are bound back to the exact discovered rule sequence before aggregation.
Provider failures publish a failed observation, preserve retry delays and advance
collector backoff. There is no fallback to an old successful cycle. Evidence
captures include raw bounded API responses through the shared transport.

`evaluation_complete` is not acceptance: an evaluated missing requirement can be
complete and BLOCKED; inaccessible/malformed evidence is incomplete. Dirty source
remains distinct from committed remote evidence, and native completion retains its
own authority. No daemon or remote test policy is installed by this change.

## Research Traceability

Consulted 2026-10-10. API contracts determine implementation; empirical papers and
books inform design boundaries, not undocumented GitHub semantics or Golem gains.

| Reference and consulted portion | Design consequence |
| --- | --- |
| GitHub [branch rules and rulesets](https://docs.github.com/en/rest/repos/rules), workflow/scanning/deployment parameter schemas | Preserve full rule identity, thresholds and environment/source-definition requirements |
| GitHub [rule suites](https://docs.github.com/en/rest/repos/rule-suites), both endpoints and response schemas | Separate active/evaluate/bypass results, exact ref/commit, bounded retention and historical provider verdict |
| GitHub [code scanning](https://docs.github.com/en/rest/code-scanning/code-scanning), analyses, alerts and analysis-set definition | Require analysis before empty-alert PASS; preserve category/environment and ref-specific instances; expose permission/feature errors |
| GitHub [alert severity](https://docs.github.com/en/code-security/concepts/code-scanning/code-scanning-alerts), severity and PR sections | Security severity takes precedence over ordinary severity; branch-head and PR-diff observations are not interchangeable |
| GitHub [deployments](https://docs.github.com/en/rest/deployments/deployments) and [statuses](https://docs.github.com/en/rest/deployments/statuses), query and state contracts | Exact SHA/environment filtering and explicit pending/error/inactive handling |
| Ayala and Garcia, *An Empirical Study on Workflows and Security Policies in Popular GitHub Repositories*, SVM 2023, [paper](https://arxiv.org/html/2305.16120v1), methodology and CodeQL adoption results | Workflow presence is not evidence of enabled/executed scanning; retain provider observations for reproducibility |
| Winters, Manshreck and Wright (eds.), *Software Engineering at Google*, O'Reilly 2020, [chapter 23](https://abseil.io/resources/swe-book/html/ch23.html), CI scope/dependencies and feedback | Separate evolving external policy evidence from local source acceptance; shared extensible collector and visible failure |

Regression tests exercise positive and negative domain contracts with explicit
provider fixtures. Real GitHub observation is a separate integration result:
repositories without enforced policies/scans/deployments cannot demonstrate a
positive enforced-policy path. Do not create or weaken production policy to make
this test green, or present hypothetical-policy fixtures as active GitHub policy.

## Approved Live Integration, 2026-10-10

With explicit user approval, a separate public synthetic-only repository was
created: [golem-policy-validation-20261010-27a0a589](https://github.com/seadonggyun4/golem-policy-validation-20261010-27a0a589).
No Golem product source or credentials were uploaded. Deployment records and SARIF
findings were explicit fixtures, not real deployments or real vulnerability scans.
The original Golem repository's settings were not changed.

| Path | Actual GitHub result | Golem result |
| --- | --- | --- |
| Required deployment absent | Ref update rejected, HTTP 422 | BLOCKED / MISSING |
| Required deployment failure | Ref update rejected, HTTP 422 | BLOCKED / FAIL |
| Required deployment success | Ref update accepted | PASS |
| Code-scanning synthetic error | [PR 1](https://github.com/seadonggyun4/golem-policy-validation-20261010-27a0a589/pull/1) merge rejected, HTTP 405, blocking scanner alert identified | FAIL for the tool; BLOCKED for the rule |
| Same scanning candidate with clean replacement analysis | PR merge accepted | PASS for the tool |
| Full collector on protected deployment/scanning branches | Active rules discovered; exact-source evidence queried and published | PASS for each required policy, no native completion inferred |
| Required workflow configuration | HTTP 422 after valid source file, documented PR/merge-group triggers and SHA/ref were supplied | Positive enforced-policy verification NOT completed |

GitHub documents required workflows as an organization/enterprise-level ruleset
feature, not a personal-repository feature. See [workflow rules](https://docs.github.com/en/enterprise-cloud%40latest/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets#require-workflows-to-pass-before-merging).
The API rejection itself does not prove its exact underlying cause; an eligible
organization test repository is needed for that positive integration path. Do not
substitute ordinary Actions/check success for required-workflow enforcement.

Live testing also exposed and fixed ruleset-only protection discovery and offset /
fractional timestamp parsing. Regressions cover both, including contradictory
disabled protection metadata and timezone-equivalent instants. Private command,
HTTP and collector-cycle captures retain failure attempts as well as successful
observations. The test repository is retained for audit and archived after testing;
archival does not prove historical policy success or real application health.

## Candidate Scanning Adapters

The collector's optional `--candidate-context PRIVATE_JSON` binds scanning to a
candidate, while `--branch` still names the protected base branch. The local
checkout must be at the exact scanned candidate SHA, not merely its base/head.

```json
{"kind":"pull_request","number":3,"ref_mode":"merge"}
```

`head` and `merge` are distinct explicit modes. The adapter verifies the open PR,
base repository/branch/SHA, canonical pull ref and (for merge mode) exact base/head
parents. Null `merge_commit_sha` metadata is not guessed: the canonical merge ref
and its parents must independently verify. Closed/moved/conflicting candidates
fail. Each alert's scoped instances are queried, rather than trusting the
repository-wide most-recent instance. These observations are conservatively
about open instances on the selected ref; they do not reproduce GitHub's entire
changed-line merge eligibility algorithm or grant merge permission.

```json
{
  "kind":"merge_group",
  "run_id":123,
  "head_ref":"refs/heads/gh-readonly-queue/main/pr-3-example",
  "head_sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "base_sha":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
}
```

Merge-group resolution requires a real GitHub Actions run whose event is
`merge_group`, with exact repository/head SHA/head branch, plus the live queue ref,
current base ref and base ancestry. A caller-created queue-looking ref or a push
run cannot stand in for provider provenance. Third-party-only queue execution
without an Actions run requires another authenticated event adapter; it is not
silently accepted. All identities and analysis/alert/instance sets are re-read
after observation; movement, missing data, permissions or shared request-budget
exhaustion remain non-PASS. No queue or GitHub App is installed automatically.

Actual REST integration on synthetic [PR 3](https://github.com/seadonggyun4/golem-policy-validation-20261010-27a0a589/pull/3)
observed **BLOCKED -> PASS** after replacing a finding analysis with a clean one
on the same pull merge ref; closing the PR then invalidated its context. Synthetic
SARIF is not a real vulnerability assessment. The test repository was archived
again. A prior failed attempt (null merge metadata) was preserved and produced a
regression. Actual merge queue execution remains **NOT VERIFIED**: the approved
test repository belongs to a personal account, and no organization test repository
is available. Provider-shaped positive/negative regressions are not that live test.

## Additional Design Sources

Consulted 2026-10-10; design rationale, not proof of achieved coverage/performance:

- [Codex app-server protocol and events](https://learn.chatgpt.com/docs/app-server):
  owning stdio client, initialize handshake and turn/usage identity boundaries.
- [GitHub scanning REST](https://docs.github.com/en/rest/code-scanning/code-scanning):
  explicit PR refs, category-specific analyses and scoped alert instances.
- [GitHub merge queues](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue)
  and [merge-group event](https://docs.github.com/en/webhooks/webhook-events-and-payloads#merge_group):
  queue SHA is not PR SHA; feature eligibility and provider event provenance.
- Saltzer, Reed and Clark, *End-to-End Arguments in System Design*, ACM TOCS
  2(4), 1984, pp. 277-288, [author-hosted paper](https://web.mit.edu/Saltzer/www/publications/endtoend/endtoend.pdf):
  receiver-side confirmation cannot be replaced by transport success. Accordingly
  collection, inbox publication and actual native owner application stay distinct.
- Winters, Manshreck and Wright (eds.), *Software Engineering at Google*,
  O'Reilly, 2020, [chapter 12](https://abseil.io/resources/swe-book/html/ch12.html):
  regress behavior/contract boundaries, not private implementation structure.
  Tests cover candidate movement, incomplete usage, late response mismatch,
  timeout/cleanup and secret-free persistence alongside live integration evidence.
