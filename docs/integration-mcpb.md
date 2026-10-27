# Claude Desktop MCPB 설치·사용 안내

최신 검증본은 [README](../README.ko.md)에서 확인한다. 검토한 기능별 MCPB를 사용하며, 이미 같은 검증본이 연결돼 있으면 재설치하지 않는다. profile은 기존 권한의 상한이다.

## Install and Configure

1. **Settings → Extensions → Advanced settings → Install Extension**에서 검토한 MCPB를 선택한다. 기존 동일 identity에는 지원되는 **Update**를 사용한다. archive SHA·manifest·설치 파일을 대조하고 local-process 설치 확인을 마친다.
2. **Configure**에서 기존 정책·정확한 SHA와 전달 동의를 지정한다. task 패키지의 필수 입력은 **Existing reviewed D4 policy**, **Exact owner-reviewed policy digest**, **Explicit consent to this existing owner policy**다. 설치나 동의 체크만으로 새 action 승인이 생기지 않는다.
3. task의 optional **resource**는 별도 검토한 계약·SHA·동의가 있을 때만 선택한다. helper는 quality, host는 parallel 패키지의 별도 계약이며 task 설정에 추가하지 않는다. read/prepare는 해당 D2 정책을 사용한다.
4. 저장·활성화 후 해당 연결만 reload하고 새 대화에서 **의도한 확장**의 실제 도구를 확인한다. `golem_projects_list`와 허용 Work 조회로 연결을 확인한다. `golem_setup_status`만 보이면 설정 진단 단계이므로 정책·producer pin을 임의 변경해 통과시키지 않는다.

기존 [프로젝트 등록](integration-d1.md)·[전달 범위](integration-d2.md)·[D4 action](integration-d4.md)을 보존한다. Codex의 전달 동의를 Claude에 재사용하지 않는다. 패키지는 owner가 고정한 외부 Python/SDK/native runtime이 필요하며, uv가 의존성을 다운로드할 수 있다. local process는 사용자 OS 권한으로 실행된다.

## Work Flow

연결 후 [공통 Work 사용 흐름](integration-codex-plugin.md#work-flow)을 따른다. Claude에서도 실제 MCP 도구명은 `golem_…`이며, 노출된 도구와 현재 정책의 교집합만 사용할 수 있다.

저장 결과는 원 ID의 `golem_execution_read(operation="stored_result")`로 조회하고 실행 요청을 재전송하지 않는다. 필요한 QA·완료 문서·finalize·보고서를 처리한 뒤 `golem_completion_check`로 현재 DONE을 확인한다. pending·stale·결과 유실·COMMIT_UNKNOWN은 보존하며 자동 재실행·repair·rollback하지 않는다. `AGENTS.md`/`CLAUDE.md`가 Desktop의 권한으로 자동 적용된다고 가정하지 않는다.

<details>
<summary>패키지 생성이 필요한 경우</summary>

검토한 checkout에서 필요한 profile을 선택하고 새 출력 경로를 사용한다. 경로와 digest는 owner가 검토한 값으로 대체한다.

```sh
python3 tools/integration_distribution.py catalog
python3 tools/integration_distribution.py build --profile task --output /absolute/private/golem-task.mcpb
python3 tools/integration_distribution.py verify --input /absolute/private/golem-task.mcpb --reviewed-sha256 OWNER_REVIEWED_ARCHIVE_SHA256
```

`read`·`prepare`는 조회/준비, `task`는 Work 수명주기, `quality`는 QA/증거, `parallel`은 기존 candidate/workspace용 상한이다. 서로의 권한을 자동 포함하지 않는다. builder는 설치·승인·Work 변경을 하지 않으며, 생성 성공만으로 client 검증이 완료되지는 않는다. 외부 runtime이 필요하고 서명된 self-contained 배포를 뜻하지 않는다.

</details>

## 업데이트·정리

- 새 archive SHA·설치 bytes와 필요한 client 검증을 확인한다. runtime·정책 변경은 [D5](integration-d5.md)에 따라 검토하며 기존 승인 bytes/key/pin을 자동 이전하지 않는다.
- owner-private 복구 자료를 보존하고 **Extensions → 대상 확장 → Remove**로 확인한 구버전 Golem만 제거한다. 검증된 Golem 한 개와 의도한 연결 한 개만 남기고 실제 목록·설정을 재확인한다.
- 기존 Work·승인·registry·evidence·CAS·journal와 다른 확장·설정은 보존한다. 설정 저장·handshake·도구 호출·현재 Work 완료는 각각 구분한다.
