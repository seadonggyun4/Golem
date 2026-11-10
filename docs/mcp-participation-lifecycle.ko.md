# MCP 도구 탐색과 D5 참여 기록 수명주기

상태: **2026-11-10 수정 런타임의 양쪽 새 Desktop 대화·기존 권한 읽기 검증 통과**.
도구 정의 탐색만 할 때 참여 기록은 늘지 않았고, 실제 조회를 시작한 연결마다
참여 기록이 한 개만 추가됐다. 제품 실행·QA·완료는 `NOT_RUN / HOLD`다.

공개 main에 반영하는 범위는 참여 수명주기 런타임 5파일, 해당 fixture·정적 검증과
문서다. 설치된 개발 snapshot의 다른 변경을 이 커밋에 포함하지 않는다.
특히 공개 D4의 기존 action schema는 유지한다. 아래 실제 client 결과는 선택된
설치 runtime의 관측이며, 이 커밋 전체의 신규 설치 검증으로 확대하지 않는다.

## 확인한 원인과 근거의 한계

기존 D4 stdio 경로는 MCP 요청을 받기 전에 `lifecycle.participation()`을 호출했다.
이 함수는 registry에 새 `d5-client-*` 디렉터리와 `participant.json`, `live.lock`을
만들고, 연결 종료 시 lock descriptor만 닫는다. 기록을 삭제하지 않는 것은 기존 보존
계약이다. 따라서 실제 Work 도구를 호출하지 않은 짧은 도구 탐색 연결도 기록을 남겼다.
문제의 설치 snapshot은 D4 action 0개인 읽기 연결에서도 이 시작 경로를 사용했다.
공개 main의 action schema와 설치 snapshot의 권한 구성을 구분한다.

```text
기존: MCP 프로세스 시작 → D5 참여 기록 → initialize / tools/list → 선택적 tools/call
수정: MCP 프로세스 시작 → initialize / tools/list
                                      ↓ 첫 실제 tools/call
                         기존 D5 참여·fence 확보 → 기존 도구/권한 검사 → 호출
```

문제 확인 당시 검증 캠페인은 client별 참여 기록을 최대 12개로 제한했으나
Codex registry에는 13개가 남았다. 기존 기록은 모두 같은 승인 binding이었고 삭제하거나 다시 작성하지
않았다. 증거는 다음 수준으로 구분한다.

| 관측 | 확인 가능한 결론 | 확정하지 않은 내용 |
| --- | --- | --- |
| 로컬 probe 전후 inventory와 프로세스 기록 | 4개는 승인된 동시 3연결·재연결 1회에서 추가됐다 | 다른 연결의 호출 주체 |
| Desktop catalog 조회 구간과 기록 생성 시각 | 5개 생성 시각이 각각 catalog 요청 시작~응답 구간에 들어간다 | 각 기록을 만든 정확한 PID·요청 ID |
| 나머지 생성 시각과 서버 starting/ready 로그 | 4개는 개별 서버 시작 구간과 시간상 일치한다 | 시간 일치만으로 인증한 client 신원 |
| 마지막 기록과 catalog 조회 | 13번째도 반복된 catalog 생성 패턴과 일치한다 | 13번째의 정확한 호출 주체 |

`participant.json`은 binding을 저장하며 PID·Desktop 요청 ID를 저장하지 않는다.
따라서 catalog 탐색이 참여 증가를 유발한다는 코드 경로와 반복된 시간상관관계는
확인했지만, **13번째 caller 자체는 미확정**으로 유지한다. Desktop 로그의
`serverCount=13`은 전체 MCP 서버 수이며 참여 기록 13개의 증거가 아니다.
개인 경로·프로젝트명·대화 ID·원본 로그는 private 감사 자료에만 보관한다.

이후 수정본 적용 전까지 기존 연결의 추가 기록도 보존했고, 이번 설치 adapter 검증
시작 시에는 Codex 22개·Claude 6개였다. 이 과거 증가는 아래 새 검증의 증가분에
합치거나 소급 승인하지 않는다. 새 검증 전후는 각각 22→22, 6→6으로 대조했다.

## 12개 캠페인 한도와 128개 registry quota

두 숫자는 별개 계약이다. 12개는 해당 검증 묶음에서 승인한 캠페인 한도이고,
128개는 기존 D5 구현이 검사하는 보존된 참여 디렉터리 수의 상한이다. 살아 있는
프로세스 수의 상한이 아니다. 128개 검사 통과는 12개 캠페인 한도 준수를 뜻하지 않는다.

이번 수정은 두 한도를 늘리거나, 과거 참여 기록을 삭제하거나, 캠페인 한도를 소급해
바꾸지 않는다. 호출 예산에는 도구 실행 횟수와 연결 참여 횟수를 따로 기록한다.
승인된 캠페인 한도를 넘으면 추가 검증을 멈추고 원인과 미실행 항목을 남긴다.

## 수정 계약: D4 stdio의 첫 실제 호출에서 참여

변경 범위는 Desktop stdio의 네 진입점(공통 entry, 직접 D4, management, Owner)에서
**참여 확보 시점**을 옮기는 것이다.
`initialize`, 알림, `tools/list`만 수행한 연결은 D5 참여 기록을 만들지 않는다.
정책·producer·tool scope 검사나 metadata 응답의 기존 한도는 생략하지 않는다.

- 첫 실제 `tools/call`을 전달하기 전에 기존 `lifecycle.participation()`으로 registry
  lock·binding 구조·maintenance fence·128개 quota를 검사하고 live lock을 확보한다.
  현재 등록·권한은 이어지는 기존 도구 경로에서 다시 검사한다.
  조회 도구를 호출하는 경우도 포함한다. 참여 전에 backend/native 호출을 수행하지 않는다.
- 같은 연결의 후속 호출은 확보한 참여를 유지한다. 첫 호출이 동시에 들어와도 참여를
  중복 생성하거나 검사 전에 한 호출을 전달하지 않는다.
- 등록 실패·maintenance·quota·결과 불확실 상태에서는 원래 거부 계약을 따른다.
  실패한 도구를 자동 재호출하거나 기존 intent/result를 새 ID로 다시 실행하지 않는다.
- 종료 시 해당 연결의 descriptor만 닫는다. 기록은 보존하며 다른 연결·Owner 앱·
  프로세스를 종료하지 않는다. 재연결은 새 연결이고 과거 준비안이나 승인을 되살리지 않는다.
- Owner의 준비안 조회·후보 저장은 MCP 밖의 로컬 검토 경로에서도 같은 참여 guard를
  통과한다. 연결·빈 준비안 목록만 확인하는 동작은 참여를 만들지 않는다. UI 경로를
  이용해 현재 binding·fence 검사를 우회할 수 없다.
- D2 경로의 기존 읽기·감사 계약과 [D6](integration-d6.md)의 등록·전달·감사 계약은
  유지한다. D6 hook뿐 아니라 `integration_gateway.py`의 HTTP app lifespan도
  delegate마다 시작 시 참여를 확보하는 기존 동작을 유지한다. D6를 Desktop stdio의
  도구 탐색 수명주기로 재분류하지 않는다.

정확한 action·owner·native 승인·lock·CAS·완료 predicate는 그대로다. 참여 기록을
만들었다는 사실은 실행 승인, 인간 신원 인증, QA PASS 또는 완료가 아니다.
Owner 창을 자동으로 열지 않는 기존 headless 계약도 유지한다.

## 검증과 설치 상태

아래 완료 조건은 구현·fixture·실제 client 검증을 구분해서 기록한다.

| 검증 | 완료 조건 | 현재 결과 |
| --- | --- | --- |
| 초기화·목록·재연결 fixture | 네 stdio 진입점의 실제 SDK 50연결, 최대 5동시; 새 참여 0개 | `PASS` |
| 첫 호출·동시 호출 fixture | backend 이전 참여 확보, 동시 첫 호출 1개, 후속 호출 재사용 | `PASS` |
| 거부·종료 fixture | 127/128 경합·freeze·부분 등록 실패·실제 EOF drain, 기록 보존 | `PASS` |
| 권한·불확실 결과 회귀 | exact action·producer pin·COMMIT_UNKNOWN·재실행 금지 유지 | `PASS` |
| D2 회귀 | 기존 읽기·감사·등록/전달 범위와 revoke·drift 검사 | 15개 `PASS` |
| D6 hook·gateway 보안 회귀 | hook 15개, 인증·권한·감사·HTTP guard 16개 | 31개 `PASS` |
| D6 HTTP delegate lifespan | 시작 시 delegate 참여의 기존 코드 유지; app lifespan 직접 통합 실행 | 정적 대조, 직접 실행 `NOT_RUN` |
| 정적 연결 원장 | 실제 변경 경로와 지문 대조, 누락·불일치 0, 효과·권한 분류 변경 0 | `PASS` |
| 수정본 설치 adapter의 로컬 stdio | client별 3동시·1재연결, 정확한 도구 집합, EOF 정상 종료, 참여 증가 0 | 양쪽 `PASS` |
| 새 Desktop 모델 대화·catalog | 실제 앱의 새 대화에서 수정 runtime 채택과 도구 전달 확인 | 양쪽 `PASS`, metadata 참여 증가 0 |
| 기존 권한 읽기 | 각 client의 projects_list·work_inspect(status/record) 각 1회 | 양쪽 `PASS`, 연결별 참여 1개·변경 실행 0 |
| 실제 Work 실행·QA·완료 | 별도 승인된 범위에서만 검증 | `NOT_RUN / HOLD` |

격리 native component 바이너리와 Tk 표시 환경을 명시하지 않은 선택적 검사는
skip으로 구분한다. 수정 경로의 실제 SDK stdio·Unix socket·Owner inspect/export
fixture와 정적 guard 우회 방지 검사를 실행한다. 공개 main에서 다시 수행한 결과는
해당 커밋의 CI로 확인한다. 기존 전체 개발 snapshot의 회귀 숫자를 그대로 이식하지 않는다.
D6 HTTP guard fixture 통과는 HTTP app lifespan이나 실제 원격 서비스 검증을 뜻하지 않는다.

### 설치 후 확인한 범위

공개 Styxis wrapper 0.2.8을 재설치하지 않고, 검토한 별도 runtime과 새 D2/D4·launcher
pin 및 adapter state를 선택했다. 기존 D1 등록·native pin·대상·도구 범위는 유지했고,
D4 실행 action은 양쪽 모두 0개다. 기존 정책·승인·Work·증거는 새 후보와 별도로 보존했다.

| 항목 | Codex | Claude |
| --- | --- | --- |
| 설치 adapter 로컬 stdio 프로세스 | 동시 3개 + 재연결 1개 | 동시 3개 + 재연결 1개 |
| 연결별 허용 메시지 | initialize·initialized 알림·tools/list 각 1회 | 동일 |
| 예상 도구 집합 | 28개와 정확히 일치 | 2개와 정확히 일치 |
| registry 참여 기록 | 22→22, 추가 0개 | 6→6, 추가 0개 |
| 기존 registry 파일 | 178개 bytes·mode·존재 보존 | 146개 bytes·mode·존재 보존 |
| 정상 EOF 종료 | 4개 모두 exit 0, stderr 0 bytes | 4개 모두 exit 0, stderr 0 bytes |
| tools/call·native·Work·모델 호출 | 모두 0회 | 모두 0회 |

양쪽 Work 전체 파일 inventory와 기존 정책·native·adapter pin도 전후에 일치했다.
결과는 private `metadata-probe/codex/result.json` 및
`metadata-probe/claude/result.json`에 보존했다. 하네스는 실패 재시도와 강제 종료를
제공하지 않으며, 승인 시간창을 늘리거나 기존 참여 기록을 삭제하지 않았다.

이 검증은 설치된 adapter를 별도 로컬 프로세스로 실행한 결과다. 설정에서 새 state를
선택한 사실과 이미 실행 중인 Desktop 프로세스의 runtime 교체는 별개다. 별도 프로세스
경로·부모 프로세스 관측에서는 Codex·Claude 실제 앱의 새 runtime 채택도 확인했다.
다만 구 Codex live 프로세스도 보존돼 있으며 기존 대화 전부가 전환됐다는 뜻은 아니다.
이후 아래 별도 새 Desktop 대화에서 도구 전달과 기존 권한 읽기를 확인했다.
하네스의 metadata 결과는 Owner 창 표시 여부를 직접 관찰하는 UI 검사를 대신하지 않는다.
이 metadata 단계에서 실제 Work 조회·QA·완료·후보 저장·원격 서비스 호출은 하지 않았다. metadata-only 성공을
실제 작업 성공이나 모든 Core 기능 검증으로 승격하지 않는다.

후속 설치나 권한 변경도 변경 파일·producer/launcher pin·대상·검증 호출을 묶어
별도 검토한다. 문서나 소스 변경만으로 기존 정책·승인·Work·증거·COMMIT_UNKNOWN을
갱신하지 않는다. 실제 제품 실행·QA·완료의 HOLD는 계속 유지한다. 소스 커밋·push는 별도로 요청받아 진행하며 설치 설정을 자동 변경하지 않는다.

### 새 Desktop 대화의 읽기 검증 (2026-11-10)

| 관측 | Codex Desktop | Claude Desktop |
| --- | --- | --- |
| 새 대화의 정의 탐색 | 노출 확인, 참여 22→22 | 노출 확인, 참여 6→6 |
| 실제 Golem 조회 | projects_list 1회, work_inspect status 1회·record 1회 | 동일 |
| 최초 조회 이후 참여 | 22→23, 같은 연결에서 한 개 재사용 | 6→7, 같은 연결에서 한 개 재사용 |
| native 읽기 감사 디렉터리 | 2개 추가 | 2개 추가 |
| mutation·제품 실행·QA·완료 | 모두 0회 | 모두 0회 |

Codex의 실제 tool-call 응답과 Claude의 실제 tool 카드 응답을 각 native 읽기 감사의
정확한 인자·결과 hash와 대조했다. 결과는 `AVAILABLE`, `native_state_changed=false`,
`execution_authorized=false`였다. 조회 응답에 대상 ID가 직접 포함되지 않는 경우에도
실제 요청과 현재 승인 binding·native argv로 귀속을 확인했으며 실패 호출을 반복하지 않았다.
검사 대상 inventory의 정책·설정·원본 승인·D1·Work·증거는 전후 bytes/mode가 동일했고, 기존 registry
기록의 변경·삭제는 없었다. 새 참여와 읽기 감사만 추가됐다.

이 결과는 모든 Core 기능, 기존 대화 전체의 전환, 새로운 Intent 계약·QA 수락·완료를
검증했다는 뜻이 아니다. 과거 live 프로세스와 불확실 결과는 보존한다.
private 감사에는 응답 원본과 파일 inventory를 보존하고 공개 문서에는 개인 경로·
프로젝트 이름·대화 ID·정책 bytes를 싣지 않는다.

관련 계약: [D5 업데이트·정지 확인](integration-d5.md),
[D2 전달 범위](integration-d2.md), [M6 배포와 Owner 앱](mcp-m6-distribution.ko.md).
