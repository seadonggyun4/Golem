# QC7 qualification 준비와 회귀 보강

상태: **테스트/시나리오 작성, 실행 HOLD / 모든 실행 결과 NOT_RUN**. QC7 qualification 통과가 아니다. 컴파일·fixture·회귀·native host·CLI·MCP·패키지·client 검증은 실행하지 않았다. 기존 업무 자료를 테스트 corpus로 사용하지 않는다.

## 기준과 증거 분리

[P0](intent-assurance-qa-p0-contract.ko.md)와 [T01–T12](intent-assurance-qa-coverage.ko.md)를 그대로 적용한다. 원문 의미 누락은 검토자의 OMISSION 판단과 연결하며 native가 자연어 누락을 자동 탐지했다고 표시하지 않는다. 모델/새 대화만으로 독립 reviewer 인증을 주장하지 않는다.

실행 가능한 fixture의 작성과 실제 통과를 구분한다. pure unit, native integration, host/CLI, MCP fixture, package, 실제 Codex, 실제 Claude는 서로 다른 증거다. mock을 native 성공으로, native 성공을 실제 client 성공으로 복사하지 않는다. 기존 A01–A27 증거를 새 bytes의 통과로 재사용하지 않는다.

## 이번 보강

| 범위 | 작성한 검사 | 상태 |
| --- | --- | --- |
| QC1 host | policy뿐 아니라 bundle pin 변경·관측 거부, 유효한 observer 복귀 대조 | NOT_RUN |
| QC2 참조 | 네 root 객체 각각 누락, bytes 치환, 중복 객체 거부, 같은 집합의 역순 정상 처리 | NOT_RUN |
| QC3 gate | legacy predicate에 대한 QC5의 명시적 UNSUPPORTED_VERSION 기대값 반영; 허용으로 완화하지 않음 | NOT_RUN |
| QC4 관측 replay | request/assessment/head/operation hash 변경, prepare sequence 불일치, ACCEPTED 값 주입, duplicate replay에서 상태 불변 | NOT_RUN |
| QC4 부분 기록 | Work 관측만 존재하는 합성 prefix를 재생할 수 있어도 현재 QA 수락은 불가 | NOT_RUN |
| QC5 완료 | 기존 요청/legacy 우회/관측 없음/권한 없는 조회에서 DONE 금지 fixture 유지 | NOT_RUN |
| QC6 exact host | action ID·action SHA·operation의 각 불일치 거부, 정상 참조 선택 | NOT_RUN |
| QC6 전달 | native execution PASS + intent BLOCKED를 그대로 전달; transport 성공으로 수락 승격 금지 | NOT_RUN |
| QC6 실패 보존 | mock spawn 실패 1회, 로그·UNKNOWN 결과 보존, 자동 재시도 0회 | NOT_RUN |

새 C test는 `tests/c/test_intent_qa_observation.c`이며 CMake/CTest에 등록했다. Python 보강은 `tools/test_integration_intent.py`에 있다. 관측 replay fixture의 최소 합성 assessment는 authority 수락 증명이 아니며 정상 QC4·QC5 전체 진행 fixture를 대신하지 않는다.

## 실행 캠페인 대조표

기계 판독 원장: `docs/schemas/intent-qc7-scenarios.json`. 각 행은 단계·표면·필수 관측·fixture 준비 정도와 NOT_RUN을 기록한다. `fixture_status=PARTIAL` 또는 `NOT_AUTHORED`는 단순 미실행과 다르다. 원장은 실행 도구가 아니며 자동으로 subprocess·client·Work를 호출하지 않는다.

- 모든 실패 사례: 예상 native 오류/차단 이유, 전후 Work/authority head·sequence, 파일 inventory, 효과 횟수, 원본 receipt 보존을 함께 비교한다. exit!=0 하나로 PASS 처리하지 않는다.
- 정상 진행성: 완전한 baseline→review→mapping→실제 QA→수락→finalize→reopen/current DONE이 필요하다. 합법적인 N/A와 질문 해결도 포함한다. 실패 테스트만 통과해서 qualification 완료로 판단하지 않는다.
- 두 journal: prepare 이전/이후, Work CAS 이전/이후, authority acceptance 이전/이후, 응답 직전의 fault injection이 필요하다. pending/unknown을 보존하며 재시도·repair·rollback하지 않는다.
- 현재성: QA 뒤 source/snapshot·oracle·review epoch·policy/revocation 변경, 다른 Work/receipt 참조를 대조한다. 이전 자료를 삭제하지 않고 현재 수락만 차단한다.
- lock: D01→Work→authority 순서, 동일 Work 경쟁, 별도 Work 경쟁, timeout/프로세스 종료/디스크 부족을 실제 격리 fixture로 확인한다. 지금 deadlock 부재나 원자성을 보장하지 않는다.
- 호환성: legacy v1/v2 golden을 별도로 재실행한다. 새 v3 완료는 새 predicate만 허용한다.
- client: Codex와 Claude 각각 도구 노출·결과 표시·Owner 후보·다중 연결/재연결에서 자동 창 0개를 별도 기록한다. 설치 변경과 실제 Work action은 당시 정확한 승인을 별도로 받아야 한다.

## HOLD 해제 후 실행 조건

사용자가 실행을 허용하기 전에는 아래 절차를 실행하지 않는다. 새 임시 fixture root만 사용하고 실제 TopSolar·registry·승인·Work·증거를 테스트 입력으로 쓰지 않는다.

1. 현재 source inventory와 빌드 설정을 고정하고 compile/schema/package closure를 검증한다.
2. 작성된 pure/unit 및 회귀를 실행하고 오류를 수정한다. 실패 기록과 최초 source SHA를 보존한다.
3. 아래 opt-in 정상 진행·native fault injection·동시성 harness를 격리 실행한다. 별도 opt-in인 실제 ENOSPC 및 D01 등록/폐기 writer 통합 경합도 실행 권한을 확인한 뒤 실행한다.
4. 각 결과에 source/artifact hash, 정확한 명령·설정, 시작/종료, exit, 원본 출력과 전후 상태를 연결한다. skip·한도·BLOCKED는 별도 기록한다.
5. 필수 행에 FAIL/NOT_RUN/미작성 항목이 남으면 qualification을 통과로 표시하지 않는다. 실제 client 검증은 독립 캠페인이다.

이번에는 소스 문법·diff 및 보존 상태만 점검한다. 기존 설치/정책 pin을 갱신하지 않으며 commit/push 하지 않는다.

## QC7 통합 fixture 보강 — 작성됨 / NOT_RUN

`tests/c/intent_qc7_integration.py`는 새 임시 root만 만들고 기존 native 문서/실행 fixture의 합성 C 프로그램을 재사용한다. 기존 Work를 v3로 고치거나 v1 실행 결과를 v3에 이식하지 않는다. 처음 생성할 때부터 v3 spec을 사용한다. `intent_qc7_driver.c`는 native parser·review host·enrollment·product scope·execution·QA acceptance를 호출하며, `intent_qc7_completion_faults.c`는 실제 completion 구현의 저장 경계만 테스트 전용으로 감싼다. 두 파일은 설치/패키지/MCP에 포함하지 않는다.

CMake option `GOLEM_ENABLE_QC7_INTEGRATION`은 **기본 OFF**다. 켜면 다음 **23개** CTest 항목이 등록된다. 이번에는 configure/build/CTest를 실행하지 않았다.

| 시나리오 | 실제 검사하도록 작성한 내용 |
| --- | --- |
| normal | 원문/기준선 저장, 서로 다른 합성 owner·producer·reviewer와 exact bundle, 질문/답변/해결, 합법 N/A, v3 enrollment, 개발 prepare/finish, 실제 C QA 1회, QA 결과·완료 문서, QC4 ACCEPTED, QC5 finalize/report, 새 프로세스 reopen/current DONE |
| completion-response-lost | finalize 기록 뒤 응답 유실, finalize 재호출 없이 별도 조회로 현재 완료 확인 |
| before/after-prepared·observation·accepted | 각 두 원장 경계에서 자식 종료; authority/Work sequence·관측 수의 정확한 증가량 확인 |
| prepared/accepted-pending-crash | native journal의 staging guard에서 자식 종료; pending 보존 확인 |
| prepared/observation/accepted-io | 저장 함수 오류 반환 주입; immutable prefix 보존 및 재시도 없음 |
| before/after-completion-payload/event | QC5 CAS payload·Work event 경계 종료; 기록 유무와 RECOVER_REPORT/VERIFY_COMPLETION 구분 |
| completion-payload/event-io | QC5 저장 실패 뒤 현재 QA 수락 보존·완료 승격 금지 |
| response-lost | QC4 두 원장 기록 후 응답만 유실; accept 재호출 없이 읽기 전용 current 조회 |
| concurrent | 같은 이전 head/request를 두 프로세스에 동시에 전달; native Work lock/CAS로 성공 하나·수락 관측 하나만 허용 |
| lock-exit·authority-exit | fixture common-dir shared lock 아래 실제 Work/authority lock 보유; 다른 Work/같은 authority 경쟁 및 holder 종료 뒤 lock 해제 |

각 fixture는 QA 실행 횟수 `invoked == "x"`, 기존 합성 사용자 파일, 기존 immutable 파일 inventory, authority/Work head·sequence를 비교한다. 읽기 조회 전후 inventory가 같아야 한다. 정상 진행 뒤 실제 합성 source를 바꾸면 과거 execution PASS는 유지하되 현재 intent acceptance는 차단해야 한다. 잠금 holder 종료는 읽기 전용 테스트 프로세스에만 적용한다.

실패·응답 유실 자료는 자동 삭제하지 않는다. 임시 root, 정확한 request·stdout·stderr, 경합한 두 프로세스의 결과를 남기고 경로를 출력한다. `GOLEM_QC7_OUTPUT`은 향후 실행 시 생성할 임시 자료의 parent만 선택한다. 실제 Work를 입력하는 옵션은 없다. 모든 mutation request는 한 번만 전달하며 crash 뒤 accept/finalize·QA 자동 재실행은 없다.

### 통합 경로 대조에서 보완한 QC4 generation 비교

QA receipt의 manifest generation은 실행 당시 문서 카운터이고, 결과·완료 문서를 제출하면 현재 카운터는 증가한다. 이 차이까지 전체 JSON 동등성으로 비교하면 정상 제출 후 수락을 막는다. `gi_qa_manifest_matches`는 **native로 검증된 두 manifest**에서 양의 정수 generation의 단조 증가만 구분한다. receipt 원본을 수정하지 않으며 다른 필드는 모두 같아야 한다. 기존 `ex_receipt_current`의 실제 source/snapshot·의존 문서 무결성 검사와 product scope의 현재 manifest·exact Work head/epoch 검사는 그대로 필요하다. helper의 성공만으로 수락하지 않는다. generation 누락·역행과 source 변경의 거부 unit fixture도 추가했다.

### 남은 범위

- storage IO 반환 주입과 실제 ENOSPC는 별개다. 아래 bounded-volume fixture를 추가했으며 실행은 NOT_RUN이다. 별도의 모든 short-write 위치 주입을 완전 검증했다고 주장하지 않는다.
- 기존 common-dir 모형과 아래 실제 D01 writer/authorized_root 통합 fixture는 별개다. 둘 다 NOT_RUN이며 실제 Codex/Claude 동작을 대신하지 않는다.
- QC6 MCP 전달 mock, 실제 host 등록, package, Codex/Claude E2E는 위 native 통합 테스트와 구분한다. 기존 T12 상태를 승격하지 않았다.
- 새 C 코드의 컴파일 및 23개 fixture 결과는 모두 NOT_RUN이다. 이 문서와 fixture 작성은 QC7 qualification 통과를 의미하지 않는다.


## 이번 정적 확인·보존 기록

Python AST(테스트 모듈 import 없음), 원장 18행의 경로/NOT_RUN/evidence-empty 일관성, opt-in 23개 등록 대조, `git diff --check`를 확인했다. C 컴파일·실행 성공을 뜻하지 않는다.

읽기 전용 설치 확인: Codex `golem-m7-finish-complete/golem/0.2.7` 한 개와 Claude `local.mcpb.golem-contributors.golem-prepare` 0.1.19 한 개가 남아 있다. Codex의 기존 `apps-export` launcher/60초 설정을 그대로 두었으며 TopSolar 복원이나 최신 QC 소스 설치를 주장하지 않는다. 설치 원장의 두 기존 D2 파일 hash와 원래 Intent Assurance 설계 7개 hash를 대조했고 변경이 없었다. 실행/도구 호출 없이 확인한 설치 파일 상태이며 client handshake/E2E 근거는 아니다. 이번 변경은 checkout 소스·테스트·문서뿐이며 설치/정책/승인/Work/증거/COMMIT_UNKNOWN을 수정하지 않았다. commit/push도 하지 않았다.


## 실제 ENOSPC·D01 writer 추가 — 소스 작성 / NOT_RUN

기존 23개에 **별도 opt-in 3개**를 추가했다. 기본값은 모두 OFF이며 이번에 configure·build·마운트·fixture·회귀를 실행하지 않았다.

| 등록 항목 | 구현·기대 조건 |
| --- | --- |
| `intent_qc7_enospc_qa` | 새 64MiB HFS+ 이미지에서 정상 QA까지 준비 → 커널 write/fsync ENOSPC 확인 → fault 인자 없이 실제 QC4 수락 저장 → 수락 관측/Work sequence 증가 없음·기존 prefix 보존 |
| `intent_qc7_enospc_completion` | 같은 격리 준비와 QC4 수락 이후 실제 파일시스템을 채움 → QC5 완료 저장 실패 → 완료 승격 없음·기존 승인/QA receipt 및 prefix 보존 |
| `intent_qc7_d01_writers` | 실제 `registration_plan/register` 두 writer 경쟁으로 등록 1회 → 실제 `authorized_root` 안에서 native Work/authority lock 보유 → 별도 register/revoke writer가 정확한 `AUTHORITY_REGISTRATION_BUSY`로 차단 → 읽기 holder 종료/lock 해제 → 실제 revoke 두 writer 경쟁으로 폐기 1회 → 기존 locator/authority/Work bytes 보존·새 authorized_root 거부 |

ENOSPC 구현은 `tests/c/intent_qc7_enospc.py`와 `IntentFlow.test_real_enospc`다. 새 이미지의 plist mount-point와 device를 확인하고, host/log device와 다를 때만 최대 64MiB까지 filler를 쓴다. 부모 로그는 이미지 밖에 저장한다. 실제 errno가 ENOSPC여야 하며 다른 오류나 native 저장 성공을 PASS로 취급하지 않는다. 이미지·filler·부분 기록·stderr를 보존하고 생성한 mount만 정상 detach한다. 강제 해제·호스트 디스크 채우기·sudo·복구/재호출은 없다. detach 실패도 실패로 남긴다. macOS hdiutil이 없는 플랫폼은 exit 77/NOT_RUN이며 대체 mock PASS로 승격하지 않는다. 이 fixture는 파일시스템 ENOSPC를 검증하도록 작성한 것이지 실제 하드웨어 전원 유실 내구성 시험은 아니다.

D01 구현은 `tests/c/intent_qc7_d01_race.py`다. 새 임시 Git repository·authority·Work만 생성하고 기존 `intent_authority.py`와 native `golem_intent_host`를 그대로 호출한다. 등록/폐기 exact plan SHA와 owner 승인 인자는 합성 fixture 대상에만 제공한다. 권한 함수·native parser·writer를 mock하거나 운영 코드에 fault flag를 추가하지 않았다. IPC gate와 native READY 출력으로 실행 순서를 동기화하고 bounded timeout으로 deadlock을 실패 처리한다. 이미 실패한 mutation을 같은 ID로 재시도하지 않으며, 별도 관측/새 경합 phase를 구분한다. 테스트 root와 결과 JSON은 자동 삭제하지 않는다.

실행 옵션: `GOLEM_ENABLE_QC7_INTEGRATION`에 더해 각각 `GOLEM_ENABLE_QC7_REAL_ENOSPC`, `GOLEM_ENABLE_QC7_D01_RACES`를 명시적으로 선택해야 한다. D01에는 `GOLEM_BUILD_INTEGRATION_HOST`가 필요하다. **이 옵션 설명은 실행 승인이나 HOLD 해제가 아니다.**

추가분 정적 확인 범위는 Python AST(모듈 import 없음)·CMake 인자 연결·원장 경로·diff 검사다. 새 fixture의 컴파일/실행/통과 근거는 없으며 결과는 모두 NOT_RUN이다. 기존 정책·승인·Work·증거·설치·commit/push 상태는 변경하지 않는다.


QC1–QC7 전체 P0 재대조와 이번 permission/admission/placeholder 수정은 [정적 검토 기록](intent-assurance-qc1-qc7-static-review.ko.md)을 따른다. 작성된 회귀는 NOT_RUN이며 qualification 통과가 아니다.

- [QC schema·golden 대조 준비](intent-assurance-schema-golden.ko.md): 구조 정의·고정 bytes·native probe 작성, 실행 동등성 NOT_RUN.

### 문맥 결과 schema·golden 연결 준비

정상 진행의 accept/current/done/stale 응답을 원본 로그 SHA와 연결하는
오프라인 collector와 회귀 6개를 추가했다. [절차와 한계](intent-assurance-schema-golden.ko.md).
실행은 NOT_RUN이며 crash·경합 결과나 미관찰 schema를 정상 진행 PASS로 대체하지 않는다.
