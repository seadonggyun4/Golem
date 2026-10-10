# Continuous Revision Status Collection

`tools/status_collector.py` provides a restartable foreground service. It reuses
revision projection and adds automatic GitHub policy discovery, named-check and
domain-policy evaluation. No GitHub settings, commits, checks, workflows, deployments or Work
completion records are modified. A service supervisor owns lifetime/restart; this
tool does not install a global daemon or change the user's launch configuration.

## Entry Points

Use the existing revision-status index, repository root, target policy branch and
a private state directory outside the repository:

```sh
python3 tools/status_collector.py collect INDEX.json --cwd REPOSITORY \
  --branch main --state PRIVATE_STATE --credentials gh --follow

python3 tools/status_collector.py status INDEX.json --cwd REPOSITORY \
  --branch main --state PRIVATE_STATE
```

Without `--follow`, collect performs one cycle. `--follow --max-cycles 2` is a
bounded integration check; absent a positive limit, it runs until SIGINT/SIGTERM
or a fatal integrity/resource failure. Signals interrupt the interval wait;
an in-flight request completes or reaches its socket timeout before shutdown.
No daemon remains after bounded validation. A supervisor can restart the same
command with the same state directory; do not run two writers for one directory.
Supported platforms are macOS/Linux (POSIX flock). Windows requires a lock adapter.

`--credentials env` uses `GH_TOKEN`, with no token meaning public access only.
Explicit `--credentials gh` reads the existing github.com GitHub CLI credential
into memory; it never prints or writes it. The shared execution recorder captures credential-command metadata only;
bounded stdout/stderr stay in memory and no secret-bearing stream or argv is
persisted. Credential acquisition does not bypass the execution inventory.
Credential loss publishes a failed
cycle instead of silently falling back to anonymous access. Grant only required
read permissions: metadata, checks, commit statuses and administration to read
legacy branch protection. No permission-setting or authorization bypass occurs.

## Discovery And Evaluation

Every cycle discovers the branch's active applicable rules through GitHub's
branch-rules API, including organization-level active rules. Evaluate/disabled
rulesets are not active policy. For a protected branch, legacy branch protection
is also read unless branch metadata explicitly marks it disabled with no named
check requirements. Ruleset-only protection may set `protected=true` alongside
`protection.enabled=false`; active rules are still queried in that case.
Contradictory disabled summaries fail validation. Failure/ambiguous 404 when
legacy protection is not explicitly disabled means `DISCOVERY_FAILED`, not empty policy.
An unprotected branch still gets ruleset discovery. Named requirements are the
union of legacy contexts/checks and ruleset `required_status_checks`, retaining
app/integration IDs and both policy sources.

Required workflow definitions and other rules are preserved in the inventory,
not silently discarded. `discovery_complete` means the policy APIs were completely
read; `evaluation_complete` is a separate property. Workflow, code-scanning and
required-deployment rules use the domain adapters in `tools/github_policy.py`.
See [policy evaluation](github-policy.md) for evidence scope and limitations.
Unknown gate types remain `POLICY_GATE_EVALUATION_REQUIRED` and block PASS.
`evaluation_complete` means an adapter evaluated the available evidence, not that
the requirement passed; query/validation failure sets it false and participates
in persistent collector backoff. Known non-check constraints (reviews, signatures, branch
creation, etc.) remain visible but are not a merge-authorization predicate here.
This is not an automatic universal compliance or branch-merge approval engine.

The exact local commit SHA is queried for check runs and legacy commit statuses.
GitHub's `filter=latest` selects check attempts; separate queued/in-progress and
bounded all-attempt queries prevent waiting/requested/pending reruns being
concealed by terminal results. Observed unfinished checks conservatively hold a
domain-policy PASS at `EXECUTION_PENDING`, even for unrelated job names. Conflicting
observations remain conflicting. App-pinned requirements reject a different app;
legacy statuses cannot establish app identity. When check and legacy status names
collide, both observations are retained. Legacy statuses use the API's documented
newest-first ordering, never a guessed wall-clock sort. Neutral/skipped results
are not promoted to PASS, even though GitHub may accept them for merging.

No requirements is `NOT_REQUIRED`, never PASS. Missing named requirements block.
Policy and branch are read again after checking; movement blocks the cycle.
The remote GET sequence is not globally atomic. The observation describes one
bounded polling window, not all changes between polls or a provider signature.

Each cycle also discovers deployment environments from the complete bounded
repository deployment inventory (up to 32 environments). It queries statuses for
the unique latest-created deployment per environment, without filtering by the
local SHA and accidentally selecting an older successful deployment. Timestamp
ties, duplicate identities, missing retained statuses and incomplete pagination
block the inventory. Exact commit matching still applies in the common deployment
channel; a newer deployment of a different SHA remains STALE, not local PASS.
Deployment API failures are visible independently from required-check discovery,
stop further requests on access/rate errors and participate in backoff. Environment
inventory describes GitHub deployment records, not discovered runtime services,
currently serving health or a complete backup of deployment history.

Dirty source is `COMMIT_ONLY_DIRTY_SOURCE`; `commit_status` preserves the remote
evaluation separately, including FAIL/BLOCKED. Historical commit success does not
verify uncommitted changes or native completion. Each result includes the ordinary
five-channel projection plus a distinct `required_checks` policy evaluation.

## Lifecycle, Freshness And Resources

- All GETs are serial and certificate-verified against api.github.com. Redirects
  and proxies are refused. Pagination follows validated Link next URLs only on
  the same resource with unchanged filters; cycles, changing totals, more than
  20 pages/2,000 rows or an exhausted 128-request budget block completeness.
- ETags/body hashes persist across restarts. `304` requires an intact cached
  representation; a corrupt cache triggers a full refetch, never stale acceptance.
  Raw responses and HTTP outcomes are retained for each observation, including
  revalidated bodies. Cache is an optimization, not the authoritative evidence.
- Default interval is 60 seconds, TTL 180 seconds; interval cannot be below 60.
  TTL is measured from query start. Retry-After, rate-limit reset and poll-interval
  headers can increase waits. Failed cycles back off exponentially. The next
  permitted poll and consecutive failure count persist before sleeping, so restart
  cannot immediately retry a rate-limited request.
- A failed cycle replaces the current pointer with the failure. It never falls
  back to an earlier PASS. Readers verify manifest/body hashes, configuration
  identity, current source identity and TTL. Expiry/clock rollback yields
  `EXPIRED_CAPTURE`; changed source yields `STALE_SOURCE`. Local evidence is
  reprojected against the current revision. TTL does not assert collector liveness.
- Single-writer flock, private directories/files, immutable UUID cycle captures,
  fsync and atomic head replacement protect publication. A crash before publishing
  the pointer can leave an orphan capture, not a partially published PASS. Hashes
  detect accidental tampering; they do not authenticate a malicious local owner.
- Each response is capped at 2 MiB, a cycle's received bodies at 16 MiB and encoded
  captures at 24 MiB and results at 4 MiB. A 512 MiB state budget reserves 64 MiB before collecting;
  cache is also bounded. The collector stops rather than silently deleting audit
  history. Operators archive/rotate the private state root explicitly. Inventory
  scans are bounded by that local state budget; multi-repository fleets should use
  separate roots and supervised processes, not one shared mutable directory.

`status` performs no remote requests. Its within-TTL result remains a historical
capture, not an always-current guarantee. Neither collector nor reader can set
native acceptance or deployment authorization. An unattended installation must
supervise failures/quota, maintain credentials and rotate evidence; simply writing
the service code is not proof of long-term uptime.

## Research And Design Traceability

Consulted 2026-10-10; these are design sources, not measurements of Golem benefit.

| Source | Application |
| --- | --- |
| GitHub [branch rules](https://docs.github.com/en/rest/repos/rules#get-rules-for-a-branch) and [branch protection](https://docs.github.com/en/rest/branches/branch-protection) | Discover active inherited policy; distinguish absent requirements from inaccessible policy; preserve integration identity |
| GitHub [check runs](https://docs.github.com/en/rest/checks/runs), [commit statuses](https://docs.github.com/en/rest/commits/statuses) | Provider-defined attempt selection, nonterminal reruns, newest-first legacy statuses and missing requirements |
| GitHub [REST best practices](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api) | Serial requests, conditional revalidation, poll intervals, persistent rate-limit waits; no retry loop through 403/429 |
| Lamport, *Time, Clocks, and the Ordering of Events in a Distributed System*, CACM 21(7), 1978, [author's paper](https://lamport.azurewebsites.net/pubs/time-clocks.pdf), ordering and physical-clock discussion | Do not interpret independent timestamps as a global atomic ordering; source/policy rechecks and explicit observation windows instead |
| Shahin, Babar and Zhu, *Continuous Integration, Delivery and Deployment: A Systematic Review*, IEEE Access, 2017, [paper](https://arxiv.org/pdf/1703.07019), foundations/review results | CI evidence, release readiness and actual deployment are separate; observation does not authorize effects |
| Beyer et al. (eds.), *Site Reliability Engineering*, O'Reilly, 2016, [chapter 6 by Rob Ewaschuk](https://sre.google/sre-book/monitoring-distributed-systems/) | Simple comprehensible collection, visible failures, explicit operational ownership; collector health is not application health |
| Winters, Manshreck and Wright (eds.), *Software Engineering at Google*, O'Reilly, 2020, [chapter 23](https://abseil.io/resources/swe-book/html/ch23.html) | Unified actionable feedback with source-specific observations and preserved history |

GitHub recommends webhooks instead of polling where available. This implementation
uses authenticated conditional polling because it can run locally without public
ingress or webhook-registration write permissions. Event delivery/webhook adapters
can later trigger the same discovery/observation path; they must not bypass policy
revalidation, evidence publication, rate limits or freshness. No webhook service,
SLSA certification, whole-book review, or distributed consensus is claimed.
