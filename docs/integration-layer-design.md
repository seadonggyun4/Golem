# Golem Integration Layer and MCP Design

상태: **설계 + D1 일부 구현**. 작성·소스 검토: 2026-10-21.
기준 소스: `96ad031b3a28b189ee7183fcff2f6c34c0ddecfb`.
schema·프로젝트 승인 registry·읽기 backend의 구현 범위는 [D1 계약](integration-d1.md)에
정리한다. 새 client installer, hook, 인증 서비스 또는 MCP 서버의 완료를 의미하지 않는다.
기존 계약은 각 링크가 권위이며 D1 계약에서 구현했다고 명시한 것 외의 새 이름·경로는 제안이다.
MUST/금지는 향후 구현 요구사항이며 과거 저장 형식을 소급 변경하지 않는다.
연구 근거·열람 범위·대안 비교: [조사 기록](integration-layer-references.md).

## 1. Product Boundary

AWE는 **Agentic Workflow Engine**이다. Golem은 서로 다른 AI agent가 작업 상태와
검증 증거를 이어받아 협업하는 경량 헤드리스 엔진이다.

| 주체 | 책임 |
| --- | --- |
| Agent | 사용자 의도 해석, 계획·코드 수정·도구 사용·판단 |
| Golem core | 작업·의존성·소유권·인계·증거 관리와 제출 유효성의 기계적 검사 |
| Integration layer | 승인된 client와 프로젝트 연결, 동일 core 계약으로 입출력 중개 |
| MCP adapter | integration 서비스를 tools/resources로 노출. 별도 workflow 판정기 아님 |

[책임 계약](agent-golem-boundary.md)을 유지한다. 승인된 QA 실행은 가능하지만 범용
agent 실행 daemon, 모델 선택·호출, 모든 대화 수집은 필수 기능이 아니다.
공유 대상은 승인된 작업 자료·관측 사실·명시적으로 작성한 판단 변경분이다.
MCP 연결이 client의 전체 대화·숨은 지침·내부 추론 접근권을 만들지는 않는다.

| 목표 | 제외 범위 |
| --- | --- |
| 사용자 단위 설치 후 여러 client 연결 | 공식 ChatGPT/Claude 설치 프로그램 변경·자동 번들 포함 |
| 프로젝트 최초 승인 후 검증된 연결 재사용 | 홈 전체 탐색·발견한 저장소의 무조건 초기화 |
| 세션 시작/재개 시 진단·맥락 전달 | hook 실행만으로 claim/resume/heartbeat/reconcile |
| 원래 fencing·승인·QA·완료 계약 재사용 | MCP용 상태 머신·memory DB로 core 대체 |
| client/SDK 변경을 adapter에 격리 | 분산 HA·다중 장치 CAS 동기화·범용 agent 직접 실행 |

## 2. Existing Contracts and Gaps

기준 소스의 문서와 구현을 함께 확인한 재사용 지도다.

| 기존 지점 | 재사용 계약 | 필요한 연결 |
| --- | --- | --- |
| [agent_entrypoint.py](../tools/agent_entrypoint.py), [설치](agent-entrypoint.md) | 지침 보존, plan/apply/check, SDK/CLI/file pin | 여러 client 설정의 관리형 설치 |
| [instruction_bundle.py](../tools/instruction_bundle.py), [bundle](instruction-bundles.md) | 비-Git 부모·명시된 자식 저장소의 검토된 지침 | 자동 부모 상속을 가정하지 않는 registry |
| [agent_session.h](../include/golem/agent_session.h), [coordinator.c](../src/agent_session/coordinator.c) | status/next, claim/begin/submit, 명시적 resume/reconcile, exact-key replay | host 신원과 native session의 mapping |
| [session_binding.h](../include/golem/session_binding.h), [runtime profile](runtime-profile.md) | host 관측·session fence·불변 runtime binding | 승인 client/runtime mapping |
| [context.h](../include/golem/context.h), [context resume](context-resume.md) | freshness·정확한 projection·provider count·handoff | host별 전달과 실제 로딩의 독립 관측 |
| [Work records](work-records.md), [증분 이력](incremental-history.md) | 원본 보존 조회·검증 cursor | client별 cursor/cache·누락/재시작 처리 |
| [execution](execution.md), [approval](approvals.md), [completion](completion.md) | 승인 명령·receipt·현재 완료 판정 | typed 도구·승인 UI와 기존 callback 연결 |
| [facts/judgments](fact-judgment.md), [evidence](evidence-verification.md) | 관측/판단 분리·증거별 검증 차원 | handoff의 파생 읽기 모델 |
| [usage pipeline](usage-pipeline.md), [integrations](usage-integrations.md) | 소유 stream·Work 귀속·native import | client별 선택적 연결; 미관측은 0이 아님 |

기존 Python/TypeScript binding은 capsule validate/replay/adapter description 중심이다.
[Python binding](../bindings/python/src/golem_runtime/__init__.py)을 완전한 session SDK로
가정하지 않는다. 초기 backend는 기존 CLI의 `--output-mode full`과 고정 argv를 사용한다.
C facade는 별도 ABI·동등성 검증 후 같은 backend interface 아래 추가한다.

## 3. Architecture and Modules

```text
Owner-controlled installer / project approval UI
                 |
        private integration registry
                 |
Client A -- stdio MCP adapter A --+
Client B -- stdio MCP adapter B --+-- integration service
CLI/hook ------------------------+         |
                                     NativeBackend
                                pinned CLI / future C facade
                                           |
                              existing core gates and locks
                                           |
                               project/.golem/Work stores
```

기본은 **client가 필요할 때 시작하는 stdio 프로세스**다. 여러 프로세스가 같은 core
store lock을 사용한다. 연결 수명 동안 Work handle을 열어 잠금을 점유하지 않는다.
provider count·사용자 승인·네트워크 대기 중 Work lock을 유지하지 않는다.
원격 gateway는 12절의 선택적 모드이며 기본 daemon이 아니다.

| 제안 모듈 | 책임 | 금지 |
| --- | --- | --- |
| `integration/registry` | 설치·project·grant·binding 검증 | native Work 이벤트 수정 |
| `integration/install` | 관리 항목 계획·적용·검사·제거·복구 | 사용자 설정 전체 재생성 |
| `integration/clients/<client>` | 탐지·probe·설정 렌더링·입력 전달 | core 판정 복제·사용량 추측 |
| `integration/service` | 승인·주체·요청·관측의 공통 중개 | workflow reducer 복제 |
| `integration/native_backend` | strict JSON·고정 argv·bounded subprocess·원본 보존 | shell 문자열·자유 argv·PATH 검색 |
| `integration/mcp` | 공식 SDK 기반 framing·profile·도구 매핑 | client 이름을 인증으로 취급 |

모듈 경계는 논리적이다. D1은 기존 도구 패턴에 맞춘 `tools/integration_*.py`로 구현하며
위 디렉터리 구조를 새로 만들지는 않는다. 향후 MCP 구현은 공식
MCP SDK의 검증된 release를 lockfile로 고정한다. 선택 SDK의 실제 protocol 지원을 먼저
검사한다. 미지원 profile은 비활성화하며 독자 JSON-RPC 구현으로 메우지 않는다.
transport·client 설정·domain service·native backend는 독립 시험 가능한 경계로 유지한다.

## 4. Invariants and Threat Model

| ID | 불변조건 |
| --- | --- |
| I1 | QA·수락·DONE 권위는 core. integration READY/DELIVERED는 native DONE이 아님 |
| I2 | client/project 연결은 owner/sequence/token/input/source/binding 검사를 대체하지 않음 |
| I3 | 불명확한 효과·live foreign owner·손상에서는 자동 재실행·강제 인수·저널 수정 금지 |
| I4 | 탐지·설정·clientInfo·roots·모델의 승인 문장은 프로젝트 승인 증거가 아님 |
| I5 | 읽기 전용 경로는 Work/CAS/저널/receipt/문서 revision을 쓰지 않음 |
| I6 | 취소/timeout/응답 유실은 효과 없음이 아님. 옛 receipt는 새 lease가 아님 |
| I7 | 맥락·handoff·cache는 파생물. 필수 원문 누락·예산 초과를 숨기지 않음 |
| I8 | pin·승인·보호 검사를 유지. 기존 Work·증거의 자동 migration 없음 |
| I9 | project·주체·수신처 경계를 목록·원문 조회·쓰기에서 모두 검사 |
| I10 | native fencing ID·파일 해시·session label은 인증이나 내용 진실성 증명이 아님 |

신뢰: 설치를 승인하는 사용자/조직 정책, 선택한 host/실행 파일, OS 사용자 경계.
비신뢰: 저장소 문서·모델 출력·MCP 인자·다른 client 선언·외부 tool 결과.
프로젝트 파일이 권한을 늘리거나 hook executable을 선택하지 못한다.
같은 OS 계정의 악성 프로세스가 registry를 바꾸거나 core CLI를 직접 실행하는 공격까지
이 계층만으로 차단하지 않는다. 강한 격리에는 별도 OS 사용자·sandbox·host 경계가 필요하다.
pinning은 TOCTOU를 전부 해결하는 sandbox가 아니다 [S8, S9, S13].

## 5. Multi-Client Installation

### Storage

`USER_CONFIG`, `USER_DATA`, `USER_CACHE`는 OS별 표준 경로로 해석하고 계획에서 실제
위치를 보여준다. Unix 0700/0600 또는 동등 ACL을 적용한다. 프로젝트가 이 root를 바꾸거나
환경 확장으로 다른 곳을 가리키지 못한다. 아래 layout은 제안이다.

```text
USER_CONFIG/golem/integration/v1/
  clients/<client-id>.json       # owner-approved config references
  projects/<project-id>.json     # roots and grant generations
USER_DATA/golem/
  releases/<release-id>/         # immutable engine + matching SDK + adapter
  integration/installs/<id>/     # plans, backups, receipts
  integration/requests/<id>/     # bounded request/reply records
USER_CACHE/golem/integration/    # rebuildable projections/cursors
project/.golem/
  integration/manifest.json      # proposed non-secret reference
  workspace/works/...            # existing owner-selected layout
```

기존 `.golem`의 실제 배치는 프로젝트별로 다르며 예시대로 이동시키지 않는다.
기존 `.golem/project.json`을 native 자동 발견 계약으로 해석하지 않는다.
새 manifest만으로 로컬 grant가 생기지 않는다. credential/grant는 Git에 넣지 않는다.
ignore는 암호화·유출 방지가 아니다.

### Install State Machine

`DISCOVERED -> PLANNED -> OWNER_APPROVED -> APPLIED -> RELOAD_REQUIRED -> VERIFIED`.
불일치/중단은 `BLOCKED/PARTIAL`. 적용과 실제 client 활성화 검증을 분리한다.

1. 사용자가 지정한 client/profile 위치만 탐지한다. 홈·대화 저장소 전체를 스캔하지 않는다.
2. format-aware parser로 계획한다. unknown key·주석·비관리 항목을 보존할 수 없으면
   무손실 patch 또는 수동 적용을 사용한다. 설정 전체를 parse/re-serialize해 덮어쓰지 않는다.
3. plan은 대상 path/file identity, before/after bytes, 관리 scope, executable/SDK/plugin digest,
   installer version, 권한·변경 이유를 포함한다. 사용자에게 정확한 diff를 보여준다.
4. apply는 사용자 승인과 정확한 plan digest 둘 다 요구한다. digest는 인증 자체가 아니다.
   현재 bytes/identity 재검사, installer 배타 lock, private backup 후 파일별 atomic publish.
5. 여러 파일 전체가 원자적이라고 주장하지 않는다. manifest를 마지막에 게시한다.
   중간 실패·사용자 변경은 보존하고 검토 없는 rollback/재적용을 금지한다.
6. 사용자 reload 후 실제 도구 발견·읽기 요청·선택적 hook 관측을 검사한다. 설정 존재만으로
   HOOK_ACTIVE나 모델 로딩을 판정하지 않는다. hook trust도 별도다.
7. 제거는 여전히 일치하는 관리 항목만 대상으로 한다. grant 폐기와 설정 제거를 구분한다.
   Work·과거 SDK pin·증거·사용자 hook·다른 프로세스는 삭제/종료하지 않는다.

전역 설치는 client 연결을 제공할 뿐이다. 프로젝트 `.golem` 생성은 별도 승인 후 최초
attach 시 허용할 수 있다. 최초 승인에 초기화 범위가 포함됐으면 그 결정적 bootstrap만
반복 승인 없이 허용한다. 새 Work·계획·QA 명령을 자동 생성하지 않는다.

### Client Matrix

| Surface | 설계 경로 | 제한 |
| --- | --- | --- |
| Codex 로컬 host 계열 | 공식 MCP 설정 adapter, 실제 profile probe [S5] | 설정 공유와 hook 지원은 별개. exact host/version 확인 전 자동 hook 미지원 |
| Claude Code | scope adapter, opt-in SessionStart/compact hook [S6] | interactive/noninteractive trust가 달라도 Golem grant는 별도 검사 |
| Claude Desktop | 별도 adapter와 local MCP probe | Code용 설정/hook 복사 금지. 자동 context는 검증 전 UNKNOWN |
| ChatGPT/Claude 웹·원격 host | 승인 HTTP gateway 또는 staged context | local stdio·디스크·hook이 있다고 가정하지 않음 |
| 미지원 client | 명시적 CLI 진입·읽기 context | 자동 로딩으로 표시하지 않음 |

기능별 `DECLARED/OBSERVED_SUPPORTED/UNSUPPORTED/UNKNOWN`, probe 범위·시각·버전을 기록한다.
실제 요청 관측만 승격한다. 제품명/user-agent는 인증이 아니다. hook 미지원 시 명시적 진입으로
대체하며 안전 검사 자체를 생략하지 않는다. 공식 설치 프로그램에 Golem을 포함하는 설계는 아니다.

## 6. Identity and Project Consent

| ID | 발급/관측 주체 | 의미·한계 |
| --- | --- | --- |
| `installation_id` | installer의 난수 ID | 로컬 설치, 사람 신원 아님 |
| `principal_id` | trusted host/인증 issuer mapping | 실행 주체/원격 계정, model 이름과 별개 |
| `client_instance_id` | 승인 adapter | 병렬 창/프로세스, 이름만으로 host 인증 아님 |
| `client_session_ref` | host가 공개한 reference | 대화 참조, 내부 대화 수집 권한 아님 |
| `native_session_id` | host mapping, 기존 grammar 준수 | core fencing label, 인증 credential 아님 |
| `project_id` | owner-approved registry | root/worktree 등록. basename/remote URL로 대체 불가 |
| Work identity | 기존 core | Work ID + spec digest + 등록 store identity. 복제가 새 Work는 아님 |

stdio는 승인된 launch/profile과 OS 사용자 경계에 binding한다. MCP clientInfo는 선언이다.
host가 session 신원을 제공하지 않으면 모델이 입력한 ID를 인증된 대화 ID로 승격하지 않고
`LOCAL_COOPERATIVE`로 기록한다. 강한 host 인증이 필요한 정책에서는 해당 client 쓰기를 막는다.
같은 계정의 두 client를 독립된 사람·독립 QA로 인증했다고 주장하지 않는다.
원격은 issuer/sub/audience mapping을 local delegate에 연결한다.
credential은 도구 인자·resource·prompt·CAS에 넣지 않는다. opaque binding handle도 원래
인증 주체·grant에 매 요청 결박하며 다른 주체가 복사해 사용할 수 없다.

### Proposed Records

새 schema family: `golem.integration-project.v1`, `golem.integration-grant.v1`,
`golem.integration-client-binding.v1`. 구현 전 closed JSON Schema와 golden fixture가 필요하다.

| Record | 최소 필드 |
| --- | --- |
| Project | project ID, canonical root/OS file identity, `.golem` root, enumerated repository/worktree roots, manifest digest, engine/SDK pins, generation |
| Grant | issuer/principal/client scope, project identity/generation, Work IDs/spec digests 또는 명시적 creation scope, operations/data classes/destinations, validity/revocation generation, approval reference |
| Binding | principal/client instance/host session assurance, project/grant generation, native session mapping, runtime/profile pin, lifecycle status |

권한은 `project.inspect`, `work.read`, `context.read`, `work.write`, `execution.request`,
`evidence.export` 등으로 분리한다. execution.request도 native 실행 승인을 대체하지 않는다.
새 Work는 별도 creation grant와 기존 bootstrap 계약을 사용한다. 모델이 scope를 늘리지 못한다.

새 ID는 원칙적으로 난수 ASCII reference로 만들고 기존 native ID grammar와 한도를 그대로
검사한다. generation/sequence는 범위가 검증된 비음수 정수로 bool/float와 구별한다.
digest는 해당 기존 계약의 lowercase SHA-256, optional/UNKNOWN은 명시 enum으로 표현한다.
unknown key/version, duplicate key, invalid UTF-8/NUL, 과도한 nesting·배열·문자열을 거부한다.
새 schema는 native schema와 섞지 않고 기존 bytes를 임의 canonicalize하지 않는다.
mutation의 session_id는 승인 binding의 native mapping과 일치해야 하며 모델이 다른 owner를
이름만 바꿔 가장하지 못한다. native binding의 attach는 쓰기 operation이므로 readonly attach
hook에서 호출하지 않는다. 이름이 같아도 두 attach의 의미는 별개다.

장기 project consent와 단기 mutation capability를 구분한다. 후자는 boot/clock/expiry에
의존할 때 trusted host가 검증하며 boot 변경·clock 역행을 만나면 자동 연장하지 않는다.
폐기·만료·clock 불확실 시 새 dispatch를 차단한다. 읽기 권한도 별도 grant 상태를 따른다.

root 이동·교체는 같은 pathname/remote URL만으로 재신뢰하지 않는다. worktree의 common dir,
backlink, checkout identity를 구분한다. 쓰기 root는 개별 등록한다. symlink/hardlink/reparse
point/case alias는 거부 또는 OS별 검증된 명시 등록을 요구한다. 문자열 prefix 포함 검사 금지.
미등록 부모/자식 저장소에 승인을 상속하지 않는다. 이동 재승인은 Work migration이 아니다.
grant current generation을 매 요청 확인한다. 폐기는 신규 read/dispatch를 막지만 이미 전달한
대화 입력을 회수하거나 발생한 효과를 취소한 것으로 표시하지 않는다.

## 7. Common Requests and Native Dispatch

service 요청은 version, operation, opaque binding reference, project/Work identity와 관측/입력
reference를 갖는다. mutation에는 stable request_id, exact native bytes/digest, native key와
expected_sequence 및 해당 operation의 모든 fence가 필요하다. 인증 context는 transport/host가
제공하며 모델 JSON에서 만들지 않는다. raw path/argv/env/shell을 받는 범용 도구는 금지한다.

1. SDK wire/profile 검사 후 schema·size·UTF-8·duplicate key를 검증한다.
2. principal/binding/grant/root/pins/data destination을 검사한다.
3. read는 지정된 native read-only API로 원본 결과·시각·heads를 반환한다.
4. mutation은 integration admission 후 grant/pin을 다시 확인하고 원래 native request를 전달한다.
   native가 같은 store lock 아래 현 owner/lease/sequence/input/source/binding을 검사한다.
5. 원래 receipt/진단/stdout bytes/exit status를 보존하고 별도의 integration 상태를 도출한다.

grant 폐기/업데이트와 dispatch는 같은 프로젝트 admission 순서로 직렬화한다.
lock order는 `integration project admission -> native Work lock`; 역순 금지.
장기 외부 실행은 admission lock을 계속 잡지 않고 host gate가 dispatch 직전 재검사한다.
이후 폐기는 진행 중 효과에 대해 CANCELLATION_REQUESTED일 뿐 취소 성공이 아니다.
원격 승인·provider count 동안 lock을 보유하지 않는다. 직접 core CLI/C API는 이 추가 인증
계층을 통하지 않을 수 있어 전 경로 인증이 강제된다고 주장하지 않는다.

### Approval Channel

관리·외부 효과 승인은 모델 tool-call 인자 밖의 owner-controlled 채널에서 수집한다.
기존 [approval.h](../include/golem/approval.h)의 describe/decide/recheck/receipted execution을
재사용한다. UI가 보여주는 정확한 action digest, operation, Work/source/input scope와
issuer·policy epoch·유효기간을 결박한다. decide는 이미 수집된 결정을 즉시 읽고 Work lock
안에서 사용자 입력을 기다리지 않는다. dispatch 때 recheck가 폐기/epoch/현 fence를 확인한다.
소비 intent 후 실패는 원래 UNCERTAIN이며 다시 dispatch하지 않는다. MCP 승인 확인만으로
native 승인 receipt나 별도 shell/외부 시스템 승인이 생겼다고 해석하지 않는다.
UI 연결이 없으면 PENDING_APPROVAL에서 멈춘다. 자동 승인 callback은 시험 fixture 외에 금지한다.

### Idempotency and Ambiguity

integration request identity는 principal/project/Work/spec/operation/exact native bytes에 결박한다.
JSON-RPC ID는 업무 idempotency key가 아니다. 같은 ID·다른 bytes는 REQUEST_CONFLICT.
dispatch 전에 원래 key/bytes를 private durable record에 보존한다.
native commit과 integration 기록은 단일 transaction이 아니다.
`NOT_DISPATCHED/NATIVE_RESULT_RECORDED/COMMIT_UNKNOWN`을 구분한다.
COMMIT_UNKNOWN에서 새 key로 자동 재실행하지 않는다. 보존된 동일 bytes/key와 원래 core의
명시적 재호출 규칙으로 조사한다. 역사적 receipt는 현 lease·효과 권한이 아니다.

read는 native store를 쓰지 않아도 private audit/cache를 남길 수 있다.
native_state_changed와 integration_record_written을 구분한다. 필수 audit 실패 시 차단하고
cache 실패를 빈 성공으로 바꾸지 않는다. read-only 시험도 두 저장 범위를 따로 검사한다.

## 8. Context Delivery and Changes

### Read-Only Attach

attach는 읽기 전용 논리 작업이다. binding 등록은 별도 owner-approved enrollment다.
프로젝트가 미승인이면 승인으로 돌아가며 Work가 여러 개면 명시 선택한다.
최근 사용·경로·대화 요약으로 Work를 자동 선택하지 않는다.

1. pin/grant/root/client의 provider·remote destination을 검증한다.
2. full native status/next를 조회·보존한다. head/sequence가 다르면 bounded 재조회 또는 차단.
   읽기는 예약이 아니며 무한 안정화 loop를 만들지 않는다.
3. [current selection](current-context-selection.md)과 [projection](context-projection.md)을 재사용한다.
   semantic summary·최근 N개·별도 dependency graph를 새로 만들지 않는다.
4. 지원 입력 채널로 전달하고 scoped 원문 reference를 제공한다.
5. AVAILABLE/DELIVERED_TO_HOST/HOST_ACKNOWLEDGED/NOT_OBSERVED를 구분한다.
   host acknowledgement도 모델의 이해·준수 증명이 아니다.

startup/compact hook은 이 read 절차만 수행한다. hook이 없으면 같은 service를 명시 호출한다.
실패 시 맥락 동기화 실패·원인을 보여주고 예전 cache로 준비 완료를 선언하지 않는다.

### Budgets

실행 handoff는 current-v1/original-v1 complete recipe, renderer v2, freshness, 원문 누락 0 계약을
유지한다. v1은 기존 소비자에만 명시 사용한다. projection_digest/provider input_sha256/native
receipt를 혼합하지 않는다. 정확한 envelope/count는 [context_resume.py](../tools/context_resume.py)를
재사용한다. Hosted client가 전체 대화·tools·tokenizer를 공개하지 않으면 전체 예산은 UNKNOWN.
일부 projection count로 전체 대화 예산이 검증됐다고 표시하지 않는다.
reading aid는 `context_role: READING_AID`; 완전 실행 입력과 분리한다. 필수 입력 누락/예산 초과는
차단하고 명시적 예산·범위 검토를 요청한다. 전체 대화 수집을 우회 해결책으로 만들지 않는다.

### Incremental Synchronization

history schema 2 cursor를 client/project/Work/spec/root/binding에 결박한다. 소비 상태와 cursor를
함께 저장하고 stream+sequence+digest로 재전달 중복을 제거한다. invalid/prefix mismatch는 원래
FULL pagination으로 reset하고 has_more를 처리한다. corrupt CAS는 fallback으로 숨기지 않는다.
notification은 재조회 hint다. 유실·역전·재접속·profile별 차이는 bounded polling으로 보완한다.
stream 사이 전역 순서를 wall time으로 추측하지 않는다 [S10]. cache로 lease/current DONE을 확정하지 않는다.
cache key는 schema/renderer/recipe/heads/source/binding/policy/provider-envelope identity를 포함한다.
cache/index는 재구성 가능해야 한다. 원래 replay의 O(total history) 비용은 남을 수 있고
O(delta) disk access·token/비용 절감은 측정 전 주장하지 않는다.

## 9. Safe Handoff and Resume

handoff는 검증 참조·판단 전달이지 소유권 transfer API가 아니다. native에 없는 release/transfer를
수행한 것처럼 표시하지 않는다. 제안 `golem.integration-handoff.v1`은 project/Work/spec/store,
producer assurance, 관측 heads/sequence/source/selection, runtime/instruction pins, 상태,
context/evidence/receipt와 judgment-delta refs, 미확정 효과, 다음 native operation을 담는다.
기존 fact/judgment/export를 조합하며 긴 assessment를 반복 작성하지 않는다.
원문 참조가 끊기면 INCOMPLETE이고 자동 완료 불가다. 생성은 private integration bundle만 쓴다.
수신자는 자기 grant로 다시 검사하고 발신자의 권한을 상속하지 않는다. 선언 provenance를
서명된 신원·독립 QA로 승격하지 않는다.

| 경계 | 허용 | 금지 |
| --- | --- | --- |
| live foreign owner | WAIT·owner/lease 근거 | 강제 인수·heartbeat 대행 |
| 같은 owner | 명시적 의도와 현 fence로 계속 | attach hook만으로 연장/실행 |
| CLAIMED·효과 시작 전 | 기존 명시적 resume 후 fresh claim 검토 | 임의 release event |
| RUNNING 중단·효과 불명 | RECOVERY_REQUIRED·효과 조사·명시적 reconcile | no-effects 추정·재실행 |
| reboot/clock 역행/active=null | native preflight와 명시적 resume | 시계 보정·자동 resume |
| stale sequence/token/input/source/binding | 원래 진단과 current 읽기 | 최신 token 임의 선택·오류 성공 변환 |
| DENY/손상 | 차단·원본 보존·정식 복구 안내 | 정책 완화·journal/CAS 수정 |
| verified DONE | current completion 읽기 | reboot 정리용 resume·과거 PASS 승격 |
| 과거 Work | 지원 schema의 read compatibility 검사 | 자동 enrollment/migration/downgrade write |

live claim을 다른 client에 즉시 옮기는 native 기능은 새로 약속하지 않는다. 기존 완료/만료/
명시 recovery 조건의 대기를 제품 제약으로 표시한다. Work lease는 source 파일 격리가 아니다.
같은 checkout을 병렬 수정하려면 별도 Work·승인된 [workspaces](workspaces.md)/admission을 쓰거나
cooperating writers를 직렬화한다. client 수 증가 자체가 안전한 동시 작업의 근거는 아니다.

## 10. MCP Surface

### Protocol Profiles

기준은 `2026-07-28`; legacy `2025-11-25` 지원은 별도 profile이다. modern request별 version과
server/discover, legacy initialize를 SDK adapter에 격리한다. native binding을 transport session과
섞지 않는다. modern HTTP에 legacy GET stream/session을 그대로 적용하지 않는다 [S1, S2].
Roots는 deprecated이고 원래도 access-control이 아니다. 새 승인에 쓰지 않고 legacy hint만
허용한다 [S3]. sampling/elicitation/tasks 확장은 필수가 아니다. 승인 UI가 없으면 owner-side
승인 경로와 PENDING_APPROVAL을 반환한다. 모델의 approve=true는 human approval이 아니다.
modern multi-round-trip/legacy 승인 요청 차이는 transport adapter에 한정한다.

### Proposed Tools

미구현 이름이다. 독립 closed schema·권한·한도를 갖고 임의 operation dispatcher는 노출하지 않는다.

| Tool | 매핑 | 효과 |
| --- | --- | --- |
| `golem_projects_list` | 승인 registry subset | read; 미승인 path/타 project 이름 누출 금지 |
| `golem_work_inspect` | record/status/next/completion | read; 독립 관측 구분 |
| `golem_context_get` | candidate/render | read; publish 몰래 호출 금지 |
| `golem_history_read` | history schema 2 | read; FULL/DELTA/has_more 유지 |
| `golem_evidence_read` | scoped store/CAS read | read; data class 검사 |
| `golem_handoff_prepare` | fact/judgment/evidence bundle | integration write, native read-only |
| `golem_session_claim` | 원래 claim | native write; 모든 fence 유지 |
| `golem_session_begin` | 원래 begin | native write; 효과 시작과 구분 |
| `golem_session_resume` | context-aware explicit resume | native write; preflight/count/fence |
| `golem_session_reconcile` | 원래 resolution/output/evidence | native write; 명시적 효과 판단 |
| `golem_document_submit` | 원래 문서 등록 | native write; session submit과 별개 |
| `golem_session_submit` | 원래 output/evidence submit | native write; 문서 등록으로 대체 금지 |
| `golem_execution_request` | approval/receipted execution | 승인 contract만, raw shell 금지 |
| `golem_completion_check` | 원래 completion 읽기 | read; finalize/report materialize 아님 |

초기 읽기 release는 read 도구만 제공한다. start/heartbeat/reject_output/finalize 등은 원래 CLI에
남기고 각 typed 도구를 별도 명세·시험 후 추가한다. escape hatch는 만들지 않는다.
installer apply/grant approve/auto-repair 관리 도구는 모델에 제공하지 않는다.
tools/list·resources/list는 요청 인증의 허용 subset으로 결정한다. 같은 권한의 목록이
select_project 같은 연결 상태에 따라 달라지는 설계를 피한다. 매 호출에 project/Work를 명시한다.
readOnlyHint 등 annotation은 UI hint이며 집행의 대체가 아니다 [S4].

### Resources, Data and Results

제안 URI: `golem://projects/<id>/works/<id>/context/<digest>`,
`golem://projects/<id>/works/<id>/evidence/<digest>`.
raw filesystem path/임의 URL을 dereference하거나 digest만으로 전역 CAS를 읽지 못한다.
등록 Work의 허용 graph·data class·destination을 재검사한다. 같은 bytes라도 다른 Work의
grant를 추론하지 않는다. raw evidence에 native token/개인정보가 있으면 data-class 정책에 따라
차단하거나 승인된 별도 파생물을 제공하고 원본 digest와 구분한다. 원본은 다시 쓰지 않는다.

structured result는 schema/state/request_id/scope/observed heads/native result ref/blockers/
next operation/evidence refs/assurance를 갖는다. 기본은 간결 조회, 원문 별도 보존이다.
required 입력은 reference만 제공해 전달 완료가 아니다. URI 미지원 host에는 scoped fetch를
제공하고 완전한 필수 입력 수신이 안 됐으면 실행 handoff를 차단한다.
untrusted 자료를 tool description/서버 지침과 섞지 않는다. Markdown 명령·승인·URL을
권한으로 해석하지 않는다. 임의 자동 fetch·cross-project search를 기본 제공하지 않는다 [S13].
private mode도 redaction이 아니며 자동 secret 탐지 보장은 없다.

### Errors

wire/schema/unsupported-version은 profile의 표준 오류로, domain 실패는 구조화된 tool error와
isError로 전달한다. native code/phase/diagnostic/errno와 원본 ref를 redaction 후 보존한다.

| 제안 domain code | 다음 처리 |
| --- | --- |
| PROJECT_APPROVAL_REQUIRED / GRANT_REVOKED | owner-side 승인/재등록 |
| CLIENT_ASSURANCE_INSUFFICIENT / PIN_MISMATCH | host probe/검토 업데이트 |
| OBSERVATION_STALE / CONTEXT_BUDGET_EXCEEDED | current 읽기/예산 검토, truncation 없음 |
| LIVE_OWNER / RECOVERY_REQUIRED | WAIT/효과 조사, takeover/retry 없음 |
| REQUEST_CONFLICT / COMMIT_UNKNOWN | 원래 bytes/receipt 검사, 새 key 금지 |
| UNSUPPORTED_CONTRACT / NATIVE_FAILURE | 미지원/원래 진단; fallback 권한 확대 금지 |

현재 native schema가 아닌 제안 예시:

```json
{
  "schema": "golem.integration-error.v1",
  "state": "BLOCKED",
  "code": "COMMIT_UNKNOWN",
  "request_id": "request-001",
  "native_state_changed": "UNKNOWN",
  "integration_record_written": true,
  "automatic_retry_allowed": false,
  "next_operation": "INSPECT_ORIGINAL_NATIVE_REQUEST",
  "evidence_refs": []
}
```

## 11. Updates and Recovery

단위는 engine commit/binary digest + matching SDK + integration schema/client adapter + MCP SDK/
protocol profile + instruction bundle이다. version 문자열만으로 같다고 판정하지 않는다.
project pin이 권위이며 전역 latest 설치가 pin을 바꾸지 않는다. 공용 pin-verifying launcher를
쓸 수 있으나 launcher 변경도 설치 승인이 필요하다.

`CHECK -> STAGE -> VERIFY -> QUIESCE -> OWNER_APPROVE -> SWITCH -> RELOAD -> READ_ONLY_VERIFY`.
새 immutable destination에 stage한다. 기존 CAS/저널/receipt/문서 revision과 진행 attempt의
binding을 수정하지 않는다. 모든 참여 client의 quiescence가 확인되지 않으면 switch를 보류한다.
임의 구형 CLI 실행까지 OS 수준으로 막는 기능이라고 주장하지 않는다.

doctor·지원 schema 읽기·synthetic Work 시험·기존 승인 Work의 무변경 status/next를 분리한다.
기존 Work를 probe로 resume하지 않는다. 미지원 schema는 차단하고 old binary로 쓰지 않는다.
profile default refresh는 미래 claim만 바꾸며 기존 attempt 정체성은 보존한다.
protected bytes와 tracked/dirty metadata는 구분하되 byte 동일만으로 재기준화하지 않는다.
원래 selection/contract approval/checkpoint 절차를 안내한다. GIT_PAGER 같은 금지 상속 환경은
값 노출 없이 진단하고 launcher는 명시 allowlist 환경을 쓴다. 실패 시 정책을 낮추지 않는다.

현재 source-build는 owner가 소스·dirty 변경분·build 근거를 검토하는 수동 승인 모드다.
hash만으로 publisher authenticity를 주장하지 않는다. 무인 download/update를 추가하려면
신뢰 root·서명 metadata·expiry·rollback/freeze 방지·key rotation이 필요하다 [S12, S15].
현 구현의 TUF/in-toto 준수를 주장하지 않는다. clock 불확실/metadata 만료는 무인 update 차단.
config drift는 새 plan/approval 대상으로 자동 overwrite하지 않는다.

| 실패 | 복구 |
| --- | --- |
| 설치 중간 실패 | backup/현재 bytes/manifest 비교, 관리 항목만 승인 복구 |
| 새 native event 없는 switch 실패 | 보존 artifact·compatibility 검토 후 승인 pointer 복원 |
| 새 event/효과 발생 후 실패 | 단순 downgrade·옛 디렉터리 복원 금지, 원본 보존·조사 |
| 이동/SSD 분리/root 교체 | I/O·effect uncertainty 보존, 재승인 전 신규 dispatch 금지 |
| 종료/제거 | 자신이 소유한 adapter/child만 종료 요청; 다른 client/VM/PID 무단 종료 금지 |

## 12. Remote and Hosted Mode

원격 client의 local project 접근은 owner가 선택한 gateway/delegate가 필요하다. 기본 localhost
server를 외부 공개하는 설정 변경으로 대체하지 않는다. 다른 장치가 network filesystem의 같은
`.golem`에 쓰는 모델은 지원하지 않는다. 한 권위 host가 기존 core lock을 사용한다.
MCP HTTP auth, issuer/audience/expiry 검증, scope/project mapping, revocation, TLS, Origin/DNS
rebinding 방어, rate/queue/body/timeout 한도가 필요하다 [S2, S7]. provider token passthrough 금지.
stdio proxy도 downstream 주체를 공용 credential 하나로 섞지 않는다.
HTTP 인증 성공과 work.write/QA 승인은 별개다. local read 권한은 cloud 전송 권한이 아니므로
project/data class/destination grant를 확인한다. scoped staged export도 선택할 수 있다.
연결 단절 시 결과는 STALE/UNKNOWN이며 과거 PASS를 current DONE으로 승격하지 않는다.
Hosted 제품별 권한·hook·원문 로딩 지원은 실제 시험 전 UNKNOWN이다.

## 13. Scale and Maintenance

- core reducer/store/approval/budget을 복제하지 않는다. backend별 동일 fixture로 동등성을 검사한다.
- Work lock은 짧게 사용한다. 독립 project/Work 읽기는 bounded concurrency·fair queue로 분리한다.
- request/output 한도는 native 한도를 우회하지 않는다. 더 작은 MCP 한도는 scoped paging/ref를
  사용하되 필수 입력은 완전 수신을 확인한다. truncation을 성공으로 보이지 않는다.
- cache/cursor/spool/audit quota·보존 정책을 설정한다. pending/COMMIT_UNKNOWN은 자동 GC하지 않고
  공간 부족 시 쓰기를 차단한다. native evidence는 cache GC 대상이 아니다.
- latency·queue·blocker·전달 bytes·원문 조회를 관측하되 credential/prompt는 기본 telemetry 제외.
  실제 tokens/cost는 기존 provider adapter 관측만 사용한다. null은 무료가 아니다.
- config/integration/MCP/native 버전을 분리한다. 새 도구는 owner·schema·권한·client profile·
  deprecation 계획을 함께 갖는다. unknown version은 차단한다.
- SDK/client release마다 fixture와 실제 host smoke를 실행한다. mock만으로 지원을 확대하지 않는다.

## 14. Verification and Delivery Gates

아래는 **향후 구현 수락 시험**이며 이번 문서 작성의 PASS가 아니다. native/service/실제 MCP/
실제 client 활성화를 각각 기록한다. 명령·exit code·JUnit·소스/dirty diff·binary/SDK hash·doctor·
platform·미검증 항목을 묶는다.

| ID | 조건 | 필수 결과 |
| --- | --- | --- |
| T01 | 기존 설정/주석/hook, 반복 설치/제거, stale plan | 비관리 bytes 보존·중복 없음·stale 거부 |
| T02 | 여러 파일 중간 crash/동시 installer/reload 누락 | PARTIAL/RELOAD_REQUIRED·backup·허위 활성화 없음 |
| T03 | 미승인/폐기 grant, clientInfo 위조, 복사 handle | read/list/write 거부; I2/I4/I9 |
| T04 | root 교체/symlink/worktree/복제 Work | identity 거부, 자동 재신뢰 없음 |
| T05 | 두 client 동시 claim/resume/live foreign owner | 원래 fence, WAIT, mutation 원자성 |
| T06 | status 이후 sequence/lease/source/binding 변화 | 최종 native 거부, cached preflight 우회 없음 |
| T07 | reboot/clock 역행/active=null/lease equality | 기존 preflight 동일, hook no-write |
| T08 | RUNNING/효과 후 응답 유실/SIGKILL | COMMIT_UNKNOWN/RECOVERY_REQUIRED, 자동 재실행 0 |
| T09 | exact-key replay/다른 bytes/취소와 늦은 응답 | 옛 receipt 의미 유지, 충돌 거부 |
| T10 | DONE/old schema/missing·corrupt CAS/DENY | DONE no-resume, 미지원·손상 차단 |
| T11 | required 누락/예산 초과/count 뒤 입력 변화 | complete-input/freshness/digest 유지 |
| T12 | cursor mismatch/event 추가/유실/중복/역전 | FULL 재동기화·has_more, lease 추론 없음 |
| T13 | 악성 문서 승인/shell/URL/타 Work digest | 권한 확대 불가·scoped retrieval·data 취급 |
| T14 | QA 승인 거절/만료/FAIL 결과 | 원래 approval/recheck/receipt, self-score 완료 불가 |
| T15 | update 중 client 잔존/old writer/event 뒤 rollback | 보류/차단, evidence overwrite 없음 |
| T16 | inherited Git env/credential/protected metadata | allowlist·진단·정식 재기준화 외 우회 없음 |
| T17 | modern/legacy/unknown version/없는 hook·resource | 실제 wire/profile, 명시적 수동 대체 |
| T18 | HTTP issuer/audience/Origin/교차 project/proxy | auth/승인 분리·passthrough/누출 거부 |
| T19 | disk full/queue·size·depth 한도/stdout 잘림 | bounded 실패·불완전 JSON 성공 금지·불확실성 보존 |
| T20 | 실제 두 client startup/compact/handoff/reload | discovery/host 전달/native gate 독립 관측 |

read-only 시험은 native 전체 inventory/hash/mode와 생성·삭제까지 비교한다. integration cache/
audit 변화는 별도다. synthetic disposable Work가 기본이며 실제 제품 Work는 승인된 읽기만
허용한다. 비공개 설치·제품 증거를 공개 fixture에 복사하지 않는다.
macOS/Linux 지원은 실제 native platform/filesystem 조건에 따른다. Windows native runtime은
현재 보장하지 않는다. Windows client -> Linux host도 별도 검증이다. physical reboot/power loss,
network filesystem, 모든 과거 engine, Hosted 활성화는 시험하지 않으면 NOT_VERIFIED다.
clock injection은 물리 재부팅 시험이 아니다.

### Delivery Sequence

| 단계 | 범위 | Gate |
| --- | --- | --- |
| D0 | 이 설계·근거·traceability | 설계 검토; 구현 완료 아님 |
| D1 | registry/grant/installer + readonly CLI backend | closed schemas, T01-T04/T10/T16/T19, no-write |
| D2 | readonly MCP + explicit context/handoff | real wire/profile·두 client, T11-T13/T17/T20 |
| D3 | opt-in startup/resume hooks | host별 지원 관측·failure fallback, 자동 write 없음 |
| D4 | typed mutations·승인 QA | T05-T10/T14와 native 회귀·동시성·sanitizer |
| D5 | staged update/reload/recovery | T02/T15와 참여 client quiescence |
| D6 | optional remote gateway | 별도 보안 검토·T18·승인된 실제 Hosted 연결 |

D1의 schema·승인 registry·읽기 backend는 구현했다. client installer를 포함한 D1 전체와
D2-D6는 완료하지 않았다. 다음 단계는 D1 계약의 검증된 범위 위에 client 설치와 D2의
읽기 MCP를 별도로 구현하는 것이다.
이 설계 작성은 실제 자동 설치·맥락 이해·비용 절감·제품 운영의 실증 결과가 아니다.

### Document-Only Review Results

2026-10-21 macOS 작업에서 새 문서의 로컬 참조·JSON 예시·S1-S15 참조와 T01-T20 식별자,
변경 파일의 whitespace를 검사했다. 재사용 기반의 기존 Python suite
`test_agent_entrypoint`, `test_instruction_bundle`, `test_context_resume`는 **56/56 통과**했다.
이 테스트는 disposable fixture/기존 provider mock 경로이며 새 MCP 서버·client hook·remote
인증·실제 provider 입력을 시험한 것이 아니다. native runtime 전체·Linux/Windows·원격 CI를
이번 문서 작업으로 재검증하지 않았다. 기존 제품 설치/Work/VM은 변경하지 않았다.
