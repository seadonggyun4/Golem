# 안정적인 MCP 연결과 고정 도구 목록 설계

상태: **PROPOSED_NOT_IMPLEMENTED**. 이 문서는 새 연결 계약의 제안이며 현재 runtime·설치·정책을 변경하지 않는다. 기존 기본 동작인 **profile과 현재 owner 권한의 교집합만 노출**하는 계약을 유지한다. 별도 노출 범위와 연결 전환 계약을 확정하기 전에는 아래 interface를 구현·적용하지 않는다.

## 해결할 문제

현재 Golem은 owner의 정확한 action이 추가되면 MCP 도구 목록도 달라질 수 있다. 새 정책을 선택해 backend가 정상 시작해도 client가 같은 대화의 도구 목록을 다시 읽지 않으면 agent가 그 action을 요청할 도구를 받지 못한다. 앱 재시작을 매 action 준비 절차에 포함하는 방식은 정상적인 개발 흐름의 완료 조건이 될 수 없다.

현재 코드에서 목록과 실행의 결합은 다음과 같다.

| 코드 | 현재 계약 |
|---|---|
| [integration_feature_profiles.py](../tools/integration_feature_profiles.py) | `Scoped.tools()`는 profile과 현재 `service.tools()`의 교집합을 반환하고, `Scoped.call()`도 두 범위를 검사한다. |
| [integration_service.py](../tools/integration_service.py) | D1/D2·resource·Intent·owner 준비 서비스가 허용하는 조회·준비 도구만 제공한다. |
| [integration_mutations.py](../tools/integration_mutations.py) | 현재 승인된 D4 exact action에 해당하는 도구를 목록에 추가한다. 호출 때도 action·대상·입력·현재성을 다시 검사한다. |
| [integration_mcp.py](../tools/integration_mcp.py), [integration_mutation_mcp.py](../tools/integration_mutation_mcp.py) | 동적인 도구 이름을 이미 구현된 고정 schema로 변환한다. |
| [integration_transfer.py](../tools/integration_transfer.py), [integration_mutation_contract.py](../tools/integration_mutation_contract.py) | 선택한 정책의 bytes·producer·대상·action·native 승인 pin을 검사한다. 정책 파일의 임의 덮어쓰기는 거부한다. |
| [connection_relay.py](../plugins/golem/scripts/connection_relay.py) | child 교체 때 catalog 세대와 marker를 바꾸고 목록 변경 알림을 보낸다. 호스트의 재목록이나 모델 전달을 보장하지 않는다. |

[현재 연결 진단과 관측 계약](integration-connection-renewal.md)은 위 상태를 구분하고 잘못된 준비를 차단한다. 진단 통과나 알림·ACK만으로 같은 대화의 도구 전달 문제까지 해결됐다고 선언하지 않는다.

## 목표와 범위

owner가 명시적으로 선택한 유한한 도구 정의를 MCP 연결의 앞단에 유지한다. 같은 정의 안에서 D1/D2/D4의 허용 범위나 exact action이 바뀌어도 client가 도구 목록을 다시 받아야 하는 의존성을 없앤다. 실제 호출은 매번 현재 backend의 기존 권한·native 검사로 판단한다.

```text
Codex 또는 Claude의 같은 대화
        │ 고정된 이름·typed schema·설명·annotation
        ▼
client별 안정적인 MCP 진입점
        │ 선택한 catalog 밖 호출 차단
        │ 요청을 재생·재전송하지 않음
        ▼
현재 owner가 선택한 backend 세대
        │ D1 → D2 → D4 / 별도 resource·helper·host 계약
        ▼
기존 native parser·승인·lock·fence·CAS·완료 predicate
```

앞단의 고정 목록은 **사용 가능한 interface의 정의**다. 해당 Work의 접근권한, 등록된 action, 실행 가능성, QA PASS 또는 완료를 뜻하지 않는다. 미구현 scheduler·merge 기능은 이 목록에 추가하지 않는다. 모든 client를 하나의 공유 daemon이나 공통 권한으로 합치지 않는다.

## 1. 별도의 명시적 노출 계약

새 방식은 opt-in이어야 한다. 기존 `read/prepare/task/quality/parallel`의 현재 권한 교집합 방식은 기본값과 호환 경로로 남긴다. 기존의 좁은 노출 승인을 더 넓은 family 정의 노출 승인으로 해석하지 않는다.

계약 확정 때 다음 내용을 고정해야 한다. 아래 표는 필요한 필드의 의미이며 아직 JSON 형식이나 CLI를 확정한 것이 아니다.

| 선택 내용 | 제약 |
|---|---|
| client·전달 대상 | 기존 client별 분리를 유지한다. 다른 client의 동의를 가져오지 않는다. |
| profile과 정확한 도구 이름 | 선택한 profile 안의 검토된 유한 subset만 허용한다. 전체 제품의 자동 합집합을 만들지 않는다. |
| 도구 정의 inventory | 이름·typed input schema·설명·annotation의 canonical bytes와 hash를 고정한다. |
| catalog revision과 호환성 | 이전 정의와 동일한지 실제 bytes로 확인한다. 버전 문자열만으로 호환 판정하지 않는다. |
| 검토한 앞단 코드와 연결 범위 | 정확한 프로그램·선택 기록을 검토한다. 같은 OS 사용자라는 사실을 사람의 승인 인증으로 표현하지 않는다. |

정의에는 프로젝트 경로, Work 내용, action ID, 승인 bytes, credential을 넣지 않는다. generic `dispatch`, 임의 명령 실행, 정책 적용·승인 발급 MCP 도구를 추가하지 않는다. 기존 `SCHEMAS`와 typed 도구 이름을 재사용한다. resource·management·helper·Intent 등은 별도 검토 없이 자동으로 목록에 포함하지 않는다.

현재 설명의 “승인된 도구”라는 표현도 새 모드에서는 interface 정의와 호출 승인을 혼동하지 않도록 구분해야 한다. `projects_list`의 현재 허용 도구와 workflow 진단은 기존 교집합 의미를 유지하고, 고정 노출 목록과 별개로 보고한다.

## 2. 안정적인 진입점과 두 개의 세대

정책-only 갱신 때 client 설정의 executable 경로나 MCP 서버 identity를 계속 바꾸지 않는 진입점이 필요하다. 이 진입점은 client별 stdio 수명주기를 유지하며, owner가 선택한 backend만 제한적으로 교체한다. frontend의 신규 버전과 native/backend의 신규 버전은 서로 다른 갱신이다.

| 구분 | 변경 원인 | 대조할 근거 |
|---|---|---|
| catalog identity·revision | 도구 이름·schema·설명·annotation 또는 앞단 protocol ABI 변경 | 검토한 canonical inventory, 같은 대화에 실제 전달된 정의 |
| backend authority epoch | owner가 선택한 새 runtime·정책·등록·exact action 집합 | 정확한 old/new 선택 pin, 현재 child identity와 상태, 호출 시 기존 권한 검사 |

catalog identity는 같은 정의를 제공하는 동안 안정적이어야 한다. backend 교체만으로 catalog marker를 새로 만들고 모델의 정의 관측을 무효화하면 같은 문제가 남는다. 반대로 과거 catalog 관측을 최신 backend의 권한 적용 증거로 사용해서도 안 된다.

현재 v1 marker는 child 세대를 포함한다. 제안한 분리는 별도 versioned 계약으로 도입하고 v1의 의미를 사후에 바꾸지 않는다. 모델 관측은 **해당 대화가 그 interface를 받았음**만 나타낸다. 현재 backend 선택·owner 승인·native admission은 독립적으로 확인한다. marker는 상관관계 증거이며 chat 신원이나 사람의 승인 인증이 아니다.

진짜 ABI 변경 때는 기존 catalog를 현재 것으로 계속 제공하지 않는다. owner의 새 노출 선택, host의 지원되는 목록 갱신, 같은 대화의 실제 정의 관측을 다시 확인한다. host가 재목록을 지원하지 않거나 수행하지 않으면 명확한 차단 상태로 남긴다. 목록 변경 알림을 일괄 숨기는 방법으로 해결하지 않는다.

## 3. 호출 시 기존 검사를 그대로 유지

고정 목록은 `tools/list`만 담당한다. 호출은 다음 기존 검사에 연결한다.

1. 고정 노출 subset과 profile 상한을 검사한다.
2. 현재 backend의 `Scoped.call()`과 D2/D4 dispatcher를 사용한다. 도구가 목록에 있다는 이유로 `service.tools()`의 현재 권한 검사나 호출 경로를 건너뛰지 않는다.
3. D1의 client·project·Work·등록 세대·native pin과 D2의 tool·전달 대상·budget·producer를 검사한다.
4. D4의 정확한 action/request, 원본 입력 bytes, 승인 pin, helper/resource/host 계약을 검사한다.
5. 기존 native parser·승인·최신성·lease·lock·fence·CAS·완료 predicate가 실제 결과를 결정한다.

D4 실행 action이 0개여도 고정 interface 정의를 제공할 수 있다. 그 정의로 미승인 호출을 하면 기존의 차단 결과를 반환하고 native 실행은 0회여야 한다. 준비 결과·stored result·hash 일치·도구 정의 노출을 실행 승인이나 현재 완료로 승격하지 않는다.

`PENDING_APPROVAL`, `GRANT_STALE`, 정책·producer 변경, 결과 유실, `COMMIT_UNKNOWN`은 기존 의미를 유지한다. 오래된 요청을 새 backend에 자동 재전송하거나 이전 성공 결과로 새 호출을 성공 처리하지 않는다. 목록·초기화가 D5 참여 기록이나 Work 읽기를 불필요하게 발생시키지 않아야 한다.

## 4. owner 전용 backend 전환

고정 catalog와 현재 D1/D2/D4는 별개의 선택이다. agent가 임의 정책을 작성해 자신에게 선택하거나 승인할 수 있는 MCP 경로를 만들지 않는다. owner의 정확한 검토 뒤에만 old/new 선택의 CAS와 pin을 검사하는 로컬 제어면을 사용한다.

최소 전환 절차는 다음과 같다.

1. 새 정책·runtime·native·선택 자료를 별도 위치에 준비한다. 기존 immutable 정책·승인·기록은 보존한다.
2. 고정 catalog ABI와 backend 호환성, 정확한 old/new pin, 현재 client·연결 identity를 대조한다.
3. 해당 연결이 idle인지 확인하고 진행 중 요청·server request·partial frame이 있으면 전환을 차단한다. 다른 대화나 앱 전체를 종료하지 않는다.
4. 기존 drain·종료 확인·child 초기화 계약을 재사용해 해당 backend만 교체한다. 새 child의 protocol/ABI와 실제 선택을 확인하기 전에는 요청을 전달하지 않는다.
5. 같은 catalog라면 host-facing 목록과 connection은 유지한다. 실제 선택 결과는 backend epoch로 따로 보고한다.
6. 전환 실패·응답 유실·불확실 상태는 보존하고 중단한다. 자동 재시도·이전 backend fallback·rollback·진행 중 호출 replay를 하지 않는다.

정책 파일을 제자리에서 고쳐 기존 digest 검사를 우회하는 hot reload는 허용하지 않는다. runtime/source 변경이 producer 선택을 요구하면 그 검토도 그대로 필요하다. 기존 D5 유지보수나 여러 client의 등록 전환이 필요한 경우 그 절차를 생략하지 않는다.

## 5. 준비안과 시간 제한

기존 M2 준비안은 service instance·정확한 plan hash·등록 binding·현재 Work basis·유효기간에 묶인다. backend 교체 후 디스크의 과거 준비안을 새 instance에 등록하거나 수명을 연장하지 않는다.

정상 흐름은 다음과 같다.

```text
고정 interface 노출 확인
  → 현재 backend 선택 확인
  → 현재 입력으로 새 비권한 준비
  → owner의 정확한 검토·action 선택
  → 필요한 backend 권한 전환 확인
  → 현재 instance에서 실행 직전 준비·확인
  → 기존 exact action 호출·결과 조회
```

앞 단계의 실제 결과가 있어야 다음 action bytes를 확정할 수 있는 순서는 유지한다. 설치·연결 진단 중 짧은 native approval TTL을 먼저 소비하지 않는다. 검토 후보 생성은 정책 적용이 아니며 기존 요청의 재실행 승인도 아니다. 만료·stale·불확실 결과를 자동으로 새 request/plan으로 바꾸지 않는다.

## 6. migration과 적용 한계

이미 실행 중인 구 relay는 파일을 교체한다고 새 동작을 얻지 않는다. **구 실행 중 relay에 이 구조를 사후 주입할 수 없다.** 최초 전환에는 client가 지원하는 해당 연결 교체가 필요하며 실제 새 frontend identity와 도구 전달을 확인해야 한다. 앱 전체 재시작을 일상 action 처리나 반복 재시도의 기본 해법으로 삼지 않는다.

동일 host PID 아래 새 backend child가 생성되고, 같은 stdio connection·catalog hash·대화가 유지되는 관측은 정책-only 전환의 유효한 검증 근거가 될 수 있다. PID만으로 동일 대화나 사람의 승인을 인증하지 않는다. 다른 프로세스로 새 서버를 열어 성공한 것을 기존 Desktop 연결의 성공으로 대신하지 않는다.

다음은 별도 검증 범위다.

- 처음부터 잘못 캐시된 host 연결과 오래된 frontend의 최초 migration.
- 실제 catalog ABI 변경, SDK 변경, frontend 자체의 보안 업데이트.
- Codex와 Claude의 서로 다른 host 재목록·설치·수명주기 동작.
- 모델 계정 한도, 저장공간·권한·native 환경 오류.

따라서 “모든 변경에 재연결이 전혀 필요 없다”는 보장은 목표가 아니다. **같은 검토 interface 안의 정상적인 exact action·정책 전환에 앱 전체 재시작이 필요하지 않음**을 입증하는 것이 핵심이다.

## 확정해야 할 선택

| 선택 | 권고안 |
|---|---|
| 고정 정의 노출과 기존 호출 권한의 분리 | 별도 owner opt-in으로만 도입. 기존 설정 자동 migration 금지. |
| 처음 허용할 catalog 범위 | 선택한 한 profile의 검토된 유한 subset. 다른 family·관리·helper 권한 자동 추가 금지. |
| backend 선택 제어면 | client별 exact old/new pin·CAS·idle 전환. MCP 자기 승인·범용 실행 경로 금지. |
| readiness의 의미 | 같은 대화의 catalog 전달과 현재 backend 선택을 분리. 둘을 만족해도 새 준비 가능 상태이며 실행 승인이 아님. |

이 선택들은 아직 확정되지 않았다. 구현을 시작할 때 versioned schema, canonicalization, 저장 형식, CAS/결과 유실 처리, 명시적 활성화 방법을 P0 계약으로 확정한다. 이번 문서는 현재 정책에 그 선택을 적용하지 않는다.

## 단계별 구현·완료 조건

| 단계 | 구현 범위 | 완료 조건 |
|---|---|---|
| S0 계약 | 고정 노출·backend 선택·두 세대·호환·차단 상태 | 위 정책 선택과 정확한 wire/storage 계약을 검토하고 native/D1/D2/D4와 충돌 없음 확인 |
| S1 정의·호출 분리 | 정적 typed catalog와 기존 call gate 연결 | 기본 교집합 회귀 유지, 새 모드의 정의 제공이 권한을 추가하지 않음 |
| S2 안정적인 전환 | client별 앞단·exact backend 교체·불확실 결과 보존 | busy/경합/crash/응답 유실 시 replay0, 같은 ABI의 catalog bytes 유지 |
| S3 호스트 fixture | 같은 host·대화에서 정책-only 전환 | host가 목록을 다시 읽지 않아도 기존 도구 정의로 현재 backend에 전달; 기존 권한·HOLD 준수 |
| S4 실제 client 수락 | 명시적 격리 대상에서 Codex·Claude 각각 검증 | 앱 전체 재시작 없이 같은 대화의 승인된 흐름이 이어짐. 도구 노출·권한·native 결과 각각 근거 기록 |

## 필수 검증 대조표

| 시나리오 | 통과 기준 |
|---|---|
| 기존 mode | 교집합·직접 호출 차단·resource/helper/host 분리 회귀를 그대로 유지 |
| 새 catalog, D4 action0 | 선택한 고정 정의 노출; 모든 미승인 action은 native 실행 전 차단 |
| 같은 family의 action 추가·철회·만료 | host-facing catalog bytes/hash 불변; 호출 결과만 현재 권한에 따라 달라짐 |
| 다른 project·Work·client·profile·action·request | 기존 정확한 scope 검사로 차단, 교차 접근·승인 이전 없음 |
| 변경된 정책·producer·native·action bytes | 정확한 pin 검사를 유지하고 차단 |
| pending·stale·HOLD·fence·COMMIT_UNKNOWN | 자동 재시도·repair·replay 없이 원본 자료와 결과 보존 |
| 선택 경합·busy·partial frame·server request | 전환 차단, 진행 중 요청 중복 dispatch0 |
| 전환 중 crash·응답 유실 | 불확실 결과 유지; 자동 fallback·rollback·재실행0 |
| host가 목록을 재조회하지 않음 | 정책-only 전환은 같은 정의로 진행; 실제 ABI 변경은 current로 인증하지 않고 차단 |
| catalog 변경·잘못된 marker | 현재 정의/세대 대조 실패, 과거 대화 관측 재사용 금지 |
| 준비안이 남은 상태에서 backend 교체 | 과거 plan은 instance/basis 검사로 거부; 자동 부활·TTL 연장0 |
| initialize·tools/list·여러 연결 | 불필요한 참여 기록 증가0, Work 호출0, Owner 자동 창0 |
| 데이터 최소화 | 고정 정의에 경로·Work 내용·action bytes·secret 없음 |
| 실제 Codex·Claude | 각 client의 같은 대화·host·앞단·child·정의·허용 호출 근거를 따로 확인 |

검증 수준을 합쳐 보고하지 않는다.

- **소스·정적 대조**: 고정 schema, 권한 검사, 분기·효과·목록의 정합성만 확인한다.
- **격리 fixture·fake model**: no-relist·경합·결과 유실·재시도 차단 등을 재현한다. 실제 모델 대화 성공이 아니다.
- **실제 공식 host + 격리 모델 fixture**: 같은 host protocol과 next-turn 정의 전달을 검사한다. 현재 사용자 Desktop의 수락을 대신하지 않는다.
- **실제 client 대화**: 별도 승인한 격리 대상에서만 수행한다. 미노출·한도·미실행은 `NOT_RUN` 또는 구체적인 차단으로 남긴다.
- **native QA·완료**: 필요한 별도 exact 승인과 실제 native 결과로만 확인한다. 연결·catalog 통과에서 추론하지 않는다.

이 문서의 모든 신규 기능은 **미구현**이다. 제안의 테스트 항목을 과거 CI 통과나 현재 설치본의 검증 결과로 표시하지 않는다.
