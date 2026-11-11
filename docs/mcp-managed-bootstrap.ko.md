# MCP로 관리형 개발을 시작하는 경계

자연어 요청을 받은 agent가 필요한 MCP 인자를 구성한다. 연결과 준비 도구의
노출만으로 제품 개발·QA·완료 권한이 생기지는 않는다. 설치된 프로그램,
feature profile, 현재 D1/D2와 D4 exact action, native 상태가 모두 맞아야 한다.
이 안내의 M2 준비는 이미 등록·허용된 Work를 대상으로 한다. 새 Work·D1 등록이나
owner 정책을 자동 생성하지 않는다. [연결 참여 수명주기](mcp-participation-lifecycle.ko.md)와
실제 도구 호출·Work 변경의 효과도 구분한다.

```text
프로젝트·Work 조회
  → 소스 기준점과 요구사항 확인
  → 관리형 scope·selection 준비 → owner 검토 → 정확한 문서 제출
  → 현재 입력·세션 확인 → 계획 문서 제출
  → 실행 계약 검토 → prepare → 개발 → finish
  → qa-plan → run → schema-5 결과 제출
  → 현재성 검증 → 별도 완료 판단·기록 → 현재 완료 조회
```

이 순서는 [native 실행 계약](execution.md), [관리형 workflow](workflow.md),
[D4 exact action](integration-d4.md)을 사용한다. MCP에서 차단된 Work 변경을
Core CLI 직접 호출로 우회하지 않는다. 설치·정책 선택은 별도의 owner 관리 절차다.

`projects_list`의 각 프로젝트에는 `workflow_capabilities.workflows.managed_bootstrap`
진단이 포함된다. 기존 9개 도구의 필요 여부와 소스 캡처 → assessment 검증 → scope
등록 → selection 도출·등록 → session_start 순서를 함께 안내하며, profile 제외와
owner 서비스 미제공, 제공된 client 관측의 도구 누락을 구분한다. client 관측이 없으면
그 결과를 추정하지 않는다. HEAD는 필수(`required=true`)지만 조회하지 않았으므로
`NOT_OBSERVED`이며, 이 진단은 소스를 캡처하거나 Work 준비 완료를 판정하지 않는다.
모든 도구가 보여도 `execution_authorized=false`, native 조건은 `NOT_CHECKED`다.

## 최초 문서와 소스 기준점

일반 planning 문서 하나를 등록한 상태는 관리형 scope·selection이 준비된 상태와
다르다. metadata의 schema version, kind, 필요한 assessment/selection을 native
parser로 검사하고 원문과 요구사항에 맞는 문서를 제출해야 한다. 단순 스키마
유효성을 의미 검토·owner 승인·현재 stage 충족으로 보고하지 않는다.

첫 문서가 없는 Work도 native `work record`로 빈 documents/assessments와 실제
genesis journal·head·sequence를 조회한다. Python이 빈 record를 대신 만들지 않는다.
이 조회가 scope나 selection을 생성하거나 session 시작 조건을 충족시키지는 않는다.

첫 관리형 문서의 순서는 다음과 같다. 각 변경이 성공한 후 상태를 다시 관측해 다음
exact action을 준비한다. 미래 generation이나 native key를 임의로 예측하지 않는다.

```text
action_prepare(discovery_snapshot) → owner의 exact D4 선택 → discovery_snapshot
  → 원래 native stdout 복원 → discovery assessment 구조검사·내용 검토
  → action_prepare(document_submit, schema_version=2, kind=scope, stage=planning)
  → owner가 정확한 bytes를 검토·D4 등록 → document_submit
  → workflow_read(operation=select, selection_id=<scope ID>, revision=<실제 revision>,
                  target_kind=development)
  → 반환 selection을 담은 schema-3 stage-selection 준비·검토·제출
  → 실제 selection ID를 쓰는 session_start 준비·검토·실행
```

`discovery_snapshot`은 기존 공통 MCP의 exact D4 도구다. 일반 Work 읽기 권한으로
소스 파일을 자동 캡처하지 않는다. `action_prepare(tool=discovery_snapshot)`의
`fields_json`에는 검토할 [snapshot plan](../samples/discovery/plan.json)을 문자열로
담은 `plan_json`이 필요하다. 등록된 프로젝트 root와 명시적으로 선택한 상대 파일
경로만 허용하며, 준비 자체는 소스 캡처를 수행하지 않는다. 실제 캡처는
owner가 검토한 정확한 action을 선택한 이후에만 수행한다. 도구가 없는 경우 현재
profile·D4 범위를 확인하고 owner 검토로 연결하며, CLI로 우회 캡처하지 않는다.

새 초안은 기존 Owner 앱에서 같은 살아 있는 연결의 정확한 `plan_id`·`plan_sha256`로
검토한다. D4 action이 없는 첫 Work도 기존 first-action 후보 경로를 쓴다. 후보 파일
저장과 실제 정책 선택·적용은 별개이며, 저장만으로 action이 승인되거나 도구가
노출되지는 않는다. 준비안은 서비스 인스턴스·30분·변하지 않은 관측 기준에 묶인다.
연결 종료·만료·상태 변경 때 과거 준비안을 되살리거나 자동으로 다시 실행하지 않는다.

`next`의 `START_REQUIRED`는 현재 세션이 없다는 뜻이다. 아직 없는 selection을
생략하고 session_start를 실행하라는 지시가 아니다. 이 경로는 일반 Work schema
1/2의 계약이며, Intent Work schema 3의 SESSION gate는 별도 exact product access를
계속 요구한다. **Work specification 버전과 document metadata 버전은 별개다.**

`action_prepare`의 고정 입력은 다음과 같다. 일반 planning 문서나 agent 진술을
assessment·native snapshot 대신 채우지 않는다.

| 필드 | 최초 scope 문서의 계약 |
| --- | --- |
| `session_id` | 비어 있지 않은 영문/숫자로 시작하는 1~64자 ID, 이후 영문·숫자·`_`·`-` 허용. 준비안의 caller label이며 사람 신원 인증·세션 시작 증거 아님 |
| `native_binding_id` | 별도 native binding이 없으면 빈 문자열 |
| `context_json`, `count_json` | document_submit에서는 둘 다 빈 문자열. 문자열 `"{}"`로 대체 불가 |
| `body` | native가 요구하는 섹션·요구사항·부모 참조를 갖춘 실제 Markdown 본문. 누락 시 질문 반환 |
| `fields_json` | JSON 객체를 직렬화한 문자열. `schema_version:2`, `document_id`, `kind:scope`, `stage:planning`, `producer_attempt`, `requirement_ids`, `source_snapshot`, `scope_revision`, `template_version`, `policy_version`, `assessment` 필요 |
| 부모 | `parents` 또는 `parent_ids` 하나만 사용. 첫 scope의 빈 부모는 명시적 `[]`; 기존 부모는 관측된 정확한 reference 사용 |
| 자동 도출 | Work ID·현재 document generation·revision·supersedes·새 준비 key는 실제 관측에서 생성. native key와 D4 request ID는 plan에 보존 |

`session_resume`과 `role_enroll`은 context/count의 별도 계약이 있으므로 위 빈 문자열
규칙을 모든 도구에 적용하지 않는다. 실제 native parser로 검사되는 합성 예제는
[`integration_managed_bootstrap.py`](../tests/c/integration_managed_bootstrap.py)에 있다.
이 예제의 scope·stage-selection·session 시작은 임시 Work만 대상으로 하며,
실제 프로젝트용 승인 bytes나 미래 generation의 템플릿이 아니다.

같은 fixture의 `prepare()`는 세션 시작 전에도 transport의 `session_id`에
`fixture-owner`를 넣고 `native_binding_id`·`context_json`·`count_json`은 빈 문자열로
전달한다. session_start 준비의 `fields_json` 예제는 `{"selection_id":"selection"}`이며,
이 ID는 직전에 실제 등록한 stage-selection을 가리킨다. 본문은 discovery report와
native 문서 template으로 생성한다. 예제 ID·해시를 실제 Work에 복사하거나 아직 없는
selection을 만들어 넣지 않는다.

외부 schema가 잘못되면 원래 `SCHEMA` 코드와 함께 `validation_diagnostic`에
입력 경로·기대 타입/형식·누락 여부를 반환한다. 예를 들어 빈 session_id는
`$.session_id`의 identifier 형식 오류다. 원래 입력값, 승인 token/key 값,
알 수 없는 입력 필드 이름은 포함하지 않는다. 외부 schema(`INPUT_SCHEMA`)와
native envelope 등의 내부 형태 검사(`CONTRACT_SHAPE`)를 구분한다. document_submit의
비어 있어야 하는 context/count도 원래 `ACTION_CONTEXT_SCOPE` 코드와 함께 설명한다.
설명이 추가돼도 `NOT_DISPATCHED`나
`COMMIT_UNKNOWN`·자동 재시도 금지 의미는 변하지 않는다. 외부 schema를 통과한 뒤
본문·metadata 필드가 빠져 있으면 기존 `PREPARATION_INPUTS_MISSING` 질문을 사용한다.

입력이 남은 초안의 `preparation_state=INPUTS_REQUIRED`와 입력을 갖춘
`REVIEW_REQUIRED`를 구분한다. 입력을 갖춘 초안의 같은 기준을 재조회한 값은
`CURRENT_BASIS_REVIEW_REQUIRED`이며, 미입력 초안은 재조회해도 `INPUTS_REQUIRED`를 유지한다.
모두 `execution_authorized=false`이고 현재 native
실행 조건을 인증하지 않는다. `owner_handoff`는 같은 초안의 검토 참조와 다음 owner
단계를 안내할 뿐 승인 발급·정책 적용을 하지 않는다. `approved_action_prepare`와
`action_confirm`은 이미 owner가 등록한 action을 대조하는 도구이며 새 초안을
자기승인하는 경로가 아니다.

`source_snapshot`은 임의 파일 목록의 SHA-256이나 Git commit ID와 동의어가 아니다.
discovery assessment에서는 `discovery validate`가 snapshot 객체의 JSON-C compact
직렬화로 계산한 digest를 사용하고, native 문서 등록이 이 값을 대조한다.
agent가 다른 JSON serializer나 로컬 inventory 해시로 그 값을 대신 만들지 않는다.
M2도 assessment 안 snapshot의 원래 JSON member order를 보존한다. 키 정렬로
snapshot을 바꾼 뒤 기존 digest를 붙인 요청은 native가 거절하며, MCP가 digest를
다시 계산해 고치거나 이미 승인된 bytes를 교체하지 않는다.

실제 `discovery_snapshot` 응답에서는 **`native_stdout_base64`를 복원하고 그 raw bytes의
SHA-256을 `native_stdout_sha256`와 대조한 뒤**, JSON member order를 보존해 assessment의
snapshot으로 사용한다. 편의를 위한 `native_reply`는 MCP JSON 전달 중 키 순서가
정렬될 수 있어 native digest의 직렬화 기준으로 삼지 않는다. raw stdout의 해시와
native `discovery validate`가 반환하는 `snapshot_digest`는 서로 다른 값이며, 문서의
`source_snapshot`에는 후자를 사용한다. 무결성 대조는 실제 조사·QA의 진실성이나
현재 소스와의 일치를 추가 인증하지 않는다.

현재 [native discovery snapshot](discovery.md)은 **HEAD commit이 있는 Git 저장소만
지원**한다. 실행 계약의 snapshot과 전체 change inventory도 HEAD를 요구한다.
HEAD 없는 초기 저장소의 파일 목록을 만들었다고 이 조건이 해소되지는 않는다.

- 추적할 파일과 제외할 파일, 비밀·생성물 여부를 먼저 검토한다.
- Git 기준점 생성이 필요하면 정확한 추적·커밋 범위에 대해 owner의 별도 결정을 받는다.
- 이 준비 경로는 파일을 자동으로 stage/commit/push하거나 가짜 HEAD를 만들지 않는다.
- HEAD 없는 snapshot 형식이나 자동 migration은 이번 구현에 포함하지 않는다.

HEAD 조회 실패는 기존 오류 코드와 함께 `discovery.head_unavailable` 진단을 남긴다.
이는 unborn 저장소 확정이 아니다. 저장소·접근 상태를 먼저 확인하고, 실제 초기
저장소인 경우에만 선택 파일과 초기 커밋 범위를 owner가 검토한다. 최초 HEAD는 읽었지만
마지막 대조가 실패한 경우 `discovery.head_recheck_unavailable`로 구분한다. 다른 Git
오류를 HEAD 부재로 바꾸지 않으며 진단을 위한 추가 probe·자동 재시도·커밋은 없다.

소스 변경 여부를 관찰한 unsigned 실행 기록도 native observed-development receipt의
대체가 아니다. 문서 metadata의 `source_snapshot`은 계획 기준점이고, 실제 개발 후
소스 상태는 `finish`가 발급하는 별도 execution receipt에 들어간다. 기존 기준점,
등록 문서나 receipt를 덮어써서 새로운 소스를 과거 실행 결과로 인증하지 않는다.

## QA·검증·완료를 구분하기

| 경로 | 확인하는 것 | 확인하지 않는 것 |
| --- | --- | --- |
| `execution_request`의 `prepare`·`finish` | 승인된 계약의 기준점·개발 후 관측과 receipt | QA 실행·PASS·완료 |
| `execution_request`의 `run` | 고정 gate/case의 실제 실행 결과와 불변 QA receipt | 모든 제품 요구사항의 진실성·현재 완료 |
| `execution_read(operation=stored_result)` | 이미 저장된 과거 결과 | 현재 소스에서의 유효성·재실행 |
| `execution_read(operation=verify)` | 지정 receipt의 native 현재성·무결성 검사 | QA 재실행·QA PASS·완료 |
| `execution_verify` | owner가 고정한 receipt의 같은 native 현재성 검사 | QA 재실행·권한 발급·완료 |
| `completion_finalize`·`intent_completion_finalize` | 선택된 native 완료 predicate와 필요한 현재 수락 | 다른 predicate·merge·배포 보증 |
| `completion_check` | 현재 조건에 따른 완료 판단 재조회 | QA 실행 자체·새 완료 기록 생성 |

`execution_read(operation=verify)`와 D4 `execution_verify`는 모두 기존
`execution verify` native 경로를 사용한다. 전자는 D2가 허용한 조회이며 후자는
정확한 action bytes를 선택한 D4 경로다. 둘은 권한·감사 계약이 다르므로 자동으로
서로 전환하지 않는다. 검증 성공은 신선한 **FAIL receipt**에도 가능하다. 구조화된
QA status와 각 case 결과를 별도로 확인해야 한다.

`task` profile은 이제 기존 `execution_verify` 도구를 허용 가능한 도구 집합에 포함한다.
실제 노출·호출은 현재 D4 owner policy와의 교집합으로 제한된다. 기존 정책에 action을
자동 추가하지 않으며, `read`·`prepare` profile에는 해당 D4 action을 추가하지 않는다.
profile 진단은 profile 제외, owner action 부재, client 도구 미노출을 구분한다.

개발 모드에서는 schema-5 결과와 native 관측 receipt, 현재 입력, gate/case PASS 및
선택한 완료 predicate가 필요하다. 문서 전용 완료는 실행 사실을 주장하지 않는다.
Intent/QC가 적용된 Work는 별도의 현재 QA 수락도 필요하며 일반 QA PASS로 이를
대신하지 않는다. [QC4](intent-assurance-qc4-implementation.ko.md)와
[QC5](intent-assurance-qc5-implementation.ko.md)를 따른다.

## 차단 시 처리와 검증 범위

pending 승인, 바뀐 입력·정책·producer pin, 만료된 세션, 누락된 case,
결과 유실·`COMMIT_UNKNOWN`은 기존 계약대로 보존하고 차단한다. 같은 요청을 임의로
재실행하거나 다른 ID로 바꿔 우회하지 않는다. 저장 결과 조회가 현재성 검사나
현재 완료를 대신하지 않는다는 점도 유지한다.

회귀 fixture는 task profile의 owner action 필터, 정확한 Work/action/receipt pin,
동일 request의 저장 결과 반환, 현재성 검사 결과가 PASS·완료로 승격되지 않는 것을
검사한다. 합성 fixture 통과는 실제 client E2E·제품 실행 성공과 구분한다.
이 변경만으로 기존 설치·정책·승인·Work·증거는 변경되지 않는다. 실제 프로젝트
개발·QA·완료와 설치 전환은 별도의 승인된 범위에서 검증해야 한다.

회귀 진입점은 `test_integration_diagnostics`, `test_integration_m2`,
`test_integration_mutations`, `test_integration_m4`, `test_integration_m6`와 CTest의
`integration_managed_bootstrap`, `work_record_integration`, `discovery_cli`다.
임시 native fixture의 Work 생성·문서 등록은 실제 제품 Work 실행과 구분한다.
`integration_managed_bootstrap`은 기존 schema2 문서 검증 외에 새 임시 Git 저장소의
실제 D4 snapshot → 원래 stdout 복원 → native assessment validate → scope·selection
등록 → session_start 경로도 검사한다. 초기 샘플 snapshot의 합성 해시를 실제 캡처로
보고하지 않으며, 이 테스트의 결과는 `CLAIM_REQUIRED`까지다. claim·제품 개발·QA·완료나
Codex·Claude Desktop E2E, 실제 UnderWhat Work 성공을 의미하지 않는다.
이 문서는 설치 완료나 Desktop에서의 도구 노출·승인 등록 완료를 주장하지 않는다.
