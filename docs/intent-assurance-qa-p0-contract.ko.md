# QA coverage P0: 채택 결정과 확정 개발 계약

2026-11-03 (Asia/Seoul). 소스 기준 `a0de4e5441faa8586597f76ddde9a0240e35918c`.
상태: **Q1–Q5 사용자 채택 / LOCAL_NO_MERGE P0 설계 계약 확정 / 구현·실행 검증 NOT_RUN**.
사용자 결정: “제시한 정책 5개는 권고안대로 채택하고 P0 계약을 구체적으로 확정”.
이는 개발 설계 결정이다. native assertion·실제 정책 적용·Work 생성·승인 발급·설치·실행 권한이 아니다.
기존 정책/승인 bytes/key/pin·Work·증거·COMMIT_UNKNOWN은 보존한다. 실행 HOLD와 TopSolar 실험 폐기를 유지한다.

## 1. 결정과 적용 우선순위

[QA 상세 계획](intent-assurance-qa-coverage.ko.md)의 Q1–Q5를 아래 범위에서 채택한다.
[기존 Intent 계약](intent-assurance-contracts.ko.md)의 원문·stage·control/protected·resolution·
impact 원칙은 그대로 유지하며, full P6/merge 보증을 이 문서로 축소하지 않는다.
기존 설계 원문은 역사적 snapshot으로 보존한다. 상충하는 QA 보충 계획의 미승인 표시는 이 후속 기록이 대체한다.

| 결정 | 확정 내용 | 보증 경계 |
| --- | --- | --- |
| Q1 / D02 한정 | owner 전용 exact decision, agent draft와 분리. LOCAL_COOPERATIVE trust class | 동일 uid의 적대적 접근을 막는 사람 신원 인증/서명 보증 아님. 강한 인증 정책은 미지원 |
| Q2 / D03 | 기존 7 stage 원문 직접 대조. producer 자기검토는 필수 review로 인정하지 않음 | trusted host가 등록한 별도 reviewer principal/role·세션·대상·입력 전달 provenance 필요. 모델 이름/새 대화만으로 독립 판정 금지 |
| Q3 / D03 | native 자동 QA + 별도 의미 review. 필수 수동 시나리오 관측은 adapter 전까지 UNSUPPORTED | owner의 의미 검토가 자동 QA receipt나 수동 제품 실행 증거를 대신하지 않음 |
| Q4 / P6 한정 | LOCAL_NO_MERGE, 단일 새 Work가 고정 baseline 전체를 담당 | merge·배포·분할 Work 합성·project 전체 완료 없음. full intent predicate와 별도 identity |
| Q5 / M01-A | immutable acceptance 유지. 의미/범위 변경은 successor Work | 원 Work 제자리 migration·자동 handoff·old QA 이전 금지 |

이 선택은 D02/D03의 모든 플랫폼·강한 issuer·수동 adapter 문제를 해결했다는 뜻이 아니다.
owner는 의미 review를 할 수 있지만 해당 산출물의 producer로 등록된 동일 principal이면 필수 독립 review로 인정하지 않는다.
provenance 확인이 안 되면 reviewer를 추정하지 않고 차단한다. 승인과 review는 서로 다른 purpose다.

## 2. P0 불변조건

1. 기준은 exact source bytes와 채택 범위다. 요약/추출 결과는 원문을 대체하지 않는다.
2. baseline 저장 commit은 ACTIVE·승인·실행 권한이 아니다. ACTIVE 상태에도 unresolved barrier가 남을 수 있다.
3. baseline의 모든 requirement/constraint를 담당한다. 일부 scope 선택으로 전체 완료를 우회할 수 없다.
4. 필수 검증 의무가 결과·현재성·검토 중 하나라도 부족하면 QA 수락/완료를 막는다.
5. legacy 실행 PASS는 역사적 native 사실로 보존한다. 새 QA 수락과 동일하지 않다.
6. 읽기/초안/질문·resolution control은 관련 product gate 차단 중에도 가능하다.
7. 두 journal의 commit을 원자적으로 주장하지 않는다. 미확정 binding/acceptance는 차단 상태다.
8. 직접 C/CLI·MCP·role/documents 완료 모두 같은 새 enrollment gate를 통과한다.
9. 기존 D1/D2/D4 및 native 승인·lease·lock·fence·snapshot 검사는 추가 조건과 함께 계속 적용한다.
10. 모든 결과는 선언된 지원 범위의 수락이다. 의미적 무결점·독립 신원·전체 제품 완성의 증명이 아니다.

## 3. 타입·참조·한도 계약

다음은 **구현할 닫힌 논리 계약**이며 현재 API 입력이 아니다. 기존 JSON/domain registry는 수정하지 않는다.
구현 PR에서 기계 판독 JSON Schema·C parser·golden bytes를 함께 제공하고 이 표와 대조해야 한다.
새 v1 객체는 기존 bound envelope의 schema/project_id/work_id/created_by_assertion/baseline_digest/body를 따른다.
필드 누락/unknown·중복 key·잘못된 UTF-8·범위 초과는 거부한다. optional은 아래 명시한 null만 허용한다.
공통 object identity는 기존 domain+길이+exact bytes 방식, CAS는 기존 raw SHA-256이다.

| 객체/identity | body의 닫힌 필드와 의미 |
| --- | --- |
| `golem.intent.qa-applicability.v1` | `rows`: 각 행 `requirement_ref, route, target_refs, disposition, rationale, review_ref, decision_ref`. route=UI/API/BATCH/STATE_TRANSITION/OTHER_LOCAL. disposition=REQUIRED/NOT_APPLICABLE/UNDECIDED. 미결 draft의 review/decision만 null 허용 |
| `golem.intent.qa-obligations.v1` | `applicability_ref, oracle_plan_ref, obligations`; 각 의무 `id, requirement_ref, route, target_ref, condition, expected_outcome, oracle_ref, stage, evidence_kind`. condition=정확한 비어 있지 않은 조건 설명, stage=기존 7 stage, evidence_kind=NATIVE_QA/SEMANTIC_REVIEW |
| `golem.intent.qa-mapping.v1` | `obligations_ref, execution_contract_digest, mappings`; 각 행 `obligation_id, gate_id, gate_version, case_id`. SEMANTIC_REVIEW 의무는 실행 mapping에 넣지 않고 기존 review 참조로 해소 |
| `golem.intent.qa-assessment.v1` | `input_tuple, execution_receipt_ref, review_refs, obligation_results, blockers, execution_status, intent_qa_status, assurance`. native 파생 결과이며 agent가 overall status를 발급하지 못함 |
| `golem.intent.work-enrollment.v1` | `baseline_ref, work_spec_digest, requirement_mapping, support_profile, policy_ref, activation_decision_ref, predecessor_ref`; predecessor만 최초 Work에서 null. 모든 baseline 요구/제약을 exact Work acceptance ID와 연결 |

requirement_ref/target_ref/oracle_ref/review_ref는 typed object digest다. 기존 source/requirement/trace/oracle/
review 객체를 재사용하며 임의 파일 경로·URL 문자열을 권위 ref로 받지 않는다. 신규 타입은 별도 원장이 아니라
기존 authority의 승인된 typed publication에 연결한다. 해당 참조 타입의 native validator가 없으면 미지원 차단한다.

`input_tuple`은 baseline·constraint_epoch·policy·applicability·obligations·mapping·Work identity/selection/
generation·source snapshot/checkpoint·artifact inventory·oracle/reviewer policy refs를 고정한다.
관측 project head는 별도 진단 값이다. 결과 게시 자체가 head를 바꾸었다는 이유로 즉시 자기 결과를 stale로
만들지 않는다. freshness는 관련 tuple/의무의 변경으로 판정하고 mutation CAS는 expected head를 사용한다.

`obligation_results` 행은 obligation_id, evidence_refs, status(PASS/FAIL/ERROR/NOT_RUN/UNKNOWN/STALE/UNSUPPORTED)를
갖는다. N/A는 결과 상태가 아니라 적용성 결정이다. blockers는 code·subject ref·원인 ref를 갖는다.
`intent_qa_status`는 ACCEPTED/BLOCKED/STALE/UNCERTAIN이며 사용자 표시 QA PASS는 ACCEPTED일 때만 허용한다.
raw execution_status의 PASS/FAIL/ERROR는 기존 receipt에서만 얻고 미실행은 null이다.
assurance는 LOCAL_COOPERATIVE_REVIEWED_NOT_PROVEN이다. 기존 independent_review 필드를 임의 true로 바꾸지 않는다.

### 유한 한도와 범위

기존 D08·quota.c와 execution 한도를 늘리지 않는다. 이 profile의 동작 한도는 아래의 교집합이다.

- control 객체 256KiB 이하, UTF-8 source 각16MiB·baseline 총64MiB 이하.
- baseline requirement+constraint 중 Work acceptance로 추적할 항목 합계256개 이하. 더 큰 기존 intent
  proposal은 저장 가능해도 이 profile로 실행할 수 없다. 자동 분할 없음.
- 항목마다 다섯 route 행을 정확히 하나씩 요구: 최대1280행. 각 target refs는 최대64개이며
  전체 trace node4096/edge16384/parent64 한도를 함께 적용한다.
- obligations 최대4096개, mapping edges 최대16384개. 한 객체 bytes 상한이 먼저 걸리면 거부한다.
  NATIVE_QA는 기존 최대8 gate×64 case를 재사용하며 공유 case는 명시적 다대다 mapping이 필요하다.
- identifier는 기존 native ID parser를 재사용하고 refs는 lowercase64 hex digest다.
  condition/expected_outcome/rationale은 각각 UTF-8 1–4096bytes, empty/placeholder-only 금지.
- unresolved 최대256, review observation 최대256 등 기존 한도를 유지한다. 의미 불명확성은 문자열 길이로 해결하지 않는다.
- read 응답의 기존 한도를 넘는 경우 bounded cursor로 목록을 조회할 수 있지만 불완전 수신을
  review 완료로 인정하지 않는다. complete delivery manifest가 필수다.
- quota lane/예약·no-delete·no-auto-rollover 유지. 한도 초과는 LIMIT_EXCEEDED이며 권한/수치 자동 변경 없음.

새 per-object 수치는 기존 상한 안에서의 이 profile 설계 한도이며 production quota 변경 승인이 아니다.
기존 requirement1024 상한을 전역256으로 축소하거나 파일을 migration하지 않는다.

## 4. 적용성·의미·결과 완전성

모든 baseline 항목의 모든 route 행이 있어야 한다. REQUIRED는 하나 이상의 정확한 target과 의무가 필요하다.
NOT_APPLICABLE은 target_refs가 빈 배열일 수 있으나 정확한 이유와 별도 review/owner decision이 필수다.
UNDECIDED draft는 저장할 수 있지만 관련 product dispatch/QA 수락/완료는 차단한다.
OTHER_LOCAL은 CLI/library 등 로컬 대상의 누락을 막기 위한 분류이지 임의 실행 capability가 아니다.
필수 remote/network/수동 관측을 이 분류로 우회할 수 없다.

정상·예외·권한·경계·전이 조건의 충분성은 원문·설계 대상 inventory와 함께 TEST_DESIGN review에서 판단한다.
native는 집합/참조·검토 필요성·판정의 권한/현재성을 강제하며 자연어 의미의 정답을 증명하지 않는다.
모든 route N/A인 항목은 의미 review가 정당성을 확인해야 하며 전체 Work의 NATIVE_QA 의무가0인 경우
이 development profile로 완료 불가다. documents/no-change 완료로 자동 전환하지 않는다.

PASS의 필수 조건: 모든 의무에 정확한 현재 evidence가 있고, NATIVE_QA는 연결된 모든 case PASS,
SEMANTIC_REVIEW는 필요한 별도 review PASS, 해당 closure unresolved=0이다.
결과가 하나라도 없거나 불완전하면 집계 평균·다수결·coverage 비율로 보충하지 않는다.
blocking:false·새 ID·다른 Work·구버전 predicate를 이용한 우회도 거부한다.

## 5. 단계 gate와 순환 방지

| 보호 경계 | 필요한 선행 검토/자료 | 아직 요구하지 않는 미래 결과 |
| --- | --- | --- |
| 개발 착수 | ACTIVE 기준선, REQUIREMENTS/DESIGN/TASK_DECOMPOSITION review, 개발 대상·의무 준비, scoped barrier 해소 | 구현/QA 결과·FINAL_VALIDATION |
| QA dispatch | 위 조건 + IMPLEMENTATION/TEST_DESIGN review, 고정 mapping/실행 승인·snapshot | QA 실행 결과·최종 완료 |
| intent QA 수락 | native 실행 receipt, 모든 의무 결과, INTEGRATION/FINAL_VALIDATION review, 현재 tuple·barrier | completion receipt |
| 완료 finalize/current | intent QA ACCEPTED + 기존 development/role/reentry/currentness 조건 | 별도 merge/deploy 증거를 이 profile에서 주장하지 않음 |

각 stage는 원문을 직접 수신해야 한다. TASK_DECOMPOSITION은 단일 task 설계의 적정성,
INTEGRATION은 단일 local artifact의 구성 검토를 수행한다. stage를 임의 생략하는 것이 아니다.
FINAL_VALIDATION은 raw QA receipt를 검토한 뒤 발급하며 아직 없는 intent QA ACCEPTED를 선행 요구하지 않는다.
qa-result 문서의 **관측 기록**은 실패/미검증 중에도 보존할 수 있다. 그 등록을 accepted publish/PASS로
혼동하지 않는다. gate는 제품 수락 전이에 적용하며 실패 기록·질문 해결을 막지 않는다.

## 6. lock·journal·현재성 계약

초기 profile은 보수적 직렬화를 채택한다. 기존 Work writer lock을 QA 중 풀지 않는다.
모든 신규 복합 경로의 순서: **D01 common-dir guard → Work handle lock → authority lock**.
authority lock을 보유한 상태에서 Work lock을 새로 기다리는 경로는 금지한다.
D01 기존 common-dir→authority만 사용하는 경로는 Work를 열지 않으므로 유지 가능하다.
callback 재진입/handle 공유/역순 lock은 금지하며 contention은 bounded 실패/대기로 처리한다.

authority lock은 짧은 gate 검사·intent 기록 경계에만 유지한다. 긴 QA·reviewer 호출 전에 해제한다.
Work lock 유지 중 authority 재획득은 같은 순서다. 게시 시 epoch/관련 tuple/권한을 다시 대조한다.
project-only control은 Work lock을 기다리지 않고 변경/barrier를 기록할 수 있다. 그 사이 실행된
과거 epoch 결과는 historical로 남기며 현재 accepted publish를 허용하지 않는다.
이미 시작한 외부 효과를 취소했다고 주장하지 않으며 기존 supervisor/lease 취소 계약을 유지한다.

enrollment는 Work의 새 불변 schema marker로 시작하고, authority binding→Work acknowledgment를
exact request/expected heads로 기록한다. 둘 중 하나만 존재하면 ENROLLMENT_PENDING으로 차단한다.
QA acceptance도 prepared intent→Work의 exact observation receipt→authority acceptance 순서로
연결하고, 모든 참조 검증 전에는 accepted가 아니다. reader는 현재 연결과 tuple을 다시 검사한다.
두 journal 중간 실패는 보존하며 자동 재시도·repair·rollback하지 않는다. 명시적 복구는 별도 계약 대상이다.
이 설계의 deadlock/원자성/진행성은 QC7 시험 전 보장된 구현 결과가 아니다.

## 7. 버전과 변경

신규 Work schema는 **version3 예약**, 기존 v1/v2는 불변이다. 구현 착수 시 실제 registry 충돌이
발견되면 다른 번호로 임의 교체하지 말고 문서를 개정한다. v3는 기존 필드에 intent_binding(기존 authority registration identity·baseline_ref·policy_ref)과
support_profile=LOCAL_NO_MERGE를 필수로 한다. 미래 enrollment digest는 spec에 넣지 않는다.
고정 spec digest를 참조하는 enrollment를 후속 게시하고 Work acknowledgment가 이를 연결한다.
이 순서로 spec↔enrollment hash 순환을 피하며 pending 동안 모든 protected mutation을 차단한다.
현재 구형 parser의 version 거부를 유지하고 조용한 legacy fallback은 없다.

신규 predicate identity: `golem.completion.intent.local-no-merge.v1` ([QC5 소스 구현](intent-assurance-qc5-implementation.ko.md), 실행 NOT_RUN).
기존 제안 `golem.completion.intent.v1`의 full P5/P6 target CAS·merge 보증과 다르다.
새 predicate는 기존 development/role predicate를 내부 합성하되 외부의 legacy finalize 우회를 거부한다.
소스의 native completion dispatch에 연결했으며 설치·배포본 지원이나 실행 검증 완료를 뜻하지 않는다.

기획/의미/acceptance 변경은 새 baseline+successor Work가 원칙이다. 원 Work의 approval/QA를 복사해
current로 간주하지 않는다. 같은 Work에서는 의미·요구 집합을 바꾸지 않는 provenance/설명 보충만
별도 reviewed change로 허용하고 관련 review를 재검사한다. 분류가 불명확하면 successor 또는 질문으로 차단한다.
QA 계약 변경·새 소스는 기존 재검증/새 정확한 승인 계약을 따르며 과거 결과 자동 재실행 없음.

## 8. 충돌·누락 검토 결과

| 확인 지점 | 조정/유지한 내용 |
| --- | --- |
| 기존 ACTIVE에도 unresolved 가능 | ACTIVE 자체를 QA PASS로 취급하지 않음. protected closure에서만 의무0 요구 |
| 기존 7 stage vs QA만 강화 | 7 stage 유지·선행표로 순환 제거 |
| 기존 full P6의 P5 선행 | 별도 local-no-merge predicate; full 구현/완료를 주장하지 않음 |
| source/baseline store 이미 구현 | 재구현하지 않고 issuer/review/활성화/ref resolver만 추가 |
| 기존 schema-1/2 직접 writer | 새 Work version3 예약, sidecar-only gate 금지 |
| Work lifetime lock vs 짧은 project guard | Work lock 유지, authority 짧게 해제·재검사; 역순 acquisition 금지 |
| QA PASS와 수동/의미 review 혼합 | raw execution_status와 intent_qa_status 분리, unsupported 수동 의무 차단 |
| 요구1024 vs Work acceptance256 | 초기 profile 합계256, 전역 기존 한도 변경 없음 |
| 기존 UI/API/BATCH/STATE에 없는 CLI/library | OTHER_LOCAL 닫힌 분류 포함, capability 추가 없음 |
| 모든 항목 N/A로 빈 성공 | native QA 의무0 development 완료 거부 |
| 자기 publication이 head 변경 | 관련 tuple freshness와 mutation expected head 분리 |
| spec↔enrollment digest 순환 | spec의 기존 authority/baseline/policy 고정 → enrollment의 spec digest → Work acknowledgment 순서 |
| TopSolar/기존 증거 | 실험 폐기·HOLD 유지, local 자료·원본 설계 변경 없음 |

P0 설계 exit는 이 문서와 Q 결정 기록으로 충족한다. **구현 exit·실행 검증 exit는 미충족**이다.
기계 판독 schema/parser 일치·lock 경쟁·두 journal crash·상한·native/MCP 동등성은
[QC0–QC7 및 T01–T12](intent-assurance-qa-coverage.ko.md)의 향후 증거가 필요하다.
현재 정책 추가 선택은 없다. 지원 범위 확장·strong issuer·수동 adapter·merge·quota 변경이 필요해지면
별도 변경 계약으로 검토하며 이번 승인에 포함시키지 않는다.
