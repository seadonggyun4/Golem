# 같은 대화의 도구 메타데이터 관측

Owner 연결 대조는 모델이 도구 이름을 다시 작성하는 시험이 아니다. **실제 도구 metadata를 읽은 한 번의 순수 `functions.exec` 원본 receipt**에서 이름·marker·대화·turn·원래 시각을 가져온다. 실행 권한과 Work HOLD는 바뀌지 않는다.

```text
검토한 같은 대화에서 metadata만 수집
 → 완료된 Codex rollout의 정확한 경로·SHA 선택
 → offline collector: thread / turn / 고정 코드 / call_id / 원본 output 대조
 → observation.json + provenance.json (새 private 폴더)
 → 기존 Owner의 marker·instance·catalog·5분 현재성·idle·exact 전환 검사
```

## 지원하는 수집

[`integration_stable_observation.py`](../tools/integration_stable_observation.py)의 `metadata_script(prefix)`가 만드는 아래 코드만 지원한다. prefix는 대상 서버에서 실제 사용하는 정확한 값을 검토한다. 이름·marker를 코드에 직접 넣거나 `tools.*` 함수를 호출하지 않는다.

```javascript
const selected = ALL_TOOLS.filter(t => t.name.startsWith('mcp__golem_local__'));
text({schema:'golem.external-tool-metadata.v1',entries:selected.map(t => ({name:t.name,description:t.description.split('\n').filter(line => line.startsWith('Fixed catalog observation only; no authority:')).join('\n')}))});
```

이 코드는 metadata를 읽을 뿐 Golem 도구를 호출하지 않는다. deferred 목록에 이름만 있고 marker가 든 상세 정의가 없다면 관측은 실패한다. 지원되는 정의 검색·로드는 별도로 허용한 범위에서만 진행한다. 실패한 수집을 자동 반복하지 않는다.

## 원본에서 수집하기

collector는 네트워크·MCP·모델·Owner·native를 호출하지 않는다. 현재 지원하는 입력은 **선택한 Codex 대화의 local rollout JSONL**뿐이다. `session_meta`, 완료된 target turn의 `task_started`·`turn_context`·`task_complete`, 정확한 `exec` 입력과 같은 `call_id`의 `custom_tool_call_output`을 연결한다. 첫 host-injected `create_thread`/`send_message_to_thread` 결과만 허용하며, 추가 실행·action 도구 호출이 있으면 차단한다. reasoning·모델 final·다른 turn의 내용은 출력에 넣지 않는다.

```sh
python3 tools/integration_stable_observation.py \
  --trace /absolute/reviewed-rollout.jsonl --trace-sha256 <exact-sha256> \
  --catalog /absolute/reviewed-catalog.json --catalog-sha256 <exact-sha256> \
  --thread-id <exact-chat-id> --turn-id <completed-turn-id> \
  --server-name golem_local --server-prefix mcp__golem_local__ \
  --started-not-before-ns <reviewed-window-start-nanoseconds> \
  --output-directory /absolute/new-private-output
```

원본과 catalog는 소유자·변경 여부·정확한 SHA를 검사한다. 기존 rollout의 mode를 바꾸지 않는다. 최대 입력은 16MiB·100,000행·행당 2MiB, metadata는 64KiB·128도구다. catalog는 **대조용**이며 관측에서 빠진 이름이나 marker를 채우는 데 사용하지 않는다. `nop`를 `noop`로 교정하거나 같은 개수의 다른 이름을 허용하지 않는다.

출력은 새 폴더 0700·파일 0600이며 덮어쓰지 않는다. 관측 시각은 원본 tool output의 UTC timestamp다. 현재 시각·파일 mtime·변환 시각으로 갱신하지 않으며 5분이 지난 자료는 거부한다. 부분 출력은 보존하고 같은 경로로 자동 재시도하지 않는다. `observation.json`은 기존 Owner 입력 형식이며 `provenance.json`은 입력 SHA·고정 script SHA·원본 행 SHA·call ID·원래 시각·출력 SHA를 별도로 기록한다.

## Claude의 정의 검색 결과 대조

검색어와 반환된 도구 이름은 별도로 검사한다. 실제 Desktop 관측에서는 `query: golem_work_noop_run, limit: 1`에 `Golem:golem_adapter_noop_run`이 반환됐다. 이는 서로 다른 두 도구이며, 첫 검색 결과를 요청한 정의로 간주하면 안 된다. 원래 이름을 바꾸거나 다른 도구를 호출해 확인하지 않는다.

정의 관측을 준비할 때 현재 목록의 정확한 이름과 설명을 사용하고, 검토한 검색 횟수·결과 개수 안에서 **반환된 상세 정의의 이름이 정확히 일치하는 항목만** 선택한다. 단일 최상위 결과가 정확한 이름 조회를 보장한다고 가정하지 않는다. 이름·marker·schema 중 필요한 정보가 없거나 다른 이름이면 `NOT_OBSERVED`로 기록한다. 실패 후 추가 검색은 자동 수행하지 않고 원래 검증 범위를 따른다.

Anthropic의 [공식 tool search 설명](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool)은 검색어/패턴과 반환된 tool reference를 구분한다. 이 API 설명만으로 Desktop의 내부 검색 알고리즘이나 정확한 이름 조회 지원을 확정하지 않는다. 실제 Desktop의 요청·응답 카드와 모델 답변을 따로 보존한다. 모델 답변의 `nop` 오타와 검색이 반환한 다른 `noop` 도구도 서로 다른 관측이다.

## 검증 범위와 한계

- `read_thread(includeOutputs=true)`의 관측된 지원 응답은 `functions.exec` receipt를 생략한다. `--input-format read-thread`는 `MISSING_MACHINE_RECEIPT`로 거부하며 final 답변을 대신 사용하지 않는다.
- Claude의 읽을 수 있는 원본 receipt 형식은 이 collector에 구현하지 않았다. Claude 응답을 Codex 형식으로 포장해 통과시키지 않는다.
- 로컬 rollout의 hash 일치는 **선택한 bytes의 무결성**이다. host 서명·사람 인증·모델 내부 상태의 진실성을 보증하지 않는다. 위조된 로컬 로그를 암호학적으로 판별하는 기능은 없다.
- `server_name`은 호출자가 선택한 표시값이며 host 신원 인증이 아니다. 실제 entries의 정확한 `server_prefix`는 별도로 대조하고 출처를 기록한다.
- 전체 이름 inventory와 marker의 상관관계를 확인한다. 모든 도구의 input schema가 모델 문맥에 동시에 로드됐다는 주장은 하지 않는다. `full_input_schema_delivery_verified`는 `false`다.
- collector 성공은 준비 허가·실행 승인·전환 성공이 아니다. 기존 [Owner 계약](integration-stable-owner.md)의 정확한 상태·native 권한·불확실 결과 차단은 그대로 적용한다. provenance를 기존 Owner가 별도로 인증한다고 주장하지 않는다.

회귀는 [`test_integration_stable_observation.py`](../tools/test_integration_stable_observation.py)의 합성 원본으로 수행한다. 실제 client·Work 검증과 구분한다.
