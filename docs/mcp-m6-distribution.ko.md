# M6 Setup/업무 스킬·기능 profile·패키징·설치·재로딩

## 현재: 남은 전달 경로 3개 연결

선택적 공통 관리 정책에 `adapter_convert`, `adapter_probe`, `candidate_serve`와 별도 승인 `candidate_stop`을 추가했다. 관리 도구는 5개이며 `management_host_status`가 연결이 소유한 프로세스 상태·관측된 socket identity를 알려준다. native 명령 연결은 17개, 중지 제어를 포함한 관리 operation은 18개다.

- 변환: 고정 input ID의 원본 bytes를 stdin으로 전달하고 json/msgpack 형식만 선택한다. native codec을 재사용하며 결과는 base64·SHA로 보존한다.
- probe: owner-private `golem.management-probe.v1` 입력에서 executable pin, cwd, timeout_ms를 고정한다. cwd는 승인된 target과 같아야 하며 실행 파일은 cwd 밖에서 hash를 재검사한다. 임의 argv/shell/env는 제공하지 않는다. 원본 native `--allow-process` 경로를 사용하고 NETWORK/CREDENTIAL/EXPORT/HOST_EXECUTION 효과를 별도로 승인한다. 이는 OS sandbox 제공을 뜻하지 않는다.
- host: owner-private `golem.management-host.v1` 입력에서 기존 M5 host policy pin·host ID를 선택한다. 기존 D4와 M5의 등록 Work·config·root·resource 계약을 재사용하고 native `--approve-config`가 config digest를 판정한다. 시작과 특정 launch action/request에 대한 중지 action을 모두 미리 검토해야 한다. 새 process group은 시간 제한 없이 연결이 소유하며 output 한도·명시 중지·정상 연결 종료로 종료한다. 관측 socket identity는 M5 socket 승인으로 자동 이전되지 않는다.

프로세스 시작과 socket 관측은 native readiness/QA/완료를 증명하지 않는다. stop/정상 종료는 모든 worker의 종료 attestation을 대신하지 않는다. 비정상 연결 유실 시 저장 PID를 채택하거나 자동 재시작하지 않으며 결과 유실은 COMMIT_UNKNOWN으로 격리한다. 실제 서비스 시작·복구·승인 발급과 새 Desktop E2E는 NOT_RUN이다. 후보 Codex 0.2.7/Claude MCPB 0.1.10은 미설치·기본 비활성이고 기존 검증 설치본은 유지한다.

아래의 14-operation/0.2.6/0.1.9 기록은 직전 개발 snapshot의 당시 결과다.


## 선택적 프로젝트 관리 MCP 확장

사용자는 자연어로 요청하고 agent가 catalog의 ID와 구조화된 인자를 채운다.
공통 stdio entry `integration_owner_maintenance.py mcp`는 기존 profile의 D2/D4
서비스를 재사용한다. 별도 관리 정책·검토 SHA·명시적 consent가 모두 있을 때만
`management_catalog`, `management_prepare`, `management_request`, `management_result`를
추가한다. 기존 Work profile·권한·native 승인·소유권·완료 predicate를 변경하지 않는다.

- catalog: 선택 프로젝트·target/input ID·관리 operation·이미 검토된 action 조회.
- prepare: 정확한 입력과 target fence를 대조하고 비권한 준비안 반환. 사용자에게 JSON
  프롬프트 작성을 요구하지 않으며 부족한 입력은 agent가 질문한다.
- request: 관리 정책에 이미 고정된 action만 한 번 전달. 효과·native/producer/input
  pin·project/Work·directory identity·snapshot·출력 예산을 검사한다.
- result: 같은 action/request ID의 보존된 결과만 조회. 원래 action에 한 번 intent가
  생기면 새 request ID로도 재실행하지 않는다. 유실·변조·partial·COMMIT_UNKNOWN 보존.

14개 한정 operation: daemon_status/init/submit/run_once/drain/recover, journal_inspect/
verify_salvage/salvage, adapter_describe/noop_probe, admission_probe, approval_describe/decide.
승인 결정은 원본 요청 bytes를 그대로 기존 `approval call`에 전달한다. Python에서
승인·복구·scheduler를 재구현하지 않는다. daemon은 --once/--drain만 지원하며 무기한
서비스·임의 worker 실행 파일·shell/argv·C pointer/handle은 MCP 입력으로 받지 않는다.
복구는 정확한 stopped-owner attestation과 원본 hash가 필요하다. attestation은 실제
종료를 독립 인증하지 않으며 core의 lock/guard를 대체하지 않는다.

관리 정책 schema는 `schemas/project-management.json`, 모든 inputSchema는 closed
object다. data_class는 APPROVED_MANAGEMENT_CONTENT이고 기존 D2 목적지와 일치해야
한다. 정책·audit registry는 프로젝트 밖의 owner-private 경로에 두고 기존 프로젝트
D1 등록과 base D2/D4 정책에 결합한다. catalog/prepare는 정책을 만들거나 적용하지 않는다.

후보 배포물은 Claude MCPB 0.1.9 및 Codex plugin 0.2.6이다. optional management consent는
기본 false다. 이전에 설치·검증한 0.1.8/0.2.5와 실제 승인/producer pin은 그대로 보존한다.
새 source를 기존 정책에 자동 적용하지 않으며 새 후보의 검토·선택 전 실제 Desktop에
설치하지 않는다. 실제 서비스 시작·복구·승인 발급과 새 후보 Desktop E2E는 NOT_RUN이다.
SDK stdio fixture와 실제 Desktop 검증을 구분한다. P4/P5 scheduler·merge 및 P7 signed
self-contained runtime은 이 확장으로 구현된 것이 아니다.

---

아래 M6 원장과 당시 결과는 기존 명시 범위의 기록이다. owner 83개는 누락 도구 수가
아니며 parent route·기존 facade·host API·owner 전용 경계를 포함한다. 새 관리 facade와
남은 native/CLI 전용 경로는 별도 operation 대조 원장에 기록한다.

상태: 명시 범위의 profile·패키징·스킬·기존 owner 경로 코드 구현, 정적·fixture 검증 완료 기록. 운영 검증은 별도다. 실제 설치·업데이트·연결·재로딩·client/Work E2E·외부 서비스·승인/등록/정책 적용·merge·commit/push는 NOT_RUN이다. 서명 trust root·embedded runtime의 재배포·정식 host qualification을 선택하거나 인증하지 않는다.

## 실제 제공 경로

- `integration_feature_profiles.py`: read/prepare/task/quality/parallel의 유한 source 도구 상한과 기존 owner scope의 교집합. `.tools()`에서 줄이고 `.call()`에서도 다시 차단한다. profile 선택은 grant·승인·network·credential·export 권한을 만들지 않는다.
- `integration_distribution_entry.py`: 기존 D2 Transfer/Service와 D4 Policy/Service 및 별도 Resources/Helpers/Hosts를 그대로 사용한다. 기존 consent와 정확한 SHA가 있어야 policy를 읽는다. helper는 quality, host는 parallel에서만 별도 세 인자로 선택한다. 기본 비활성이며 환경변수나 CLI의 명시 owner 입력으로만 구성한다. setup 실패에는 원래 public setup-only 안내를 제공한다.
- `integration_distribution.py`: 기존 MCPB manifest 0.4/uv 구조를 재사용한 deterministic review artifact build/verify/extract. 정확한 공개 파일 allowlist, import closure, 스킬·문서·schema·asset, 전체 내용 SHA, native artifact의 선택적 owner SHA를 대조한다. 새 추출 경로만 허용하고 traversal/duplicate/case alias/symlink/크기 초과/추가 파일·기존 경로를 차단한다. 실패 시 partial 자료를 자동 삭제하거나 repair하지 않는다.
- `integration_owner_maintenance.py`: owner-local schema/plan/inspect/apply를 기존 Installer와 D5 Manager에 위임한다. 원래 plan schema·SHA·producer·registry/설치 identity·관측·lock·quiet/미해결 효과 검사·runtime probe를 재사용한다. 원본 plan을 변환하거나 재발급하지 않는다. 별도 authority DB, MCP 관리 tool, 자동 repair/retry는 없다.
- Setup과 Golem Work skill을 분리했다. 업무 스킬은 실제 도구 discovery→명시 Work status/next→허용 읽기/준비→정확한 이미 승인된 action 확인→허용된 원래 결과 재조회 경로를 안내한다. 설치·설정/재연결을 일반 Work 실패의 해결책으로 실행하지 않는다. private Codex package builder도 유지되는 plugin manifest와 두 스킬을 명시적으로 포함한다.

## Profile·권한

| profile | ceiling | 필수·추가 계약 |
| --- | --- | --- |
| read | D2 native/자료 읽기 | 기존 D1/D2, 외부 파일은 별도 resource |
| prepare | read + M2 비권한 초안/입력 + M5 제안 검토 | 기존 D1/D2; owner action 확인은 D4 profile에서만 |
| task | read/M2 + 기존 D4/M3 | 정확한 D4 action; QA는 원래 별도 승인 |
| quality | read/M2 + QA/evidence/research/accounting | D4, helper는 별도 M4 exact effects opt-in |
| parallel | read/M2 + 기존 candidate/workspace/inventory | D4, host/종료 attestation 별도 M5 opt-in |

실제 tools/list는 현재 정책·Work·resource·helper·host와 profile 교집합이다. source에 code가 포함됐다는 사실, 현재 도구 노출, owner 승인, 실제 호출 성공은 별개다. M4 cost inbox는 disposable 첫 단계 재구성이며 live run 정산이 아니다. workspace_read는 역사 D4 결과이며 현재 RESUME 검사는 writable native 계약의 정확한 D4 action이다. QA/PASS·선택·hash를 현재 완료·target 채택·merge로 승격하지 않는다.

## 배포 artifact의 한계와 P7

feature-package.json은 무권한 파일 inventory/기능 설명이다. owner가 따로 검토한 전체 archive SHA가 필요하며, builder가 계산한 hash 자체가 owner 승인이나 서명이 아니다. 패키지에는 실제 policy·registry·Work·credential·evidence·로그를 수집하지 않는다. 원본 저장소·현재 cwd나 ambient PYTHONPATH 없이 추출된 runtime import closure를 검사한다. 설치는 수행하지 않는다.

기존 uv MCPB profile은 외부 Python/SDK 의존성 해결을 요구할 수 있다. 자동 network/서비스 권한을 제공하지 않으며 offline/embedded/self-contained release라고 표시하지 않는다. 별도 검토된 native binary를 복사할 수 있지만 실행·ABI·동적 라이브러리·codesign·실제 client qualification을 인증하지 않는다. 사용자는 완성 artifact와 검토된 외부 runtime/native를 제공받을 경우 원본 clone/build 없이 실행할 수 있는 경로를 갖지만, 실제 신규 설치 환경의 성공은 NOT_RUN이다.

P7 embedded Python/dependencies/native closure의 완성 배포, OS별 code signing/notarization·trust root, 공급망 서명/업데이트 channel·registry 등재는 NOT_IMPLEMENTED 또는 정책 미결이다. 이를 테스트 skip/NOT_RUN만으로 숨기지 않는다. 기존 배포 문서의 제안 상태를 완료로 바꾸지 않는다.

## 설치·전환·재로딩

owner bridge의 installation은 기존 install/remove/bootstrap, maintenance는 freeze/stage/verify/switch/restore/thaw/ready만 허용한다. apply에는 명시 owner flag와 원래 plan digest가 필수다. repair 명령을 노출하지 않는다. 실제 사용자 상태에서는 이번 작업으로 실행하지 않았다.

준비에는 기존 Installer.plan 또는 Manager.plan, 결과 조회에는 기존 inspect를 사용한다. 부분 설치/전환·결과 유실·COMMIT_UNKNOWN은 원래 자료를 보존한다. 별도 자동 재실행·rollback을 하지 않는다. stop 요청·시간 경과·lease 만료만으로 정지했다고 판정하지 않는다. D5 ready는 원래 reload probe·Work inventory·binding/producer/runtime 대조를 요구하며 owner ACK만으로 열리지 않는다. 실제 SDK probe/desktop reload는 NOT_RUN이다.

## owner backlog 83개

83개는 설치 목록과 동일하지 않다. 실제 원장에는 daemon/admission/worker/supervisor/자원·승인 관리 API와 기존 읽기/action의 owner 측 경계가 함께 있다. 고정 ID·원래 current/target route를 유지하고 아래 고정 표에서 소스·실제 경로·기능 profile·효과·한도·검증을 대조한다. owner API를 패키지에 포함했다고 MCP 제공이나 승인 완료로 계산하지 않는다. owner backlog는 삭제하지 않는다.

M5 scheduler·typed-edge acceptance·receiver resource broker·merge queue·integration workspace/fresh QA·target ref CAS broker·merge publication receipt 7개는 NOT_IMPLEMENTED다. 기존 unsupported17개도 그대로 유지한다.

## 검증·보존

임시 설치 root·가짜 owner policy/registry·capture double·기존 D5/Installer fixture만 사용한다. 실제 사용자 설치/연결/재로딩/승인/Work를 변경하지 않는다. 검증 결과와 고정83개 표는 아래 최종 기록을 따른다.


## 사용·검토 경로

owner-local `integration_distribution.py catalog`는 profile의 source 상한만 출력한다. build는 명시 profile과 새 output을 요구한다. verify/extract에는 owner가 따로 검토한 archive SHA가 필요하다. 코드가 출력한 hash를 자동 승인으로 사용하지 않는다. extract는 새 private directory에 검토 artifact를 풀 뿐 client 설정이나 registry를 적용하지 않는다. schema payload는 기존 D2/D4·Installer·D5 정의에서 생성하며 native parser를 Python으로 복제하지 않는다.

기존 Installer는 계속 D2 관리형 client 설정만 다룬다. D4 feature entry는 owner가 선택한 기존 Codex launcher의 정확한 command/args 또는 MCPB의 별도 owner policy 설정으로 연결할 수 있다. mutation policy를 기존 D2 transfer policy로 가장하거나 Installer schema에 몰래 추가하지 않는다. 실제 client 활성화·D4 profile 설치는 NOT_RUN이다. profile 변경은 새 grants/승인을 만들지 않는다.

## 고정 83개 대조

분류는 기존 native owner CLI/경계33개, native host API43개, candidate owner host/start2개, native 승인 결정5개다. 기존 capability ID/current/target route/effects를 그대로 고정했다. **83개는 owner 경계 검토이며 새 MCP 관리 기능 83개 제공이나 실제 승인 완료가 아니다.** owner 관리 backlog83개는 원장에 남긴다.

| 고정 ID | 실제 source 근거 | owner 경로·profile 관계 | 잠재 효과 | 검증·한도 |
| --- | --- | --- | --- | --- |
| `session.reject_output` | `src/agent_session/coordinator.c` | EXISTING_NATIVE_OWNER_CLI_OR_SCOPED_FACADE; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ, NATIVE_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing per-operation native owner or D2/D4 authority; package inclusion never enables operations outside exposed policy scope. |
| `cli.route.adapter` | `src/cli/main.c` | EXISTING_NATIVE_OWNER_CLI_OR_SCOPED_FACADE; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | DISCLOSURE, AUDIT_WRITE, NATIVE_READ, NATIVE_WRITE, PROCESS | 기존 native/owner guard와 M6 static frozen row; Existing per-operation native owner or D2/D4 authority; package inclusion never enables operations outside exposed policy scope. |
| `cli.route.agent` | `src/cli/main.c` | EXISTING_NATIVE_OWNER_CLI_OR_SCOPED_FACADE; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | DISCLOSURE, AUDIT_WRITE, NATIVE_READ, NATIVE_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing per-operation native owner or D2/D4 authority; package inclusion never enables operations outside exposed policy scope. |
| `cli.route.approval` | `src/cli/main.c` | EXISTING_NATIVE_OWNER_CLI_OR_SCOPED_FACADE; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | DISCLOSURE, AUDIT_WRITE, NATIVE_READ, NATIVE_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing per-operation native owner or D2/D4 authority; package inclusion never enables operations outside exposed policy scope. |
| `cli.route.daemon` | `src/cli/main.c` | EXISTING_NATIVE_OWNER_CLI_OR_SCOPED_FACADE; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | DISCLOSURE, AUDIT_WRITE, NATIVE_READ, NATIVE_WRITE, PROCESS | 기존 native/owner guard와 M6 static frozen row; Existing per-operation native owner or D2/D4 authority; package inclusion never enables operations outside exposed policy scope. |
| `cli.route.doctor` | `src/cli/main.c` | EXISTING_NATIVE_OWNER_CLI_OR_SCOPED_FACADE; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | DISCLOSURE, AUDIT_WRITE, NATIVE_READ, NATIVE_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing per-operation native owner or D2/D4 authority; package inclusion never enables operations outside exposed policy scope. |
| `cli.route.init` | `src/cli/main.c` | EXISTING_NATIVE_OWNER_CLI_OR_SCOPED_FACADE; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | DISCLOSURE, AUDIT_WRITE, NATIVE_READ, NATIVE_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing per-operation native owner or D2/D4 authority; package inclusion never enables operations outside exposed policy scope. |
| `cli.route.journal` | `src/cli/main.c` | EXISTING_NATIVE_OWNER_CLI_OR_SCOPED_FACADE; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | DISCLOSURE, AUDIT_WRITE, NATIVE_READ, NATIVE_WRITE, CLEANUP | 기존 native/owner guard와 M6 static frozen row; Existing per-operation native owner or D2/D4 authority; package inclusion never enables operations outside exposed policy scope. |
| `cli.route.profile` | `src/cli/main.c` | EXISTING_NATIVE_OWNER_CLI_OR_SCOPED_FACADE; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | DISCLOSURE, AUDIT_WRITE, NATIVE_READ, NATIVE_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing per-operation native owner or D2/D4 authority; package inclusion never enables operations outside exposed policy scope. |
| `cli.route.reentry` | `src/cli/main.c` | EXISTING_NATIVE_OWNER_CLI_OR_SCOPED_FACADE; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | DISCLOSURE, AUDIT_WRITE, NATIVE_READ, NATIVE_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing per-operation native owner or D2/D4 authority; package inclusion never enables operations outside exposed policy scope. |
| `cli.dispatch.adapter.convert` | `src/cli/adapter.c` | EXISTING_NATIVE_OWNER_CLI_OR_SCOPED_FACADE; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | DISCLOSURE, AUDIT_WRITE, NATIVE_READ, NATIVE_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing per-operation native owner or D2/D4 authority; package inclusion never enables operations outside exposed policy scope. |
| `cli.dispatch.adapter.describe` | `src/cli/adapter.c` | EXISTING_NATIVE_OWNER_CLI_OR_SCOPED_FACADE; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | DISCLOSURE, AUDIT_WRITE, NATIVE_READ, NATIVE_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing per-operation native owner or D2/D4 authority; package inclusion never enables operations outside exposed policy scope. |
| `cli.dispatch.adapter.noop` | `src/cli/adapter.c` | EXISTING_NATIVE_OWNER_CLI_OR_SCOPED_FACADE; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | DISCLOSURE, AUDIT_WRITE, NATIVE_READ, NATIVE_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing per-operation native owner or D2/D4 authority; package inclusion never enables operations outside exposed policy scope. |
| `cli.dispatch.adapter.probe` | `src/cli/adapter.c` | EXISTING_NATIVE_OWNER_CLI_OR_SCOPED_FACADE; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | DISCLOSURE, AUDIT_WRITE, NATIVE_READ, NATIVE_WRITE, PROCESS | 기존 native/owner guard와 M6 static frozen row; Existing per-operation native owner or D2/D4 authority; package inclusion never enables operations outside exposed policy scope. |
| `cli.dispatch.approval.call` | `src/cli/approval.c` | EXISTING_NATIVE_OWNER_CLI_OR_SCOPED_FACADE; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | DISCLOSURE, AUDIT_WRITE, NATIVE_READ, NATIVE_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing per-operation native owner or D2/D4 authority; package inclusion never enables operations outside exposed policy scope. |
| `cli.dispatch.approval.describe` | `src/cli/approval.c` | EXISTING_NATIVE_OWNER_CLI_OR_SCOPED_FACADE; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | DISCLOSURE, AUDIT_WRITE, NATIVE_READ, NATIVE_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing per-operation native owner or D2/D4 authority; package inclusion never enables operations outside exposed policy scope. |
| `cli.dispatch.candidate.call` | `src/cli/candidate.c` | EXACT_M5_OWNER_HOST_OR_OWNER_START; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | DISCLOSURE, AUDIT_WRITE, NATIVE_READ, NATIVE_WRITE, PROCESS, GIT, CLEANUP, NETWORK | 기존 native/owner guard와 M6 static frozen row; M5 action/query pin contract; serve/start remains owner-only, NOT_RUN. |
| `cli.dispatch.candidate.serve` | `src/cli/candidate.c` | EXACT_M5_OWNER_HOST_OR_OWNER_START; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | DISCLOSURE, AUDIT_WRITE, NATIVE_READ, NATIVE_WRITE, PROCESS, GIT, CLEANUP, NETWORK | 기존 native/owner guard와 M6 static frozen row; M5 action/query pin contract; serve/start remains owner-only, NOT_RUN. |
| `cli.dispatch.daemon.init` | `src/cli/daemon.c` | EXISTING_NATIVE_OWNER_CLI_OR_SCOPED_FACADE; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | DISCLOSURE, AUDIT_WRITE, NATIVE_READ, NATIVE_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing per-operation native owner or D2/D4 authority; package inclusion never enables operations outside exposed policy scope. |
| `cli.dispatch.daemon.recover` | `src/cli/daemon.c` | EXISTING_NATIVE_OWNER_CLI_OR_SCOPED_FACADE; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | DISCLOSURE, AUDIT_WRITE, NATIVE_READ, NATIVE_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing per-operation native owner or D2/D4 authority; package inclusion never enables operations outside exposed policy scope. |
| `cli.dispatch.daemon.run` | `src/cli/daemon.c` | EXISTING_NATIVE_OWNER_CLI_OR_SCOPED_FACADE; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | DISCLOSURE, AUDIT_WRITE, NATIVE_READ, NATIVE_WRITE, PROCESS | 기존 native/owner guard와 M6 static frozen row; Existing per-operation native owner or D2/D4 authority; package inclusion never enables operations outside exposed policy scope. |
| `cli.dispatch.daemon.status` | `src/cli/daemon.c` | EXISTING_NATIVE_OWNER_CLI_OR_SCOPED_FACADE; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | DISCLOSURE, AUDIT_WRITE, NATIVE_READ, NATIVE_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing per-operation native owner or D2/D4 authority; package inclusion never enables operations outside exposed policy scope. |
| `cli.dispatch.daemon.submit` | `src/cli/daemon.c` | EXISTING_NATIVE_OWNER_CLI_OR_SCOPED_FACADE; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | DISCLOSURE, AUDIT_WRITE, NATIVE_READ, NATIVE_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing per-operation native owner or D2/D4 authority; package inclusion never enables operations outside exposed policy scope. |
| `cli.dispatch.doctor.admission` | `src/cli/doctor.c` | EXISTING_NATIVE_OWNER_CLI_OR_SCOPED_FACADE; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | DISCLOSURE, AUDIT_WRITE, NATIVE_READ, NATIVE_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing per-operation native owner or D2/D4 authority; package inclusion never enables operations outside exposed policy scope. |
| `cli.dispatch.journal.inspect` | `src/cli/journal.c` | EXISTING_NATIVE_OWNER_CLI_OR_SCOPED_FACADE; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | DISCLOSURE, AUDIT_WRITE, NATIVE_READ, NATIVE_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing per-operation native owner or D2/D4 authority; package inclusion never enables operations outside exposed policy scope. |
| `cli.dispatch.journal.salvage` | `src/cli/journal.c` | EXISTING_NATIVE_OWNER_CLI_OR_SCOPED_FACADE; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | DISCLOSURE, AUDIT_WRITE, NATIVE_READ, NATIVE_WRITE, CLEANUP | 기존 native/owner guard와 M6 static frozen row; Existing per-operation native owner or D2/D4 authority; package inclusion never enables operations outside exposed policy scope. |
| `cli.dispatch.journal.verify-salvage` | `src/cli/journal.c` | EXISTING_NATIVE_OWNER_CLI_OR_SCOPED_FACADE; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | DISCLOSURE, AUDIT_WRITE, NATIVE_READ, NATIVE_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing per-operation native owner or D2/D4 authority; package inclusion never enables operations outside exposed policy scope. |
| `cli.dispatch.runtime_profile.current` | `src/cli/runtime_profile.c` | EXISTING_NATIVE_OWNER_CLI_OR_SCOPED_FACADE; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | DISCLOSURE, AUDIT_WRITE, NATIVE_READ, NATIVE_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing per-operation native owner or D2/D4 authority; package inclusion never enables operations outside exposed policy scope. |
| `cli.dispatch.runtime_profile.link` | `src/cli/runtime_profile.c` | EXISTING_NATIVE_OWNER_CLI_OR_SCOPED_FACADE; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | DISCLOSURE, AUDIT_WRITE, NATIVE_READ, NATIVE_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing per-operation native owner or D2/D4 authority; package inclusion never enables operations outside exposed policy scope. |
| `cli.dispatch.runtime_profile.register` | `src/cli/runtime_profile.c` | EXISTING_NATIVE_OWNER_CLI_OR_SCOPED_FACADE; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | DISCLOSURE, AUDIT_WRITE, NATIVE_READ, NATIVE_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing per-operation native owner or D2/D4 authority; package inclusion never enables operations outside exposed policy scope. |
| `cli.dispatch.runtime_profile.validate` | `src/cli/runtime_profile.c` | EXISTING_NATIVE_OWNER_CLI_OR_SCOPED_FACADE; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | DISCLOSURE, AUDIT_WRITE, NATIVE_READ, NATIVE_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing per-operation native owner or D2/D4 authority; package inclusion never enables operations outside exposed policy scope. |
| `cli.dispatch.reentry.call` | `src/cli/reentry.c` | EXISTING_NATIVE_OWNER_CLI_OR_SCOPED_FACADE; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | DISCLOSURE, AUDIT_WRITE, NATIVE_READ, NATIVE_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing per-operation native owner or D2/D4 authority; package inclusion never enables operations outside exposed policy scope. |
| `cli.dispatch.reentry.validate` | `src/cli/reentry.c` | EXISTING_NATIVE_OWNER_CLI_OR_SCOPED_FACADE; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | DISCLOSURE, AUDIT_WRITE, NATIVE_READ, NATIVE_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing per-operation native owner or D2/D4 authority; package inclusion never enables operations outside exposed policy scope. |
| `cli.dispatch.work.init` | `src/cli/work.c` | EXISTING_NATIVE_OWNER_CLI_OR_SCOPED_FACADE; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | DISCLOSURE, AUDIT_WRITE, NATIVE_READ, NATIVE_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing per-operation native owner or D2/D4 authority; package inclusion never enables operations outside exposed policy scope. |
| `native.golem_harness_probe` | `include/golem/adapter_descriptor.h` | EXISTING_NATIVE_OWNER_CLI_OR_SCOPED_FACADE; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ, PROCESS, AUDIT_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing per-operation native owner or D2/D4 authority; package inclusion never enables operations outside exposed policy scope. |
| `native.golem_admission_open` | `include/golem/admission.h` | NATIVE_OWNER_HOST_API_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ, NATIVE_WRITE, AUDIT_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing native host ownership/resource/fence APIs; no generic scheduler, automatic host start or new MCP grant. |
| `native.golem_admission_open_diagnostic` | `include/golem/admission.h` | NATIVE_OWNER_HOST_API_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ, NATIVE_WRITE, AUDIT_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing native host ownership/resource/fence APIs; no generic scheduler, automatic host start or new MCP grant. |
| `native.golem_admission_close` | `include/golem/admission.h` | NATIVE_OWNER_HOST_API_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ, AUDIT_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing native host ownership/resource/fence APIs; no generic scheduler, automatic host start or new MCP grant. |
| `native.golem_admission_identity` | `include/golem/admission.h` | NATIVE_OWNER_HOST_API_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ, AUDIT_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing native host ownership/resource/fence APIs; no generic scheduler, automatic host start or new MCP grant. |
| `native.golem_admission_enqueue` | `include/golem/admission.h` | NATIVE_OWNER_HOST_API_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ, NATIVE_WRITE, AUDIT_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing native host ownership/resource/fence APIs; no generic scheduler, automatic host start or new MCP grant. |
| `native.golem_admission_lookup` | `include/golem/admission.h` | NATIVE_OWNER_HOST_API_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ, AUDIT_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing native host ownership/resource/fence APIs; no generic scheduler, automatic host start or new MCP grant. |
| `native.golem_admission_grant` | `include/golem/admission.h` | NATIVE_OWNER_HOST_API_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ, NATIVE_WRITE, AUDIT_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing native host ownership/resource/fence APIs; no generic scheduler, automatic host start or new MCP grant. |
| `native.golem_admission_resize` | `include/golem/admission.h` | NATIVE_OWNER_HOST_API_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ, NATIVE_WRITE, AUDIT_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing native host ownership/resource/fence APIs; no generic scheduler, automatic host start or new MCP grant. |
| `native.golem_admission_cancel` | `include/golem/admission.h` | NATIVE_OWNER_HOST_API_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ, NATIVE_WRITE, AUDIT_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing native host ownership/resource/fence APIs; no generic scheduler, automatic host start or new MCP grant. |
| `native.golem_admission_dispatch` | `include/golem/admission.h` | NATIVE_OWNER_HOST_API_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ, NATIVE_WRITE, AUDIT_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing native host ownership/resource/fence APIs; no generic scheduler, automatic host start or new MCP grant. |
| `native.golem_admission_begin` | `include/golem/admission.h` | NATIVE_OWNER_HOST_API_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ, NATIVE_WRITE, AUDIT_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing native host ownership/resource/fence APIs; no generic scheduler, automatic host start or new MCP grant. |
| `native.golem_admission_publish_work` | `include/golem/admission.h` | NATIVE_OWNER_HOST_API_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ, NATIVE_WRITE, AUDIT_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing native host ownership/resource/fence APIs; no generic scheduler, automatic host start or new MCP grant. |
| `native.golem_admission_settle` | `include/golem/admission.h` | NATIVE_OWNER_HOST_API_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ, NATIVE_WRITE, AUDIT_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing native host ownership/resource/fence APIs; no generic scheduler, automatic host start or new MCP grant. |
| `native.golem_admission_release` | `include/golem/admission.h` | NATIVE_OWNER_HOST_API_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ, NATIVE_WRITE, AUDIT_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing native host ownership/resource/fence APIs; no generic scheduler, automatic host start or new MCP grant. |
| `native.golem_daemon_recover` | `include/golem/daemon.h` | NATIVE_OWNER_HOST_API_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ, NATIVE_WRITE, AUDIT_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing native host ownership/resource/fence APIs; no generic scheduler, automatic host start or new MCP grant. |
| `native.golem_daemon_init` | `include/golem/daemon.h` | NATIVE_OWNER_HOST_API_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ, NATIVE_WRITE, AUDIT_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing native host ownership/resource/fence APIs; no generic scheduler, automatic host start or new MCP grant. |
| `native.golem_daemon_submit` | `include/golem/daemon.h` | NATIVE_OWNER_HOST_API_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ, NATIVE_WRITE, AUDIT_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing native host ownership/resource/fence APIs; no generic scheduler, automatic host start or new MCP grant. |
| `native.golem_daemon_inspect` | `include/golem/daemon.h` | NATIVE_OWNER_HOST_API_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ, AUDIT_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing native host ownership/resource/fence APIs; no generic scheduler, automatic host start or new MCP grant. |
| `native.golem_daemon_open` | `include/golem/daemon.h` | NATIVE_OWNER_HOST_API_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ, NATIVE_WRITE, AUDIT_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing native host ownership/resource/fence APIs; no generic scheduler, automatic host start or new MCP grant. |
| `native.golem_daemon_tick` | `include/golem/daemon.h` | NATIVE_OWNER_HOST_API_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ, NATIVE_WRITE, PROCESS, AUDIT_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing native host ownership/resource/fence APIs; no generic scheduler, automatic host start or new MCP grant. |
| `native.golem_daemon_close` | `include/golem/daemon.h` | NATIVE_OWNER_HOST_API_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ, AUDIT_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing native host ownership/resource/fence APIs; no generic scheduler, automatic host start or new MCP grant. |
| `native.golem_record_begin` | `include/golem/record.h` | NATIVE_OWNER_HOST_API_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ, AUDIT_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing native host ownership/resource/fence APIs; no generic scheduler, automatic host start or new MCP grant. |
| `native.golem_record_write` | `include/golem/record.h` | NATIVE_OWNER_HOST_API_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ, AUDIT_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing native host ownership/resource/fence APIs; no generic scheduler, automatic host start or new MCP grant. |
| `native.golem_record_finish` | `include/golem/record.h` | NATIVE_OWNER_HOST_API_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ, AUDIT_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing native host ownership/resource/fence APIs; no generic scheduler, automatic host start or new MCP grant. |
| `native.golem_record_call` | `include/golem/record.h` | NATIVE_OWNER_HOST_API_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ, AUDIT_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing native host ownership/resource/fence APIs; no generic scheduler, automatic host start or new MCP grant. |
| `native.golem_journal_recover` | `include/golem/replay.h` | NATIVE_OWNER_HOST_API_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ, NATIVE_WRITE, AUDIT_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing native host ownership/resource/fence APIs; no generic scheduler, automatic host start or new MCP grant. |
| `native.golem_resource_run` | `include/golem/resource.h` | NATIVE_OWNER_HOST_API_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ, NATIVE_WRITE, PROCESS, AUDIT_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing native host ownership/resource/fence APIs; no generic scheduler, automatic host start or new MCP grant. |
| `native.golem_supervisor_run` | `include/golem/supervisor.h` | NATIVE_OWNER_HOST_API_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ, NATIVE_WRITE, PROCESS | 기존 native/owner guard와 M6 static frozen row; Existing native host ownership/resource/fence APIs; no generic scheduler, automatic host start or new MCP grant. |
| `native.golem_supervisor_run_at` | `include/golem/supervisor.h` | NATIVE_OWNER_HOST_API_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ, NATIVE_WRITE, PROCESS | 기존 native/owner guard와 M6 static frozen row; Existing native host ownership/resource/fence APIs; no generic scheduler, automatic host start or new MCP grant. |
| `native.golem_supervisor_run_streamed` | `include/golem/supervisor.h` | NATIVE_OWNER_HOST_API_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ, NATIVE_WRITE, PROCESS | 기존 native/owner guard와 M6 static frozen row; Existing native host ownership/resource/fence APIs; no generic scheduler, automatic host start or new MCP grant. |
| `native.golem_supervisor_run_bulk` | `include/golem/supervisor.h` | NATIVE_OWNER_HOST_API_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ, NATIVE_WRITE, PROCESS | 기존 native/owner guard와 M6 static frozen row; Existing native host ownership/resource/fence APIs; no generic scheduler, automatic host start or new MCP grant. |
| `native.golem_supervisor_run_observed` | `include/golem/supervisor.h` | NATIVE_OWNER_HOST_API_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ, NATIVE_WRITE, PROCESS | 기존 native/owner guard와 M6 static frozen row; Existing native host ownership/resource/fence APIs; no generic scheduler, automatic host start or new MCP grant. |
| `native.golem_worker_options_default` | `include/golem/worker.h` | NATIVE_OWNER_HOST_API_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ | 기존 native/owner guard와 M6 static frozen row; Existing native host ownership/resource/fence APIs; no generic scheduler, automatic host start or new MCP grant. |
| `native.golem_worker_open` | `include/golem/worker.h` | NATIVE_OWNER_HOST_API_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ, AUDIT_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing native host ownership/resource/fence APIs; no generic scheduler, automatic host start or new MCP grant. |
| `native.golem_worker_submit` | `include/golem/worker.h` | NATIVE_OWNER_HOST_API_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ, NATIVE_WRITE, AUDIT_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing native host ownership/resource/fence APIs; no generic scheduler, automatic host start or new MCP grant. |
| `native.golem_worker_start` | `include/golem/worker.h` | NATIVE_OWNER_HOST_API_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ, NATIVE_WRITE, PROCESS, AUDIT_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing native host ownership/resource/fence APIs; no generic scheduler, automatic host start or new MCP grant. |
| `native.golem_worker_inspect` | `include/golem/worker.h` | NATIVE_OWNER_HOST_API_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ, AUDIT_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing native host ownership/resource/fence APIs; no generic scheduler, automatic host start or new MCP grant. |
| `native.golem_worker_diagnostics` | `include/golem/worker.h` | NATIVE_OWNER_HOST_API_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ | 기존 native/owner guard와 M6 static frozen row; Existing native host ownership/resource/fence APIs; no generic scheduler, automatic host start or new MCP grant. |
| `native.golem_worker_recording_status` | `include/golem/worker.h` | NATIVE_OWNER_HOST_API_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ | 기존 native/owner guard와 M6 static frozen row; Existing native host ownership/resource/fence APIs; no generic scheduler, automatic host start or new MCP grant. |
| `native.golem_worker_cancel` | `include/golem/worker.h` | NATIVE_OWNER_HOST_API_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ, NATIVE_WRITE, AUDIT_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing native host ownership/resource/fence APIs; no generic scheduler, automatic host start or new MCP grant. |
| `native.golem_worker_heartbeat` | `include/golem/worker.h` | NATIVE_OWNER_HOST_API_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ, NATIVE_WRITE, AUDIT_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing native host ownership/resource/fence APIs; no generic scheduler, automatic host start or new MCP grant. |
| `native.golem_worker_acknowledge` | `include/golem/worker.h` | NATIVE_OWNER_HOST_API_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ, NATIVE_WRITE, AUDIT_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing native host ownership/resource/fence APIs; no generic scheduler, automatic host start or new MCP grant. |
| `native.golem_worker_close` | `include/golem/worker.h` | NATIVE_OWNER_HOST_API_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ, AUDIT_WRITE | 기존 native/owner guard와 M6 static frozen row; Existing native host ownership/resource/fence APIs; no generic scheduler, automatic host start or new MCP grant. |
| `operation.policy.ap_request.approve` | `src/policy/approval_model.c` | NATIVE_OWNER_APPROVAL_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ, NATIVE_WRITE | 기존 native/owner guard와 M6 static frozen row; Exact native owner decision; never model/skill/profile approval; actual application NOT_RUN. |
| `operation.policy.ap_request.deny` | `src/policy/approval_model.c` | NATIVE_OWNER_APPROVAL_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ, NATIVE_WRITE | 기존 native/owner guard와 M6 static frozen row; Exact native owner decision; never model/skill/profile approval; actual application NOT_RUN. |
| `operation.policy.ap_request.expire` | `src/policy/approval_model.c` | NATIVE_OWNER_APPROVAL_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ, NATIVE_WRITE | 기존 native/owner guard와 M6 static frozen row; Exact native owner decision; never model/skill/profile approval; actual application NOT_RUN. |
| `operation.policy.ap_request.recover` | `src/policy/approval_model.c` | NATIVE_OWNER_APPROVAL_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ, NATIVE_WRITE | 기존 native/owner guard와 M6 static frozen row; Exact native owner decision; never model/skill/profile approval; actual application NOT_RUN. |
| `operation.policy.ap_request.revoke` | `src/policy/approval_model.c` | NATIVE_OWNER_APPROVAL_ONLY; M6가 완전한 owner 관리 권한을 새로 노출하지 않음; 기존 제한적 M1~M5 facade는 원래 원장 기준으로 유지 | NATIVE_READ, NATIVE_WRITE | 기존 native/owner guard와 M6 static frozen row; Exact native owner decision; never model/skill/profile approval; actual application NOT_RUN. |


## 검증·skip·미구현

M6 제품 fixture21개와 M6 adversarial static8개를 포함해 검증한다. 실제 임시 설정의 install/remove 원복, freeze/fence/inspect와 ACK만으로 ready 거부, 원래 plan SHA·partial 상태 보존, profile 교집합·직접 호출 차단·별도 helper/host opt-in, 5종 deterministic package·전체 파일/schema/asset/스킬·별도 cwd import closure·변조/추가파일/traversal/symlink/duplicate/용량/서명 보증 위조 차단을 검사했다.

전체 회귀와 원장 결과는 아래 최종 검증 기록을 따른다. 실제 MCP SDK가 없는 선택적 gateway/SDK icon/stdio 검사는 skip이다. skill-creator quick_validate.py는 현재 Python과 bundled Python 모두 PyYAML이 없어 실행에 실패했으며 두 스킬에 대해 **SKIP(검증기 의존성 부재)**로 기록한다. 스킬의 고정 bytes·frontmatter/name·역할 분리·문서/manifest 연결·업무 안내의 승인/불확실성 경계는 별도 M6 정적 검사와 패키지 fixture로 대조한다. 검증기를 통과했다고 표시하지 않는다. 의존성을 전역 설치하거나 network로 가져오지 않았다.

M5의 7개 미구현, P7 self-contained runtime/의존성·서명/신뢰 root·host/OS qualification·자동 업데이트/유통 의무가 남는다. 실제 host/client/Work E2E·외부 API·승인/등록/정책 적용·실제 설치/재로딩·migration·CI·Linux/Windows 운영·merge·commit/push는 NOT_RUN이다.


## 최종 검증 기록 (2026-10-26)

- M6 fixture21개, M6 static adversarial8개 통과. 전체 integration355개 중337 통과/18 skip, capability 회귀363개 통과. historical Python package가 native `golem` 실행 이름을 침범하지 않는 package entrypoint 검사1개와 기존 native 단위39개도 통과했다. Native·기존 launcher/설치/승인 구현을 수정해 검사를 우회하지 않았다.
- integration skip18개는 선택적 gateway16·SDK icon1·실제 stdio MCPB1이다. 별도 skill-creator quick_validate는 PyYAML 부재로 두 스킬 모두 SKIP이며 이를 성공으로 집계하지 않는다. 실제 client/Work E2E·외부 서비스·설치/재로딩은 NOT_RUN이다.
- source/근거552개, 관측2282개, capability1187개, whole-file surface444개. M0~M6 selected/repository blocker0이며 M6 mandatory profile은 5개 기능 profile·고정 owner83개·source function27개를 대조한다. 기존 M1~M5 고정 ID·guards·M5 미구현7개·unsupported17개를 보존한다. owner backlog83개도 유지한다.
- 원본 HEAD `e583b17469c50edd1e18df90880df07940c77b69`와 기존 `assets/Golem-codex-plugin.png` 변경 목록, 개발 HEAD `2e690091a55f366d5f99580ee375fca7610f2f77`, 빈 staging을 확인했다. 기존 선택542개 source 중 M6에서 명시한 기존 runtime/스킬/manifest4개와 문서·검사 모델/fixture 밖 예상하지 않은 변경은 없다. 실제 private Work 전체 bytes를 검사했다는 뜻은 아니다. 실제 연결/설정/launcher/승인/registry/Work/evidence/CAS/journal/후보 디렉터리를 적용·삭제·정리하지 않았다.
- 8개 고정 원장 산출물은 저장 bytes와 재계산 결과를 대조한다. 검토용 feature artifact는 새 개발 build 디렉터리에만 생성하며 설치·등록·재로딩·실행 승인을 뜻하지 않는다. 임시 fixture만 정리한다. commit/push는 수행하지 않았다.

## Owner 검토 앱: MCP와 분리된 선택적 표시 계층

MCP 서버 시작은 화면을 열지 않는다. `integration_owner_desktop.py`의 기존 launcher 인자는
호환되지만 이제 headless로 동작한다. 검토 앱은 사용자가 별도로 실행한다. 기존 설치의
launcher·producer·정책 pin을 이 문서나 새 소스를 근거로 자동 변경하지 않는다.

```text
Codex/Claude의 각 MCP 연결 → 각 서비스의 독립적인 준비안·정책 검사
                                      ↕ 선택적으로 지정한 private Unix IPC
사용자가 Owner 앱 열기 → 연결 선택 → 초안 조회 → 확인 → 미적용 후보 저장
```

owner가 고른 기존 0700 디렉터리만 `--review-directory /absolute/private/path`로 지정한다.
서버의 `--review-label Codex` 또는 `Claude`는 표시용이며 인증된 client 신원이 아니다.
Unix socket 경로 제한 때문에 짧은 경로가 필요하다. 경로가 잘못되면 검토 기능만 비활성화하고
MCP는 유지하며, 자동 디렉터리 생성·권한 수정·다른 위치 탐색·재시도는 하지 않는다.
기본값에서는 IPC endpoint도 만들지 않는다.

Owner 앱은 같은 검토된 Python/runtime에서 다음과 같이 명시적으로 연다.

```text
python tools/integration_owner_desktop.py owner-app --review-directory /absolute/private/path
```

앱을 반복 실행하면 OS 파일 잠금으로 기존 앱을 선택하고 활성화만 요청한다. PID를 저장해
프로세스를 채택하거나 강제 종료하지 않는다. 같은 연결의 검토 창도 중복 생성하지 않는다.
창 닫기는 표시 계층만 종료한다. 후보 저장 중 닫은 창은 숨기고 진행 중 결과를 기다리며
MCP 연결과 다른 창의 검토 상태는 종료하지 않는다.

연결 선택은 label·profile·무작위 instance ID로 구분한다. 준비안에는 기존 service instance,
plan ID/SHA, project/Work, policy, 30분 TTL 및 native 관측 기반의 최신성 검사가 그대로 적용된다.
재연결은 새 서비스이므로 과거 준비안을 되살리지 않는다. 단절된 연결 파일은 자동 복구하거나
새 연결에 붙이지 않는다. 기존 스풀을 전역 검색해 목록을 합치지 않는다.

IPC는 catalog/inspect/export만 제공하고 activation endpoint는 activate만 받는다. TCP·HTTP·
임의 명령·일반 파일 읽기·승인 발급·정책 적용·native 실행은 제공하지 않는다. 기존 owner가
선택하는 첨부/출력 경로는 원래 Controller/export_candidate 검사에 다시 전달된다.
0700 디렉터리, 0600 descriptor, 무작위 capability, 정확한 instance 및 요청 ID, 크기·시간·요청
수 상한을 검사한다. 같은 OS 사용자로 실행되는 악성 코드를 격리하거나 인간을 인증하는
경계는 아니다. UI의 확인은 후보 작성 의사이며 native 승인 증명이 아니다.

후보 저장은 동일 준비안에 대해 서비스당 최대 한 번 시도한다. 다른 Owner 앱의 재접속이나
명시적 재조회도 이 저장 fence를 초기화하지 않는다. 응답 유실은 OWNER_EXPORT_UNKNOWN이며
자동 재시도하지 않는다. 부분 파일·원래 정책·native 승인은 그대로 남긴다. 이는 exactly-once
완료 보증이 아니며, 새 연결에서 옛 준비안을 복원하는 기능도 아니다.

resource/helper/host/management 계약을 이 launcher가 자동 이월하지 않는 기존 한계는 유지된다.
GUI는 Tk가 가능한 owner 환경에서만 필요하다. headless MCP의 Tk 의존성은 제거했다.
POSIX Unix socket/flock 구현이며 Windows 지원·서명된 독립 실행 배포는 제공하지 않는다.

### 설계 근거와 검증 연결 (2026-11-01)

문헌의 원칙을 아래처럼 적용했다. 자료 전체를 검증 완료 증명으로 사용하지 않으며, 고전 RPC의
재전송 알고리즘을 그대로 도입하지 않는다. Golem의 불확실 결과 보존·무재실행 계약이 우선한다.

| 자료 | 분석과 적용 | 확인할 실패 조건 |
| --- | --- | --- |
| Saltzer·Schroeder, *The Protection of Information in Computer Systems* (1975), [원문](https://www.cs.virginia.edu/~evans/cs551/saltzer/) | 최소 권한·매 접근 검사·공유 메커니즘 최소화: UI만 공유하고 서비스별 정책/준비안은 합치지 않는다. 토큰 보유를 native 승인으로 해석하지 않는다. | 잘못된 token/instance, 교차 Work, 정책 drift, 범위 밖 operation 거부 |
| Saltzer·Reed·Clark, *End-to-End Arguments in System Design* (1984), [논문](https://www.cs.princeton.edu/~jrex/teaching/spring2005/reading/saltzer84.pdf) | 통신 성공은 후보 파일의 완전한 저장이나 실행 성공을 의미하지 않는다. 최종 native·정책 검사를 원래 서비스에 남긴다. | 전달 성공과 후보/승인/완료를 구분, 응답 유실 보존 |
| Birrell·Nelson, *Implementing Remote Procedure Calls* (1984), [논문](https://www.cs.cmu.edu/~15712/papers/birrell84.pdf) | 호출의 위치/신원 결합과 통신 실패의 의미를 분리한다. request ID로 중복 수신을 막고, 서비스 instance가 바뀌면 기존 참조를 거부한다. | 중복 request와 재접속 후 중복 export 거부 |
| Saltzer·Kaashoek, *Principles of Computer System Design*, 8장 (2009), [공개 교재](https://ocw.mit.edu/courses/res-6-004-principles-of-computer-system-design-an-introduction-spring-2009/6b31587ec59b1b002cb7a710d9781453_faults_open_5_0.pdf) | 오류의 전파 범위를 모듈 경계로 제한한다. Tk/Owner 앱 장애가 MCP 통신을 중단시키지 않도록 프로세스와 상태를 분리한다. | Tk import 불가·UI 종료·중복 앱 활성화 시 MCP 유지 |
| Kleppmann, Cambridge *Distributed Systems* 강의노트 (2024/25), [자료](https://www.cl.cam.ac.uk/teaching/2425/ConcDisSys/dist-sys-notes.pdf) | 응답 부재는 미실행 증거가 아니다. 무조건 재전송하지 않고 export fence와 UNKNOWN 상태를 사용한다. | 저장 후 응답 유실, 부분 publication, 재검토 뒤 재저장 거부 |
| Fowler, *Presentation Model* (2004), [저자 자료](https://martinfowler.com/eaaDev/PresentationModel.html) | 표시와 검토 제어를 분리해 GUI 없이 수명주기·권한 검사를 시험한다. 이 자료는 저자의 패턴 초안이며 동료 심사 논문으로 표시하지 않는다. | headless 회귀 + 실제 Tk 검사 분리 |

수명주기 fixture는 다중 headless 연결에서 Tk import 금지, 실제 SDK initialize/tools/list와 M2,
별도 Unix 검토 조회, UI 종료 후 서버 유지, 단일 Owner 앱 activation, 만료/변조/교차 scope,
부분 파일·응답 유실·중복 저장을 검사한다. 실제 Codex/Claude 재설치·모델 대화 E2E·TopSolar
작업 실행과는 구분한다. 이전 단일 창 검증이나 CI 성공을 다중 연결 사용성 증거로 재사용하지 않는다.
