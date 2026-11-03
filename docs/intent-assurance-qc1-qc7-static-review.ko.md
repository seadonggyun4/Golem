# QC1–QC7 / P0 소스 재대조

2026-11-03. **정적 재대조·수정 작성 / 실행 HOLD / NOT_RUN**.
검토 대상은 현재 checkout의 누적 QC1–QC7 변경이다. Git HEAD만으로 미커밋 구현을 제외하지 않는다.
이 기록은 실행 qualification이나 모든 우회 부재의 증명이 아니다. 기존 정책·승인·Work·증거·설치에는 적용하지 않았다.

## P0와 구현 연결

| P0 요구 | 코드 경로 | 정적 판정·제한 |
| --- | --- | --- |
| exact source·baseline 전체 | `review.c:gi_review_bind/definition`, 기존 source/baseline resolver | 원문 span/typed digest·항목 집합·순서·256개 한도 대조. 자연어 추출 누락 자동 증명 없음 |
| owner/reviewer·7 stage | `review_host.c`, `review.c` | 등록 principal/role/session·exact bundle·purpose·입력 digest·원문 검토 진술 검사. 같은 uid 적대자/실제 사람 인증은 지원 밖 |
| 질문·resolution 유지 | `gi_review_apply/publish` | unresolved가 PASS를 차단하고 resolution 뒤 downstream stage 무효화. control 경로를 product gate로 막지 않음 |
| 다섯 route·모든 의무 | `qa_paths.c`, `qa_resolve.c` | baseline requirement/constraint×5행, target closure, N/A review/owner decision, 모든 native 의무 mapping, native 의무0 차단. unknown/remote/manual adapter는 지원으로 승격하지 않음 |
| 개발/QA 선행 stage 구분 | `product_access.c:check/gi_product_request` | 개발3·dispatch5·수락/완료7, receipt-specific final input. 미래 ACCEPTED를 dispatch 선행으로 요구하지 않음 |
| native gate 공통 적용 | `document/record.c`, session/execution entrypoints, `product_gate.c` | v3 scope 없음·enrollment 미확정 차단. 문서는 관측으로 저장 가능하나 수락 아님. candidate/workspace v3 명시적 미지원 |
| QA 원시 결과·현재 수락 분리 | `qa_result.c`, `qa_acceptance.c` | 누락/중복/불일치/unknown은 PASS 아님. receipt native currentness·snapshot·contract·semantic review·final review 대조. Work permission 검사를 이번에 보완 |
| 두 journal 불확실성 | `gi_product_enroll`, `gi_qa_accept/current` | authority 준비→Work 관측→authority 수락; 두 연결 검증 전 ACCEPTED 아님. 실패 후 poisoned/미확정 보존. 자동 repair/재실행 없음 |
| current 완료·legacy 우회 차단 | `predicate_intent.c`, completion dispatch/store, registry | 새 predicate로 native development 조건과 QC4 current를 합성. historical replay와 live gate 구분. legacy v1/v2의 v3 평가 거부. full merge/deploy 의미 없음 |
| exact MCP host·기본 OFF | `integration_intent.py`, `intent_product_host.inc`, mutation/service/distribution | optional owner 계약·D1/D2/D4·producer/bridge/packet/control pin·D01 guard. read operation은 mutation binding을 거부. 모델에는 승인 발급/정책 적용 없음 |
| durable intent·재실행 차단 | `integration_mutations.py:_admit/_mutate` | request conflict/COMMIT_UNKNOWN/동일 action 중복 dispatch 차단 유지. 모듈 shadowing을 이번에 수정 |
| lock·crash·진행성 | QC7 Python/C driver 및 실제 ENOSPC/D01 writer fixture | 23+3개 opt-in 작성. mock/native/client 구분. 전부 NOT_RUN: deadlock 부재·원자성·정상 진행 보장 주장은 아직 불가 |

## 확인하여 수정한 결함

1. **QC4 native Work permission 누락**: `accept_owned`가 writable/poisoned는 확인하지만 DENY/ASK_ALWAYS를 직접 검사하지 않았다. 이제 요청 해석·host scope·첫 journal 저장 전에 각각 POLICY_DENIED/APPROVAL_REQUIRED로 거부한다. exact Intent 선택은 기존 Work permission을 덮어쓰지 않는다. 출력 sentinel·event/관측 수·poisoned 불변 fixture를 추가했다. 읽기 assessment/current의 기존 계약은 변경하지 않았다.
2. **QC6 Python 이름 충돌**: `integration_intent as intent`와 `_admit`의 local durable `intent` dict가 충돌했다. 분기에서 UnboundLocalError 또는 dict attribute 오류가 발생할 수 있었다. 모듈을 `intent_api`로 구분하고 durable 파일 identity/bytes는 유지했다. 실제 `_admit`가 OWNER_INTENT_HOST_REQUIRED까지 도달하는 mock 회귀를 추가했다. 이는 native/client E2E가 아니다.
3. **QC2 placeholder 표기 우회**: `TBD`만 거부하여 ` tbd ` 등은 통과할 수 있었다. 공백 제거 후 유한 placeholder(TODO/TBD/N/A)를 대소문자 구분 없이 차단한다. 원문 자체는 재작성하지 않는다. 조건/이유의 의미 충분성을 문자열 검사로 보증하지 않는다.
4. 새 Python 회귀 class가 직접 실행의 `unittest.main()` 뒤에 놓이지 않도록 진입점을 파일 끝으로 정리했다.

앞선 QC7 generation 비교 보완도 대조했다. QA receipt 원본 generation을 현재 값으로 수정하지 않으며, 비교 복사본에서만 양의 단조 증가를 구분한다. 다른 필드는 정확히 같아야 하고 기존 native snapshot/의존 문서 검사와 현재 Work head/epoch 조건은 유지된다.

## 남은 검증·구현 경계

- 컴파일·native 단위·통합·회귀·패키지·실제 client 검증은 실행하지 않았다. 작성된 fixture의 성공을 주장하지 않는다.
- P0의 기계 판독 schema/golden 전체 범위는 아직 exit 조건이다. 현재 별도 JSON Schema는 QA paths 계열 중심이며, 모든 host/control/assessment/enrollment 조합의 독립 schema와 golden 동등성 시험이 완결됐다는 주장은 하지 않는다. native 닫힌 parser는 실제 판정 경로다.
- 의미 충분성·원문 직접 검토·실제 reviewer provenance는 선택된 LOCAL_COOPERATIVE host 진술의 신뢰 경계다. native hash 일치가 진실성을 증명하지 않는다.
- LOCAL_NO_MERGE만 대상이다. 강한 신원 인증·수동/remote adapter·GLOBAL/UNSCOPED constraint·분할 Work 합성·merge/deploy는 미지원이며 자동 허용하지 않는다.
- QC7 actual ENOSPC는 macOS bounded image backend다. 다른 OS의 skip은 NOT_RUN이다. native lock fixture는 실제 Desktop/model 전달 검증을 대신하지 않는다.
- 실행 HOLD가 해제되기 전에는 설치 producer pin 갱신·기존 Work 적용·실행 결과 승격을 하지 않는다. COMMIT_UNKNOWN은 그대로 보존한다.

## 이번 확인 방법

소스의 gate 호출·publication/replay·host 전달·D4 durable 경로를 읽고 P0 불변조건에 대조했다.
Python AST와 import alias/local shadowing 정적 탐색, 원장 경로/NOT_RUN 일관성, diff whitespace 확인을 수행했다.
테스트 모듈 import, build/configure, 실제 syscall fault, native 호출, MCP/모델 호출은 하지 않았다.
기존 설치 목록과 원장 D2 pin은 읽기 전용으로 확인한다. 이 수정은 아직 설치본에 반영되지 않았다.

- [QC schema·golden 대조 준비](intent-assurance-schema-golden.ko.md): 구조 정의·고정 bytes·native probe 작성, 실행 동등성 NOT_RUN.
