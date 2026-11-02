# Truthound Dataset Release Gate reference specification

Identity `io.styxis.golem.dataset-release-gate`, version `0.1.0`, experimental.
The manifest is a structurally valid contract fixture, NOT a working binding or release.
Golem does not import/copy Truthound implementation. Truthound is external Evidence.

Tool declarations inspected in the connected Truthound Local inventory on 2026-11-02:

| Tool | Exact input schema | Declared result and limit |
| --- | --- | --- |
| `check_file` | object, required string `path` | null/duplicate check; quality failures can still be successful calls |
| `profile_file` | object, required string `path` | bounded column types/aggregate statistics, no sample values |
| `scan_pii` | object, required string `path` | sampled potential PII; counts are estimates |

All return `{data: object|null,error:object|null,ok:boolean,operation:string,
schema_version:1,truncated:boolean}`. Current grants/tool delivery remain client-specific.
No calls, raw data reads or Truthound configuration changes were performed in this audit.
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
This is not a currently installed native predicate; M4–M7 must connect and test it.

```
Agent dataset proposal → exact source/pack binding (planned)
→ external Truthound observations → existing Evidence acceptance
→ semantic proposal → explicit owner decision → READY_FOR_RELEASE intent
→ separately authorized release (outside pack)
```

Tool success ≠ Evidence accepted ≠ semantic review passed ≠ owner approved
≠ release authorized ≠ Work completed. Mock data is never advertised as an actual
Truthound integration run. Portable receipt remains planned under M6.
