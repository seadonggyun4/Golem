# QC5 LOCAL_NO_MERGE 완료 predicate

상태: **소스 구현 / 실행 검증 HOLD / NOT_RUN**. 빌드·단위/fixture·회귀·실제 Work·Codex/Claude 검증과 설치는 하지 않았다. 아래는 구현 계약이며 통과 결과가 아니다.

## 완료 조건

확정 [P0](intent-assurance-qa-p0-contract.ko.md)의 `golem.completion.intent.local-no-merge.v1`을 별도 dispatch로 구현했다. 기존 v1/v2 predicate의 검증 본체는 내부 합성으로 재사용하고, 외부의 legacy finalize와 documents/no-change 우회는 Work v3에서 거부한다. 기존 Work v1/v2에는 신규 predicate를 적용하지 않는다.

finalize와 현재 완료 조회는 모두 다음 조건을 요구한다.

1. 정확한 COMPLETION owner scope, Work spec·head/sequence·정책·baseline·material·현재 review epoch와 일곱 stage가 일치한다.
2. [QC4](intent-assurance-qc4-implementation.ko.md)를 다시 평가해 **현재 ACCEPTED**여야 한다. native QA PASS만으로는 부족하며 두 authority 기록과 Work 관측이 모두 필요하다.
3. 선택한 QA 관측 frame은 해당 Work의 최신 관측이어야 한다. 완료 문서의 native QA receipt와 QC4 receipt가 같아야 한다. 의무 결과는 비어 있을 수 없고 모두 PASS여야 한다.
4. 기존 development/role predicate의 문서·QA/development snapshot·checkpoint·요구사항·research/reentry·blocking issue 조건을 유지한다. development mode만 허용하며 role도 development enrollment만 합성한다.
5. 기존 session/attempt quiescence와 완료 projection 검사를 유지한다. 새 predicate도 report가 없으면 기존 `RECOVER_REPORT`, 현재 조건이 달라지면 재검증/차단이며 자동 복구하지 않는다.

전체 요구사항과 native QA 의무0 거부는 QC2/QC3의 기존 완전성 검사에서 계속 적용한다. merge/deploy·여러 Work의 종합 완료·전역 constraint 보증은 제공하지 않는다.

## 요청과 권한

Work v3의 finalize는 completion request schema_version=3이다. 기존 `operation`, `selection_id`, `key`, `expected_generation`, `issues`에 다음 두 필드가 추가된다.

- `predicate`: `golem.completion.intent.local-no-merge.v1`
- `intent_qa_observation`: 정확한 QC4 Work observation frame digest

resume는 `{schema_version:3, operation:"resume", selection_id:...}`의 닫힌 형식이다. 새 scope는 기존 product-access 구조에서 boundary/channel=`COMPLETION`, input_kind=`qa-result`로 exact request bytes를 선택한다. 조회 scope도 기존 D01→Work lock 순서와 현재 host 검사를 요구하지만 실행·승인 발급 권한은 추가하지 않는다. 기존 QA scope를 완료 권한으로 전용하지 않는다.

완료 후 현재 조회는 현재 head에 맞춘 **별도 읽기 scope**를 사용한다. 완료 기록을 추가한 것을 입력 문서 변경으로 오인하지 않도록 QA assessment의 native 문서 generation과 Work publication head를 구분한다. 이전 finalize scope를 자동 갱신하거나 재사용하지 않는다.

## 저장·재생·현재 판정

기존 `golem_completion_call`의 permission/deadline·Work lock·CAS·불변 completion record·report 경로를 재사용한다. `dw_record_prepare`와 최종 publication의 product gate에서 결과/경계를 재대조하고, guarded publication 직전에도 전체 새 predicate와 quiescent boundary를 재평가한다. 실패·유실·부분 출력은 기존 계약대로 보존하며 자동 재실행·repair·rollback하지 않는다.

새 assessment에는 별도 predicate/native policy, intent_binding, QC4 관측·assessment digest·prepared event·accept operation을 포함한다. 기존 evidence_root는 이 assessment와 boundary를 함께 hash한다.

역사적 replay는 당시 Work prefix의 QC4 관측과 native 자료로 기록의 구조·digest·연결을 재구성한다. 현재 host 권한이나 현재 QA ACCEPTED를 역사적 replay에 요구해 과거 자료를 열 수 없게 만들지 않는다. 반대로 과거 기록을 읽었다는 이유로 현재 ACCEPTED/DONE을 반환하지 않는다. 현재 조회는 live QC4를 반드시 다시 대조한다. Markdown은 과거 기록임과 LOCAL_NO_MERGE 범위를 명시한 파생 표시이며 수락 증거 원본이 아니다.

## 변경 경로

- `src/completion/predicate_intent.c`: 닫힌 요청 형식, QC4+기존 predicate 합성, 별도 renderer.
- `src/completion/evaluator.c`, `store.c`: version dispatch, exact request와 guarded publication, 현재 조회 연결.
- `src/intent/product_access.c`: 별도 COMPLETION scope·stage·record guard.
- `src/intent/qa_acceptance.c`: 이미 승인된 completion scope에서 QC4의 현재 수락을 읽기 전용으로 재검사.
- `src/document/registry.c`: v3 completion replay를 새 predicate로 전달. 다른 미지원 event를 자동 허용하지 않는다.

## 검증 기록과 남은 확인

`test_intent_completion.c`에 요청 형식, 누락/추가 필드, legacy predicate 우회, QA 관측 없음, resume/finalize 구분 fixture를 작성하고 CMake에 등록했다. **실행하지 않았다.** 기존 QC1~QC4 fixture도 재실행하지 않았다.

HOLD 해제 후 필요한 검증: 완전한 QC1~QC5 성공 fixture, 정상 finalize/reopen/current DONE, revoked authority, 누락/부분 QC4 acceptance, stale snapshot·review·문서, 다른 receipt/Work, report 유실, publication 직전 변경, crash/응답 유실, v1/v2 회귀. 동시성·deadlock·진행성은 QC7 시험 전 보장하지 않는다.

이번 source-only 점검은 `git diff --check` 및 선언/호출·문서 연결 대조다. 컴파일 통과 또는 QA 통과로 표시하지 않는다. 기존 설치 Codex 0.2.7·Claude 0.1.19와 D2 hash, 과거 Intent 설계 7개를 읽기 전용으로 확인했으며 변경하지 않았다. 설치 활성 상태·도구 노출은 재검증하지 않았다. TopSolar·정책·승인·Work·증거·COMMIT_UNKNOWN 보존, commit/push 없음.

QC6 공통 MCP·Owner 전달은 [별도 exact Intent host 구현](intent-assurance-qc6-implementation.ko.md)으로 연결했다. source-only이며 설치·실행 검증은 여전히 NOT_RUN이다.
