# QC3 native 제품 gate — 구현 상태와 차단 범위

2026-11-03. 미커밋 개발 소스. **컴파일·실행·fixture·회귀 검증 NOT_RUN, 설치 미적용**.
[P0](intent-assurance-qa-p0-contract.ko.md)를 유지하며 기존 v1/v2 Work는 migration하지 않는다.
**추가 구현: [QC2 참조·현재 stage·exact-request 허용 경로](intent-assurance-qc3-access.ko.md).**
아래 최초 차단 상태 이후 development/QA dispatch의 제한된 허용 경로가 추가됐다.
QC4 수락 소스는 후속 [QC4 구현](intent-assurance-qc4-implementation.ko.md)으로 연결했다. QC5 완료와 실행 검증은 완료되지 않았다.

## 새 Work marker와 enrollment

[product_gate.c](../src/intent/product_gate.c), [product_gate.h](../src/intent/product_gate.h)를 추가했다.
기존 `dw_spec`에 Work version3을 연결했다. 이 profile은 기존 v2의 필드/runtime_profile에
`intent_binding={registration_ref,baseline_ref,policy_ref}`, `support_profile=LOCAL_NO_MERGE`를 필수로 한다.
각 ref는 exact digest다. 다른 profile·unknown/누락 필드 거부, 구버전 reader는 v3을 거부한다.
기존 파일의 version·policy·권한을 변경하거나 자동 업그레이드하지 않는다.

private `gi_product_enroll`의 순서는 다음과 같다.

1. 기존 D01 common-dir 보호를 유지한 host가 Work writer handle을 먼저 연다.
2. `gi_product_enrollment_approval`로 enrollment exact bytes의 SHA, spec/registration, baseline
   operation/request, 새 operation, 두 journal의 expected sequence/head를 묶은 별도 digest를 검토한다.
   실행 승인을 재사용하지 않는다. 이 digest는 기존 `ex_hash`의 compact JSON identity다.
3. 기존 QC1 source/definition/baseline validator와 committed replay를 재사용한다.
   project/Work/policy/baseline, historical ACTIVE·미결0·정확한 activation decision을 대조한다.
   요구/제약 전체와 Work acceptance ID를 일대일로 빠짐없이 매핑한다. 중복·추가·누락은 거부한다.
4. Work lock을 가진 상태에서 authority lock을 열고 기존 journal에 exact enrollment를 게시한다.
5. 그 receipt의 operation/request/sequence/event와 registration을 기존 Work CAS/event에
   `intent-enrollment` acknowledgment로 불변 기록한다. Work expected head/sequence도 다시 검사한다.
6. authority handle을 닫고 반환한다. 이 과정에서 QA·reviewer·외부 작업은 실행하지 않는다.

새 이벤트는 기존 `dw_apply` replay에 연결했다. 같은 Work의 두 번째 enrollment는 거부한다.
기존 operation은 재조회로 성공 처리하지 않고 거부한다. authority 게시를 시도한 뒤 실패하면
Work handle을 poisoned로 두며 기존 bytes/부분 기록은 보존한다. 두 journal은 원자적이지 않다.
authority만 게시된 상태는 Work acknowledgment가 없어 계속 차단된다. 자동 retry/repair/rollback 없음.
caller guard는 정확한 registration의 현행 D01 등록·폐기·owner 선택을 확인해야 하며 재진입해서는 안 된다.
LOCAL_COOPERATIVE의 trusted caller 경계이며 같은 uid 공격자·사람 신원 인증을 새로 제공하지 않는다.

`gi_product_enrollment_verify`는 읽기 전용으로 authority operation/request/sequence/event,
committed/pending와 exact payload SHA 및 저장된 enrollment 내용을 다시 대조한다.
성공은 binding 무결성만 뜻하고 제품 gate를 열지 않는다.

현재 최초 Work만 지원한다. predecessor_ref가 null이 아니면 successor 참조 validator가 없으므로
UNSUPPORTED로 거부한다. 실제 등록 API/CLI/MCP나 설치된 host에 권한을 추가하지 않았다.

## 제품 경계에 연결한 검사

| 경계 | 구현 위치·결과 |
| --- | --- |
| session 제품 진행 | agent_session coordinator의 비조회 operation 전에 DEVELOPMENT gate |
| execution prepare/finish/run | execution dispatcher에서 부작용 전에 QA_DISPATCH gate |
| 실행 중 승인 재검사 | 기존 `ex_authorize`에도 같은 추가 gate; native 승인·lease 검사는 그대로 |
| legacy development 완료 | `co_evaluate_v1` 진입 gate로 직접 호출도 차단 |
| role/documents 완료 | `rc_completion` 진입 gate로 legacy 우회 차단 |
| 현재 완료 안내 | `co_hint`에서 DONE 판단 전에 gate |
| 공통 event/reference 게시 | prepare와 최종 게시에 v3 검사. 문서 관측과 private enrollment 외 unsupported 전이 차단 |
| candidate/workspace | 제품 경로 진입 gate. 이 profile에서 지원하지 않는 후보/작업공간 효과 차단 |

문서 등록은 관측 자료를 보존하는 경로로 유지한다. 문서에 PASS/DONE 문자열이 있어도
수락이나 완료 권한이 되지 않는다. QC1 authority의 질문·답·해결 control은 Work 제품 gate와 분리돼 있다.
일반 읽기·역사 receipt 검사와 자유로운 외부 프로세스까지 통제하는 OS sandbox는 구현 범위가 아니다.

## 의도적으로 허가하지 않는 상태

- Work acknowledgment가 없으면 REQUIREMENTS_UNMET(ENROLLMENT_PENDING).
- acknowledgment만 있거나 검토한 product-access scope가 없으면 UNSUPPORTED.
- historical activation과 acknowledgment를 현재 reviewer 권한·제품 실행 허가로 승격하지 않는다.
- 공개 predicate `golem.completion.intent.local-no-merge.v1`의 수락 구현은 QC4/QC5 전까지 제공하지 않는다.

따라서 **이 코드로 새 v3 Work를 만들어 개발·QA·완료를 진행할 수 있다고 주장하지 않는다.**
초기 구현은 등록·차단 경로였으며 이후 선행3/5 stage와 로컬 typed 참조 해소를 추가했다.
수락/완료까지는 7 stage와 결과 자료에 대한 추가 계약,
binding 읽기 대조를 제품 수락에 합성하는 경로, epoch/input tuple 변경 재검사,
QC4 acceptance·QC5 predicate를 연결해야 허용 분기를 추가할 수 있다.
이를 임의의 `ready=true`나 허용 callback으로 대체하지 않았다.
기존 v1/v2가 새 intent 보증을 획득한 것도 아니다.

## 검사 상태

[test_intent_product_gate.c](../tests/c/test_intent_product_gate.c)를 CTest에 등록했다.
legacy 추가 gate 통과, v3 marker 오류, pending의 각 경계 차단, acknowledged 상태의 미지원 차단,
문서 관측/제품 게시 구분, 직접 execution 승인·completion predicate 차단, 승인 digest의 CAS 결합을 다룬다.
테스트 코드만 작성했으며 실행하지 않았다. 두 journal 장애 주입·다중 프로세스 lock 순서·실제 재개
검증은 NOT_RUN이며 이 테스트로 대체됐다고 주장하지 않는다.

텍스트 diff·문서 링크·기존 설계/정책 hash 확인만 수행한다. build/CTest/정적 분석기/CI는 NOT_RUN.
Codex·Claude 설치·정책·TopSolar·승인·Work·증거를 변경하지 않았고 commit/push도 하지 않았다.
