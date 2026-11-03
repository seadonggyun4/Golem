# QC1 기준선·검토 native 연결 구현 기록

2026-11-03. 기준 HEAD `a0de4e5` 위 **미커밋 개발 소스**.
상태: **private native 제어 경로 구현 / 컴파일·실행 검증 NOT_RUN / 설치 미적용**.
[P0](intent-assurance-qa-p0-contract.ko.md)의 Q1–Q5 및 LOCAL_NO_MERGE 범위다.
실행 HOLD는 유지하며 실제 authority/TopSolar/Work/정책/승인/증거를 변경하지 않았다.
현재 Codex·Claude 설치의 기능 완료나 검증 통과를 뜻하지 않는다.

## 구현과 재사용

- [review.h](../src/intent/review.h), [review.c](../src/intent/review.c): 기준선의 실제 source coverage,
  전체 requirement/constraint 참조와 정의 원문 구간을 결합하는 `gi_review_bind`.
  기존 `gi_baseline_coverage_validate`, `gi_source_identity`, `gi_span_validate`, strict JSON parser와
  document의 closed field/ID/digest primitives를 재사용한다.
- 정의 객체는 baseline의 requirement_refs, constraint_refs 순서로 정확히 제공해야 한다.
  누락/추가/다른 Work/잘못된 schema/중복 ID/원문 밖 span/그 정의와 연결되지 않은 coverage 구간은 거부한다.
  요구·제약 합계256 상한, source·control 기존 한도를 적용한다.
- 기존 domain registry에 requirement.v1·constraint.v1의 exact identity만 추가했다.
  `gi_domain_digest` 자체는 기존과 같이 구조/채택 인증이 아니다. object store의 허용 객체 종류는
  확대하지 않았다. 정의 bytes는 caller가 보존·재제공하고 매번 exact digest와 내용을 대조한다.
- `gi_review_create/apply/inspect/free`: opaque private native 상태와 실패 원자적 reducer.
  기존 raw/Source/baseline bytes를 수정하지 않는다. `execution_authorized=false`,
  `authority_current_verified=false`를 조회 결과에 명시한다.
- `gi_review_load/publish`: 기존 committed baseline reader → 정의 검증 → control 역사 replay →
  현재 trusted guard → 기존 journal append. owner lock·quota·expected head/sequence·pending 실패를 재사용한다.
- 기존 journal에 read-only committed payload visitor를 추가했다. 전체 journal 검사 후 payload 길이·hash를
  재대조하고 borrowed bytes를 제공한다. pending/poison/reentry는 거부한다. reader가 repair하지 않는다.

## 닫힌 제어 계약

공통 root는 `schema=golem.intent.review-control.v1`, project_id, work_id, baseline_digest,
expected_epoch, operation, body다. baseline/project/Work는 native 상태와 정확히 같아야 한다.
각 성공 control은 epoch를 1 증가시킨다. 이 epoch는 **QC1 control revision**이며 아직 미구현인
project 전체 constraint epoch를 대체하지 않는다. stale·overflow·unknown/duplicate field를 거부한다.

| operation | body 필드 | 효과·차단 |
| --- | --- | --- |
| review | stage, producer, reviewer, input_manifest, definitions_digest, verdict, evidence_digest | 7개 stage만 지원. producer=reviewer 거부, 미결 질문이 있는 PASS 거부. 비PASS는 제거할 수 없는 의무 생성 |
| activate | decision_digest, review_digest, policy_digest | 현재 REQUIREMENTS review·정확한 issuer policy·source adoption·owner activation 검사. ACTIVE는 product 허가 아님 |
| question | question_digest, evidence_digest | baseline 전체를 보수적으로 차단할 의무. 해결됐던 ID 재사용도 거부 |
| answer | question_digest, evidence_digest | trusted 답변 결합; 기존 답 임의 교체/다른 질문에 같은 답 digest 소비 금지 |
| resolve | close, carry, evidence_digest | 현재 의무의 정확한 분할·중복/누락 거부. close는 답과 별도 resolution 검토 필요. 의미 수정 뒤 REQUIREMENTS 재검토 필요 |

원문의 QUESTION_REQUIRED가 있으면 baseline digest를 ID로 하는 초기 aggregate 의무를 만든다.
그 의무의 답/해결 검토는 **모든 해당 원문 구간**을 다뤄야 한다. 일부 답변이면 carry를 유지해야 하며,
aggregate 의무를 닫을 수 없다. 제품 실행이 없는 control lane이므로 답변·resolution은 계속 가능하다.
누적 question ID/answer digest는 baseline당 각각256까지 보존한다. 상한 후 자동 삭제/재사용 없음.
이는 초기 control 구현의 추가 제한이며 production quota를 늘리지 않는다.

정의 body: id, exact_text, source_spans(source_ref/start/end), modality, quantifier, negative,
conditions, acceptance_oracle_refs, derivation_rationale. constraint는 scope(LOCAL/GLOBAL/UNSCOPED),
applies_to, exclusions를 추가한다. oracle refs의 의미/실제 검증 결과 해소는 QC2/QC4 범위다.
원문 구간·ID가 맞아도 의미 정확성을 native가 증명하지 않는다.

## owner·reviewer host adapter

[review_host.h](../src/intent/review_host.h)와 [review_host.c](../src/intent/review_host.c)에
`gi_review_host_open/authorize/guard/publish`를 연결했다. `gi_review_authorize`가 요구하던
역할·세션·purpose·exact bytes 대조를 native 구현으로 제공한다. 항상 허용하는 fallback은 없다.

- owner가 모델 입력 밖에서 선택한 policy/bundle SHA와 실제 bytes를 strict JSON으로 대조한다.
  policy는 project/Work·LOCAL_COOPERATIVE·policy_epoch·ACTIVE/REVOKED principal의
  ID/OWNER/PRODUCER/REVIEWER 역할·세션을 고정한다. baseline과의 순환 hash를 피하기 위해
  policy는 baseline을 참조하지 않고, 별도 bundle이 policy와 baseline을 묶는다.
- bundle은 registration·baseline·policy·전체 control hash·owner/session·publication operation·
  expected journal sequence/head·유효시간·증거 원문/각 SHA를 고정한다. 한 bundle은 최대1시간,
  증거256개이며 전체 JSON은 기존 GI_CONTROL_MAX 안에 있어야 한다. 동일 digest 중복도 거부한다.
- `gi_review_host_observe_files`는 기존 D01 guard를 앞뒤로 호출하고 owner-private directory fd에서
  선택된 policy/bundle 파일을 매번 다시 읽는다. 단일 파일명만 허용하며 symlink·다중 hardlink·
  다른 uid·group/other 권한·비정규 파일·크기 초과·경로 inode 교체를 거부한다.
  기존 trusted D01 등록/폐기 검사와 owner lock을 caller가 유지해야 한다. 이 observer는 등록을
  생성하거나 승인하지 않는다. 일반 모델 경로·파일 탐색은 받지 않는다.
- 각 callback과 게시 전/commit 직전에 현재 registration/policy/bundle pin, expiry, 관찰한 시간의
  역행을 다시 검사한다. publish는 저장된 실제 baseline의 issuer_policy_ref도 현재 policy와 대조한다.
  기존 `gi_review_publish`의 parser/reducer/journal lock/CAS/pending 차단을 그대로 호출한다.
- STAGE는 producer와 reviewer의 등록된 ID·역할·세션이 각각 유효하고 서로 달라야 한다.
  새 review의 stage/input_manifest/definitions_digest/verdict를 선택한 증거와 대조한다.
  activate에서는 기존 REQUIREMENTS PASS 증거의 현재 reviewer 권한을 다시 검사한다.
- SOURCE_ADOPTION은 정확한 baseline에 대한 owner의 전체 source decision 검토 진술만 허용한다.
  ACTIVATION은 같은 review/policy를 대조한다. ANSWER는 질문과 SAME_BASELINE disposition,
  RESOLUTION은 정확한 close/carry와 별도 reviewer를 검사한다. reviewer 자신의 owner 답변을
  resolution으로 자체 승인하는 경우도 거부한다. scope/acceptance 변경은 이 경로에서 허용하지 않는다.

증거 schema는 `golem.intent.review-host-evidence.v1`이며 공통 필드는 purpose, project_id,
work_id, baseline_digest, policy_digest, policy_epoch, issuer, issuer_session, producer,
producer_session, body다. 비review 목적의 producer/session은 빈 문자열이다.

| purpose | body |
| --- | --- |
| STAGE | stage, input_manifest, definitions_digest, verdict, original_source_reviewed=true |
| SOURCE_ADOPTION | disposition=ADOPT_EXACT_BASELINE, all_source_decisions_reviewed=true |
| ACTIVATION | review_digest, policy_digest |
| ANSWER | question_digest, disposition=SAME_BASELINE |
| RESOLUTION | close, carry, disposition=SAME_BASELINE |

증거에는 소비 control hash를 넣지 않는다. control이 증거 hash를 참조하고 그 둘을 별도
owner-selected bundle이 고정하므로 순환 hash가 없다. 원문 검토 boolean은 **선택된 주체의 진술**이며
의미 정확성이나 독립 신원을 증명하지 않는다. input_manifest의 전체 artifact/oracle 의미 해소는
QC2 이후 계약이다. 같은 uid에 대한 공격 방어나 암호학적 사람 인증을 추가했다고 주장하지 않는다.

역사 replay는 과거 상태만 재현한다. `active=true`도 `authority_current_verified=false`이며
실행 권한이 아니다. 실제 host 정책 등록·공개 CLI/MCP 노출·설치는 하지 않았다.
private C adapter 호출 연결은 구현했으나 QC3 protected product gate와 제품 배포 연결은 후속 범위다.

## 저장·실패·지원 범위

현재 control은 intake lane만 사용한다. resolve라는 이름으로 기존 resolution 예약 권한을 자동 부여하지 않는다.
intake가 소진되면 차단하며 예약 lane 연결은 이후 별도 검토해야 한다.
동일 operation이 이미 있으면 publish는 재실행하지 않고 거부한다. 기존 read-only lookup으로
stored receipt/pending을 확인할 수 있다. 실패·부분 게시·unknown은 기존 journal 계약대로 보존한다.

이 구현은 고정 baseline의 local control reducer다. baseline 교체/resolve_and_activate,
project-wide impact graph·scope별 독립 진행·자동 successor 생성은 지원하지 않는다.
질문은 전체 local baseline을 차단하는 보수적 범위이며, 무관 Work를 임의 차단하거나 project 전체
진행성을 구현했다고 주장하지 않는다. P0의 일반 상태·지원 계약을 이 제한으로 소급 변경하지 않는다.

## 테스트 코드와 상태

[test_intent_review.c](../tests/c/test_intent_review.c)를 작성하고 `intent_review` CTest에 등록했다.
원문/정의 mismatch·정의 누락·self-review·missing authorizer·unknown field·다른 Work·duplicate JSON·
stale epoch·activation 거부·미결 질문 PASS 거부·answer/resolve·carry 중복·닫힌 ID 재사용 거부·
committed baseline→review 저장→reopen replay·중복 operation 거부 사례를 포함한다.
[test_intent_review_host.c](../tests/c/test_intent_review_host.c)도 `intent_review_host`에 등록했다.
exact control/증거·scope/purpose·principal 불일치·clock 역행/expiry·현재 pin/등록 거부·증거 변조·
private 파일 mode/symlink/경로 이탈을 다루는 코드를 추가했다. 모두 미실행이다.
실행용 fixture는 `/tmp/golem-intent-review-*`만 사용하도록 작성했다. **실제로 생성/실행하지 않았다.**

| 검사 | 이번 상태 |
| --- | --- |
| 코드 읽기·diff/문서 링크 검사 | 수행 범위만 별도 보고 |
| 빌드·컴파일·CTest·fixture·ASan/회귀 | NOT_RUN (사용자 HOLD) |
| native host adapter | 코드 연결 완료, 컴파일·실행 NOT_RUN; 실제 issuer 자료 등록 없음 |
| native 제품 보호 gate | QC3 후속, 미구현 |
| MCP/CLI/Owner UI 노출·설치·실제 Work | NOT_RUN / 미적용 |
| 최신 source inventory/M0 실행 재생성 | NOT_RUN; 새 함수·파일의 원장 반영은 검증 재개 시 수행 |
| commit/push·CI | NOT_RUN |

따라서 **QC1 개발 코드가 추가됐지만 QC1 exit gate는 아직 통과하지 않았다**.
host adapter 실행 검증과 제품 통합, 미지원 변경/해결 경로 확인 없이 QC1 전체 완료로 표시하지 않는다.
후속 QA PASS/완료 보증은 QC2–QC5가 구현·검증되기 전까지 기존 선언 gate 수준 그대로다.

### 2026-11-03 host adapter 작업의 확인 범위

텍스트 검사에서 `git diff --check`와 이 문서의 상대 링크 존재 확인은 통과했다.
기존 Intent Assurance 설계 7개 문서는 작업 전 SHA와 동일했다. 이는 컴파일/정적 분석기/회귀 실행 결과가 아니다.
Codex 캐시의 0.2.7 한 개와 Claude Golem prepare extension 한 개(실제 manifest 0.1.19)를
읽기 전용으로 확인했다. 설치 원장에 기록된 양쪽 D2 원본 hash도 일치했다.
Codex의 실제 `.mcp.json`은 `workpack-codex-discovery-20261102/apps-export` launcher를 참조한다.
이 관찰을 TopSolar 복원 완료나 현재 연결 정상 검증으로 바꾸지 않았고, 설정/설치/원장은 수정하지 않았다.
이번 host adapter는 두 설치본에 적용하지 않았다. 기존 정책·승인·Work·증거를 변경하는 명령,
빌드·테스트·native 도구 호출·commit/push는 수행하지 않았다.
