# QC1–QC7 schema·golden 대조 준비

상태: **구현 준비 자료 작성 / 실행 HOLD / 모든 native 동등성 실행 NOT_RUN**.
P0의 권한·lock·CAS·완료 계약은 변경하지 않았다. JSON Schema는 native 승인 검사를 대체하지 않는다.

## 제공 자료

- `schemas/intent-qc-contracts.v1.schema.json`: QC1–QC6 경계의 30개 구조 정의. QC7은 이 계약을 검증하는 fixture 계층이다.
- `../tests/fixtures/intent/schema-golden/manifest.json`: 324개 고정 bytes, 각 SHA-256, 기대 결과와 native 대조 범위. 30개 정의마다 정상 구조·필수 필드 누락·미등록 필드·중복 키 입력을 포함한다.
- `../tests/c/intent_schema_golden.py`: strict UTF-8/중복 키 검사, Draft 2020-12 구조 검사, 고정 native probe 비교, 독점 생성 보고서. 입력 해시·native source 지문·정의 coverage가 달라지면 중단한다.
- `../tests/c/intent_schema_probe.c`: 파일/Work를 열지 않는 stdin probe. policy/request의 private production parser는 별도 test-only translation unit에서 직접 재사용한다. 설치 API나 권한 우회용 hook은 추가하지 않았다.
- `schemas/intent-schema-native-map.json`: 각 정의의 실제 소스, native 전용 조건, 기존 문맥 fixture와 실행 상태.

`valid`라는 golden 이름은 **구조 예제**라는 뜻이다. 합성 digest, 빈 native_inputs/runtime_profile, NOT_RUN assessment를 포함하는 문맥 예제는 native 통과 입력이 아니다. 실증 결과·승인·현재 QA 수락을 나타내지 않는다. fixture 원본 문자열은 그대로 복사했고 신규 예제는 별도 파일이다.

## 실제 parser 대조 결과

| 영역 | 구조 정의 | native에서만 확정하는 조건 |
|---|---|---|
| QC1 | source, baseline, requirement/constraint, review control, host policy/bundle/evidence | 원문 exact bytes·UTF-8 span·전체 coverage, owner/reviewer/session, 등록·폐기·시각·epoch·7단계 검토 |
| QC2 | applicability/obligations/mapping, artifact/target/oracle/plan | 요구사항×5경로의 완전한 집합, 실제 참조·본문 hash·oracle 일치, N/A 검토 증거 |
| QC3 | Work v3, enrollment/event, product access/material | 등록/Work/authority lock·head·CAS, 1:1 acceptance, 지원 profile, exact request·현재 stage |
| QC4 | QA request/assessment/observation, prepared/accepted publication | native QA receipt·현재 입력·semantic review, 두 journal 연결과 불확실 결과, 승인 정책 |
| QC5 | completion request | 기존 completion parser와 현재 QC4 acceptance·최종 검토·완료 predicate |
| QC6 | host packet, optional Intent host policy, read arguments/action reference | 실제 D01 등록·producer/file pin·정확한 D4 action·inherited FD·host scope |

기존 QA-path Schema의 ID에 빠져 있던 최대 길이 64를 `dw_id`의 capacity 65와 맞췄다. 완료 finalize의 expected_generation 상한은 기존 native의 `GOLEM_DOCUMENT_MAX_REVISIONS + 1`인 4097이다.

구조적으로 표현 가능한 조건과 native의 문맥 검사는 동일한 판정 집합이 아니다. 문자열 길이는 Schema의 문자 수와 native의 UTF-8 바이트 수가 다르다. embedded JSON 문자열, duplicate member, uint token, 해시/집합/clock/등록 상태는 추가 대조가 필요하다. 기존 runtime profile·native input manifest의 내부 계약은 해당 parser에 위임하며 `{}` 구조 예제를 실제 유효 입력으로 승격하지 않는다.

## 바이트 identity golden

`gi_domain_digest`가 등록한 16개 domain 전체에 compact/spaced 입력을 각각 고정했다. 기대값은 ADR-D08의 `SHA256(schema + NUL + uint64_le(byte_length) + exact_bytes)`로 독립 산출하여 파일에 고정했다. 미등록 domain·중복 키·단독 surrogate 거부도 포함한다.

이 35개 입력은 **identity만** 대조한다. `gi_domain_digest`는 full shape validator가 아니므로 body가 없는 입력에 identity가 생성되어도 정상이며, 승인·증거 진실성·QA PASS와 무관하다. Schema validator가 identity 함수를 full validator로 오인하지 않도록 별도 범주로 둔다.

## 실행 해제 후 확인 절차

1. 이 문서와 P0의 HOLD 해제가 별도로 확인된 뒤, 별도 build에서 `GOLEM_ENABLE_INTENT_SCHEMA_GOLDEN=ON`을 선택한다. 기본값은 OFF다. 현 단계에서는 configure/build도 실행하지 않았다.
2. Python `jsonschema`의 Draft 2020-12 지원 환경을 준비한다. runner는 의존성을 자동 설치하지 않으며 누락을 PASS/skip으로 처리하지 않는다.
3. `intent_schema_golden.py <source-root> <built-probe> --report <새 보고서 경로>`를 한 번 수행한다. 이전 보고서 덮어쓰기·자동 재시도는 없다.
4. probe 지원 범위(policy, QA request, completion request, identity)의 기대값과 native 결과를 대조한다. parser 거부와 도구 실행 실패를 구분한다.
5. 나머지는 기존 QC7 실제 정상 흐름·경합·crash fixture에서 **문맥이 갖춰진 native 자료**를 수집해 대조해야 한다. 현재 runner는 이 항목을 NOT_RUN으로 남기고 전체 결과를 PARTIAL로 기록한다. 구조 corpus만으로 전체 동등성 PASS를 내지 않는다.

**남은 검증:** 새 C probe 컴파일·링크, schema validator 실행, native golden 대조, 문맥 fixture 생성 결과의 전체 schema 적용, client/package E2E. 모두 NOT_RUN이다. 30개 구조 정의를 작성했다는 사실이 이 실행 단계의 완료를 의미하지 않는다. 원래 P0 전체의 과거 D01/quota/object-preparation 저장 형식은 기존 계약·fixture에 위임하며 QC 변경 전체와 제품 전체 schema를 혼동하지 않는다.

## 보존

client 설치·launcher·정책·승인·Work·evidence·CAS·journal·COMMIT_UNKNOWN을 변경하지 않았다. 새 자료는 repository의 docs/tests에만 추가했다. 원래 Intent 설계 7문서 해시는 유지한다. commit/push 및 실행 검증은 하지 않는다.

## 이번 정적 확인 기록

2026-11-03: runner AST 파싱, 30개 정의↔대조표↔corpus coverage, 324개 파일 SHA, native source 지문, 참조 fixture 경로, 원래 설계 7문서 SHA, `git diff --check`를 확인했다. Schema validator·C 빌드·native probe는 실행하지 않았다.

실제 디스크 목록은 Codex `golem-m7-finish-complete/golem/0.2.7` 한 개, Claude `local.mcpb.golem-contributors.golem-prepare` 0.1.19 한 개다. Codex `.mcp.json`은 여전히 기존 `apps-export` launcher와 60초 초기화 설정을 가리킨다. 이번 확인을 TopSolar 복원 또는 활성 연결 E2E 확인으로 해석하지 않는다. 설치·설정 파일은 수정하지 않았으며 새 QC 코드가 설치본에 적용됐다는 주장도 하지 않는다.

## 문맥 fixture 결과의 오프라인 대조 경로

`intent_qc7_integration.py`의 정상 진행에 네 체크포인트를 연결했다:
`accept`(QA 수락), `current`(별도 재조회), `done`(완료 재조회),
`stale`(실제 합성 source 변경 뒤 현재 수락 무효화).
`tests/fixtures/intent/context-golden.json`에 기대 operation과 결과 필드를 고정했다.
fixture가 이미 수행한 native 호출의 request/stdout/stderr/종료 코드/fault와
source 지문을 별도 `context-*.json`에 기록한다. 후보 저장·native 재호출은 없다.

실행 HOLD가 해제되고 **별도로 허용된** QC7 fixture가 결과를 남긴 이후:

```text
python3 tests/c/intent_context_golden.py <source-root> <해당 fixture 로그 폴더> \
  --report <존재하지 않는 새 보고서 파일>
```

이 대조기는 프로세스를 실행하거나 Work·authority·설치 경로를 탐색하지 않는다.
지정 로그의 고정 members만 읽고 SHA·종료 코드·fault·operation·producer 지문을 대조한다.
입력과 응답 속 알려진 schema 및 embedded JSON을 재귀적으로 검사하며,
원본 stdout SHA를 보존한다. JSON 재직렬화 값을 원래 native identity로 사용하지 않는다.
중복/미등록 체크포인트, 중복 JSON 키, 파일 변조, symlink, oversized 입력은 거부한다.

- 기대 필드와 다른 결과 또는 구조 오류: FAIL.
- 기록 누락·관찰되지 않은 30개 정의 중 일부: PARTIAL, 해당 범위 NOT_RUN.
- 단일 정상 흐름이 다루지 않는 host transport·journal 형식은 여전히 미관찰로 남는다.
  이를 정상 흐름에 억지로 만들어 넣거나 기존 golden의 합성 값으로 채우지 않는다.
- crash/응답 유실·ENOSPC·경합은 기존 전용 fixture 판정을 유지한다. 종료 코드가
  불확실한 호출을 정상 성공 체크포인트로 사용하거나 재시도하지 않는다.
- native fixture의 역사적 결과를 비교할 뿐 현재 QA 수락·실제 사람 인증을 증명하지 않는다.

collector 회귀 6개(빈 자료, 부분 coverage, 변조, 미등록/중복 checkpoint, symlink)를
`test_intent_context_golden.py`에 작성했다. 자동 실행 등록이나 설치 의존성 변경은 없다.
**collector·회귀·native fixture 모두 NOT_RUN**이며 이 추가로 실행 HOLD는 해제되지 않는다.

## Journal・fault・host transport 준비 확장

- QC7 test-only snapshot에 native reducer가 읽은 enrollment/QA observation과
  `gi_journal_visit_payloads`의 committed JSON payload를 연결했다. production API는 변경하지 않았다.
  pending journal에서는 visitor를 호출하지 않고 `NOT_RUN_PENDING`을 반환한다.
  이전 opaque payload는 JSON 형식 대조 대상이 아니며 semantic 통과로 집계하지 않는다.
- `fault-golden.json`: 수락 crash 12개, 완료 crash 6개, 실제 ENOSPC 2개,
  동시 수락 1개의 기대 종료 코드·관찰/authority/Work/완료 증분을 고정했다.
  기존 fixture assertion 이후 수집한 snapshot과 native 로그 SHA를
  `intent_fault_golden.py`가 별도로 대조한다. 재실행·repair·기록 삭제는 없다.
- snapshot은 원본 native stdout에 실제 존재해야 한다. pending payload 미관찰,
  미수집 scenario, 정상 JSON 응답이 없는 실패는 성공으로 채우지 않는다.
  원본 로그는 유지하고 새 보고서만 독점 생성한다.
- `intent_host_transport_golden.py`: `transport.json` descriptor와 고정
  `packet.json`/`stdout`/`stderr` 세 파일의 SHA를 받아 packet 및 embedded
  policy/bundle/control/material 구조와 pin을 대조한다. descriptor는
  `kind`(NATIVE_HOST 또는 MOCK), `files`(파일명→SHA), `returncode`,
  `expected_operation` 네 필드다. 실제 native host의 실행 증거가 없는
  패킷 복사·mock 응답은 host E2E가 아니다. descriptor 자체도 사람 인증은 아니다.
  이 도구는 형식 관찰만 보고하며 전체 결과를 PARTIAL로 유지한다.

HOLD 해제 및 별도 실행 허용 이후에만 기존 fixture를 실행하고,
각 로그 폴더에 대해 `intent_fault_golden.py <source-root> <logs> --report <새 파일>`을
사용한다. 하나의 scenario 폴더로 21개 전체 PASS를 주장하지 않는다.
Host 비교도 동일한 인자 형식이다. 두 도구는 native를 실행하지 않는다.

**명시적으로 남는 범위:** 실제 host FD/등록·producer 관찰을 포함한 transport
E2E 증거, D01 등록/폐기 writer 및 lock-holder 전용 결과의 개별 의미 검증은
기존 전용 fixture에 남아 있다. 이번 21개와 합쳐 통과 처리하지 않는다.
새 C 수집 코드 컴파일, Python comparator 실행 및 모든 fixture 실행은 NOT_RUN이다.

추가 연결: `lock-exit`·`authority-exit`의 native before/after snapshot과
경합 reader 종료 코드도 fault golden에 연결해 총 **23개**로 확장했다.
D01 등록/폐기 writer의 두 결과, 네 held-lock 거부, 보존 assertion은
`intent_d01_golden.compare(log_folder)`로 대조한다. 이는 해당 fixture의
역사적 assertion 비교이며 D01 현재 등록 인증이나 native schema 동등성은 아니다.
이전 문단의 D01/lock 개별 의미 검증 경로에 이 오프라인 비교가 추가되었고,
실제 실행·증거 생성은 여전히 NOT_RUN이다.
