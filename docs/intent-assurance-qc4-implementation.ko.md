# QC4 실제 결과·현재성·QA 수락 연결

상태: 소스 구현, 검증 실행 **HOLD / NOT_RUN**. 빌드·fixture 실행·회귀·실제 Work 검증·client 설치는 수행하지 않았다. 이 문서는 통과 증명이 아니다. QC5 완료 predicate는 후속 [QC5 구현](intent-assurance-qc5-implementation.ko.md)에 연결했다. MCP/CLI 배포와 실행 검증은 완료 범위가 아니다.

## 기존 계약과 연결

[P0](intent-assurance-qa-p0-contract.ko.md), [QC3 exact scope](intent-assurance-qc3-access.ko.md)를 따른다. 기존 native `ex_load`의 receipt/CAS/marker 확인과 `ex_receipt_current`의 문서·checkpoint·snapshot·inventory 확인을 재사용한다. QA를 재실행하거나 agent 진술로 native 실행 상태를 채우지 않는다.

- `gi_qa_assess`: 선택한 정확한 요청의 결과 합성. 의무가 전부 PASS여도 미게시 상태는 BLOCKED이다.
- `gi_qa_accept`: exact owner scope 아래 authority 준비 → Work 관측 → authority 수락을 연결한다.
- `gi_qa_current`: 저장 요청을 새 exact scope로 읽고 실제 결과·현재성·두 journal을 다시 대조한다. 저장된 상태만 읽어 ACCEPTED라 하지 않는다.
- 내부 API는 D01 guard→Work writer lock→짧은 authority lock 순서를 전제로 한다. 조회도 일관된 Work lock을 요구하지만 native 실행·게시를 하지 않는다.

QC3 control은 boundary=`QA_ACCEPTANCE`, channel=`QA`, input_kind=`qa-result`와 request SHA를 pin한다. `QA_INSPECTION`은 첫 다섯 stage를 확인하는 내부 평가 경계이며 Work 관측 게시 권한이 아니다. 게시 경계는 일곱 stage와 최종 결과를 모두 확인한다.

## 정확한 요청

닫힌 `golem.intent.qa-request.v1` 객체: `schema`, `operation`(assess/accept), `execution_receipt_ref`(digest/null), `semantic_reviews`, `authority_sequence`, `authority_head`, `prepare_operation`, `accept_operation`.

semantic_reviews의 행은 `{obligation_id, review_ref}`이며 중복/미사용 참조를 거부한다. 최대 254개와 최종 stage 두 참조로 review_refs 256개 상한을 유지한다. 두 publication operation은 서로 달라야 한다. 요청 bytes를 복사하여 외부 host callback 중 원본 변경의 영향을 차단한다. 동일 scope의 재호출은 허용하지 않는다.

## 결과와 현재성

NATIVE_QA 의무는 고정 contract의 gate ID/version/case와 실제 native receipt의 관측을 연결한다. 모든 연결 case가 필요하며 누락·중복·추가·모순된 PASS는 UNKNOWN 또는 차단이다. FAIL/ERROR는 수락되지 않는다. receipt가 없으면 execution_status=null, 관측은 NOT_RUN이다.

SEMANTIC_REVIEW는 owner가 선택한 host evidence의 typed domain digest를 대조한다. purpose=`QA_SEMANTIC`, 현재 ACTIVE producer/reviewer와 분리된 session, 정확한 subject, 원문 검토 표시를 검사한다. body는 `{subject_digest, verdict, original_source_reviewed}`이며 INCONCLUSIVE는 UNKNOWN이다. 이는 LOCAL_COOPERATIVE 검토이며 독립적인 사람 인증이나 진실성 증명이 아니다.

최종 두 stage는 material SHA와 **정확한 QA receipt**를 묶은 `golem.intent.qa-review-input.v1` native digest를 사용한다. semantic subject는 같은 입력에 정확한 obligation을 추가한 `golem.intent.qa-semantic-input.v1` digest다. 두 digest는 native JSON serializer로 생성하며 임의 JSON 재직렬화 hash를 대신 쓰지 않는다.

assessment는 baseline/policy, review epoch, material, applicability/obligations/mapping, Work spec/selection, document generation, source inputs, checkpoint, snapshot inventory, oracle plan, reviewer policy를 연결한다. LOCAL 불변 baseline만 지원하므로 constraint_epoch=0은 해당 고정 baseline의 값이며 전역 constraint 최신성을 주장하지 않는다. GLOBAL/UNSCOPED는 계속 차단한다.

원래 Work head와 정확히 자기 관측 하나가 추가된 head만 허용해 자기 publication으로 인한 거짓 stale을 방지한다. 다른 Work 변화·review/입력 변경은 차단한다. 현재성은 조회 시점의 native 관측이며 이후 외부 파일 변경까지 영구 보장하지 않는다.

## 수락 publication

1. authority에 exact request/assessment와 이전 Work head/sequence를 준비 기록한다.
2. native CAS·guarded event publication으로 `intent-qa-observation`을 Work에 추가한다.
3. authority에서 정확히 다음 sequence에 prepared event와 Work frame을 연결한다.
4. 현재 결과를 다시 계산하고 세 기록의 exact payload와 일치할 때만 반환 상태를 ACCEPTED로 바꾼다.

Work에 저장되는 candidate assessment는 BLOCKED이며 단독으로 수락 증거가 아니다. 중간 실패·응답 유실은 보존하고 자동 재시도·repair·rollback하지 않는다. 게시 시도 후 오류는 store를 poisoned로 닫도록 요구한다. 재개는 새 읽기 scope로 상태를 확인하는 것뿐이며 누락 수락을 자동 완성하지 않는다. 두 journal의 원자적 commit을 주장하지 않는다.

## 검증 및 남은 범위

`test_intent_qa_result.c`에 정상 case 합성, 실행 없음, 누락/중복 case, 모순된 PASS, FAIL/ERROR, gate 불일치, receipt/semantic review digest 분리 fixture를 작성하고 CMake에 등록했다. **전부 NOT_RUN**이다.

두 journal의 성공·부분 실패·crash·응답 유실, 변경 경합, revoked reviewer, snapshot drift, 전체 QC1~QC4 연계 및 컴파일 검증은 HOLD 해제 후 필요하다. 소스 대조와 `git diff --check`는 실행 검증을 대체하지 않는다. QC5 완료 gate는 별도 exact COMPLETION scope에서만 연결되며 raw QA PASS를 제품 QA 수락이나 완료로 승격하지 않는다.

기존 설치·정책·승인·Work·증거와 과거 설계 원문은 변경하지 않는다. commit/push 하지 않는다.

## 이번 소스 작업의 보존 확인

읽기 전용 파일 대조에서 Codex cache의 Golem 0.2.7 한 개와 Claude extension의 Golem prepare 0.1.19 한 개를 확인했다. 양쪽 원장에 기록된 D2 파일 SHA가 일치했고, 기존 Intent Assurance 설계 원문 7개도 작업 전 SHA와 일치했다. 설치 원장이나 설정을 변경하지 않았다.

Codex 실제 `.mcp.json`은 과거 apps-export launcher를 가리킨다. 이를 TopSolar 복원 완료라고 재해석하지 않으며, 이번 작업에서는 전환·재연결·모델 호출을 하지 않는다. 활성 프로세스 및 도구 노출은 HOLD로 재검증하지 않았다. 신규 QC4 소스는 설치된 두 client에 배포하지 않았다.


QC7 소스 대조 보완: native QA receipt 입력과 현재 입력 비교에서는 제출 후 증가한 document generation만 단조 증가로 구분한다(`gi_qa_manifest_matches`). 다른 manifest 필드·실제 의존 문서·snapshot·현재 Work/epoch 검사는 유지한다. receipt bytes는 변경하지 않는다. [QC7 통합 fixture](intent-assurance-qc7-qualification.ko.md)에 정상 제출/역행/변경/완료 시나리오를 작성했으며 실행은 HOLD/NOT_RUN이다.
