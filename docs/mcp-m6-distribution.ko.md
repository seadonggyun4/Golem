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

## Owner 검토 창과 후보 생성 (선택적·미설치)

`tools/integration_owner_review.py:export_candidate`는 owner host에 연결할 로컬 API다.
MCP tool은 아니다. `tools/integration_owner_desktop.py`의 네이티브 검토 창과 stdio launcher가
같은 service의 살아 있는 M2 instance를 공유한다. 기존 설치본에는 적용하지 않았다.
API는 owner가 선택한 D2 준비 정책 또는 기존 D4 Policy,
plan ID/SHA, 새 action ID, private 출력 디렉터리를 받는다. 별도 프로세스에서 저장된
plan을 불러와 instance 제한을 우회하는 CLI는 제공하지 않는다.

1. M2 `action_prepare`의 초안을 미승인 입력으로 취급한다.
2. 기존 service/registry lock, M2 load·observe·basis 비교, D4 shape·producer·attachment
   검사로 현재 선택을 확인한다. native 승인 attachment는 owner가 별도로 선택해야 한다.
3. 기존 action JSON 내부 문자열을 보존하여 `action.json`, `policy-candidate.json`,
   `review.json`을 새 디렉터리에만 기록한다. 기존 정책과 승인 bytes는 수정하지 않는다.
4. 검토 완료는 정책 활성화나 native admission이 아니다. 연결에 후보 hash를 선택하는
   별도 owner 절차와 실행 시점의 native 검사가 여전히 필요하다.

현재 helper/candidate/workspace의 별도 효과 검토는 이 API에서 지원하지 않고 차단한다.
stale, 취소된 정책, 중복 action, instance 유실, 기존 출력 경로는 거부한다. 부분 IO 실패는
보존하며 재시도·덮어쓰기·repair하지 않는다. live source scan과 native 실행은 NOT_RUN이다.
동일 OS 사용자에게서 agent와 owner를 강하게 격리하는 인증 경계를 새로 제공하지 않는다.

fixture: `tools/test_integration_owner_review.py`. 현재 6개 테스트에서 후보 생성, 기존
Work/정책 보존, 동의·stale·instance 유실·취소·중복 차단 및 부분 실패 보존을 확인했다.
실제 Desktop owner UI/E2E 성공 근거로 사용하지 않는다.


### 검토 창 사용 흐름

Tk를 지원하는 Python과 `tools/requirements-mcp.txt`의 고정 SDK가 필요하다. `import tkinter`만
성공하는지에 더해 실제 GUI 세션이 있어야 한다. 기본 패키지 launcher는 그대로이며 UI 파일은
검토된 package inventory에 포함된다. 두 client 모두 **기존 연결의 owner-reviewed launcher를
아래 경로로 명시 교체할 때만** 활성화한다. 두 번째 Golem 연결을 추가하지 않는다.

```text
<검토한 Python> tools/integration_owner_desktop.py
  --profile prepare
  --policy <owner 검토 D2 준비 파일>
  --reviewed-policy-sha256 <그 파일의 검토 SHA-256>
  --approve-owner --approve-owner-review-ui
```

- agent가 같은 연결에서 `action_prepare`를 호출하면 **준비안 목록 새로고침**으로 현재 연결의
  유효한 준비안을 선택한다. project/Work/plan ID/SHA가 채워지면 새 action ID를 지정하고
  **현재 초안 조회**를 누른다. 목록 선택 자체는 승인이나 현재 native 상태 검증이 아니다.
  만료·다른 instance의 준비안은 재사용하지 않으며 준비 호출을 자동 반복하지 않는다.
- 실행 요청이라면 **이미 승인된 native 첨부** JSON을 별도로 선택한다. UI가 새 승인을 발급하지
  않는다. 원문과 첨부 SHA를 확인하고 확인란·최종 대화상자를 거쳐 후보 파일을 만든다.
- 출력 부모는 Work·registry 밖의 owner-private 디렉터리다. 파일은 새 하위 디렉터리에만 생성한다.
  생성된 policy-candidate SHA를 실제 연결에 채택하는 일은 여전히 별도 owner 결정이다.
- 입력 변경은 검토 확인을 취소한다. 처리 중 버튼/입력은 잠기며 성공·실패 후 같은 선택을 자동
  재실행하지 않는다. 재검토는 명시적인 새 읽기이고 부분 실패 자료는 삭제하지 않는다.
- 창 닫기로 진행 중 MCP 작업을 종료하지 않는다. 최소화하거나 client에서 연결을 정상 종료한다.
  stdio EOF 후 진행 중 검토가 끝나면 창도 닫힌다. 네트워크 listener나 브라우저 서버는 없다.

D2 prepare에서는 첫 action 후보만 생성하고, 기존 D4 task/quality/parallel에서는 기존 정책에
후보를 추가한다. 빈 D4 정책은 여전히 거부되며 D2 연결에 실행 도구를 추가하지 않는다.
이 launcher는 resource/helper/host/management 설정을
자동 이월하지 않는다. 해당 선택적 계약이 필요한 연결은 이 최초 UI launcher의 지원 범위 밖이다.
기존 prepare-only D2 연결을 임의로 D4로 바꾸지 않는다. 동일 OS 사용자에 대한 강한 인증·격리는
제공하지 않는다. 설치별 launcher/artifact pin과 native admission은 그대로 필요하다.

검증: disposable controller, 실제 Tk 창, 실제 SDK stdio→M2→동일 창→후보 생성·정상 EOF fixture.
이 fixture 결과를 실제 client의 UI 후보 저장이나 native 실행 성공으로 승격하지 않는다.
macOS에서 raw Python 창을 앱으로 식별하지 못하면 검토된 앱 bundle 실행부가 필요하다.
현재 앱 bundle은 별도 설치 검토 후보이며 기본 launcher에 자동 적용되지 않는다. 실제 설치·
GUI 저장·원래 연결 복원 상태는 workspace 설치 원장과 연결된 검증 기록에서 확인한다.
