# QC2 요구사항·검증 경로 연결

2026-11-03. 미커밋 소스 구현. **컴파일·fixture·회귀·실행은 NOT_RUN(HOLD), 설치 미적용**.
[P0 계약](intent-assurance-qa-p0-contract.ko.md)의 전체 baseline·LOCAL_NO_MERGE 범위를 유지한다.

## 구현

[qa_paths.h](../src/intent/qa_paths.h)의 `gi_qa_paths_inspect`는
[QC1](intent-assurance-qc1-implementation.ko.md)의 `gi_review_bind`를 먼저 호출한다.
정확한 source/definition/baseline 검사를 재사용하고 적용성→의무→실행 mapping을 대조한다.
새 journal·승인·실행 경로는 만들지 않는다. 실패 시 출력은 변경하지 않는다.

- 모든 requirement와 constraint마다 UI/API/BATCH/STATE_TRANSITION/OTHER_LOCAL 행을 정확히 하나씩 요구한다.
  추가·중복·누락·다른 baseline/Work를 거부한다.
- REQUIRED의 모든 target에 최소 한 의무가 있어야 한다. N/A·UNDECIDED 행에 의무를 넣어 우회할 수 없다.
  N/A의 이유와 review/decision 참조가 필수다. UNDECIDED만 두 참조의 null을 허용하며 미결 수를 반환한다.
- 각 의무의 ID·조건·예상 결과·stage·evidence kind·oracle ref를 검사한다. 빈 문자열·공백·기본 placeholder
  TODO/TBD/N/A/기호만 있는 설명을 거부한다. 설명의 의미적 충분성은 자동 증명하지 않는다.
- 정의의 acceptance_oracle_refs마다 같은 요구의 의무 연결을 요구한다.
- 적용성/의무/mapping의 identity는 기존 domain+길이+exact bytes를 재사용한다.
  execution contract digest는 기존 `golem_execution_contract_validate`의 identity 규칙을 그대로 사용한다.
  두 hash 체계를 서로 대체하지 않는다.
- NATIVE_QA마다 실제 contract의 정확한 gate ID/version/case ID mapping이 필요하다.
  중복 edge·없는 case·없는 의무·semantic 의무의 실행 mapping을 거부한다. 명시된 공유 case는 허용한다.
  native 의무0개를 development 완료 가능 모델로 인정하지 않는다.
- 기존 객체256KiB, 요구/제약256, route1280, target/row64, 의무4096, mapping16384 한도를 유지한다.
  직접 참조 node4096(검토·결정 포함 보수적 합집합), target edge16384 상한도 적용한다.
  아직 해소하지 못한 typed 객체 내부 graph 한도를 통과했다고 주장하지 않는다.

[기계 판독 schema](schemas/intent-qa-paths.v1.schema.json)는 닫힌 JSON 필드를 설명한다.
JSON Schema의 문자 길이와 native UTF-8 bytes 한도는 다르며 native 검사가 최종 기준이다.
중복 JSON key와 집합/교차 참조 대조도 native parser/validator가 담당한다.
새 domain 등록은 identity만 제공하며 object store의 게시 타입이나 기존 권한을 확대하지 않는다.

## 미지원 참조와 후속 경계

기존 `gi_qa_paths_inspect`는 참조를 해소하지 않는 구조 조회다. 추가한
`gi_qa_paths_resolve`의 로컬 typed 지원과 제품 gate 연결은
[허용 경로 구현 기록](intent-assurance-qc3-access.ko.md)에 구분한다. 미지원 schema는 계속 차단한다. 임의 SHA나 caller의 `verified=true`를 받아 이 공백을 대체하지 않는다.
이 참조는 `unsupported_references`에 **참조 발생 수**로 남긴다(고유 객체 수가 아님).
구조 조회의 GOLEM_OK만으로 수락 가능한 계획이라고 판정하지 않는다.
`structurally_complete`는 미결 적용성 없는 구조 대조만 뜻하고 `qa_accepted`·`execution_authorized`는 항상 false다.

원문 대비 대상 inventory/조건의 의미적 완전성, 실제 typed 참조 해소와 현재 권한 검토,
Work acceptance ID와 실행 case requirement_id의 enrollment 대조는 제품 scope의 native 계약 검사를 함께 사용한다.
P0가 정한 미지원 차단을 유지하며 이 항목들을 검증 완료로 재분류하지 않는다.
QC3 native product gate, QC4 실제 결과·현재성, QC5 QA/완료 predicate는 이번 변경에 포함되지 않는다.
**현재 제품의 QA PASS/완료 경로가 QC2에 의해 차단되기 시작한 것은 아니다.**

## 검증·보존

[test_intent_qa_paths.c](../tests/c/test_intent_qa_paths.c)에 실제 QC1 source/definition fixture와
닫힌 적용성·의무·mapping 및 기존 execution contract parser 연결 사례를 작성했다.
구조 일치에도 미지원/권한 false, 없는 case, semantic mapping, placeholder, 중복 경로,
실패 시 출력 보존을 포함한다. `intent_qa_paths` CTest에 등록했으나 실행하지 않았다.

코드/문서 텍스트 대조와 diff 공백·상대 링크 확인만 수행한다. 컴파일·정적 분석기·테스트·CI는 NOT_RUN.
기존 정책·승인·Work·증거·설치·TopSolar 자료는 수정하지 않았고 commit/push도 하지 않았다.
QC2 모델 코드 추가와 QC2 exit gate 통과를 구분하며, HOLD 해제 전에는 통과로 기록하지 않는다.
