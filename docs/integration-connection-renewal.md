# Golem 연결 확인과 갱신

Owner 앱을 직접 열고 **Codex 연결·갱신 → 연결 상태 확인**을 선택한다.
Codex adapter에는 Python 3.11 이상이 필요하다. 기존 설정의 interpreter가 더 오래됐으면
검토한 Python의 절대 경로를 명시적으로 선택하며 자동 검색·대체하지 않는다.
설치 버전, 설정에서 선택한 launcher·정책·runtime, 실제 Desktop 하위 프로세스의
지문과 도구 목록을 따로 보여 준다. 이 조회는 Work 도구를 호출하지 않는다.
연결 전환은 아래 네 단계의 근거를 모두 구분한다. **설정 저장과 초기화만으로
개발 대화의 연결 검증을 완료 처리하지 않는다.**

```text
검토한 설치·state 선택
        ↓
같은 개발 대화의 실제 도구 정의에서 marker·도구 이름 관측
        ↓
Owner 앱에서 대화·turn 관측과 정확한 relay·선택 설정 대조
        ↓
지원되는 대상 연결 갱신 → 새 child 초기화·목록 변경 알림
        ↓
호스트의 현재 세대 tools/list 요청·응답 → 실제 연결 재확인
        ↓
같은 대화의 다음 turn에서 새 marker·필요 도구 정의 대조
        ↓
연결 준비 확인 → 새 단기 action 준비 → 별도 기존 승인·native 검사
```

| 단계 | 확인 근거 | 이 단계만으로 알 수 없는 것 |
|---|---|---|
| 디스크 선택 | 지원되는 설정 조회와 adapter 승인 파일의 정확한 지문 | 실행 중인 Desktop의 반영 여부 |
| 의도한 연결 | 실제 대화에 전달된 marker와 현재 relay의 세대·지문 대조 | 사람이 누구인지, 실행 권한이 있는지 |
| 호스트 목록 | 해당 연결의 현재 세대에 완성된 `tools/list` 전달 관측 | 그 목록을 모델이 받았는지 |
| 같은 대화의 도구 | 대화·turn·marker·실제 도구 이름의 외부 관측 대조 | Work admission·QA PASS·완료 |

이 확인 뒤에만 새 단기 실행 준비를 시작한다. 설치·재연결을 기다리는 동안 기존
준비안의 30분 수명을 연장하거나 새 서비스로 옮기지 않는다. 연결이 바뀌어 낡은
준비안은 역사 기록으로 보존하고, 새 준비 자체도 기존 정책과 사용자 지시에 따라
별도로 판단한다. 연결 준비 확인은 실행 권한을 추가하지 않는다.

## 버튼이 하는 일

| 표시 | 동작과 한도 |
|---|---|
| 대화 관측 대조 | 현재 대화·turn·정의의 marker·실제 도구 이름을 한 live relay와 대조한다. 모호하거나 오래된 관측은 연결 선택 근거가 되지 않는다. |
| Golem 연결 갱신 | 정확히 대조한 Codex relay가 이미 승인·설정된 state로 해당 연결 하나만 전환한다. 같은 설정의 무의미한 재실행은 거부한다. |
| 호스트 MCP 갱신 요청 | 사용자가 명시한 공식 Desktop control socket이 검증된 경우에만 지원한다. Codex API는 Golem 선택자가 없는 **전체 호스트** 갱신이므로 별도 확인이 필요하다. |
| 지원되는 live 전환 경로 미확인 | 제어 경로가 없거나 확인되지 않은 상태다. 갱신 버튼을 차단하고 기존 연결과 실행 HOLD를 유지한다. 제어 소켓 부재·같은 호스트 PID·다른 대화의 구버전 연결을 앱 재시작 필요성으로 해석하지 않는다. |
| 갱신 후 상태 확인 | 지원되는 갱신 요청 뒤 설정과 실제 연결을 다시 읽는다. 프로세스를 종료하거나 앱을 실행하지 않는다. |

역사 연결 기록은 삭제하지 않는다. 검증된 기록의 소켓 경로가 없는 경우에만
`CLOSED_ENDPOINT_ABSENT`로 구분하며, 이는 프로세스 종료·작업 완료 인증이 아니다.
남아 있는 소켓·불확실 후보는 기록 수정 시각의 최신순으로 최대 16개를 관찰한다
(같은 시각은 연결 ID 순서). 이 시각은 관찰 순서에만 사용하고 신원·현재성의 근거로
쓰지 않는다. Owner 기록 128개·relay 디렉터리 1024개 탐색 한도는 그대로다.
연결 거부·시간초과·잘못된 소유자·변경된 기록과 상한 밖 후보는 **미관찰**로 남기므로
관찰한 연결 하나가 정상이더라도 전체 정상으로 판정하지 않는다. 이 경우에는
**일부 연결 미관찰**과 사유를 표시하고, 근거 없이 앱 재시작을 반복 안내하지 않는다.
별도 페이지 조회는 제공하지 않으며 명시적인 상태 확인으로 같은 제한 안에서 다시 관찰한다.

같은 Desktop 호스트 안에 구버전·신버전 MCP 연결이 공존할 수 있다. 디스크에 새
adapter가 설치됐거나 신버전 연결 하나가 관찰돼도 현재 개발 대화가 그 연결을 사용한다는
뜻은 아니다. 반대로 구버전 연결이 남아 있거나 호스트 PID가 같다는 이유로 전체 앱을
재시작해야 한다고 판단하지 않는다. 대상 대화의 정의 관측과 연결 대조를 따로 유지한다.
같은 adapter 안의 검토한 state 전환과 새 plugin 실행 코드 교체는 서로 다른 경계다.
현재 구현은 모든 설치·catalog 변경을 무중단 반영한다고 보장하지 않는다.

## 보존과 성공 판정

- 새 권한을 만들지 않는다. 기존 adapter 승인, 정확한 launcher bytes, 설정 지문을
  다시 대조하고 새 서비스가 기존 D1/D2/D4 검사를 수행한다. 다른 client는 변경하지 않는다.
- 응답 대기 중인 양방향 MCP 요청이 있거나 일부 프레임이 남으면 갱신하지 않는다.
  **통신 요청이 없다는 것은 제품 작업·native lease가 끝났다는 뜻이 아니다.**
  Owner는 진행 중인 별도 작업을 확인해야 한다.
- 기존 child에는 stdin EOF만 전달한다. 강제 종료하지 않고 정상 종료와 출력 소진을
  기다린다. 최대 30초 안에 확인하지 못하면 `UNKNOWN`으로 남기고 새 child를 시작하지 않는다.
- 새 child의 초기화는 한 번, 최대 60초다. 갱신 도중 들어온 요청은 새 child에 넘기지
  않으며 자동 재시도하지 않는다. 기존 준비안·응답·불확실 결과는 되살리거나 삭제하지 않는다.
- 초기화 성공 뒤 `notifications/tools/list_changed`를 보낸다. 이 알림이나 공식 API의
  접수 응답은 **현재 모델에 도구가 전달됐다는 증거가 아니다.** 현재 대화의 실제 목록을
  별도로 확인한다. 독립 stdio 검사 결과를 Desktop 성공으로 대신하지 않는다.
- 목록 확인과 일반 MCP 연결은 Owner 창을 자동으로 열지 않는다. Owner 창을 닫아도
  MCP 서비스는 유지된다. 기존 Work·승인·증거·COMMIT_UNKNOWN을 재실행하지 않는다.

공식 호스트 경로는 [Codex app-server 문서](https://learn.chatgpt.com/docs/app-server#api-overview)의
`config/mcpServer/reload`, `mcpServerStatus/list`를 사용한다. 구현은 명시적으로 선택하고
신원을 확인한 Desktop socket에 지원되는 `app-server proxy --sock`으로 연결한다.
현재 host의 공식 socket을 선택·검증하지 못하면 그 경로는 미지원으로 표시한다.
사설 DB·IPC 조작이나 새 app-server helper로 기존 Desktop을 대신 갱신하지 않는다.
`config/batchWrite`의 디스크 변경 응답과 live host reload 접수는 별개다.

## 승인 state 위치 확인

유지보수 controller는 adapter의 저장 구조를 추측하지 않고 설치본의 읽기 명령을 사용한다.

```sh
python3 -I -B /absolute/installed/scripts/launcher.py inspect-state \
  --client codex --state /absolute/reviewed-state
```

`golem.launcher-inspection.v1` 결과는 실제 `approval_path`, 승인 bytes의
`approval_sha256`, `launcher_sha256`, client·adapter 버전을 제공한다. command/args는
노출하지 않는다. 선택한 지문을 다시 검사할 때는 `--expected-approval-sha256`와
`--expected-launcher-sha256`을 지정한다. 기존 shared lock·승인 parser를 사용하며,
없는 state를 만들거나 서버를 초기화하지 않는다. 다른 client 승인·부분 기록·symlink·
지문 변경은 기존 계약대로 차단한다. 결과의 `execution_authorized`는 항상 false다.

## 서버에는 있지만 대화에 없는 도구

`READY`는 child 초기화 상태다. relay는 갱신 세대별로 **호스트가 실제 보낸**
`tools/list` 요청과 호스트로 전달한 응답만 관찰한다. 새 세대에 목록 재조회가
없으면 `HOST_CATALOG_NOT_RELISTED`, 응답을 전달하면
`HOST_CATALOG_RESPONSE_SENT`로 표시한다. 마지막 완성 목록의 지문은 현재 세대의
관측과 구분한다. 페이지 연결·응답 ID·세대·오류를 대조하며 진단을 위해 새 목록
요청을 만들어 보내지 않는다. 응답 전달도 호스트 캐시 반영이나 모델 노출 인증이 아니다.
구버전 relay에 이 정보가 없으면 `NOT_OBSERVED`다.

새 relay는 유효한 목록 응답의 첫 도구 설명에 다음 불투명 marker를 추가한다.

```text
golem-connection-v1:<연결 ID 32hex>:<child 세대>:<catalog 세대>:<nonce 32hex>
```

도구 이름·입력 schema·권한은 추가하거나 바꾸지 않는다. marker는 같은 대화의 실제
도구 정의에서 확인해야 한다. 로컬 `connection-status`에서 읽은 값을 모델이 받았다고
대신 기록하면 안 된다. Owner 앱의 **현재 대화에서 확인한 도구 정의**에 대화 ID,
관측 turn ID, marker, 실제 도구 이름과 이번 준비에 필요한 도구 이름을 구분해 입력한 뒤
**대화 관측 대조**를 선택한다. 필요 도구를 비워 두면 준비는 보류하며, 입력을 바꾸면
기존 대조 결과를 현재 준비 상태로 사용하지 않는다.
앱은 현재 연결·세대·선택 pin·완성된 호스트 목록을 다시 대조하며, 다른 연결·
오래된 목록·누락된 필요 도구·불확실 갱신이면 새 실행 준비를 보류한다.

이 입력은 `EXTERNAL_MODEL_DEFINITION_OBSERVATION`이다. marker가 맞아도 대화의
공식 신원 인증, 사람의 승인 또는 Work 실행 가능성을 증명하지 않는다. 최근 관측과
현재 live 상태의 순서·현재성을 검사하며 5분을 넘긴 관측은 새 대조가 필요하다.
이 5분은 연결 진단 자료의 수명일 뿐 native·준비안의 TTL을 변경하지 않는다.
정확한 대조의 `PREPARATION_READY_NOT_AUTHORIZED`도 새 미승인 준비를 시작할 수
있는 연결 상태만 뜻한다. 기존 실행 HOLD는 그대로 유지된다.

알고 있는 연결 하나는 설치 adapter에서 읽기 전용으로 확인할 수 있다.

```sh
python3 -I -B /absolute/installed/scripts/launcher.py connection-status \
  --client codex --state /absolute/reviewed-state \
  --connection-instance EXACT_32_HEX_RELAY_ID
```

한 서비스가 준비안을 보유하거나 Desktop PID가 같다는 사실만으로 그 서비스가
현재 대화의 transport라고 판단하지 않는다. marker가 없거나 대조할 수 없다면
행을 임의로 골라 갱신하지 않고 미관찰·미지원 사유를 남긴다. 같은 대화의 호스트
상태와 다음 turn의 실제 도구 정의를 함께 대조한다. 목록 알림 후 재조회가 없다면 같은 relay 갱신이나
설치를 반복하지 않는다. 지원되는 호스트 갱신은 현재 로드된 대화의 갱신을 **예약**하므로
접수 응답 뒤 다음 turn에서 확인해야 한다. 지원되는 경로가 없으면
`LIVE_TRANSITION_UNAVAILABLE`, 대상 연결을 식별하지 못하면 `TARGET_NOT_IDENTIFIED`로
보존하며 갱신·재설치·앱 재시작을 반복하는 절차로 바꾸지 않는다. 과거
`MANUAL_RESTART_REQUIRED` 보고서를 열어도 재시작 안내나 동작을 활성화하지 않는다.
사설 IPC·다른 app-server로 기존 Desktop
성공을 대신하지 않는다. 같은 실패 경로를 반복하거나 대화만 새로 만들어 성공으로
간주하지 않는다.

격리된 Codex Desktop 바이너리 `0.167.0-alpha.3.2`의 mock MCP 검사에서는
목록 변경 알림 뒤 기존 대화의 목록이 유지됐고 호스트의 재조회도 없었다. 공식 reload는
접수됐지만 기존 대화의 즉시 조회에는 이전 목록이 남았다. 이는 해당 바이너리의
관측이며 모든 버전의 동작으로 일반화하지 않는다. 실제 제품 Work 호출은 포함하지 않았다.
같은 바이너리·같은 격리 대화에서 로컬 가짜 모델로 추가 대조했을 때, MCP 설정이
같은 reload 뒤에는 다음 turn도 이전 도구를 받았다. 검토한 **새 패키지 실행 경로로
MCP args를 변경한 뒤 공식 reload**한 경우에는 같은 대화의 호스트 목록과 다음 turn에
새 도구가 전달됐다. 따라서 설정을 무의미하게 변조하거나 권한을 늘리지 않고 실제 새
설치 경로를 선택한 뒤 지원되는 호스트 갱신을 확인한다. 이 검사는 외부 모델 호출·
Work 도구 실행 없이 수행한 호스트 fixture이며 실제 사용 중인 Desktop 인수와는 별개다.

## 검증 범위

회귀 fixture는 여러 연결의 격리, 사용 중 갱신 거부, 설정·승인 지문 변경,
정상 EOF, 초기화 실패·응답 유실·중복 요청, 갱신 중 요청의 미전달,
UI 행 선택·동의·관측 token 경합, 목록 재조회 부재, 목록 응답의 세대·페이지 연결을 검사한다.
marker의 정확한 대조·현재성·오래된/다른 대화 입력·필요 도구 누락·불확실 갱신과
adapter의 실제 승인 경로 조회도 별도로 검사한다.
실제 Desktop에 대한 도구 전달과
사용자 프로젝트 실행은 해당 설치 원장의 별도 관측이 필요하다.

선택적으로 고정된 도구 정의와 backend 권한 세대를 분리하는 경로는 [stable 연결 계약](integration-stable-connection-design.md)에 구현 범위와 한도를 정리했습니다. 기본 설치·정책에는 적용되지 않았으며, 현재 Desktop 연결의 이행·수락 검증은 별도로 필요합니다.
