> 후속 상태: QC4 QA_ACCEPTANCE 소스 연결은 [QC4 문서](intent-assurance-qc4-implementation.ko.md) 참조. 아래 development/dispatch 설명은 QC3 범위다.

# QC2 참조 해소와 QC3 exact-request 허용 경로

2026-11-03, 미커밋 소스. **빌드·컴파일·fixture·회귀·E2E NOT_RUN(HOLD), 설치 미적용**.
P0 LOCAL_NO_MERGE의 development 및 QA dispatch만 대상으로 한다. QC4 QA ACCEPTED와
QC5 완료는 이번 허용 경로로 열리지 않는다. 테스트 통과·현재 제품 적용을 뜻하지 않는다.

## 실제 연결

- [qa_resolve.c](../src/intent/qa_resolve.c): 기존 `gi_qa_paths_inspect` 전체 집합 대조 후
  제공한 exact object bytes의 domain identity·project/Work·타입·대상·oracle 내용을 검사한다.
  `unsupported_references=0`은 아래 제한된 참조의 해소만 뜻하며 실행 권한은 여전히 false다.
- [review.c](../src/intent/review.c): 7 stage별 마지막 evidence/input/definitions/producer/reviewer/PASS를
  committed control replay로 추적한다. 선행 stage 재검토는 후행 stage PASS를 무효화한다.
  resolve는 전 stage를 무효화하며 unresolved·epoch 검사는 유지한다.
- [review_host.c](../src/intent/review_host.c): owner가 선택한 정확한 evidence bytes의 현재 정책,
  ACTIVE 역할·세션·producer/reviewer 분리·purpose·subject/input·원문 검토 진술을 검사한다.
  baseline 채택과 activation owner도 현재 policy/role로 재검사한다. 사람 신원·의미의 진실성 증명은 아니다.
- [product_access.c](../src/intent/product_access.c): exact owner-selected control/material을 소유하는
  private native scope를 Work handle에 연결한다. 모델 JSON의 ready/PASS boolean으로 열 수 없다.
  scope가 없거나 값이 다르면 기존 v3 차단을 유지한다.

## 순환 없는 typed 참조

다음은 baseline-independent root envelope(schema/project_id/work_id/created_by_assertion/body)를
사용한다. 정의의 acceptance_oracle_refs가 미래 baseline을 역참조하는 순환을 만들지 않는다.
root는 승인 의미가 없으며 현재 baseline·적용성·owner-selected material이 그 사용 범위를 결합한다.

| schema | body 및 지원 범위 |
| --- | --- |
| golem.intent.qa-artifact.v1 | media_type=text/plain, content(정확한 UTF-8), sha256(raw bytes) |
| golem.intent.qa-target.v1 | id, route, locality=LOCAL, locator(표시용), artifact_ref(domain digest) |
| golem.intent.qa-oracle.v1 | target_ref, condition, expected_outcome, stage, evidence_kind; 해당 의무와 모두 같아야 함 |
| golem.intent.qa-oracle-plan.v1 | oracle_refs; 실제 의무가 쓰는 oracle 집합과 일치, 중복/미사용/누락 거부 |

자동 파일 탐색·URL fetch·network·credential·binary/manual 관측 adapter는 추가하지 않는다.
locator는 파일 접근 권한이 아니다. 명시적으로 제공한 자료 최대4096개/전체32MiB/객체256KiB,
oracle plan의 직접 부모는 기존64개 이하이며 기존 graph/의무/QA 한도를 함께 적용한다. 원문 전체와 정의는 QC1 검사를 다시 통과해야 한다.
추가·미사용·변조된 객체도 거부한다. GLOBAL/UNSCOPED 제약은 project impact adapter가 없으므로 차단한다.

적용성 review_ref/decision_ref는 `golem.intent.review-host-evidence.v1`의 **domain digest**다.
해당 bytes가 host의 owner-selected bundle에 있어야 한다(그 bundle의 저장 pin은 기존 raw SHA).
purpose=APPLICABILITY_REVIEW/APPLICABILITY_DECISION,
body={subject_digest,verdict:PASS,original_source_reviewed:true}를 사용한다.
subject는 domain 표지 `golem.intent.applicability-subject.v1`, baseline_digest,
requirement_ref/route/target_refs/disposition/rationale를 고정 순서로 담은 native `ex_hash` identity다.
row의 review/decision 참조 자체는 subject에 포함하지 않아 self-hash 순환이 없다.
reviewer는 현재 등록된 별도 producer/reviewer여야 하며 decision은 현재 OWNER다.
QC1 stage의 evidence_digest는 기존 raw SHA 계약을 그대로 유지한다.

## exact-request scope와 현재성

`gi_product_access_open`은 검토된 host와 authority fd, control/material bytes를 받는다.
두 JSON은 복사 파싱해 수명 동안 보유하며 host/fd는 caller가 close까지 보존한다.
`gi_product_access_close` 또는 Work handle close로 해제된다. 새 MCP/CLI endpoint는 노출하지 않는다.

control envelope: schema=golem.intent.product-access.v1, project_id, work_id, baseline_digest, body.
body의 정확한 필드:

- material_sha256, work_spec(native compact digest), work_sequence(event_count), work_head
- review_epoch(QC1 revision), baseline_operation, baseline_request
- boundary(DEVELOPMENT/QA_DISPATCH), channel(SESSION/EXECUTION), request_digest(raw SHA), input_kind

material은 같은 envelope의 schema=golem.intent.product-material.v1이며 body는
baseline(원문 JSON 문자열), sources[{control,text}], definitions[원문 문자열],
applicability, obligations, mapping, execution_contract(각 원문 문자열), objects[typed 원문 문자열],
native_inputs(기존 native 생성 input manifest)다. 전체 raw SHA가 stage input_manifest이므로
모든 stage는 정확히 같은 완전한 material에 대한 검토여야 한다. 일부 material 수신은 인정하지 않는다.

1. 현재 host registration/baseline/policy pin과 Work marker를 대조한다.
2. 양쪽 journal의 enrollment receipt/payload를 읽기 전용으로 다시 대조한다.
3. QC2 typed 참조·적용성 owner/reviewer 자료를 해소한다.
4. 요구 ref→enrollment acceptance ID→실제 gate/case의 requirement_id를 정확히 대조한다.
   기존 `ex_inputs`로 현재 문서·selection/source manifest를 다시 구성하고 native_inputs와 exact 대조한다.
   Work event sequence/head, 고정 execution contract도 대조한다.
5. authority를 열어 현재 baseline control을 replay한다. ACTIVE·미결0·정확한 activation·review_epoch,
   개발의 선행3 stage 또는 QA의 선행5 stage PASS와 현행 issuer 권한을 검사한다.
6. authority lock을 해제한다. 실제 요청은 선택된 channel/raw request SHA와 같아야 하며 scope당 한 번만
   진입한다. 실행 중 기존 승인 재검사와 결과 게시에서도 현재 stage/pin/Work 상태를 다시 검사한다.

lock 순서는 기존 D01 common-dir → Work handle → 짧은 authority다. 긴 QA 동안 authority lock을
유지하지 않으며 기존 Work lock·native 실행 승인·lease·snapshot·보호 검사도 제거하지 않는다.
`review_epoch`는 project-wide constraint epoch로 승격하지 않는다. 이 local profile에 없는 전역 변경은 미지원이다.

실행 prepare/finish는 DEVELOPMENT와 development-result 입력을, run은 QA_DISPATCH와 qa-result 입력을
요구한다. SESSION도 DEVELOPMENT·development-result 입력이 준비된 local 경로로 제한한다.
개발 계획 이전의 자유로운 session bootstrap은 이 scope가 대신 허용하지 않는다.
다른 contract/checkpoint·새 request·새 Work·후행 stage 부족·expiry·revocation은 차단한다.
현재 native source/snapshot 검사는 그대로이며 자료의 의미적 충분성은 검토자의 책임 있는 진술이다.

제품 publication은 선택한 session request의 정확한 record 또는 선택한 prepare/finish/run 결과만 허용한다.
범용 publication grant·role/승인 발급·candidate/workspace·merge 허가는 없다.
문서 관측은 기존대로 보존되지만 ACCEPTED/DONE으로 승격하지 않는다. QA 중 상태가 변하면 결과 bytes는
기존 불확실/부분 기록 계약으로 남으며 자동 재실행하지 않는다.

## 검증 상태·남은 범위

작성한 코드:

- [로컬 typed 참조 golden fixture](../tests/fixtures/intent/qa-resolved-local.json)
- [resolver 테스트](../tests/c/test_intent_qa_resolve.c): 정상 해소에서도 권한 false, 참조 누락·중복 거부·실패 출력 보존
- 기존 host 테스트: stage/input/registration mismatch·현재 activation 목적 거부
- 기존 QC1 테스트: 3 stage replay 후 선행 재검토가 후행 PASS를 무효화하는 사례

**전부 실행하지 않았다.** 실제 scope→native 개발/QA의 성공 E2E, 장애 주입·경쟁·계약별 광범위 회귀는
HOLD 해제 뒤 필요하다. 따라서 코드 연결과 검증 완료는 다르다.
QC4의 실제 의무 결과·수락은 [QC4 구현](intent-assurance-qc4-implementation.ko.md)의 별도 exact QA scope로 연결했다(실행 NOT_RUN). QC5 완료는 후속 [QC5 구현](intent-assurance-qc5-implementation.ko.md)의 별도 COMPLETION scope에 연결했다. 실행 검증은 NOT_RUN이다.
기존 client 설치·정책·승인·TopSolar·Work·증거는 변경하지 않았고 commit/push도 하지 않았다.
