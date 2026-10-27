# Codex MCP 설치·사용 안내

최신 검증본은 [README](../README.ko.md)에서 확인한다. **Golem Setup**은 연결 관리, **Golem Work**는 작업 진행에 사용한다. 이미 검증본이 연결돼 있으면 재설치하지 않는다.

## 1. 설치·연결 확인

대상 Codex Desktop에 속한 CLI로 설치 목록과 실제 MCP command/args를 확인한다. 아래 `codex`는 그 CLI를 가리킨다.

```sh
codex plugin list --json
codex mcp list --json
```

- 검토한 package·파일 SHA·launcher와 기존 [프로젝트 등록](integration-d1.md)·[전달 범위](integration-d2.md)·[action 승인](integration-d4.md)을 대조한다. 설치는 권한을 생성하지 않는다.
- **Launcher 직접 실행 패키지**는 기존 command/args와 runtime·정책 pin을 유지한다. adapter가 없는 설치본에서 `scripts/launcher.py`나 기본 adapter 상태를 찾지 않는다.
- **Repository adapter 패키지**는 실제 MCP 선언이 설치된 `scripts/launcher.py`를 실행할 때만 `status` → 필요한 `configure` → `status`를 사용한다. `configure`에는 검토한 launcher 파일·정확한 SHA와 명시적 승인이 필요하다. [Adapter 명령](../plugins/golem/scripts/launcher.py)을 참고한다.

Golem Setup으로 해당 연결만 reload하거나 새 대화에서 도구를 확인한다. **의도한 서버의 `golem_projects_list`와 허용 Work 조회**로 연결을 확인한다. 설치 등록·연결 표시만으로 실제 호출 성공을 대신하지 않는다. `EXISTING_APPROVAL_DIFFERS`·`PARTIAL_PUBLICATION`이면 기록을 보존하고 중단한다.

<details>
<summary>신규 설치가 필요한 경우</summary>

검토한 marketplace를 사용한다. 기존 launcher에서 private package를 만드는 예시는 다음과 같으며, 경로·이름은 owner가 검토한 값으로 대체한다. 새 출력 경로만 사용하고 GitHub 소스가 검증된 로컬 수정본과 같다고 가정하지 않는다.

```sh
python3 tools/integration_codex_plugin.py --launcher /absolute/private/reviewed-launcher.json --output /absolute/private/new-marketplace --marketplace golem-reviewed --server golem-reviewed
codex plugin marketplace add /absolute/private/new-marketplace --json
codex plugin add golem@golem-reviewed --json
```

생성기는 client 설정이나 승인을 적용하지 않는다. 설치 뒤 위 연결 확인을 수행한다. CLI가 명령을 지원하지 않으면 Plugins UI를 사용한다. launcher는 절대 command·문자열 args만 담아 owner-private 파일(0600)로 관리하며 cache를 직접 편집하지 않는다.

</details>

## Work Flow

두 client에 공통인 흐름이다. **현재 연결에 노출된 도구와 기존 승인 범위** 안에서만 진행한다.

1. `golem_projects_list` → 선택한 Work의 `golem_work_inspect`로 status/next를 읽고, 필요한 context·evidence를 조회한다.
2. 입력·초안을 준비한다. 검토된 action은 노출된 경우 `golem_approved_action_prepare` → `golem_plan_read` → `golem_action_confirm`으로 현재 basis를 대조한다. 준비·확인은 승인 발급이나 실행이 아니다. plan은 같은 연결에서 확인한다.
3. 현재 사용자 지시와 기존 owner 정책이 허용하는 **정확한 action**만 호출한다. 요청 ID·native key·승인 pin을 임의 변경하지 않는다.
4. 저장된 실행 응답은 `golem_execution_read`의 `operation="stored_result"`로 읽는다. 원래 project·Work·action·request ID와 현재 D2/D4 권한이 필요하며, 조회를 위해 `golem_execution_request`를 다시 보내지 않는다.
5. 요구되는 QA 결과·완료 문서를 제출하고, 승인된 `golem_completion_finalize`·`golem_completion_report`를 각각 처리한다. 마지막에 `golem_completion_check`로 **현재 DONE**을 확인한다. QA PASS나 finalize의 RECORDED만으로 완료 처리하지 않는다.

승인 대기·권한 부족·stale·quota·결과 유실·COMMIT_UNKNOWN이면 원 ID와 증거를 보존하고 허용된 읽기로 상태를 확인한다. 자동 재실행·repair·rollback은 하지 않는다. 없는 도구는 재설치나 권한 확대 대신 필요한 계약을 확인한다. [완료 계약](completion.md)

## 업데이트·정리

- 새 artifact·설치 bytes와 검증 범위를 확인하고 기존 identity의 지원되는 update 절차를 사용한다. runtime·정책 변경은 [D5](integration-d5.md)를 따르며 기존 승인 bytes/key/pin을 자동 이전하지 않는다.
- 복구 자료를 owner-private 위치에 보존한 뒤 **검증된 Golem 한 개와 의도한 연결 한 개만** 유지한다. 확인한 구버전 plugin·marketplace·중복 direct MCP만 지원되는 remove 명령/UI로 정리하고 재확인한다.
- 기존 Work·승인·registry·evidence·CAS·journal와 다른 플러그인·진행 중 대화를 보존한다. 설치 과정에서 앱 전체를 임의 재시작하지 않는다. local process는 사용자 OS 권한으로 실행된다.
