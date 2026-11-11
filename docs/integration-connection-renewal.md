# Golem 연결 확인과 갱신

Owner 앱을 직접 열고 **Codex 연결·갱신 → 연결 상태 확인**을 선택한다.
Codex adapter에는 Python 3.11 이상이 필요하다. 기존 설정의 interpreter가 더 오래됐으면
검토한 Python의 절대 경로를 명시적으로 선택하며 자동 검색·대체하지 않는다.
설치 버전, 설정에서 선택한 launcher·정책·runtime, 실제 Desktop 하위 프로세스의
지문과 도구 목록을 따로 보여 준다. 이 조회는 Work 도구를 호출하지 않는다.

```text
검토한 설치·state 선택
        ↓
Owner 앱에서 설정과 실제 연결 대조
        ↓
갱신 가능한 Golem 연결 한 행 선택 → 확인 → 연결 갱신
        ↓
새 child 초기화·목록 변경 알림 → 실제 연결 재확인
        ↓
개발 대화의 도구 노출 확인 → 기존 승인 범위의 작업
```

## 버튼이 하는 일

| 표시 | 동작과 한도 |
|---|---|
| Golem 연결 갱신 | 새 Codex adapter의 relay가 이미 승인·설정된 state로 해당 연결 하나만 전환한다. 같은 설정의 무의미한 재실행은 거부한다. |
| 호스트 MCP 갱신 요청 | 사용자가 명시한 공식 Desktop control socket이 검증된 경우에만 지원한다. Codex API는 Golem 선택자가 없는 **전체 호스트** 갱신이므로 별도 확인이 필요하다. |
| 정상 재시작 안내 | 이전 adapter처럼 Golem relay가 없거나 공식 control 경로가 없을 때 표시한다. 진행 중인 작업을 저장한 후 실제 사용하는 앱의 메뉴에서 정상 종료·재실행한다. 창 닫기와 플러그인 재설치는 대체 수단이 아니다. |
| 재시작 후 상태 확인 | 설정과 실제 프로세스를 다시 읽는다. 프로세스를 종료하거나 앱을 실행하지 않는다. |

처음 relay가 포함된 adapter로 바꿀 때는 기존 Desktop 프로세스가 이전 코드를
계속 사용할 수 있다. 이 경우 최초 정상 재연결이 필요하다. 이후 같은 adapter 안에서
검토한 state를 선택하면 Golem 연결 갱신을 사용할 수 있다. 새 plugin 실행 코드 자체를
교체하는 것은 relay가 수행하는 state 갱신과 다르다.

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
`config/mcpServer/reload`, `mcpServerStatus/list`, `app-server proxy --sock`을 따른다.
공개 control socket이 없는 stdio Desktop을 사설 DB·IPC 조작으로 우회하지 않는다.

## 검증 범위

회귀 fixture는 여러 연결의 격리, 사용 중 갱신 거부, 설정·승인 지문 변경,
정상 EOF, 초기화 실패·응답 유실·중복 요청, 갱신 중 요청의 미전달,
UI 행 선택·동의·관측 token 경합을 검사한다. 실제 Desktop에 대한 도구 전달과
사용자 프로젝트 실행은 해당 설치 원장의 별도 관측이 필요하다.
