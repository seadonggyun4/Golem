# Owner 앱에서 고정 연결 전환

선택적 stable 연결을 검토·설치한 경우에만 사용하는 절차다. 기본 Styxis 설치는 자동 전환되지 않는다. **고정 도구 정의의 노출과 실제 호출 권한은 별개**이며, 기존 D1/D2/D4·native 검사는 그대로 적용된다. 실제 Work 실행 HOLD도 유지된다.

```text
같은 Codex·Claude 대화에서 실제 도구 정의 확인
             ↓ marker · 전체 이름 · 대화 · turn · 원래 시각
Owner 앱 → 고정 연결·실행부 전환
             ↓ 정확한 새 selection 검토·선택 저장
             ↓ 같은 대화의 연결 확인 · idle 대조
             ↓ 해당 연결의 실행부만 1회 전환
같은 대화의 정의 + 새 backend epoch 다시 확인
```

## 준비

owner가 검토한 broker bundle, client별 store, adapter state와 정확한 pin이 필요하다. 기존 정책을 자동 복사하거나 만료 action을 갱신하지 않는다. `golem.stable-owner-ui.v1` 설정은 client별 bundle 경로·SHA, store, 확인할 도구 목록과 private 검토 기록 디렉터리를 고정한다. Codex와 Claude의 store는 분리한다.

Owner 앱은 아래 옵션으로 선택한 설정만 연다. 경로·SHA는 실제 검토한 값으로 대체하며 명령 예제 자체는 설치·선택 승인이 아니다.

```sh
python3 tools/integration_owner_desktop.py owner-app \
  --review-directory /absolute/private/existing-owner-connections \
  --stable-config /absolute/private/owner-ui.json \
  --stable-config-sha256 REVIEWED_CONFIG_SHA256
```

기존 후보 검토와 연결 진단 탭은 유지된다. 이미 열린 Owner 앱의 설정 identity가 다르거나 미확인이라면 새 설정 적용으로 표시하지 않는다. 필요하면 **Owner 창만 정상적으로 닫고** 검토한 앱을 연다. Codex·Claude를 종료하는 절차가 아니다. MCP 시작이나 탭 선택은 창·전환·상태 조회를 자동 실행하지 않는다.

## 같은 대화의 연결 확인

1. client를 고르고 명시적으로 선택 상태와 연결 목록을 읽는다. 종료·다른 client·확인되지 않은 행에서는 전환할 수 없다.
2. 실제 대화의 도구 정의에서 얻은 `golem-catalog-v2:…` marker, 전체 도구 이름, 대화·turn·server, 원래 관측 시각을 담은 외부 관측 JSON과 SHA를 선택한다. PID나 연결 목록을 보고 이 자료를 만들어 내지 않는다.
3. 관측 버튼으로 정확한 instance와 현재 선택을 대조한다. 파일 SHA 일치는 관측 내용의 진실성이나 사람의 신원을 인증하지 않는다. 자료가 5분보다 오래됐으면 현재 대화에서 새로 확인해야 한다.

호스트의 tools/list·ready와 모델이 받은 정의를 구분한다. 새 app-server나 다른 대화에서 성공한 결과는 원래 Desktop 대화의 성공이 아니다.

## 선택 저장과 실행부 전환

1. **선택 검토**에서 새 selection 파일·SHA와 이전 head CAS를 확인한다. 정확한 검토 확인 후 **선택 저장**을 1회 수행한다. 결과는 `SELECTED_NOT_LIVE_APPLIED`다.
2. 같은 대화의 외부 관측을 이용해 **전환 검토**한다. 현재 연결·old/target selection·marker·epoch와 idle 상태를 대조한다. 다른 행을 선택하면 확인란을 해제하고 그 행의 전환을 차단한다. 관측·selection 입력을 바꾸면 이전 검토를 해제한다. 원래 대상을 다시 선택해도 확인과 현재성 검사를 다시 거친다.
3. 정확한 검토 확인 후 **실행부 전환**을 1회 수행한다. 기존 child의 EOF와 정상 종료를 확인한 뒤 새 child를 한 번 초기화한다. frontend·고정 정의는 유지한다.
4. ACK만으로 완료 처리하지 않는다. 같은 대화의 도구 정의와 새 backend epoch를 다시 관측한다. 성공은 `PREPARATION_READY_NOT_AUTHORIZED`이며 Work 실행·승인·QA·완료 권한이 아니다.

busy·pending·stale·ABI 불일치·결과 유실이면 중단한다. 시도와 결과는 private 불변 기록으로 남기며 자동 재전송·복구·rollback하지 않는다. 저장 뒤 응답만 유실될 수 있으므로 창을 다시 열어도 같은 효과를 반복하지 않는다. 창 닫기는 MCP 연결을 종료하지 않으며 진행 중 제어 작업을 취소하거나 재실행하지 않는다.

Owner 앱을 완전히 닫았다가 다시 열면 디스크의 과거 ACK만으로 현재 준비 완료를 복구하지 않는다. 기록 정리의 마지막 저장까지 성공했는지 새 앱이 인증할 수 없기 때문이다. 해당 기록은 과거 결과로 보존하고 관측을 차단하며, 같은 전환을 재실행하지 않는다. 정상 전환 후 현재 대화 대조는 **동일 Owner 앱 인스턴스에서** 마친다.

## 최초 전환과 지원 한계

구형 relay에서 stable frontend로 처음 바꾸는 작업은 client가 지원하는 **해당 Golem 연결 교체**가 필요하다. 구형 relay의 backend refresh로 frontend ABI까지 바꾸지 않는다. 이후 같은 catalog 안의 실행부 전환은 앱 전체 재시작이나 host의 목록 재조회에 의존하지 않는다. catalog 자체가 바뀌면 별도 노출 선택과 지원되는 연결 갱신이 필요하다.

지원되는 연결 제어 경로가 없으면 그 단계는 미검증으로 남기고, 앱 재시작·재설치 반복으로 대신하지 않는다. 구현·fixture 통과와 실제 설치·Desktop 같은 대화 검증은 따로 기록한다. 자세한 계약은 [고정 연결 설계](integration-stable-connection-design.md)를 따른다.
