# Golem Work Pack (experimental design)

A Golem Work Pack is a local package defining the roles, inputs, capability ceiling,
prohibited effects, Evidence, approval and completion conditions for a particular
job as a versioned machine-readable contract. It is data, not agent instructions.
Golem is the product; AWE (Agentic Workflow Engine) is its architecture/category.

External agents decide, plan, author, edit and use tools. Golem owns Work state,
dependencies, ownership, handoff, Evidence, approval, freshness, completion predicates
and receipts. Packs select existing contracts; they must not create a second reducer.

## Repository and authority

One Golem repository owns core, schemas, validator, reference packs, verifier
proposal contracts, Evidence Package, receipt verification, local catalog, CLI and
conformance tests. No repository split is planned. `styxis-plugin` owns client
packaging, launchers, manifests, marketplace metadata, agent-facing GEO, installation
entrypoints and distribution/client compatibility validation. `styxis-io` owns the
company/product canonical narrative and website GEO. Runtime intent metadata is
not marketplace copy. Existing Golem plugin sources remain intact until an explicit
non-destructive migration; do not list Golem Alpha in the public Styxis catalog.

| Party | Authority | Not authority |
| --- | --- | --- |
| Agent | User-authorized proposals, edits, observations | Native PASS, owner identity |
| Owner | Exact local policies and reviewed decisions | Implicit permission from installing a pack |
| Core | Existing parser/reducer/lock/fence/receipt predicates | Semantic truth of model text |
| Integration | Policy intersection and delivery | New workflow state machine |
| Pack | Requirements and maximum capability declarations | Grants, executable scripts, model/provider settings |
| Verifier | Bounded findings proposal | Approval, QA PASS, completion |

```mermaid
flowchart TD
 A[External agent] --> P[Discover and validate exact pack]
 P --> O[Owner review: exact binding (limited)]
 O --> W[Existing native Work contracts]
 E[External Evidence provider] --> W
 V[Semantic verifier proposal] --> W
 W --> C[Native freshness and completion checks]
 C --> R[Authoritative receipt]
 R --> D[Derived JSON inventory / Markdown projection]
```

The diagram describes the target architecture, not an implemented automatic pipeline.
M2 implements bounded manifest validation, local snapshot reads, inspect and declared-version comparison. General role mappings, receipt aggregation and
pack-specific completion are not implemented. In particular READY_FOR_RELEASE is
an intent label, not native DONE or permission to publish.

```
effective capability = pack ceiling ∩ owner policy ∩ current Work state
                       ∩ current role contract ∩ runtime/integration availability
PACK_DISCOVERED ≠ PACK_VALIDATED ≠ PACK_REVIEWED ≠ PACK_BOUND
≠ CAPABILITY_AUTHORIZED ≠ ACTION_EXECUTED ≠ EVIDENCE_ACCEPTED ≠ WORK_DONE
```

No hosted orchestration, accounts, payment, billing, mandatory remote MCP, RAG server,
model proxy, persona/prompt marketplace or professional-advice agent is introduced.
Existing optional usage functionality is neither removed nor made a requirement.
The license remains PolyForm Noncommercial. A free technical asset under that license
is not thereby OSI open source; no license change is part of this work.

## Audit at source baseline f2563f5

These are reuse boundaries, not a claim that all existing paths received new E2E tests.

| Existing contract / code | Work Pack attachment point and constraint |
| --- | --- |
| [Architecture](../architecture.md), `src/core/{work_run,stage_graph,stage_run}.c`, `include/golem/core.h` | Preserve Work reducer and stage graph; no parallel Python state machine |
| [Workflow](../workflow.md), [templates](../workflow-templates.md), `src/workflow/`, `include/golem/workflow_template.h` | Template expansion is not a pack grant; conditional document closure remains native |
| [Registry](../document-registry.md), `src/document/{schema,storage,registry}.c` | Immutable revisions, CAS and generation; pack binding would be a separately reviewed additive contract |
| [Sessions](../agent-session.md), [resume safety](../resume-safety.md), `src/agent_session/`, `include/golem/agent_session.h` | Claim, lease, boot identity and foreign owner remain authoritative |
| [Roles](../role-contracts.md), `include/golem/role_contract.h`, `src/execution/` | Existing enrollment/assessment is not a custom role scheduler; reuse exact contract digest |
| [Evidence](../evidence-verification.md), `src/evidence/`, `include/golem/evidence.h` | Digest verifies bytes; receipts do not establish authorship or truth |
| [Execution](../execution.md), [recording](../execution-recording.md), `src/execution/` | Issued receipts differ from agent claims; no effect replay for uncertain result |
| [Completion](../completion.md), `src/completion/`, `include/golem/completion.h` | Current closure, QA receipt/source, blockers and ownership predicates stay unchanged |
| [Reentry](../reentry.md), `src/reentry/` | Proposed cause differs from fact; old failure and COMMIT_UNKNOWN records are preserved |
| [Candidates](../candidates.md), [workspaces](../workspaces.md), `src/candidate/`, `src/workspace/` | Candidate validation is not current-target merge authority; no scheduler/merge queue is added |
| [Proof packs](../proof-packs.md), [export](../evidence-export.md), `include/golem/proof.h` | Existing integrity/projection contracts are reused, not renamed to Work Pack |
| [D1](../integration-d1.md)–[D6](../integration-d6.md), `tools/integration_*.py` | D1 registration; D2 disclosure; D3 hooks; D4 exact actions; D5 update/recovery; D6 remote auth are distinct gates |
| `src/cli/main.c`, `include/golem/*.h`, `bindings/{native,python,typescript}` | Native C is authority; CLI and bindings are façades, M2 has no binding/MCP route |
| `samples/`, `tests/c/`, `tests/consumer/`, `fuzz/` | Follow existing strict JSON, CTest, installed consumer and seeded mutation conventions |
| `plugins/golem/`, `tools/integration_distribution.py`, `tools/integration_mcpb.py` | Existing distribution remains functional; external packaging migration is planned only |

Current installed prepare connection exposes ten policy-filtered tools (projects_list,
work_inspect, workflow_read, document_read, history_read, template_read,
contract_prepare, action_prepare, plan_read, completion_check), not the complete core.
Its installed runtime is pinned to f2563f5; development here does not update it.
Current Work schemas and journal/event versions are not migrated. M1 has no persisted
Work state. A future incompatible binding must fail closed on older readers and have
an explicit compatibility/migration procedure, never implicit `latest` replacement.

Terminology: Work Pack is distinct from workflow template, runtime profile, instruction
bundle, proof pack, MCP package, native receipt and role enrollment. Their existing
linked contracts stay canonical. New pack schema is canonical in [schema](schema.md),
future authority in [roles/evidence](roles-and-evidence.md), planned commands in
[delivery](delivery.md), and stage gates in [development](development-plan.md).

M3 additionally implements explicit local catalog listing and deterministic lexical search.
See [delivery](delivery.md) for exact input limits, ambiguity and no-authority semantics.

M4 implements limited [native document resolve/bind/explain](binding.md), with a separately
selected exact digest. General role mappings, semantic release validation and MCP delivery remain unsupported.

M5 adds [proposal validation and separate native role evaluation](proposals.md) for
existing document bindings; claims never grant authority or prove semantic correctness.

M6 adds [private evidence manifest/export/verify](receipts.md) for selected native document closures. Integrity is not authenticated origin, QA PASS or current completion. Work Pack MCP delivery remains unimplemented.

M7 adds a [Truthound capture adapter and native document scenario](reference-adapter.md), with mock/native/actual external runs distinguished; no release authority.
