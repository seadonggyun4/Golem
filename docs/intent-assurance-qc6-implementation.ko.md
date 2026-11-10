# QC6 공통 MCP·Owner 표시와 exact Intent host

후속 구현: [owner 초기 설정 host](intent-assurance-owner-bootstrap.ko.md)가 기존 설치 host에
없던 baseline 검토·활성화·Work 요구사항 등록 전달을 보완한다. 이 owner 전용 절차는
MCP의 승인 발급 도구가 아니다. 공통 `intent_read`에는 별도로 고정한
`enrollment-inspect` 메타데이터 관측이 추가되며, 실제 QA 수락·완료 action과 구분한다.

아래 최초 작성 시점의 NOT_RUN 기록은 보존한다. 후속 격리 빌드·fixture·회귀 결과는
[QC CI 기록](intent-assurance-ci-status.ko.md)에서 source별로 확인한다. 소스 구현이나
조회 성공만으로 현재 client의 QC 활성화·제품 QA·완료를 주장하지 않는다.

## 최초 QC6 구현 기록 — 당시 상태

상태: **소스 구현 / 빌드·fixture·회귀·client E2E NOT_RUN / 실행 HOLD**. 설치·기존 정책 선택·producer pin 갱신·Work 실행·승인 발급·commit/push는 수행하지 않았다. source 문법 점검을 runtime 검증으로 취급하지 않는다.

## 채택한 연결 계약

사용자가 선택한 별도 optional exact Intent host 계약을 구현했다. 기본 비활성이며 기존 D1/D2/D4 읽기·QA 실행 권한을 새 QA 수락·완료 권한으로 이전하지 않는다. [P0](intent-assurance-qa-p0-contract.ko.md), [QC4](intent-assurance-qc4-implementation.ko.md), [QC5](intent-assurance-qc5-implementation.ko.md)의 parser·현재성·승인·lock·CAS·predicate를 재사용한다. Python은 전달 범위·파일 pin·길이만 검사하며 의무 결과나 PASS/DONE을 합성하지 않는다.

| 제공 경로 | 효과와 제한 |
| --- | --- |
| `intent_read(project_id,work_id,query_id)` | owner가 선택한 assess/current/resume packet만 native에 전달. QA 실행·수락 publication·finalize 불가 |
| `intent_qa_accept(project_id,work_id,action_id,request_id)` | D4 exact action과 host binding이 모두 일치할 때 QC4 수락 1회 요청 |
| `intent_completion_finalize(...)` | 별도 exact action으로 QC5 완료 요청. 기존 QA 재실행 없음 |
| `action_prepare(tool=위 action, fields_json={binding_id})` | 기존 M2 private spool의 미승인 참조 초안. native 정책·검토 evidence 자동 생성 없음 |
| Owner 앱 plan 검토 | UNAPPROVED_DRAFT·후보 파일 생성만 표시. 정책 적용이나 실행 승인 아님 |

task/quality profile에 선택적 host 설정을 제공한다. read/prepare profile에서 수락·완료 action은 제공하지 않는다. host가 없으면 새 도구는 목록에서 제외하고 직접 호출도 차단한다. Codex/Claude는 같은 stdio·schema·서비스 코드를 사용하지만 실제 양쪽 노출/호출은 NOT_RUN이다. MCP 시작 시 Owner 앱을 열거나 GUI를 import/자동 실행하는 경로는 추가하지 않았다.

## Owner 파일과 pin

`golem.integration-intent-host.v1`은 D2/D4 digest, repository, D01 registration digest, git/native bridge 파일 pin, 최대32개 binding, transport producer SHA를 고정한다. binding은 project/Work·operation·binding ID·D4 action ID/action-file SHA·packet 파일 pin·review directory inode identity를 가진다. read binding은 빈 action ID를 사용하며 accept/finalize를 읽기로 선택할 수 없다.

packet `golem.intent-product-host.v1`의 닫힌 필드는 `schema, work, operation, policy, bundle, control, material, request, policy_sha256, bundle_sha256, policy_name, bundle_name`이다. control/material/request와 review policy/bundle은 정확한 native bytes를 문자열로 보관한다. policy/bundle은 owner-private directory의 원본 파일 bytes 및 SHA와도 일치해야 한다. packet 전체는 transport `LIMIT` 이하로 제한하며 큰 자료를 조용히 잘라내거나 범위를 확대하지 않는다.

D4 envelope의 native_json은 `{binding_id}`만 허용한다. model에 path·argv·approve boolean을 받지 않는다. 모델이 참조를 제시하거나 M2 초안을 만들었다는 사실은 owner의 별도 packet/host 선택을 대신하지 않는다. host 정책 생성과 활성화는 이번 작업에서 수행하지 않았다.

공통 launcher의 추가 설정:

- `--intent-host-policy`, `--reviewed-intent-host-sha256`, `--approve-intent-host` (distribution entry).
- 환경 설정 `GOLEM_INTENT_HOST_POLICY`, `GOLEM_INTENT_HOST_SHA256`, `GOLEM_APPROVE_INTENT_HOST`.
- D4 단독 stdio entry는 `--intent-host-policy`, `--reviewed-intent-host-policy-sha256`, `--approve-intent-host`.

세 설정이 모두 있어야 하며 값 하나만 선택하거나 profile만 바꿔 권한을 만들 수 없다. MCPB 생성기는 task/quality의 optional 설정을 만들지만 기존 설치 manifest를 수정하지 않는다. schema 생성 경로에 `schemas/intent-host.json`을 등록했다. 패키지 생성·설치 검증은 NOT_RUN이다.

## Native bridge와 lock

`golem_intent_host`는 기존 `intent_authority_host.c`의 D01 registration chain 검사와 새 `--product-fd` 경로를 사용한다. integration-host 빌드 옵션 아래 target을 등록했으며 이번에는 빌드하지 않았다. 이 bridge executable은 D01 등록의 별도 owner pin에도 포함되어야 한다. 일반 `golem completion` CLI에 숨겨진 기본 권한을 주지 않는다.

1. Python의 기존 `authorized_root`로 common-dir shared lock·등록/폐기·repository/authority identity와 producer를 대조한다. 이 함수 자체는 여전히 읽기 identity capability이며 mutation 권한이 아니다.
2. 별도 host 계약과 D4로 선택한 경우에만 상속 authority/review directory fd를 native bridge에 전달한다.
3. native registration chain을 확인한 뒤 authority lock을 닫고 Work writer lock을 연다. consistent read도 lock을 사용하지만 read operation은 게시하지 않는다.
4. QC1 host adapter가 owner policy/bundle·control·현재 파일 pin을 검사하고 QC3 scope를 연다. QC4/QC5가 실제 평가·publication을 수행한다.
5. parent는 native 종료까지 D01 lock을 유지하며 이후 등록·프로그램·packet pin을 재확인한다.

native callback의 fd 검사는 cooperative D01 lock 아래 현재 root identity를 확인하는 용도다. 같은 UID만으로 인간 승인·별도 보안 principal을 증명하지 않는다. 직접 임의 bridge 실행을 방어하는 OS sandbox를 새로 주장하지 않는다.

## 결과·불확실 상태·표시

결과는 native JSON 원문/해시와 함께 반환한다. transport returncode=0, 구조검사 성공, 과거 result 기록을 현재 ACCEPTED/DONE으로 바꾸지 않는다. 수락·완료의 저장 결과는 기존 D4 historical result 경로를 사용하고 현재 상태는 별도 query로 확인한다.

호출당 30초, stdout/stderr 각각 transport LIMIT을 적용한다. timeout·초과·불확실 결과에서 소유한 child process group을 종료하고 수집한 로그를 보존한다. D4는 dispatch-intent를 먼저 기록하므로 실패/유실은 COMMIT_UNKNOWN으로 남고 다른 request ID로 같은 action을 자동 재실행하지 않는다. 네트워크·credential·QA runner·서비스 시작·복구 권한은 추가하지 않는다.

일반 workflow 읽기가 새 완료 scope 없이 과거 기록을 조회하는 경우 native `co_hint`는 DONE 대신 `VERIFY_INTENT_COMPLETION`을 반환한다. 완료 기록이 없으면 기존 업무 흐름을 계속 읽을 수 있다. 이 표시는 QC5 완료 gate를 통과했다는 뜻이 아니다. M2 초안은 기존 record/status/next 현재성 대조와 만료·instance 계약을 유지한다.

## 작성한 검증과 남은 검증

`tools/test_integration_intent.py`: owner 동의 없음, 허용된 참조 형식, 임의 명령/승인 필드 거부, 미승인 초안, profile 상한, read→mutation 거부 fixture를 작성했다. `test_intent_completion.c`에는 scope 없는 일반 조회가 DONE을 반환하지 않는 fixture를 추가했다. 모두 **NOT_RUN**이다.

Python AST 문법 검사(모듈 import/호출 없음), source 연결 대조와 `git diff --check`만 수행한다. 다음은 HOLD 해제 후 별도 필요하다: native host 컴파일, fd/등록/폐기/lock 경쟁, QC4·QC5 정상/차단 동등성, packet drift, timeout/응답 유실, source/producer inventory 전체 검사, 패키지 import closure/생성, Codex·Claude 실제 도구 노출/조회/action, Owner 후보 검토, 다중 연결에서 자동 창 0개. 미실행을 PASS로 기록하거나 기존 원장을 최신 검증으로 승격하지 않는다.

기존 정책·승인·Work·증거·COMMIT_UNKNOWN과 누적 소스 변경을 보존한다. 이번 source를 실행하려면 별도 reviewed producer와 bridge pin 선택이 필요하며 기존 pin은 자동 수정하지 않는다.
