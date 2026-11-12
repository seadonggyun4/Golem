# 안정적인 MCP 연결과 고정 도구 목록

상태: **OPT_IN_IMPLEMENTATION_CANDIDATE · ACTUAL_DESKTOP_NOT_RUN**. 사용자에게 승인받은 선택적 계약을 소스에 구현하고 격리 fixture로 검증하는 단계다. 현재 설치·정책을 자동으로 전환하지 않으며, 기존 기본 동작인 **profile과 현재 owner 권한의 교집합만 노출**하는 계약은 유지한다. 실제 Work 실행은 **HOLD**다.

## 해결 범위

같은 도구를 호출하는 데 필요한 exact action이나 정책이 바뀔 때마다 앱 전체를 재시작하는 흐름을 없애기 위한 선택적 경로다. owner가 고른 유한한 도구 정의는 연결 앞단에 고정하고, 그 정의를 해석하는 backend와 실제 권한은 별도로 검토·선택한다.

```text
Codex 또는 Claude의 같은 대화
        │ 고정된 이름·typed schema·설명·annotation
        ▼
client별 stable stdio 진입점
        │ catalog 밖 요청 차단
        │ 현재 선택 admission + 기존 호출 경로
        ▼
owner가 정확히 선택한 backend epoch
        │ D1 → D2 → D4 / 별도 resource·helper·host 계약
        ▼
기존 native parser·승인·lock·fence·CAS·완료 predicate
```

고정 목록은 **interface 정의**이며 Work 접근, 등록된 action, 실행 가능성, QA PASS 또는 완료가 아니다. backend 전환만으로 모델이 이미 받은 정의를 무효화하지 않지만, 과거 모델 관측을 현재 backend 권한의 증거로 사용하지도 않는다. generic dispatch·임의 명령 실행·MCP 자기 승인·자동 권한 이전은 추가하지 않는다.

## 구현 경계

| 경로 | 역할과 한계 |
|---|---|
| [integration_stable_catalog.py](../tools/integration_stable_catalog.py) | 기존 profile·SCHEMAS의 명시적 subset으로 catalog 후보와 새 private broker bundle을 만든다. 설치·등록·선택 적용은 하지 않는다. |
| [stable_entry.py](../plugins/golem/scripts/stable_entry.py) | 별도의 owner 전용 CLI. 검토한 bundle 전체 bytes를 대조한 뒤 선택 저장·조회·relay 실행·정확한 연결 제어로 제한한다. 기존 plugin launcher의 기본 분기는 바꾸지 않는다. |
| [stable_contract.py](../plugins/golem/scripts/stable_contract.py) | canonical catalog와 선택 lineage, private 파일, owner lock, 이전 head CAS, 정확한 adapter approval·launcher pin을 검사한다. 선택 저장 성공과 실제 연결 반영을 구분한다. |
| [stable_relay.py](../plugins/golem/scripts/stable_relay.py) | client별 고정 catalog를 제공하고 기존 backend의 typed 호출 경로를 사용한다. idle인 정확한 연결만 EOF 종료 확인 후 한 번 교체하며 실패·유실을 재실행하지 않는다. |
| [integration_stable_readiness.py](../tools/integration_stable_readiness.py) | 디스크 선택·현재 backend·고정 정의 전달·외부의 같은 대화 관측을 분리해 판정하는 순수 함수다. I/O·권한 부여·실행은 하지 않는다. |

owner-local entry의 operation은 다음과 같이 분리한다. 각 operation은 `--reviewed-bundle-sha256`, `--client`, `--store`를 입력받으며, 아래 표가 실제 선택·설치 승인을 대신하지 않는다.

| operation | 추가로 고정하는 입력·효과 |
|---|---|
| `create` | 새 store에 검토된 catalog·최초 selection을 한 번 저장. `--approve-selection` 필요 |
| `publish` | exact 이전 head hash와 새 selection hash를 CAS로 연결. `--approve-selection` 필요 |
| `inspect` | 현재 store·catalog·approval/launcher pin만 읽기 |
| `serve` | owner가 client에 명시적으로 연결한 stable stdio frontend 실행 |
| `status` | 정확한 client/connection instance의 private 제어 socket에 상태 조회 1회 |
| `refresh` | exact marker·old/target selection을 지정한 child 전환 1회. `--approve-refresh` 필요 |
| `readiness` | exact hash로 읽은 외부 model/refresh 관측과 명시적 필요 도구를 현재 선택·상태와 대조. 원래 관측 시간을 재설정하지 않음 |

`readiness`는 `--connection-instance`, `--model-observation`, `--model-observation-sha256`, 반복 가능한 `--require-tool`을 요구한다. 전환 시도가 있었다면 `--refresh-evidence`와 `--refresh-evidence-sha256`을 함께 제공한다. `refresh`는 `--connection-marker`, `--expected-selection-sha256`, `--target-selection-sha256`, `--approve-refresh`를 요구한다.

`readiness`의 외부 관측 파일은 자동으로 만들지 않는다. marker·대상 대화·turn·실제 도구 이름은 실제 client 관측에서 가져와야 하며, 파일 hash를 고정했다는 사실만으로 내용을 진실로 인증하지 않는다. 이 CLI가 과거 실패·불확실 결과를 해소하거나 새로운 실행을 승인하지 않는다.

[기존 연결 진단](integration-connection-renewal.md)의 v1 marker와 이번 v2 marker는 다른 계약이다. 기존 Owner 패널이나 설치된 launcher가 새 계약을 자동으로 지원한다고 간주하지 않는다. optional CLI·격리 fixture의 성공을 현재 Desktop 연결의 성공으로 바꾸지 않는다.

## 확정한 P0 계약

### 명시적 catalog 노출

`golem.fixed-tool-catalog.v1`은 한 profile 안에서 owner가 검토한 정확한 도구 subset이다. broker의 `typed-interface.json`(`golem.typed-interface-inventory.v1`)도 bundle manifest에 포함해 정확한 profile·이름·schema·설명·annotation과 대조한다. 이 inventory가 없거나 변경됐으면 수작업 catalog도 채택하지 않는다. 이름·input schema·설명·annotation의 canonical bytes와 hash를 고정한다. 현재 D4 action이 0개여도 정의를 선택할 수 있지만, 호출하면 기존 권한 검사가 그대로 차단한다.

- 생성기는 기존 typed schema를 복사하며 기본 profile의 권한 교집합을 변경하지 않는다.
- catalog admission과 backend 호환성 검사도 검토된 유한 inventory에 연결한다. 파일명·도구 이름만 같다는 이유로 호환으로 처리하지 않는다.
- 도구 정의에 프로젝트 경로·Work 내용·action ID·승인 bytes·credential을 넣지 않는다.
- resource·management·helper·Intent 또는 다른 family를 자동으로 포함하지 않는다.
- catalog 변경은 기존 store의 policy-only 갱신으로 처리하지 않는다. 새 노출 선택과 host가 지원하는 연결/정의 갱신을 다시 검증해야 한다.

### 선택 lineage와 결과 유실

`golem.stable-selection.v1`은 client, revision, 이전 선택 hash, catalog hash, adapter state, 정확한 approval·launcher pin을 묶는다. `golem.stable-head.v1`은 현재 선택을 가리킨다. Codex와 Claude Desktop의 선택·local socket namespace는 분리한다.

한도는 catalog 512KiB, 도구 128개, selection/head 파일 16KiB, 선택 lineage 256개다. 한도를 자동 확대하거나 과거 기록을 지워 공간을 만들지 않는다. private 제어 request nonce는 연결당 총 1,024개, endpoint discovery는 client별 디렉터리 항목 최대 1,024개로 제한한다. 종료 기록의 자동 prune·카운터 자동 초기화는 없다.

owner-local `create`/`publish`는 정확한 검토 hash와 명시적 선택 동의가 필요하다. 기존 승인 bytes를 변경하지 않고 이미 검토된 adapter state만 참조한다. 같은 OS 사용자라는 사실을 사람의 신원 인증으로 표현하지 않는다.

- owner lock과 이전 head hash CAS로 publication을 직렬화한다.
- 기존 선택 기록을 보존하고 revision 누락·rollback·catalog 변경·approval drift를 차단한다.
- 공개 중 pending·부분 출력·fsync 실패는 불확실 상태로 보존한다. 자동 repair·rollback·재시도는 없다.
- 현재 head를 검사한 뒤 실제 요청을 전달하기까지의 admission도 publication과 직렬화한다. 검사 뒤 새 선택이 끼어들어 오래된 backend로 신규 호출이 나가는 창을 허용하지 않는다.
- 선택 publication은 `SELECTED_NOT_LIVE_APPLIED`다. 모든 실행 중 연결을 자동으로 바꾸거나 현재 연결 성공으로 주장하지 않는다.

### 고정 frontend와 backend ABI

frontend marker는 `golem-catalog-v2:<instance>:<catalog-sha256>:<nonce>`다. backend epoch와 분리되며 호환되는 backend 교체에서는 marker와 실제 정의 bytes를 유지한다. v1 marker를 v2로 재해석하지 않는다.

새 backend는 실제 구현된 catalog ABI의 exact 증거를 제공해야 한다. 최초 초기화와 replacement 초기화 모두에서 protocol·capability 및 검토한 catalog ABI를 대조한다. 동일 도구 이름 아래 input schema·설명·annotation이 바뀌면 호환으로 처리하지 않는다. ABI 관측은 제품 실행이나 Work 조회가 아니다.

고정 frontend의 `tools/list`는 선택한 정의만 반환한다. backend의 동적 권한 목록이 바뀌었다는 알림 자체는 frontend ABI 변경 증거가 아니며, 승인된 고정 ABI 대조를 대신하지 못한다. host의 재목록이 없어도 동일 interface 안의 정책-only 전환이 가능해야 한다. 실제 ABI 변경을 숨겨 같은 정의로 계속 실행하는 것은 허용하지 않는다.

### 기존 호출 권한

1. catalog subset 밖 이름과 미지원 RPC는 frontend에서 차단한다.
2. 선택이 현재 head와 일치하는지 검사한 뒤 기존 `Scoped.call()`·D2/D4 dispatcher로 전달한다.
3. D1 client·project·Work·등록 세대·native pin, D2 tool·전달 대상·budget·producer를 기존대로 검사한다.
4. D4 exact action/request·원본 입력·승인 pin과 별도 resource/helper/host 계약을 기존대로 검사한다.
5. 실제 효과와 성공은 native 승인·최신성·lease·lock·fence·CAS·완료 predicate가 결정한다.

정의 노출·준비 완료·stored result·hash 일치는 실행 승인이나 현재 완료가 아니다. `PENDING_APPROVAL`, `GRANT_STALE`, 만료, 결과 유실, `COMMIT_UNKNOWN`은 기존 의미로 차단한다. 이전 호출을 새 backend에 재전송하지 않는다.

### 정확한 owner-local 전환

정확한 client·연결 instance·현재 marker·old/new 선택 hash를 지정한다. 새 선택은 먼저 별도 private 자료로 검토·저장해야 하며 relay가 디스크 head를 자동 채택하지 않는다.

1. 현재·target 선택과 기존 adapter approval을 다시 대조한다.
2. pending client/server request·partial frame·읽지 않은 transport 데이터가 있으면 전환을 차단한다.
3. 해당 child의 stdin EOF와 정상 exit 0을 기다린다. 강제 종료하거나 다른 연결을 종료하지 않는다.
4. target child를 한 번 시작하고 protocol/capability·catalog ABI·선택 pin을 재검사한다.
5. 그 사이 들어온 요청은 새 정책으로 전달하지 않는다. 현재 선택이 바뀌면 불확실 상태로 남긴다.
6. 결과 유실·drain/initialize 실패는 자동 재시도·fallback·rollback 없이 보존한다.

전환 ACK는 현재 backend를 다시 관측해야 하는 중간 결과다. 과거 선택으로 남은 다른 연결은 보존하며, 신규 호출은 stale 검사로 차단한다. 이 프로세스의 transport idle은 native Work·lease가 idle이라는 인증이 아니다.

## 사용 흐름과 준비안

```text
기존 typed subset의 미승인 catalog + 별도 broker 후보 생성
  → owner가 exact bundle/catalog/선택 자료 검토
  → client의 지원 경로로 최초 stable 연결 선택
  → 같은 대화의 실제 고정 정의 관측
  → 현재 backend 선택과 ABI 관측
  → 현재 instance에서 새 M2 준비
  → owner exact action 검토·별도 backend 선택/전환
  → 최신 backend 상태 확인 후 기존 native 계약으로 진행
```

현재 구현은 위 흐름의 **연결·준비 선행 조건**을 제공한다. 실제 설치·정책 선택·Work 실행은 별도 정확한 범위 승인 없이 수행하지 않는다.

기존 M2 plan은 service instance·plan hash·Work basis·등록 binding·유효기간에 묶인다. backend 교체 후 과거 plan을 되살리거나 TTL을 연장하지 않는다. 짧은 native 승인 TTL은 설치/연결 진단을 통과한 뒤 실제 입력이 고정된 단계에서 준비한다.

readiness는 fresh한 현재 backend 증거와 외부 관측의 대상 대화·turn·marker·정확한 전체 도구 inventory를 대조한다. 두 관측의 유효시간은 5분이며 자동 갱신하지 않는다. backend 교체 후 host가 같은 정의를 다시 읽을 필요는 없지만, 새 backend 상태 증거는 반드시 필요하다. 성공은 `PREPARATION_READY_NOT_AUTHORIZED`이며 실제 실행 HOLD를 해제하지 않는다.

## 최초 migration과 유지보수 한계

이미 실행 중인 구 relay는 파일 교체만으로 새 구조가 되지 않는다. 최초 전환과 frontend 자체의 ABI/보안 업데이트에는 client가 지원하는 해당 연결 교체가 필요하다. 앱 전체 재시작을 매 action 처리의 기본 절차나 반복 재시도로 권장하지 않는다.

동일 host PID·stdio·catalog를 유지한 상태에서 새 backend child가 정상 반영된 관측은 policy-only 전환의 근거가 될 수 있다. PID는 대화 신원이나 사람의 승인 증거가 아니다. 별도 app-server 성공을 현재 Desktop 대화 성공으로 바꾸지 않는다.

모든 변경에 재연결이 없다는 보장이 아니다. **동일한 검토 interface 안에서의 정상적인 exact action·정책 전환이 전체 앱 재시작이나 host 재목록에 의존하지 않음**을 검증하는 것이 목표다. 계정 한도·SSD/권한 오류·호스트 미지원·기존 cache 문제는 별도 결과로 남긴다.

## 검증과 완료 조건

| 범위 | 필요한 근거 |
|---|---|
| 기본 mode 회귀 | 기존 profile 교집합·직접 호출 차단·권한 경계 불변 |
| catalog/admission | 기존 finite typed subset만 허용, 임의 이름·schema·변경된 ABI 거부 |
| 선택 publication | exact pin·lineage·CAS·경합·부분 출력·불확실 결과 보존 |
| 호출과 선택 경합 | shared admission 중 publication 차단, 이미 진행 중 요청 replay 0 |
| stdio 전환 fixture | 같은 frontend·정의·marker, 새 backend epoch, host 재목록 없이 기존 typed 호출 전달 |
| backend ABI drift | 최초/교체 initialization에서 차단, 이전 backend fallback·자동 재시도 0 |
| busy/crash/유실 | pending·partial·server request·drain 실패·응답 유실을 성공으로 승격하지 않음 |
| client 분리 | Codex/Claude endpoint·selection 격리, 다른 연결 자동 교체 없음 |
| 준비안·권한 | 이전 plan 부활·승인 이전·TTL 연장·native 검사 우회 0 |
| 기본 설치 | 기존 public launcher·client 설정·정책·권한·Owner 앱 자동 표시 동작 불변 |
| 실제 Desktop 수락 | 양쪽의 같은 대화에서 최초 migration·정의 노출·정책-only 전환·승인된 조회를 별도로 관측 |

검증 수준은 구분한다.

- **소스·정적**: 고정 schema·분기·효과·기존 권한 호출 경로를 대조한다.
- **격리 fixture**: synthetic backend와 임시 private 저장소로 정상·경합·crash·유실을 검사한다. 실제 모델이나 Work 성공이 아니다.
- **공식 host + 격리 모델 fixture**: 같은 host protocol/대화의 no-relist 동작을 확인한다. 현재 사용자 Desktop의 수락을 대신하지 않는다.
- **실제 Codex·Claude 대화**: 현재 **NOT_RUN**. 이번 소스 구현·fixture 결과를 설치 완료나 실사용 통과로 표시하지 않는다.
- **native QA·완료**: 실행 **HOLD**. 기존 별도 exact 승인과 실제 결과가 필요하다.

실제 client 수락, 기존 Owner UI의 새 stable 제어 통합, 설치 migration은 각각 구체적인 구현·관측 근거가 생겼을 때만 완료 처리한다. 관련 fixture나 정적 검사를 통과했다는 이유로 미구현·미실행 범위를 완료로 바꾸지 않는다.
