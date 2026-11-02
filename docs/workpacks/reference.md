# Truthound Dataset Release Gate reference specification

Identity `io.styxis.golem.dataset-release-gate`, version `0.1.0`, experimental.
The manifest is a structurally valid contract fixture, NOT a working release binding.
M7 implements the [bounded capture adapter and separate native document scenario](reference-adapter.md);
the general external role mapping and authoritative release predicate remain unsupported.
Golem does not import/copy Truthound implementation. Truthound is external Evidence.

Tool declarations inspected in the connected Truthound Local inventory on 2026-11-02:

| Tool | Exact input schema | Declared result and limit |
| --- | --- | --- |
| `check_file` | object, required string `path` | null/duplicate check; quality failures can still be successful calls |
| `profile_file` | object, required string `path` | bounded column types/aggregate statistics, no sample values |
| `scan_pii` | object, required string `path` | sampled potential PII; counts are estimates |

All return `{data: object|null,error:object|null,ok:boolean,operation:string,
schema_version:1,truncated:boolean}`. Current grants/tool delivery remain client-specific.
The initial inventory audit made no calls. M7 later ran six owner-approved calls on
two isolated synthetic CSVs; see the [execution record](development-plan.md). No
production data, global Truthound permissions or client connections were changed.
These tools do not promise release, full PII absence, source snapshot signing, owner
approval, or durable Golem evidence ingestion. Adapter capture must bind exact dataset
bytes/config and preserve truncation, unknown quality, sample coverage and failure.
`data_validator` maps to these capabilities only after a reviewed external adapter;
M1's capability symbols are requirements, not evidence acceptance.

Intent: validate dataset before release; review RAG source update; check evaluation
dataset change; verify quality before publishing; 데이터셋 배포 전 검증;
RAG 데이터 변경 검토; 평가 데이터셋 품질 확인.
Negative intent: edit rows, cloud upload, model training, database migration,
automatically approve release; 데이터 직접 수정; 클라우드 업로드; 모델 학습; 자동 배포 승인.

Roles: proposer, data_validator, semantic_verifier, approver, publisher. Required
artifact names: source_snapshot, dataset_identity, quality_result, profile_result,
pii_result, semantic_review, owner_decision, release_not_executed. No role gets
execution authority. Release is outside this pack: completion intent READY_FOR_RELEASE
requires exact source, current required evidence, checked result identity, review present,
blocking findings resolved or explicitly rejected by owner, recorded owner decision,
no unresolved foreign owner or uncertain effects, and explicit release not-executed.
This is not an implemented native predicate. M7 explicitly tests refusal to bind
this external-role Pack; its supported document bridge does not substitute for that predicate.

```
Agent dataset proposal → exact source/pack binding (planned)
→ external Truthound observations → existing Evidence acceptance
→ semantic proposal → explicit owner decision → READY_FOR_RELEASE intent
→ separately authorized release (outside pack)
```

Tool success ≠ Evidence accepted ≠ semantic review passed ≠ owner approved
≠ release authorized ≠ Work completed. Mock data is never advertised as an actual
Truthound integration run. M6 supports selected native document receipts; M7 can export a quoted external
observation inside such a document, without authenticating the external result.

The serialized M1 sample uses hyphenated role/evidence identifiers (for example
`data-validator`); conceptual underscore names above are prose, not accepted IDs.
Its all-zero provenance digest is an explicitly synthetic declaration, not an
authenticated release source. Production packaging must supply reviewed provenance.
