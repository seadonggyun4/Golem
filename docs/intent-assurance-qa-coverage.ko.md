# Intent Assurance: 기획 요구·경로별 QA·완료 연결 상세 계획

작성일: 2026-11-03 (Asia/Seoul). 정적 감사 기준: `a0de4e5441faa8586597f76ddde9a0240e35918c`.
상태: **Q1–Q5 채택 및 P0 설계 확정 / 구현·실행 검증 NOT_RUN / 실행 HOLD 유지**.
후속 [P0 확정 계약](intent-assurance-qa-p0-contract.ko.md)이 아래의 최초 미승인 제안 표시와
세부 미결 사항을 대체한다. 최초 제안은 비교 근거로 보존하며 runtime 적용 승인이 아니다.
이번 문서는 새 승인·schema 등록·실제 Work enrollment가 아니다. commit/push·설치 변경도 포함하지 않는다.
TopSolar 실험은 폐기 상태로 유지한다. 과거 증거·업무 자료·정책·승인·Work·COMMIT_UNKNOWN은 보존한다.

## 1. 기존 설계에 대한 위치와 중복 방지

이 문서는 [기존 계약](intent-assurance-contracts.ko.md) §2–7/9와
[기존 WBS](intent-assurance-delivery.ko.md)의 **P1b·P2·P3·P6을 상세화하는 보충 설계**다.
새 Intent 엔진이나 두 번째 요구사항 원장, 별도 Python 완료 판정기를 만들지 않는다.
대화에서 제안했던 P0–P6 번호를 독립 제품 단계로 추가하지 않는다. 아래 세부 작업에는 QC 번호를 쓴다.
기존 P4/P5 병렬·병합 기능을 이 작업으로 구현 완료 처리하지 않는다.

기존 원칙인 REQUIREMENTS → DESIGN → TASK_DECOMPOSITION → IMPLEMENTATION → TEST_DESIGN →
INTEGRATION → FINAL_VALIDATION의 **각 단계 원문 직접 대조**를 유지한다.
마지막 QA만 추가해 앞 단계의 요구 반전·제약 약화를 허용하는 축소안이 아니다.
분할/통합이 없는 경우도 stage 제외는 정확한 적용성 결정으로 남기며 자동 생략하지 않는다.

| 이번 요구 | 기존 설계/현재 기반 | 추가할 구체 사항 |
| --- | --- | --- |
| 기획 원문→요구사항 | contracts §2–3, IA-R01–R03; source/baseline 저장·coverage reader | requirement/constraint 참조의 실제 해석, 승인·의미 검토·ACTIVE reducer 연결 |
| 모든 단계 원문 대조 | contracts §5의 stage review/input manifest, A03–A05 | 경로·조건별 의무와 stage review subject의 정확한 연결 |
| 화면·API·배치·상태 전환 | 기존 oracle plan·trace graph 설계 | 적용성 표와 검증 의무의 닫힌 schema·완전성 규칙 |
| 누락/미검증 차단 | contracts §4–7의 obligation/barrier와 P2 gate | QA 실행 전 계획 coverage, 실행 후 결과 coverage, 완료 시 재평가 |
| 실제 결과 | 기존 execution gate/case·receipt·snapshot | obligation→case/result 참조와 결과 종류별 보증 분리 |
| QA PASS·완료 | 기존 completion + 제안 intent predicate | legacy QA PASS와 새 QA 수락 상태 분리; 우회 없는 native composition |
| 변경·분쟁 | 기존 impact/epoch·resolution close/carry | 변경별 재검증 집합·UNKNOWN barrier·현재성 검사 |
| MCP·Work Pack | 기존 D2/D4·준비 spool·native forwarding | 파생 조회/정확한 action 전달만; Pack bind/export는 의미 충족 증거 아님 |

## 2. 현재 구현과 미구현 경계

아래는 소스 읽기 결과이며 새 실행 검증 결과가 아니다. 과거 설계 문서의 중간 단계 상태를
현재 상태로 재사용하지 않는다. 특히 P1 journal 문서 도입부보다 후속 object-store/reader 구현을 우선한다.

| 근거 | 현재 확인한 기능 | 추가로 필요한 기능 |
| --- | --- | --- |
| [schema.c](../src/intent/schema.c), [schema.h](../src/intent/schema.h) | exact bytes/domain identity·원문 구간 union coverage·baseline 구조 | 원문 해석의 의미 타당성, source 외 참조 전체 검증, issuer/채택 |
| [object store 현황](intent-assurance-p1-object-store.ko.md), [journal.h](../src/intent/journal.h) | committed source/baseline publication·bounded reader·quota·owner lock | ACTIVE/의미 검토/제품 admission reducer. committed를 ACTIVE로 승격 금지 |
| [D01 host](intent-assurance-d01-host.ko.md) | common-dir 등록·pin·native authority 연결 | D02 인증 결정·reviewer policy·제품 쓰기 gate |
| [registry.c](../src/document/registry.c), [query.c](../src/workflow/query.c) | 문서 ID의 Work acceptance membership·선택 scope 요구 ID 후속 보존 | 기획 전체 및 baseline 전체에 대한 obligation completeness |
| [execution/model.c](../src/execution/model.c) | 개발 계획 요구 ID↔선언된 QA case 대조 | 경로·조건·oracle별 의무 대조 |
| [execution/runner.c](../src/execution/runner.c) | 정확한 case 결과·전 gate PASS·timeout/error·snapshot 검사 | 별도 의미/수동 검토와 합성하는 intent QA 수락 |
| [predicate_v1.c](../src/completion/predicate_v1.c) | 선언 gate/case PASS·동일 checkpoint·현재성·blocking issue 검사 | baseline/review/전체 의무의 현재 판정 |
| [predicate_roles.c](../src/completion/predicate_roles.c) | role 의무 + development predicate 재사용; documents 별도 보증 | 새 intent enrollment 우회 방지 |

현재 완료의 `DECLARED_GATES_ONLY`, `independent_review:false`를 유지한다.
Intent reader의 `references_unverified`, `semantic_review_required`, `adoption_unverified`,
`issuer_unverified`와 `execution_authorized:false`를 없애서 기능을 완성한 것처럼 만들지 않는다.

## 3. P0 계약 패키지: 구현 전에 동결할 것

아래 타입명/필드는 **제안 논리 모델**이다. 현재 CLI/MCP에서 사용할 수 있는 JSON이 아니다.
기존 domain registry에 이름만 추가해 지원으로 표시하지 않는다. 구현 시 closed schema·필드별 한도·
unknown/duplicate field 거부·exact bytes vector·reader 호환성 표를 함께 확정한다.

### 3.1 권위와 객체 관계

```text
기존 source/raw → requirement/constraint → baseline proposal
                                             ↓
                         review + trusted activation decision
                                             ↓
                            ACTIVE baseline (실행 승인 아님)
                                             ↓
                       적용성 표 + oracle plan + 검증 의무
                                             ↓
             기존 native QA receipt / 별도 인증된 scenario review
                                             ↓
                  intent QA 수락 판정 → versioned 완료 predicate
```

source/requirement/baseline의 root·bound 구분과 비순환 참조 규칙은 contracts §1을 재사용한다.
requirement 정의에 미래 baseline digest를 역기입하지 않는다. baseline activation은 원문 채택·
질문 해결과 별도 purpose이며, 정확한 proposal/decision/expected head/epoch에 결합한다.

| 추가/확장할 논리 객체 | 필수 결합 정보 | 권위 |
| --- | --- | --- |
| 적용성 manifest | baseline, 요구/제약 ID 전체, 경로별 REQUIRED/NOT_APPLICABLE/UNDECIDED, 이유·검토 ref | 기존 oracle-plan/trace의 구성 요소; 새 독립 승인 원장 금지 |
| 검증 의무 | stable obligation ID, requirement/constraint ref, 경로·정확한 대상 ref, 조건/예상 결과, oracle ref, stage | 검증해야 할 일; 결과나 승인 아님 |
| 실행 mapping | obligation ref, 기존 contract digest·gate ID/version·case ID, source/환경 범위 | 실행 계약의 보충 결합. 기존 계약 bytes 변조 금지 |
| 결과 association | exact obligation/mapping refs, evidence kind, receipt/case 또는 인증된 review ref, 관측 결과 | 실제 실행과 사람/agent 진술 구분 |
| QA assessment | baseline/epoch, Work/selection/generation, plan·mapping·artifact refs, 결과/미결 집합, policy version | native가 입력에서 계산. agent의 overall PASS 필드로 발급 금지 |

승인된 requirement 집합과 Work acceptance의 연결은 정확한 mapping으로 명시한다.
단일 Work 초기 범위는 baseline 전체를 담당하도록 권고한다. 분할 Work에는 전체를 다룬다는
주장을 허용하지 않는다. project 전체 완료는 별도 합성 계약 없이는 제공하지 않는다.
원문에서 아직 추출되지 않은 요구의 의미를 native가 자동 발견한다고 주장하지 않는다.

### 3.2 적용성과 완전성

- 각 요구/제약에는 화면·API·배치·상태 전환 네 경로의 적용성 행을 요구한다.
  CLI/library 등 네 경로 밖 동작은 닫힌 OTHER_LOCAL 분류와 정확한 대상을 추가하는 안을 검토한다.
  지원하지 않는 효과·대상은 UNSUPPORTED로 차단하며 네 경로에 억지로 포함하지 않는다.
- NOT_APPLICABLE은 이유·exact subject·검토·권한 있는 결정이 필요하다. 승인된 기획 범위에서
  요구를 제거하거나 의무를 완화하는 수단으로 사용하지 않는다. UNDECIDED는 관련 scope 차단.
- REQUIRED 경로마다 실제 대상(화면/route/job/상태·전이) 목록과 검증 의무를 명시한다.
  단순 'API 테스트 있음'은 충분하지 않다. 대상 inventory의 완전성도 원문/설계 직접 검토 대상이다.
- 정상·예외·권한·경계·전이 조건의 적용 여부와 기대 결과를 요구 성격별로 확정한다.
  고정된 case 개수만으로 충분성을 인정하지 않는다. 전역 제약은 적용 closure 전체에 연결한다.
- 한 case가 여러 의무를 다루는 것은 명시적 다대다 mapping과 검토가 있을 때만 허용한다.
  case 실행 결과 하나가 각 의무의 의미 충족을 자동 증명하지 않는다.
- mandatory obligation이 0이거나 전체 경로가 NOT_APPLICABLE인 경우 development 완료로
  자동 통과하지 않는다. 별도 documents/no-change 보증 계약 또는 scope 재검토가 필요하다.

### 3.3 상태와 PASS 의미

기존 QA receipt의 PASS는 변경하지 않는다. **새 계약을 등록한 Work의 공개 QA 수락**은
기존 실행 PASS + coverage + 필수 review/oracle + 현재성 + unresolved barrier를 합성한다.
실행만 성공했다면 `execution_status=PASS`, `intent_qa_status=BLOCKED`로 구분한다.
새 CLI/MCP/보고서가 이 상태를 무조건 'QA PASS'로 축약하지 못하게 한다.

| 입력 상태 | intent QA/완료 판정 |
| --- | --- |
| 필수 의무 모두 현재 유효한 PASS + 필수 검토 충족 | QA 수락 가능; 완료는 기존 predicate도 별도 충족 |
| 미연결·결과 없음·NOT_RUN·SKIP·UNKNOWN·UNSUPPORTED | BLOCKED, 누락 ID와 경로 반환 |
| FAIL·ERROR·timeout | 수락 불가; 원래 실행 receipt 보존 |
| stale 기준선/plan/소스/환경/권한 | STALE/BLOCKED; 자동 재실행 없음 |
| unresolved 의미 질문·분쟁·영향 미판별 | 관련 closure BLOCKED; GLOBAL/UNSCOPED는 보수적 확장 |
| 결과 유실·COMMIT_UNKNOWN | 불확실 상태 보존; 실패로 단정해 재호출 금지 |

현재 runner가 지원하지 않는 SKIP 등을 raw receipt에 새로 허용하는 계획은 아니다.
위 표는 새 합성 계층의 분류이며 runner의 닫힌 parser는 유지한다.

### 3.4 native 보호 지점과 lock/실패 계약

- 기준선·stage gate·QA accepted publish·completion finalize/current check를 같은 native
  판정으로 연결한다. 직접 C/CLI, MCP, role/document 완료 경로 모두 enrollment 검사 대상이다.
- 기존 `ex_contract/ex_inputs`, `wf_preconditions`, `co_evaluate`, `rc_completion`,
  reentry/approval/lease/fence/현재 snapshot 검사를 대체하지 않고 추가 조건으로 합성한다.
- source/baseline read는 기존 private authority reader를 재사용한다. Python은 조회/전달만 하며
  predicate·graph closure·issuer 정책 판정의 두 번째 구현을 만들지 않는다.
- D01 common-dir → authority lock 순서와 기존 Work handle-lifetime flock을 고려해 P0에서
  전체 lock 순서·native entrypoint·deadlock 회피를 명문화한다. 오래된 assessment를 lock 없이 재사용 금지.
- project journal과 Work journal은 원자적이지 않다. enrollment/결과 게시의 두 저장소 결합은
  exact pending marker·expected heads·명시적 receipt 확인을 설계하며 양쪽 완료 전 수락 차단한다.
  crash/불확실 상태를 자동 rollback/reconcile로 지우지 않는다.
- QA가 진행되는 동안 baseline/epoch가 변하면 늦은 결과는 historical observation으로만
  남길 수 있으며 accepted PASS/완료 게시 전 현재 입력을 재검사한다.
- question/resolution control lane은 unresolved 중에도 허용한다. product gate 차단 때문에
  질문을 해결할 수 없는 순환을 만들지 않는다. close/carry 의무는 기존 resolution 설계를 재사용한다.

### 3.5 버전·한도·호환성

기존 raw CAS hash와 intent schema-domain digest를 구분한다. 기존 승인 bytes/key/pin은 바꾸지 않는다.
D08의 무삭제·유한 quota·resolution/recovery 예약과 현재 parser 한도를 재사용한다.
새 객체의 필드별 최대 개수/bytes 및 최악 경로×조건×mapping 크기는 P0 산출물로 확정한다.
현재 execution은 최대 8 gate, gate당 64 case, Work acceptance는 최대 256개다.
더 큰 intent baseline 한도를 그대로 실행 가능 범위로 광고하지 않는다. 초과 시 차단하며
자동 truncation·quota 상향·무승인 Work 분할은 없다.

기존 proposal `golem.completion.intent.v1`을 재사용하되, 지원하는 completion 범위를 명시해야 한다.
기존 P6는 P5 병합/target 적용성에 의존한다. 초기 단일 Work 범위를 별도 profile로 제한할지
P5까지 기다릴지는 정책 선택 Q4다. merge 의무를 조용히 삭제하고 같은 full 보증을 선언하지 않는다.

## 4. 단계별 구현 범위와 완료 조건

각 exit는 **향후 증거 확보 조건**이며 지금 완료된 단계가 아니다. 실행 HOLD 중에는
계약/스키마 초안/정적 대조까지만 가능하다. 개발 및 테스트 실행은 후속 명시 지시가 필요하다.

| 상세 단계 | 기존 WBS | 구현 경계 | 완료 조건 |
| --- | --- | --- | --- |
| QC0 P0 계약 동결 | P0, ADR-D02/D03/D08/M01 | 객체/상태/error·권한 표, lock/두 journal 실패표, 버전 지원표·한도, Q1–Q5 결정 | 미결 정책을 기본 허용으로 처리하지 않음; schema golden·반례와 단계 의존성 리뷰 완료 |
| QC1 기준선/검토 연결 | P1a 후속·P1b | 기존 store 위 reference resolution·issuer/decision·stage review·resolution reducer | source 저장을 ACTIVE로 승격하지 않음; 위조/부분 답/누락 구간 차단 및 정상 resolution 진행 |
| QC2 의무/경로 모델 | P1b·P3 일부 | oracle-plan/trace 구성 요소와 순수 native validator, 요구↔경로↔조건↔case mapping | 전체 집합 대조, 중복/누락/N/A 남용/unsupported/한도 초과 거부 |
| QC3 enrollment와 보호 gate | P2 | 새 Work marker, native entrypoint·generation/epoch gate·현재성 | 구버전 writer fail closed, direct C/CLI/MCP 우회 불가, control lane 정상 진행 |
| QC4 실제 QA 합성 | P3 | 기존 receipt parser 재사용·typed evidence association·intent QA assessment | 선언 case 전부 성공해도 미검증 의무 있으면 BLOCKED; 정상 완전 사례는 수락 |
| QC5 완료/current 판정 | P6의 명시된 한정 범위 또는 full | 기존 development/role predicate + intent composition·버전 renderer | 기준선/소스/정책 drift 차단, historical 보존, old PASS 보증 승격 없음 |
| QC6 MCP/Owner 표시 | P3·P7b | bounded 조회·M2 초안·D4 exact action, owner review 표시 | native와 판정 일치, 자동 권한 없음, headless MCP 유지, 승인창 자동 증식 없음 |
| QC7 qualification | P8 | pure/native/CLI/MCP/package/client 실제 검증을 별도 기록 | 필수 실패·정상 진행성·호환성 증거 + 미검증 표; HOLD 해제 전 모두 NOT_RUN |

QC2 순수 모델 초안은 QC1과 독립적으로 검토할 수 있으나 mutation 노출은 QC3 이후다.
QC4 수락은 QC1의 검토·issuer·baseline과 QC3의 강제 gate가 없으면 완료 처리할 수 없다.
기존 general scheduler/merge 개발은 이 문서의 실행 범위에 자동 추가하지 않는다.

## 5. 수용 시나리오와 기존 A 행 연결

아래는 신규 QC 시나리오이며 기존 A01–A27을 대체하거나 번호를 재정의하지 않는다.
모든 시나리오는 **NOT_RUN**. 단순 실패 exit가 아니라 전후 head·native 상태·효과 횟수·
보존 evidence와 정상 진행성을 함께 확인해야 한다.

| QC 시나리오 | 기존 행 | 필수 판정 |
| --- | --- | --- |
| T01 원문 요구 10개 중 7개만 추출 | A03/A05 | 구간 gap 또는 필수 의미 검토의 OMISSION으로 차단. native 의미 자동 탐지로 보고 금지 |
| T02 ID 10개 모두 있으나 API/배치/상태 대상 누락 | A03/A04 | 적용성/의무 coverage 또는 원문 직접 review에서 차단 |
| T03 모든 경로를 N/A 또는 원문을 NON_NORMATIVE 처리 | A05/A09 | exact 권한·검토 없는 제외 거부; 합법적 N/A 정상 사례도 필요 |
| T04 QA 결과 case 누락/중복/다른 ID·SKIP·UNKNOWN | A06/A11 | raw parser 또는 intent result coverage 거부; accepted PASS 0 |
| T05 실행 PASS이나 review QUESTION_REQUIRED/INCONCLUSIVE | A06/A10 | 실행 사실 보존, QA 수락·완료 차단 |
| T06 QA 중/후 기획·oracle·소스·policy epoch 변경 | A08/A17/A26 | current 수락 차단, 과거 receipt 보존 |
| T07 동명이인 reviewer/producer self-approval/권한 폐기 | A09/A10 | trust class 검사 실패; 별도 대화만으로 독립 인정 금지 |
| T08 legacy finalize/role documents/direct native로 우회 | A11/A12 | 새 enrollment 강제; 기존 legacy golden은 원래 의미 보존 |
| T09 두 journal 중간 실패·disk full·결과 유실 | A20/A27 | pending/unknown 보존, 자동 재실행·중복 accepted event 0 |
| T10 정상 전 경로 충족·합법 N/A·부분 질문 해결 | A06a/A06b | 정확한 의무만 해결, carry 보존, 적법 범위 QA→완료 진행 |
| T11 한도 초과·분할 Work·미지원 경로 | A07/A27 | 명시 차단; 일부 성공을 project 전체 완료로 표시하지 않음 |
| T12 출력/설치·두 client 표시 차이 | A22/A26 | raw execution PASS와 intent QA 차단 동일 표시; client E2E와 fixture 구분 |

의미 검토 탐지 성능은 deterministic native conformance와 별도 평가한다.
기존 delivery §1의 독립 corpus/반례/false-positive·abstention 원칙을 재사용하며 수치 threshold는
정책 확정 전 임의 지정하지 않는다. TopSolar 자료를 corpus로 사용하지 않는다.

## 6. 필요한 정책 선택: 한 번에 검토할 Q 묶음

모든 권고는 **미승인 제안**이다. 이미 승인된 D01 등록 방식·D08 quota/무삭제 정책을 다시 묻거나
변경하지 않는다. 미결 부분만 아래에 모았다. 선택은 개발 계약 동결용이며 실제 Work 적용/실행 승인이 아니다.

| 선택 | 권고안 | 대안·영향 | 기존 ADR |
| --- | --- | --- | --- |
| Q1 요구 기준선·N/A의 권위 | owner 전용 exact decision; 모델은 draft만. local cooperative 보증을 명시 | 강한 인증/키 격리 요구 시 해당 host 구현 전 activation 차단. OS 동일 사용자만으로 사람 인증 주장 금지 | D02 |
| Q2 별도 검토·필수 stage | 기존 7 stage 원문 대조 유지. producer 자기검토를 필수 review로 인정하지 않음. reviewer provenance/권한 미확인이면 차단 | owner의 별도 검토를 어떤 stage에서 허용할지 명시. 단순 다른 모델/대화는 독립 증거 아님 | D03 |
| Q3 수동 시나리오 증거 | 초기에는 native 자동 QA + 별도 의미 review 지원. 수동 검증이 필수인 의무는 adapter 마련 전 UNSUPPORTED | 인증된 사용자 시나리오 assertion 추가 시 원문/대상/관측/검토자/현재성 계약 필요; 자동 실행 receipt로 변환 금지 | D03 |
| Q4 초기 완료 범위 | 새 단일 Work·고정 전체 baseline, LOCAL_NO_MERGE 한정 profile. merge/배포/project 전체 완료를 주장하지 않음 | 기존 P6 full predicate만 원하면 P4/P5 integration/target broker까지 선행. 기존 full 의미를 축소 재정의하지 않음 | D07, P6 |
| Q5 migration/기획 변경 | M01-A: 새 schema successor Work, 기존 acceptance 불변. 기존 Work는 관측-only | amendment schema는 replay/구형 writer 차단 전체 변경 필요. sidecar만 수정하는 안은 채택 불가 | M01 |

Q4 채택 시 독립 schema/predicate 식별자 또는 명시 support profile의 정확한 bytes를 QC0에서
확정하고 별도 native 검토를 거친다. 이름만 추가해 구형 reader가 새 보증을 해석하게 하지 않는다.
Q5 successor 생성·handoff는 자동 migration이 아니며 원래 Work의 active/unknown을 보존한다.

## 7. 이번 문서 작업의 검사·보존 경계

이번 작업은 기존 설계와 구현의 정적 대조, Markdown 상대 링크/구조, docs-only diff만 확인한다.
기존 7개 설계 원문은 수정하지 않고 문서 색인에 이 보충 설계 링크만 추가한다.
제품 빌드·단위/fixture/회귀·native CLI·MCP 호출·모델 E2E·설치·승인 적용·CI·commit/push는 하지 않는다.
현재 설치본이 이 제안을 지원한다고 주장하지 않는다. 기존 소스·정책·Work·과거 증거를 변경하지 않는다.

## QC1 후속 개발 기록

[QC1 구현 기록](intent-assurance-qc1-implementation.ko.md): private native 제어 코드 추가.
실제 issuer/제품 gate 연결과 실행 검증은 미완료이며 QC1 exit 통과를 주장하지 않는다.

QC6의 후속 구현 범위·선택적 host 계약·NOT_RUN 항목은 [QC6 구현 문서](intent-assurance-qc6-implementation.ko.md)에 기록한다. 기존 단계표의 완료 조건은 실행 검증 전 충족으로 표시하지 않는다.

QC7 작성된 회귀·23개 opt-in native 통합 시나리오 및 추가 실제 ENOSPC 2개/D01 writer 통합 경합 1개은 [QC7 qualification 원장](intent-assurance-qc7-qualification.ko.md)에서 구분한다. 전체 실행 상태는 HOLD/NOT_RUN이며 단계 완료 판정이 아니다.

전체 gate·저장·MCP 경로의 후속 [P0 정적 재대조](intent-assurance-qc1-qc7-static-review.ko.md): 확인 결함 수정 및 미충족 exit를 구분한다. 실행 HOLD 유지.

### Schema·golden 준비 현황

[전체 대조 준비 문서](intent-assurance-schema-golden.ko.md)와
[parser 매핑](schemas/intent-schema-native-map.json)에 QC 변경 경계 30개를 연결했다.
고정 corpus 324개와 opt-in pure native probe는 작성했지만 실행 HOLD이므로
native 동등성·문맥 결과 대조는 NOT_RUN이다. 구조 coverage를 QA/완료 검증 성공으로 집계하지 않는다.
