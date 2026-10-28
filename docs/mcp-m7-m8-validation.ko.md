# M7/M8 실제 설치·검증 기록 — 2026-10-26~28

## 2026-10-28 Codex 초기 연결 개선 검증

공통 MCP 목록 조회에 기존 읽기 서버의 제한된 REGISTRY_BUSY 대기를 연결했다. 실제 action 재시도·승인 완화·시간 한도 증가는 없다. 관련 회귀90개 중88개 통과·2개 skip 및 전체 소스 정적 검사를 통과했다. 새 producer를 명시 선택한 동일 Codex0.2.7에서 공식 app-server 연결·9개 도구 노출1.89초, projects_list1회 AVAILABLE까지2.46초를 확인했다. 모델 turn·QA·완료 실행은0회이며 원본 승인·Work·증거와 Claude를 보존했다.

과거30초 초기 연결 지연의 근본 원인은 재현되지 않아 미확정이다. 이 결과는 현재 설치본의 연결·한정 조회 성공이며 모든 환경의 시간 초과 해소나 전체 Core E2E 완료를 의미하지 않는다. 첫 후보의 producer 거부 및 복원 기록도 보존한다. 상세 로컬 workspace `timeout-investigation-20261028/validation.json`.


## 2026-10-28 최신 Codex 실사용·추가 기능 검증

Codex 공식 app-server에서 격리 프로젝트의 개발·공개/독립 테스트·문서 제출·native QA 1회·완료 확정·현재 완료 조회까지 통과했다. 이 결과는 해당 고정 입력의 한 사이클이며 Desktop GUI나 모든 Core 기능의 통과를 뜻하지 않는다. Claude는 추가 평가를 보류하고 기존 기록을 보존했다.

추가 R3 검증은 조회·비권한 준비 13개 정상 응답과 같은 Work 병합 준비의 `MERGE_WORK_ISOLATION` 예상 거부 1개를 확인했다. R4 계약 준비는 11종이 통과했고 template/completion/plan 조회 3개는 아직 NOT_RUN이다. 기존 대화의 과거 호출 상한이 남았으며, 별도 승인한 새 대화에서는 MCP 초기 연결이 30초 시간 초과돼 실제 호출이 0회였다. 원인은 미확정이고 성공으로 집계하지 않는다.

현재 원장 기준 85개 도구 중 일부 정확한 정상 호출 확인 25개, 거부 조건만 확인 1개, 과거 근거만 16개, NOT_RUN 43개다. 미검증 selector 109개와 scheduler·merge 관련 미구현 설계 7개를 별도 관리한다. 과거 QA·완료·COMMIT_UNKNOWN은 재실행하지 않았다. Codex 설치 0.2.7의 프로그램은 현재 수정 소스와 일치하지만, 정책은 검토된 조회·준비 범위로 제한돼 있다.

상세 근거는 로컬 workspace의 `codex-core-qualification-20261028/validation.json`, `진행결과.md`, `미검증기능.md`와 private 호출 trace에 보존한다. 로컬 승인·Work·증거·계정 설정은 저장소에 포함하지 않는다. 아래 기록은 각 검증 당시의 결과다.

## 2026-10-28 Claude 단일 session_start 실제 검증 PASS

Claude task 0.1.10 한 개를 활성화하고, owner가 고정한 격리 Work/action/request로 session_start를 정확히 1회 호출했다. native committed=true, session sequence 0→1, document generation 3을 확인했으며 후속 status·next 각 1회는 CLAIM_REQUIRED를 반환했다. Work 완료·QA PASS를 뜻하지 않는다(acceptance_verified=false). claim·QA·승인 발급·서비스·복구·COMMIT_UNKNOWN 재실행은 0회다. 원본 보호 2,215파일에 예상 밖 변경이 없고, 합성 Work에는 승인된 start event/CAS 3파일만 추가됐다. Codex 모델은 계정 한도로 NOT_RUN이다. 상세 workspace `core-mcp-verification-20261028/다음기능검증.md`, `private/phase-C/validation.json`. commit/push 없음. 아래 부분 설치·차단 기록은 당시 상태다.


## 2026-10-28 Claude task 설치 완료·정책 설정 차단

사용자의 직접 설치 승인으로 task 0.1.10 한 개를 공식 설치했고 archive SHA 및 83파일 bytes 일치를 확인했다. 현재 비활성이다. 한정 D4 정책 입력은 자동 승인 검토가 별도 설정 변경 승인을 인정하지 않아 차단했다. 현재 활성 Claude 연결은 0개, session_start는 NOT_RUN이다. 보호 파일 2,215개와 두 격리 Work bytes를 재확인했다. 직접 설정 파일 수정이나 다른 경로로 우회하지 않았다. 상세 workspace `core-mcp-verification-20261028/다음기능검증.md`, `private/phase-C/current-result.json`. 아래 설치 차단/0개 기록은 직접 승인 이전 당시 상태다.


## 2026-10-28 Claude 세션 시작 검증 — 설치 차단

Claude 현재 상태를 실제 두 조회로 재확인했다(session sequence 0/document generation 3/START_REQUIRED). 새 격리 Work의 session_start 한 건을 사용자가 승인했고 D4 후보의 현재 권한·pin 검사를 통과했다. 다만 task 설치 클릭이 자동 승인 검토에서 차단되어 미실행이다. prepare는 복구 package/settings 보존 후 공식 제거했으며 현재 Claude Golem 설치는 0개인 부분 전환 상태다. 설치 확인을 우회하지 않았다. Codex 모델 검증은 계정 한도로 NOT_RUN이며 재시도하지 않는다. 현재 설치와 두 Work bytes 보존을 확인했다. 자세한 대상·action·key·정책 SHA는 workspace `core-mcp-verification-20261028/다음기능검증.md`, `private/phase-C/review.json`을 따른다. 전체 Core 검증 완료가 아니다.


## 2026-10-28 M2 prepare 단계 추가

같은 격리 Work에 비권한 준비 6도구만 추가한 owner 계획을 적용했다. 현재 설치는 Codex 동일 ID 0.2.7 prepare·Claude prepare 0.1.10 각 한 개다. Claude 실제 9회(준비 4/plan 재조회 4/의도한 merge 격리 거부 1), Codex SDK 9회를 대조했다. Codex 실제 M2 모델 검증은 계정 사용 한도로 NOT_RUN이며 SDK로 대체 인증하지 않았다. Work bytes 동일, 실행·QA·승인 발급·서비스·merge 0회. 병렬 scheduler/merge는 NOT_IMPLEMENTED로 유지한다. workspace `core-mcp-verification-20261028/M2준비검증.md`, `private/phase-B/validation.json`에 기록했다. 아래 read 설치 표는 이전 profile의 당시 결과다. commit/push 없음.

## 2026-10-28 새 격리 Work 읽기 검증 — 현재 진행 범위

현재 두 read 설치본은 사용자 승인으로 새 합성 Work `core-codex-20261028`/`core-claude-20261028`에 연결했다. 정책 28도구 중 resource 미선택 2개는 숨겨 실제 노출은 26개다. Codex 실제 CLI 28회는 AVAILABLE 22/BLOCKED 6이며 마지막 도구 이후 계정 한도로 모델 요약이 실패했다. Claude Desktop 27회는 관측 17/거부 10, template list 한 건은 client timeout·서버 미전송으로 재호출하지 않았다. 복잡한 JSON 인자 오류·discovery 실패는 미통과로 유지한다. 전체 Core 기능·모든 profile E2E 완료가 아니다.

정적 원장 1,210 capability 중 C/Core 연결 936항목을 재대조했고 blocker 0이다. 내부 API/parent dispatcher를 독립 MCP operation으로 세지 않았다. 선택 fixture 324개는 최초 skip 8개를 native component 후속 검사로 보완해 모두 통과했다. 기존 실행·QA·승인·서비스·COMMIT_UNKNOWN 재실행은 0회, 새 Work bytes도 동일하다. 원본 정책은 보존하고 새 D1 읽기 등록/D2 전달만 별도 승인했다. 상세 workspace `core-mcp-verification-20261028/검증결과.md`, `validation.json`, `private/`를 따른다. 아래 2026-10-27 설치·읽기 결과는 당시 scope의 역사적 증거다. commit/push하지 않았다.

## 현재 설치·읽기 검증 — 2026-10-27 최신 수정본

**Codex 0.2.7 / Claude read 0.1.10을 설치하고, 각각 승인된 세 조회를 실제 client에서 확인했다. 전체 기능·모든 profile의 M7/M8 완료를 뜻하지 않는다.** 원본 승인을 보존하기 위해 owner가 정확한 검토 원장 `dc9fd119a15f5d4049b81261a0e8a7baae57477c7d008e205b7a7352f5979e02`의 별도 읽기 registry·D2 정책을 선택했다. 기존 native/D4 실행 승인과 관리/resource/helper/host 권한은 자동 이전하지 않았다.

| Client | 현재 한 개의 설치 | 실제 확인 범위 |
| --- | --- | --- |
| Codex | `golem@golem-m7-finish-complete` 0.2.7, 동일 server identity | 설치 bytes 9개·SDK handshake/list·bundled Codex CLI 실제 plugin 세 조회 PASS. 새 bytes의 Desktop GUI 자동 노출은 NOT_RUN |
| Claude Desktop | `local.mcpb.golem-contributors.golem-read` 0.1.10 | 설치 원본 83개·활성 커넥터·실제 UI의 세 조회 각 1회 PASS. 기존 task 0.1.8은 백업 후 공식 Remove |

각 client는 해당 기존 테스트 Work의 projects_list → work_inspect(status) → completion_check(selection)만 조회했다. native 현재 완료는 양쪽 모두 DONE/acceptance_verified=true/generation=9/completion_sequence=1, qa-result CURRENT/PASS다. agent session sequence=0·START_REQUIRED는 별도 계약이고 runtime 권한을 부여하지 않는다. 원래 QA를 실행한 것이 아니며 새 실행·복구·승인 발급·서비스 시작·COMMIT_UNKNOWN 재실행은 0회다. Claude 도구 권한은 각 1회 허용으로 처리했다.

Codex completion observation SHA는 `18cdfe11f7b0cbc363e3f1e12cefdb7e3204838f8f1ef390842c4f4488b75563`, Claude는 `e9ab1a4dcf753f3652d18cb708172c2fef2ae8a587db80345c888a0b1da7bd0f`다. Claude chat은 `Golem read 연결 검증` (`6e14c3d5-b523-4175-9edf-afc444cf6a63`)이며 실제 도구 Request/UI·서버 tools/call id 2/3/4와 새 native delivery 파일을 대조했다. 서버 로그의 RPC body는 redacted이므로 agent 진술을 raw 결과로 재구성하지 않았다.

Codex SDK의 첫 읽기는 terminal sandbox의 boot identity 조회 제한으로 거부됐으며 실제 client OS 환경에서 원래 한도로 통과했다. 첫 CLI 검사는 command-local config key 문법 오류로 도구 호출 전 중단됐고 이를 수정했다. 전역 승인 검사는 변경하지 않았다. 실제 client 증거의 부정 사례 회귀도 수행했다. 전체 코드 회귀 1471 PASS는 설치 전 고정된 동일 프로그램 bytes의 개발 검증이며 실제 client 조회 증거와 구분한다.

현재 읽기 3도구 제한은 owner가 선택한 연결 범위다. 구현된 관리 5도구/18 operation과 제품 전체 기능의 한도는 아니다. 관리 실행·추가 profile·OS·전체 scheduler/merge 등 기존 미구현/미검증 자격은 그대로다. 상세 적용 원장·proof·백업은 workspace `plugin-update-common-20261027/validation.json`, `업데이트결과.md`, `private/`, `backups/`에 있다. commit/push하지 않았다. 아래 기록은 해당 snapshot의 당시 결과다.

---

## 업데이트 전 구현 snapshot: 남은 Core 전달 누락 3개 연결

adapter stdin/binary convert, 일반 executable probe, candidate serve를 선택적 공통 MCP에 연결했다. native 명령 17개와 명시적 host stop 제어(관리 operation 총 18개), 관리 도구 5개다. 기존 native codec·probe·host config 검사를 그대로 사용하며 D4/M5 host 등록·resource·action 계약을 재사용한다. 원본 Core C 구현은 변경하지 않았다.

host는 연결이 소유한 process group으로 시작·조회·별도 승인 중지를 제공한다. 시간 제한 없는 service lifetime과 개별 native action 승인은 구분한다. output은 한정하고 정상 연결 종료 시 정리하지만 crash 후 PID 채택/재시작은 하지 않는다. readiness·모든 worker 종료·완료는 추론하지 않는다. socket 관측을 기존 M5 승인에 자동 반영하지 않는다.

격리 codec/stdio/프로세스·socket fixture와 정적·회귀 검증 대상으로 연결했다. 실제 candidate 서비스 시작, 실제 recovery/승인 발급, 새 후보 Desktop 설치·활성화/E2E는 NOT_RUN이며 이전 client PASS를 새 bytes 결과로 재사용하지 않는다. 후보 Codex 0.2.7/Claude 0.1.10과 실제 설치 Codex 0.2.5/Claude 0.1.8을 구분한다. 상세 결과는 workspace `mcp-delivery-three-20261027/구현결과.md`와 `validation.json`에 기록한다.

아래의 ‘남은 3개’는 직전 snapshot에서의 당시 상태다. 이 세 dispatcher의 구현 완료가 하위 C API 전체 E2E나 미구현 scheduler/merge 완료를 뜻하지 않는다.


## 2026-10-27 공통 프로젝트 관리 MCP 구현

사용자의 자연어 요청을 agent가 구조화된 관리 도구 호출로 변환하도록 구현했다.
`management_catalog` → `management_prepare` → 이미 검토된 action의 `management_request`
→ 원래 ID의 `management_result` 흐름이다. 사용자 프롬프트에 별도 JSON 형식은 필요하지 않다.

- 구현: 기존 D2/D4 서비스 위의 선택적 관리 정책, 관리 도구 4개, 한정 native operation 14개.
  daemon 상태/생성/제출/--once/--drain/복구, journal 검사/복구 검증/새 경로 salvage, adapter
  조회·고정 noop probe, admission 진단, 승인 contract 조회·원본 결정 요청 전달이다. Python은 native
  parser/reducer/승인/완료 predicate를 재구현하지 않는다.
- 보존: 관리 registry는 기존 승인 registry와 분리하고 base project 등록·disclosure·native
  pin에 결합한다. 기존 registry shared lock과 D5 fence를 유지한다. action 효과 전 durable
  예약, project의 pending/unknown 관리 효과 격리, target/입력/producer 변조 거부, 출력/저장
  한도, 별도 historical result 경로를 적용한다. 새 request ID로 중복 실행하지 않는다.
- 제공 구분: 테스트 정책(Codex read3/Claude task13)은 기존 구현의 기능 한도가 아니다.
  기존 owner83은 독립 누락 기능 83개가 아니며 parent route·이미 있는 facade·하위 C host
  API·operator 기능이 섞여 있다. 새 대조 원장은 이들을 항목별 source 근거로 구분한다.
- 실제 남은 전달 누락: adapter stdin/binary convert, 일반 executable adapter probe,
  unbounded candidate host serve는 새 관리 dispatcher가 제공하지 않는다.
  fixed noop probe를 일반 host 실행으로, validate를 describe로, 한정 daemon을 scheduler로
  재분류하지 않았다. 수명이 있는 C handle/callback API도 개별 raw-pointer MCP 도구로
  노출하지 않는다. P4/P5 scheduler/merge와 P7 release 의무는 그대로다.
- 배포 구분: 새 후보는 Codex 0.2.6/Claude MCPB 0.1.9, profile 5종·schema 6종·파일 83개다.
  관리 consent는 기본 false이며 기존 live 설정·정책·승인/producer pin은 그대로다.
  같은 public payload를 추출해 두 launcher 형식의 실제 SDK stdio 호출을 검증했다.
  새 후보의 실제 Desktop 설치/E2E와 정책 적용·서비스 시작·복구·승인 발급은 NOT_RUN이다.

정적 원장은 기존 552개 source를 유지하고 관리 도구/route 관찰 18개를 추가했다.
이는 Core 구현을 새로 18개 만들었다는 뜻이 아니며 기존 owner83·historical unsupported17의
ID나 권위 경계를 지우지 않았다. 상세 source/operation 대조·패키지 SHA·회귀/보존 근거는
owner-private workspace `mcp-project-management-20261027`의 원장을 따른다.

기존 실제 Desktop 세 읽기 PASS는 아래 당시 bytes/정책의 근거로 유지한다. 새 후보의
관리 권한이나 전 기능 실제 검증으로 확대하지 않는다. commit/push는 수행하지 않았다.

---

## 2026-10-27 잔여 28개 완료 조건 — 현재 판정

**기존 승인으로 끝낼 수 있는 독립 검사와 항목별 조건 정리를 완료했다. 추가로 완결한 전체 검증 의무는 0개이며, 미검증 9·미구현 10·범위 밖 9를 유지한다.** 39개 검증 의무 묶음 중 앞서 확인한 11개와 기존 owner backlog 83·unsupported 17은 별도다. 부분 검증을 전체 PASS로 재분류하지 않았다.

이번 추가 결과: M4/M5/M6 임시 계약 회귀 95 PASS, 기존 workflow selector 검사 6 PASS, 안내 링크 43개 확인. commit fixture 1개는 이번에 재실행하지 않았다. 현재 SDK base dependency 25개 요구조건 충족, Mach-O roots 80개/파일 89개 정적 참조 확인·미해결 0. 시스템 공유 캐시 11개와 동적 로딩·다른 target의 closure는 미검증이다.

현재 권한 메타데이터: Codex read 3개, Claude task 13개. Claude의 기존 action 도구는 document_submit·completion_finalize·completion_report이며 이번 재실행 대상으로 삼지 않았다. resource/helper/host 계약은 비활성이다. 실제 client 호출·설치/프로필 변경·승인 적용은 하지 않았다. 이전 실제 Codex Desktop 세 조회 PASS는 원래 증거와 함께 보존했다.

세부 JSON과 근거 원장은 owner-private workspace `m7m8-exit-conditions-20261027`의 `exit-criteria.json`, `remaining-matrix.json`, `validation.json`에 있다. 다음 표의 완료 조건은 실행 승인 자체가 아니다. 현재 금지·범위 밖 항목은 그 경계를 유지하는 것이 이번 작업의 종료 조건이다.

## 미검증 9개

| ID · 항목 | 완료 조건 | 이번에 확인한 범위 / 남은 조건 |
| --- | --- | --- |
| `U02` · 양쪽 client의 모든 profile·MCP operation 조합 | 1. client × 5 profile × 실제 MCP operation별 대상/인자/권한·효과·거부 경계를 고정한다.<br>2. 각 필수 cell에서 실제 client trace와 native/거부 결과를 확보한다. SDK discovery나 패키지 포함만으로 PASS 처리하지 않는다. | 기존 두 정책의 원래 validator·service metadata로 권한 교집합 확인. Codex read 3개, Claude task 13개. M4/M5/M6 fixture 95개 통과.<br>남음: 현재 미선택 profile용 검토된 테스트 입력과 별도 D2/D4/resource/helper/host 계약; 현재 Claude action 3종은 기존 제출·완료용이며 재실행 금지 |
| `U03` · 실제 client가 주도하는 native prepare·finish 전체 흐름 | 1. 새 격리 Work에서 실제 client가 native prepare와 finish를 기존 parser/reducer/lock/fence를 통해 호출한다.<br>2. owner의 정확한 action/request digest·현재 입력/소유권·결과 재조회·완료 증거를 연결한다. pending/stale/COMMIT_UNKNOWN은 차단한다. | M4 fixture의 준비안·정확한 D4 action·결과 검증 경계 회귀 확인. 실제 prepare/finish를 호출하지 않음.<br>남음: 새 테스트 Work와 새로 검토한 prepare/finish action; 기존 action 재사용/재실행 불가 |
| `U04` · Linux 실제 Desktop client E2E | 1. 지원되는 Linux 실제 client/계정/host에서 선택한 정확한 package·runtime·policy를 확인한다.<br>2. 설치·discovery·실제 도구 호출과 native/거부 결과를 client trace로 연결한다. 컨테이너나 macOS 결과는 대체 근거가 아니다. | 기존 Linux CI/native 관측은 당시 commit 근거로 보존. 이 Mac에서 Linux Desktop 성공으로 대체하지 않음.<br>남음: 사용 가능한 지원 Linux client/host와 별도 테스트 scope |
| `U05` · 선언한 다른 architecture의 실제 host·ABI qualification | 1. 선언 대상 darwin-arm64/linux-x86_64/linux-arm64 각각의 실제 host에서 ABI·Python/SDK/native 의존성과 설치/연결을 확인한다.<br>2. 동일 artifact/manifest와 host별 테스트 로그를 결합하고 지원하지 않는 조합을 명시한다. | 현재 host가 macOS arm64임을 유지하고 다른 architecture를 인증하지 않음.<br>남음: linux-x86_64·linux-arm64의 실제 검증 host 및 host별 reviewed manifest |
| `U06` · M4 helper의 실제 network·credential·service 효과 | 1. owner가 선택한 helper/input/producer/argv/output 및 network·credential·service 효과를 별도 pin한다.<br>2. 승인된 새 격리 호출의 효과 범위·native 결과·유실/unknown 차단을 실제 관측한다. 읽기/QA 승인을 일반 실행으로 확대하지 않는다. | helper의 별도 opt-in·고정 argv/producer/input/effects·허용 범위 거부 fixture 통과. 실제 helper 실행 없음.<br>남음: 현재 비활성인 별도 helper-effects 계약과 정확한 신규 action/effect scope |
| `U07` · M5 owner host의 실제 client candidate/workspace 흐름 | 1. 고정 socket identity/config·parent/child/target Work·operation·D4 action/request digest·종료 attestation을 대조한다.<br>2. 실제 client candidate/workspace 흐름에서 lease/resource/fence/input/tree/target drift와 결과 재조회를 확인한다. scheduler/실제 merge 완료로 승격하지 않는다. | owner host·고정 request/operation·socket/config/Work 경계를 임시 fixture로 확인. 설치 host 시작 없음.<br>남음: 현재 비활성인 별도 owner host 계약·새 action과 operator 종료 확인 자료 |
| `U08` · 실제 provider invoice·비용·Claude usage 검증 | 1. owner가 선택한 invoice/usage 원본의 provider·기간·account/project·통화·단가 버전을 정한다.<br>2. 누락·중복·대조 범위를 기록하며 counter와 실제 청구를 일치시키고 미확인 비용을 null로 유지한다. | 기존 client token counter 관측과 비용/청구/Claude usage unknown/null 유지. provider 또는 billing API 호출 없음.<br>남음: 선택된 billing 원본 resource 계약 또는 명시적 provider/billing 접근 권한; 현재 그런 자료 없음 |
| `U09` · 전체 transitive dynamic/runtime dependency closure | 1. native·선택 Python/SDK·표준/외부 extension의 직접/간접 의존성을 target별로 닫는다.<br>2. OS shared-cache 및 runtime dlopen/optional import 경로까지 검증하고 허용 host에서 clean/offline launch와 ABI 근거를 확보한다. 정적 참조 검사만으로 full closure를 선언하지 않는다. | 현재 SDK dependency metadata 25개 요구조건 충족. native/Python/SDK/stdlib roots 80개에서 Mach-O 파일 89개 정적 참조 조사; 미해결 참조 0. 시스템 참조 11개 미전개.<br>남음: OS 공유 캐시 11개·동적 로딩 경로의 검증 근거; 다른 target의 동일 runtime closure |
| `U10` · 현재 미커밋 변경 bytes의 새로운 원격 CI | 1. 현재 변경 bytes를 고정한 정확한 revision/원격 입력으로 필수 CI lane을 실행한다.<br>2. required checks 성공과 skip 사유를 artifact SHA·revision에 연결한다. 과거 commit의 성공을 현재 dirty source 인증으로 사용하지 않는다. | 현재 dirty 경로 8개에 기존 CI selector 적용: native/python_tools/integration 선택. selector 회귀 6개·guide link 43개 통과.<br>남음: 현재 bytes의 별도 승인된 원격 전달 경로; 이번 commit/push 금지로 수행하지 않음 |

## 미구현 10개

| ID · 항목 | 완료 조건 | 이번에 확인한 범위 / 남은 조건 |
| --- | --- | --- |
| `TASK_DAG_SCHEDULER` · task DAG scheduler | 1. 승인된 scheduler 저장 형식/상태 전이와 task identity·spec/source/input fence를 정의한다.<br>2. native owner/lease/자원 계약을 통해 readiness·dispatch·crash recovery를 구현하고 stale/중복/unknown을 차단하는 fixture를 통과한다. | 기존 parallel_prepare는 cycle/참조 검증과 비권한 M2 spool임을 재확인.<br>남음: 실행 scheduler·저장 형식/권한 선택; 현재는 명시적 미구현 |
| `TYPED_EDGE_EVIDENCE_ACCEPTANCE` · typed edge evidence acceptance | 1. 선택 predecessor spec/attempt/artifact/evidence-policy/baseline을 고정한다.<br>2. ARTIFACT_OBSERVED·QA_ACCEPTED·INTEGRATION_ACCEPTED별 현재 증거와 승인 조건을 native 계약으로 판정하고 stale/잘못된 issuer/단순 hash 승격을 거부한다. | edge type/mode의 구문 검증과 실제 evidence acceptance를 구분.<br>남음: 실제 edge acceptance 구현과 선택된 evidence authority 계약 |
| `RESOURCE_RECEIVER_BROKER` · resource receiver broker | 1. owner/lease/epoch에 결합된 slot·CPU·memory receiver grant/release를 원자적으로 구현한다.<br>2. 경쟁·중복·취소·crash·만료에서 과다 할당과 권한 이전이 없음을 검증한다. 기존 native 자원 계약을 재사용한다. | 자원 수치 준비안이 receiver 예약·소유권을 생성하지 않음을 확인.<br>남음: receiver broker 구현과 자원/소유권 정책 선택 |
| `MERGE_QUEUE` · merge queue | 1. 후보 identity·현재 target baseline·검증 결과와 정확한 owner action에 결합된 queue/state를 구현한다.<br>2. 동시 후보·순서·취소·target drift·결과 유실·unknown을 차단하고 자동 재실행하지 않는 절차를 검증한다. | merge_prepare는 비권한 제안이며 queue/adoption/merge 실행이 아님을 확인.<br>남음: merge queue 구현·저장/순서 정책; 실제 merge 권한은 별개 |
| `INTEGRATION_WORKSPACE_AND_FRESH_QA` · integration workspace·fresh QA broker | 1. 선택 후보와 현재 target을 결합한 격리 integration workspace를 구현한다.<br>2. 그 정확한 tree에서 별도 승인된 새 QA와 증거를 생성·검증하고 후보 또는 target drift 시 채택을 차단한다. | 후보 개별 검증을 통합 target QA PASS로 승격하지 않는 fixture 확인.<br>남음: integration workspace/QA broker 구현·새 테스트 Work·정확한 새 QA 승인; 기존 QA 재실행 금지 |
| `TARGET_REF_CAS_BROKER` · target ref CAS broker | 1. owner 승인에 expected target ref/OID·후보 tree·정확한 update를 pin한다.<br>2. 기존 fence/target CAS를 사용해 경쟁·ABA·source/target drift를 원자적으로 거부하며 crash/unknown 결과를 보존한다. | 기존 target-check·hash 확인과 실제 ref 교체 권한을 구분.<br>남음: ref CAS broker 구현·정확한 target update 승인; 실제 merge는 이번 범위 밖 |
| `MERGE_PUBLICATION_RECEIPT` · merge publication receipt | 1. 권위 있는 CAS 결과의 before/after target·candidate·승인·integration/QA 근거를 immutable receipt에 연결한다.<br>2. receipt와 journal의 원자성·재조회·결과 유실/COMMIT_UNKNOWN을 검증하고 관측되지 않은 merge 완료를 생성하지 않는다. | 검증/후보 hash를 실제 merge 영수증으로 만들지 않음.<br>남음: merge publication 구현 및 선행 queue/integration/CAS broker |
| `P7_SELF_CONTAINED_RUNTIME` · P7 자체 완결 runtime | 1. 선택 target별 Python/SDK/native 및 의존 라이브러리·license/inventory를 재현 가능하게 포함한다.<br>2. 외부 개발 환경 없는 clean/offline host에서 설치/시작·owner scope 보존을 검증한다. 기존 runtime pin은 자동 이전하지 않는다. | 현재 package는 external-owner-pinned runtime이며 자체 완결품이 아님을 유지.<br>남음: runtime 공급/포함·플랫폼·license 정책 선택과 실제 구현 |
| `P7_SIGNING_AND_TRUST_ROOT` · P7 배포 서명·선택된 trust root | 1. issuer/key custody·trust root·서명 형식·만료/폐기 정책을 선택한다.<br>2. package/manifest/target identity를 서명하고 검증기에서 변조·알 수 없는 키·만료·폐기를 fail closed로 거부한다. | ad-hoc platform 서명을 정식 배포 서명으로 승격하지 않음.<br>남음: owner의 trust/key 정책 선택·서명/검증 구현; 이 작업에서 credential 생성/선택하지 않음 |
| `P7_FULL_HOST_QUALIFICATION_AND_UPDATE_DISTRIBUTION` · P7 정식 host qualification·서명된 유통 연계 | 1. 선택 target별 ABI·dependency closure·signed manifest·실제 설치/reload/호환성을 검증한다.<br>2. 기존 D5의 freeze/fence/probe/ready/partial/unknown 보존을 사용해 선택된 유통 채널·trust/migration을 연결한다. 공개 게시 권한은 별도다. | 기존 D5 owner updater는 구현됨을 보존하고 P7 release 체계와 구분.<br>남음: 앞선 P7 runtime/서명·host qualification 구현 및 release/channel 정책 |

## 현재 범위 밖 9개

| ID · 항목 | 완료 조건 | 이번에 확인한 범위 / 남은 조건 |
| --- | --- | --- |
| `O01` · Windows native/desktop 대상 | 1. 이번 작업에서는 범위 밖 유지가 종료 조건이다.<br>2. Windows를 목표로 추가할 경우 native POSIX 의존·runtime/installer/host 계약을 설계·구현하고 실제 Windows client/ABI 검증을 별도로 승인한다. | Windows는 현재 package target에 없으며 성공 대상으로 표시하지 않음.<br>남음: 별도 Windows 지원 목표·구현·검증 scope |
| `O02` · Hosted/remote·새 외부 서비스·credential 접근 | 1. 현재 범위 밖 상태와 권한 비확대를 유지한다.<br>2. 향후 필요하면 정확한 서비스·계정·데이터·전송/credential 효과·보존 정책의 별도 승인을 확보한 후 해당 범위만 검증한다. | Hosted/새 외부 서비스·credential/network 접근을 수행하지 않음.<br>남음: 별도 Hosted/remote/service/credential 권한 선택 |
| `O03` · 실제 target merge | 1. 이번에는 금지/NOT_RUN 유지가 종료 조건이다.<br>2. 향후 별도 실제 merge 승인과 구현된 queue/integration-QA/CAS/receipt 경로가 모두 있어야 정확한 target에서 검증한다. | 실제 target merge를 수행하지 않음.<br>남음: 사용자의 실제 merge 승인과 미구현 broker 선행조건 |
| `O04` · 공개 배포·자동 업데이트 게시·채널 선택 | 1. 이번에는 공개 게시 금지와 private 검토본 범위를 유지한다.<br>2. 향후 release issuer/trust/channel/배포물·update/migration을 명시 승인하고 P7 선행조건을 충족한다. | 공개 배포·자동 업데이트 게시·채널 선택을 하지 않음.<br>남음: 별도 공개 배포/게시 승인과 P7 구현 |
| `O05` · commit/push·PR·출시 | 1. 이번에는 변경을 미커밋 상태로 보존하고 commit/push/PR/출시를 수행하지 않는 것이 종료 조건이다.<br>2. 향후 사용자 명시 지시 없이는 재개하지 않는다. | 개발/원본 저장소의 commit/push/PR/출시를 수행하지 않음.<br>남음: 이번 사용자 금지. 완료를 위해 해제할 항목이 아님 |
| `O06` · 기존 실행·QA·COMMIT_UNKNOWN 재실행/repair/reconcile | 1. 기존 실행·QA·COMMIT_UNKNOWN을 replay/repair/reconcile/자동 rollback하지 않는다.<br>2. 원래 불확실 결과·승인·증거를 미해결로 보존한다. 새 Work 성공도 기존 unknown의 해소가 아니다. | 보호 manifest와 기존 승인·native 결과를 해시 대조하고 unknown 상태를 보존.<br>남음: 이번 금지/보존 의무. 정상 완료로 바꾸기 위한 재실행 대상이 아님 |
| `O07` · 생산 Work·전체 사용자 자료 전수 스캔·변경 | 1. 이번에는 범위 제한을 유지한다.<br>2. 향후 정확한 프로젝트·Work·데이터·읽기/쓰기·보존 범위의 별도 승인이 있을 때만 해당 범위에서 검증한다. | 승인된 명시 manifest·정책 경로만 대조하고 생산 Work/전체 호스트를 스캔·변경하지 않음.<br>남음: 현재 미선택인 생산 데이터 권한; 플러그인 설치에서 추론 금지 |
| `O08` · Claude Native Skills 자동 설치·자동 발견 확장 | 1. 지원하는 MCP 안내의 범위만 정확히 안내한다.<br>2. 별도 native Skills 전달을 원하면 공식 지원 설치 형식·skill identity/버전/권한·실제 Claude 발견/실행 근거를 별도로 검토한다. | 현재 MCPB guidance와 Codex SKILL layout을 Claude native Skills 자동 발견으로 주장하지 않음.<br>남음: 별도의 Claude native Skills 전달 목표와 지원 경로 선택 |
| `O09` · hash로 내용 진실성·모델 이해·독립 issuer 신원 인증 | 1. 이번에는 hash가 내용 진실성·모델 이해·인간 issuer 신원을 보장한다는 주장을 하지 않는다.<br>2. 추가 보증을 요구한다면 검증 가능한 threat model·독립 issuer/서명/수신 증거를 별도로 정의한다. hash 일치만으로는 이 보증을 완결할 수 없다. | hash 무결성·agent 진술·LOCAL_COOPERATIVE·현재 native 판정을 구분.<br>남음: 기존 보증 경계 밖의 별도 assurance 목표; 미실행 테스트 한 번으로 해소 불가 |

## 실제 근거와 후속 순서

1. 현재 승인 범위의 검사는 위 결과로 종료한다. 기존 실제 실행·QA·COMMIT_UNKNOWN과 owner pin을 재사용하거나 자동 재실행하지 않는다.
2. U02/U03/U06/U07을 실제 검증하려면 각각 필요한 새 synthetic 입력·정확한 action/effects/host 계약을 구체적으로 검토해야 한다. 기존 M2 준비안과 native 승인 action은 다른 권위다.
3. U04/U05/U09는 지원되는 다른 host와 runtime closure 근거가 필요하다. 현재 macOS 정적 의존성 검사는 OS shared-cache·optional/dlopen 경로와 다른 target 인증을 대체하지 않는다.
4. U08은 선택된 billing 원본/권한이 필요하다. 확인되지 않은 비용·Claude usage는 unknown/null로 유지한다. U10의 원격 CI는 현재 미커밋 bytes를 전달할 별도 허용 경로가 없으므로 NOT_RUN이다.
5. P4/P5 일곱 항목과 P7 세 항목은 선행 설계·권한·저장/trust 선택 및 구현이 필요하다. 단순 실행 허가만으로 완료되지 않는다. 기존 D5 owner 관리가 미구현이라는 뜻은 아니다.
6. 범위 밖 아홉 항목은 이번에 반드시 실행해서 없앨 backlog가 아니다. 금지·지원 대상·보증 경계로 유지하며 별도 목표가 정해질 때만 재검토한다.

근거: `m7m8-exit-conditions-20261027/private/grant-matrix.json`, `private/contracts-regression.log`, `private/python-runtime-dependencies.json`, `private/macho-dependency-graph.json`, `private/local-ci-selection.json`. SDK 메타데이터 검사는 현재 환경의 base requirements에 한정하고 optional extras나 임의 동적 import까지 인증하지 않았다. 의존성 진단에 사용한 pip vendored packaging은 기존 도구를 읽어 썼으며 새 패키지를 설치하지 않았다.

원본 소스·기존 변경·승인·Work·evidence·CAS·journal·registry·기존 COMMIT_UNKNOWN 보존과 설치 한 개/연결 한 개 대조는 최종 보존 원장에 기록한다. commit/push·실제 외부 서비스·새 client/Work 실행·승인 적용은 수행하지 않았다.


---

## 2026-10-27 Codex Desktop 세 조회 복구 — 보존된 실제 PASS

**실제 Codex Desktop 대화에서 지정 세 조회를 각 1회 완료했다. 전체 M7/M8 출시 검증 완료는 아니다.** 검증 의무 묶음 기준 확인 11개, 미검증 9개·미구현 10개·현재 범위 밖 9개다. 고정 owner backlog 83개·unsupported 17개는 그대로다.

설정에서 Golem 0.2.5 한 개가 활성이고 launcher·정책 pin은 정상이었다. 실제 실패 대화의 엔진 로그는 initialize handshake 종료 뒤 `omitting MCP server without an exact ready client`를 기록했다. 같은 설치 bytes의 직접 initialize는 성공했지만, 재요청과 공식 동일본 재설치만으로는 해당 대화의 실패한 client가 갱신되지 않았다. 지정 테스트 대화만 공식 보관·복원 후 Desktop에서 다시 열자 새 `thread/resume`의 Golem client 초기화가 성공했고 실제 도구가 노출됐다. 최초 handshake 종료의 더 깊은 OS/process 원인은 확인하지 못했으므로 단정하지 않는다. 앱 전체 재시작·내부 DB 편집·cache 직접 수정은 하지 않았다.

| 실제 Desktop 호출 | 횟수 | 시간 | 반환 근거 |
| --- | --- | --- | --- |
| projects_list | 1 | 88ms | AVAILABLE, 기존 read 세 도구의 교집합 |
| work_inspect / status | 1 | 234ms | AVAILABLE, agent session sequence=0, session acceptance_verified=false |
| completion_check / selection | 1 | 2,695ms | AVAILABLE, native action=DONE, acceptance_verified=true, generation=9, completion_sequence=1 |

status의 session 판정과 native 현재 selection의 완료 판정은 다른 계약이다. completion boundary.session_sequence=0이며 이를 generation=9와 비교해 drift나 실패로 판정하지 않는다. development-result freshness=CURRENT/status는 빈 문자열, qa-result freshness=CURRENT/status=PASS를 그대로 기록했다. 세 응답 모두 native_state_changed=false, execution_authorized=false다. native 읽기는 원래 15초 한도에서 2.482399초에 종료했고 observation hash는 앞선 검증과 같았다. 기존 QA를 실행한 것이 아니다.

설치 파일 9개와 global config bytes는 동일하며 launcher·policy·native engine·producer pin을 바꾸지 않았다. Claude와 기존 승인·Work·evidence·CAS·journal·COMMIT_UNKNOWN은 그대로다. 검증 대화의 스킬 파일 읽기 1회는 기존 filesystem allowlist에 의해 거부됐으며 권한을 확대하지 않았다. 명시된 읽기 지시와 실제 도구 설명으로 검증했다. 잘못된 서버·Work·중복/누락/순서·실패·결과 대체를 거부하는 증거 대조 회귀 8개가 통과했다. 실행·QA·승인 적용·실제 merge·commit/push는 하지 않았다.

실제 대화: `Golem M7 승인 읽기 최종 검증 2026-10-27` (`01a17c6a-3b2f-7703-83d2-23f6dc1c360d`), 성공 turn `01a17c99-0424-78d2-9faa-9a86ccc087d1`. 상세 원장과 raw trace는 owner-private workspace `codex-desktop-discovery-20261027/validation.json`, `remaining-matrix.json`, `검증결과.md`에 있다. 아래 0회 차단은 복구 전 당시 결과이며 삭제하거나 PASS로 덮어쓰지 않는다.

---

## 2026-10-27 잔여 감사 당시 판정 — 복구 전

**M7·M8 전체 완료는 아니다.** 기존 승인으로 가능한 정적·fixture·회귀와 설치 보존 확인을 마쳤다. 39개 검증 의무 묶음 중 10개를 확인했고, **미검증 10 · 미구현 10 · 현재 범위 밖 9**를 구분했다. 이는 operation 수가 아니다. 고정 원장의 owner backlog 83개와 unsupported 17개는 ID·권한 경계를 그대로 유지한다.

현재 Codex 0.2.5는 `golem@golem-m7-finish-complete`의 read profile 세 조회만 허용한다. Claude task 0.1.8은 기존 검토본 한 개와 정책을 보존했다. 설치·launcher·producer pin·권한은 변경하지 않았다.

이전 공식 bundled app-server 모델 세션의 세 조회와 native DONE 관측은 그 범위의 PASS다. 이번에 명시 승인으로 생성한 실제 Codex Desktop 대화는 **도구 미노출, 세 도구 각 0회, BLOCKED / NOT_RUN**이다. 사용자가 전달한 후속 답변도 같은 0회 결과이며 새로고침 성공 근거가 아니다. 새 결과의 delivery·session sequence·native generation·completion_sequence·action·acceptance_verified·evidence freshness/status는 모두 미확인이다. Computer Use의 Codex 앱 접근 차단 때문에 GUI 선택·재로딩을 대신 수행하지 못했고, SDK/CLI 결과로 이 공백을 대체하지 않았다. 후속 호출·재시도는 하지 않았다.

### 이번 검증과 수정

| 검사 | 결과와 한계 |
| --- | --- |
| macOS Debug native·CLI·Python/Node bindings·event bridge 등 CTest 413개 | 첫 전체 실행 412 PASS / daemon_cli 1 FAIL. 공백 포함 Python 경로의 임시 worker shebang을 canonical 경로로 수정한 후 해당 1개 PASS. 전체 413개에 통과 근거가 있으며 단일 전체 green 실행을 주장하지 않는다. |
| Python 전체 회귀 1,423개 | fixture shebang 두 곳 수정·공백 경로 회귀 추가 후 전체 1,422 PASS / export 진단 1 timeout. 부하가 끝난 뒤 해당 1개가 원래 60초 한도로 23.101초 PASS. 최초 실패와 재검증을 보존했다. |
| capability 회귀 | 368 PASS. 전체 Python 회귀의 부분집합이므로 합산하지 않는다. |
| 고정 산출물 | 8개 byte 동일. 생성기의 불필요한 EOF 빈 줄만 수정하고 development-source digest를 갱신했다. 비교기를 완화하거나 owner/runtime pin을 바꾸지 않았다. |
| 5개 profile | 각 archive 이중 재생성·엄격 verify·schema 확인, SDK stdio discovery·권한 교집합·미허용 Work 거부 PASS. Desktop/실제 native Work E2E는 아니다. Claude 설치 task archive bytes 동일. |
| 원격 CI 관측 | f7d5d89는 5 jobs 성공/8 skipped. c253944는 전체 실패이며 native/bindings의 개별 성공만 별도 근거다. 현재 미커밋 bytes의 CI는 NOT_RUN. |
| 보존 | 기존 495개 파일 사전 일치, 설치 원장 한 파일의 계획된 갱신을 제외한 494개와 Claude 86개 byte 동일. 승인·Work·evidence·CAS·journal·설정·기존 COMMIT_UNKNOWN 보존. |

제품 runtime·native core·승인 검사는 수정하지 않았다. 수정 파일은 `tools/test_integration.py`, `tests/c/daemon_integration.py`, `tools/capability_refresh.py`와 그 development review digest·생성 원장 및 설명 문서다. 기존 실행·QA·COMMIT_UNKNOWN 재실행, 승인 적용, 실제 merge, commit/push는 하지 않았다. 직접 의존성/ad-hoc 서명 관측은 정식 release 서명이나 전체 transitive closure 검증이 아니다. Client token counter는 관측값으로만 보존하며 실제 비용·청구 합계·Claude usage는 unknown/null이다.

### 항목별 분류

각 항목의 source 근거·후속 조건·과거 NOT_RUN/미구현 ID 매핑은 workspace 검증 원장 `m7m8-remaining-audit-20261027/remaining-matrix.json`에 있다. 과거 두 목록의 모든 ID를 매핑했고 원본 결과 JSON은 수정하지 않았다.

| ID | 항목 | 현재 결과 |
| --- | --- | --- |
| V01 | 현재 source의 macOS native·CLI·bindings fixture 전체 | PASS_WITH_RETEST |
| V02 | 현재 Python 도구·MCP·승인·격리 회귀 | PASS_WITH_RETEST |
| V03 | 수정된 정적 생성기·원장·권한 경계 회귀 | PASS |
| V04 | 다섯 profile의 실제 SDK stdio discovery·교집합·거부 | PASS |
| V05 | 다섯 profile package 재생성·allowlist·schema 검증 | PASS |
| V06 | 고정 원장 산출물 여덟 개의 엄격한 byte 재현 | PASS |
| V07 | 두 client 설치본·정책·producer·Work 보존 | PASS |
| V08 | 이미 실행된 원격 CI의 revision·lane별 근거 | PASS_RECORDED_REVISIONS_ONLY |
| V09 | 기존 Codex 다섯 세션의 client token counter 관측 | PASS_CLIENT_COUNTER_OBSERVATION |
| V10 | 현재 macOS native 직접 의존성·platform 서명 관측 | PASS_LIMITED_INSPECTION |
| U01 | 현재 실제 Codex 대화의 도구 노출·세 조회 | 미검증 / BLOCKED_NOT_RUN |
| U02 | 양쪽 client의 모든 profile·MCP operation 조합 | 미검증 / NOT_RUN |
| U03 | 실제 client가 주도하는 native prepare·finish 전체 흐름 | 미검증 / NOT_RUN |
| U04 | Linux 실제 Desktop client E2E | 미검증 / NOT_RUN |
| U05 | 선언한 다른 architecture의 실제 host·ABI qualification | 미검증 / NOT_RUN |
| U06 | M4 helper의 실제 network·credential·service 효과 | 미검증 / NOT_RUN |
| U07 | M5 owner host의 실제 client candidate/workspace 흐름 | 미검증 / NOT_RUN |
| U08 | 실제 provider invoice·비용·Claude usage 검증 | 미검증 / UNKNOWN_NULL |
| U09 | 전체 transitive dynamic/runtime dependency closure | 미검증 / NOT_RUN |
| U10 | 현재 미커밋 변경 bytes의 새로운 원격 CI | 미검증 / NOT_RUN |
| TASK_DAG_SCHEDULER | task DAG scheduler | 미구현 / NOT_IMPLEMENTED |
| TYPED_EDGE_EVIDENCE_ACCEPTANCE | typed edge evidence acceptance | 미구현 / NOT_IMPLEMENTED |
| RESOURCE_RECEIVER_BROKER | resource receiver broker | 미구현 / NOT_IMPLEMENTED |
| MERGE_QUEUE | merge queue | 미구현 / NOT_IMPLEMENTED |
| INTEGRATION_WORKSPACE_AND_FRESH_QA | integration workspace·fresh QA broker | 미구현 / NOT_IMPLEMENTED |
| TARGET_REF_CAS_BROKER | target ref CAS broker | 미구현 / NOT_IMPLEMENTED |
| MERGE_PUBLICATION_RECEIPT | merge publication receipt | 미구현 / NOT_IMPLEMENTED |
| P7_SELF_CONTAINED_RUNTIME | P7 자체 완결 runtime | 미구현 / NOT_IMPLEMENTED |
| P7_SIGNING_AND_TRUST_ROOT | P7 배포 서명·선택된 trust root | 미구현 / NOT_IMPLEMENTED |
| P7_FULL_HOST_QUALIFICATION_AND_UPDATE_DISTRIBUTION | P7 정식 host qualification·서명된 유통 연계 | 미구현 / NOT_IMPLEMENTED |
| O01 | Windows native/desktop 대상 | 범위 밖 / OUT_OF_SCOPE |
| O02 | Hosted/remote·새 외부 서비스·credential 접근 | 범위 밖 / OUT_OF_SCOPE |
| O03 | 실제 target merge | 범위 밖 / PROHIBITED_NOT_RUN |
| O04 | 공개 배포·자동 업데이트 게시·채널 선택 | 범위 밖 / PROHIBITED_NOT_RUN |
| O05 | commit/push·PR·출시 | 범위 밖 / PROHIBITED_NOT_RUN |
| O06 | 기존 실행·QA·COMMIT_UNKNOWN 재실행/repair/reconcile | 범위 밖 / PROHIBITED_PRESERVED_UNRESOLVED |
| O07 | 생산 Work·전체 사용자 자료 전수 스캔·변경 | 범위 밖 / OUT_OF_SCOPE |
| O08 | Claude Native Skills 자동 설치·자동 발견 확장 | 범위 밖 / NOT_CLAIMED |
| O09 | hash로 내용 진실성·모델 이해·독립 issuer 신원 인증 | 범위 밖 / NOT_CLAIMED |

상세 raw log·재검증·해시·설치 대조는 owner-private workspace의 `m7m8-remaining-audit-20261027/validation.json`과 `검증결과.md`에 기록한다. 문서/로컬 검사 완료를 제품 전체 출시나 남은 Desktop 검증 완료로 승격하지 않는다.

---

## 아래는 당시 r9 검증 기록

아래 버전·설치 경로·PASS는 당시 source/artifact/승인/Work에 한정한다. 현재 설치 및 잔여 판정은 위 기록을 따른다.

**당시 r9 결과: Claude task 0.1.8 업데이트 후 별도 Work에서 QA 1회·읽기 전용 저장 결과 재조회·QA 결과/완료 문서 제출·native finalize·보고서 물질화가 실제 Claude client에서 성공했다. Codex와 새 Claude Work 모두 현재 DONE / acceptance_verified=true / generation 9 / completion_sequence 1이다. 과거 Claude COMMIT_UNKNOWN은 재실행·repair·reconcile 없이 미해결로 보존한다. 판정 범위는 선언된 macOS synthetic C Work와 현재 M8 정합성 검사이며 제품 전체 출시 완료가 아니다.**

Codex·Claude의 개선본 실제 설치, 읽기·입력 의존 응답·미허용 Work 차단·M2 준비/확인·native claim·동일 ID 저장 결과 재조회를 관측했다. 추가 C QA는 별도 사례로 기록한다. **두 client의 선언된 synthetic C Work 완료와 모든 profile·OS·제품 전체 배포 완료를 구분한다.** r8의 Claude 보류는 후속 사용자 지시로 해제했고, 아래 r9 기록은 당시 상태다. 당시 기계 판독 결과는 [검증 행렬](mcp-m7-m8-validation.json)에 있다.

## 범위와 판정 기준

실제 대상은 macOS의 Codex Desktop 26.1021.31345(build 21828), bundled CLI 0.164.0-alpha.11.1과 Claude Desktop 3.6556.2(Sonnet 5.5 medium)다. CLI/SDK fixture를 desktop 성공으로 대신하지 않는다. 테스트 대화에서 호출한 server/tool, native immutable 결과, 현재 status/next/완료 predicate를 각각 대조했다.

사용자는 별도 synthetic project/Work/registry/정책, 두 client의 설치·재로딩, 기존 D1/D2/D4 owner 절차와 최소 정상 계정 모델 호출을 허용했다. r8에서는 Claude를 보류하고 Codex/M8을 계속했으며, r9에서 사용자가 Claude 업데이트와 별도 Work의 남은 검증을 명시 승인했다. 생산 권한, credential, 외부 service 변경, 실제 target merge, 개발/원본 저장소 commit/push·PR·공개 배포는 수행하지 않았다.

`AVAILABLE`은 전달 상태다. 실행 결과와 agent 진술, hash와 내용의 진실성, 역사적 QA와 현재 QA, QA PASS와 Work 완료를 구분한다. owner 선언의 `LOCAL_COOPERATIVE`와 issuer label은 독립된 인간 신원·서명의 인증이 아니다. 원래 native parser/reducer/lock/fence/승인/완료 predicate를 재사용했다.

## 소스·패키지 변경

| 실제 발견 | 근거 | 수정과 유지한 조건 |
| --- | --- | --- |
| feature MCPB config description 누락 | 실제 Claude 설치 미리보기의 Required 오류 6개 | 모든 config 항목에 description 제공. consent 기본 false 유지 |
| 선택하지 않은 optional 계약의 template 문자열 | 실제 Claude가 `${user_config...}`를 전달 | 정해진 optional template 6개만 없음으로 해석. concrete 값·consent triple 검사는 유지 |
| union inputSchema object root 누락 | 실제 MCP/mcp-types 2.3.0 tools/list 검증 오류 14개 | oneOf root에 `type: object` 추가. branch의 required/closed/권한/한도 유지 |
| 동일 버전 설치가 과거 cache를 재사용 | 실제 UI·설치 bytes | feature MCPB 0.1.5, Codex 0.2.2와 전체 payload identity 대조. 버전만으로 일치 판정하지 않음 |
| Setup의 private launcher-only 분기 누락 | 실제 plugin에는 adapter script가 없음 | resolved command를 먼저 구분. 검토된 direct launcher/pin 보존, default adapter로 재바인딩하지 않음 |
| 구 D2 SDK fixture의 무조건 전체 도구 노출 가정 | resource/owner/host 계약 없는 fixture의 조건부 9개 숨김 | 실제 D1/D2-only 집합과 대조. 정책·guard 확대 없음 |

`tools/test_integration_m6.py`는 config 설명, object schema root, optional consent/template의 거부 경계를 검증한다. `tests/c/integration_d2_mcp.py`는 조건부 노출의 정확한 집합을 검사한다. native core는 이 작업에서 변경하지 않았다.

테스트 launcher는 isolated Python에 module/SDK 경로를 명시했다. macOS shebang/socket 길이 문제는 전용 짧은 가상환경/임시 경로로 해소했다. 검사 한도와 거부 조건은 완화하지 않았다. Codex QA의 초기 direct bootstrap은 setup-only로 차단됐으며 실패 시점의 세부 code는 확보하지 못했다. 원 configure를 호출하고 오류 code만 private에 기록하는 검토된 launcher로 재생성·재설치하고 새 대화에서 관측했다. cache 파일만 임시 수정한 것이 아니다. 최종 판정은 검증 행렬을 따른다.

## 설치 identity와 런타임

최종 feature MCPB 5개는 0.1.8이며 전체 SHA와 파일 수는 JSON의 `artifact_index`에 있다. task SHA-256은 `f377f2d3a1b9d30bcb6210c269234af2c68ea5bb51cfe0ca84a4bb7fb2af4fb4`이다. 각 최종 archive는 payload 81개와 생성 schema 5개를 포함하며 현재 source에서 byte 동일하게 재생성된다. 실제 policy/registry/Work/evidence/credential/private log는 배포물에 포함하지 않는다. Claude의 r6 task 0.1.5 설치 SHA `bd60ba9c0f7ac705a4c2adfafb051b18f903ede8fd53a27939f343fb401627b7`과 r7의 0.1.6 산출물은 이전 버전 근거로 보존한다.

검증 루트는 `/Volumes/Extreme SSD/golem-project/m7m8-validation-20261026`다.

| 대상 | 설치·실행 identity |
| --- | --- |
| Codex 기본 E2E | `golem@golem-m7-skills` 0.2.2, server `golem-m7-skills`; `~/.codex/plugins/cache/golem-m7-skills/golem/0.2.2`에서 실제 읽기·재조회 관측 |
| Codex C QA | `golem@golem-m7-qa-reviewed` 0.2.2, server `golem-m7-qa-reviewed`; private source `qa-stage-v5/codex-marketplace`, 설치 cache `~/.codex/plugins/cache/golem-m7-qa-reviewed/golem/0.2.2` |
| Codex interpreter/SDK | canonical Homebrew Python 3.14.7, 전용 `runtime/lib/python3.14/site-packages`, MCP/mcp-types 2.3.0; `-I -B -c`의 명시 경로 launcher |
| Claude 최종 설치 | `~/Library/Application Support/Claude/Claude Extensions/local.mcpb.golem-contributors.golem-task`; 승인한 r6 task payload 81개 bytes 일치 |
| Claude launcher/SDK | 실제 `uv run --directory … tools/integration_distribution_entry.py`; 전용 Python 3.11.14, MCP/mcp-types 2.3.0 |
| native | `r5/native-golem`, SHA `ca47c364541650c9fe0dcc59b523b943d73064a16c53d10542a1275a7dd2d893`; SDK pin `r5/native-sdk.json`; QA host는 기존 `integration_approval_host.c` public API 경로 |

Codex plugin은 9개 파일이고 marketplace catalog를 포함한 생성물은 10개다. task QA 노출은 별도 검토된 D4 실행 action과 D2 scope를 포함하여 15개가 됐다. profile 선택만으로 실행 권한이 생긴 것이 아니다. M4 helper와 M5 owner host는 비활성이다.

Codex의 Setup/Work 두 스킬은 실제 세션 inventory에서 관측했다. direct launcher 분기를 실제로 적용하여 default adapter 상태를 변경하지 않았다. Claude는 manifest/config 설명과 MCP tool schema 안내를 실제로 사용했다. archive에 포함된 Codex SKILL.md가 Claude의 native Skills로 자동 로드됐다는 주장은 하지 않는다.

native는 arm64 Mach-O이며 직접 의존하는 libcrypto.3, libjson-c.5, libmd4c.0, libSystem을 관측했다. self-contained=false, signature=NOT_IMPLEMENTED, trust_root=NOT_SELECTED다. 이것은 전체 동적 closure·code signing·OS/host qualification이 아니다.

## 기본 실제 E2E 결과

| test | 관측 | 결과와 한계 |
| --- | --- | --- |
| C1 Codex final install | 0.2.2 설치 bytes, 새 desktop server ready | 실제 연결·호출 관측. 원래 공개 main/기존 설치본으로 대체하지 않음 |
| C2 source 전달·응답 | status/next/record, scope body의 evidence_read | Batch `a6cb41b9e881`; 29×62+46=1844. 정답을 prompt에 주지 않음 |
| C3 실제 미허용 Work | 실제 존재하는 `denied-work` status 1회 | `TRANSFER_SCOPE / NOT_DISPATCHED`; NOT_FOUND 대체 아님 |
| C4 준비·승인 action | approved_action_prepare→plan_read→action_confirm | exact action 일치. M2 준비를 owner 승인/실행으로 승격하지 않음 |
| C5 native claim | request `8be3791fd4bf456da3b5a02725c1acc7` | committed=true, sequence 1→2; receipt `abbf6d2453af8154ff91cd2e010b5762f813cda533be92a1d6aa21626cb39a40` |
| C6 원 ID 재조회 | 사용자가 명시 승인한 동일 ID 1회 | 같은 immutable 결과/receipt/sequence. 현재 native state는 기록된 claim state와 일치하고 attempts=1. 저장 결과의 `native_state_changed=POSSIBLE`은 그대로 보존 |
| C7 완료 | native completion_check | WAIT, completion_sequence=0, acceptance=false. claim은 begin/QA/완료가 아님 |
| A1 Claude 최초 설치 | task 0.1.4 handshake·setup_status | SETUP_VALIDATION_FAILED 보존. 정상 E2E로 집계하지 않음 |
| A2 Claude 수정본 | task 0.1.5 최종 r6 설치·설정·13개 노출 | 실제 payload bytes와 정책 path/SHA 일치 |
| A3 source 전달·차단 | scope evidence 원문, 미허용 Work | Batch `68d9cd3e0d5e`; 49×24+33=1209. `TRANSFER_SCOPE / NOT_DISPATCHED` |
| A4 claim·재조회 | request `8d26a427cead4b109c14ec8f20418fa1` 실행 1회·재조회 1회 | 같은 receipt `d58001416dd3bae5b81e963c33d48062c3c6ecb4b2c32e435ff10e24b0fc529f`; sequence=2, attempts=1 |
| A5 완료 | 실제 completion_check와 후속 native 읽기 | WAIT, completion_sequence=0, acceptance=false |

Codex claim은 0.2.1 대화 `01a17849-9f30-7301-9220-b9b6be253551`에서 관측했다. 0.2.2 대화 `01a17867-5d3c-7bc1-9858-b14cc8e51899`에서 새 읽기·원 ID 재조회를 관측했다. 두 버전 사이 runtime module bytes는 동일하며 Setup/metadata 차이를 별도로 기록했다.

Claude 기본 flow 대화는 `c4bd3586-89bb-4ce0-9dc0-a8b0aec8ebf7`다. UI 응답의 denied-work를 추측했다는 진술은 fixture 실재 검증과 구분했다. 실제 enrollment와 `.golem/works/denied`가 존재하고, client grant에는 없다. 일회 UI 승인만 사용했고 persistent always-allow를 적용하지 않았다.

최초 Claude projects_list 시간 초과는 승인 UI가 처리되지 않아 tools/call로 전달되지 않은 사례였다. 읽기 1회만 명시 재시도하여 전달을 확인했다. mutation timeout을 안전한 재실행으로 취급하지 않았다.

## C QA, 실패 근거와 보존

부모 에이전트는 별도 synthetic C fixture에서 실제 컴파일·테스트 실패를 먼저 관측하고 `logic.c`의 뺄셈을 덧셈으로 수정했다. native execution prepare/finish와 development-result/qa-plan을 원 parser/renderer 경로로 준비했다. 실제 client가 이 준비·파일 수정까지 수행했다고 주장하지 않는다.

첫 QA fixture(v4)의 author가 native describe에 사용한 JSON과 D4 `native_json`의 key 순서를 다르게 만들었다. 기존 `src/execution/model.c:ex_hash`는 json-c의 직렬화를 사용한다. 읽기 전용 native approval describe로 비교한 두 scope는 **request_digest만 달랐다**. semantic JSON 내용과 source snapshot의 일치는 원래 exact 승인 계약의 일치를 뜻하지 않는다. 제품의 guard를 고치거나 request/승인/pin을 자동 재작성하지 않았다.

| QA case | 실제 층위·판정 |
| --- | --- |
| Q-A v4 | Claude 실제 execution_request `7c77e5b7c0e24734bfe84da0b7eac61e` 1회 전달. native error 11 `stale stage result`; D4는 `COMMIT_UNKNOWN / NATIVE_FAILURE / native_state_changed=UNKNOWN`을 불변 결과로 보존 |
| Q-C v4 | Codex request `f6a1d74409774955b1282b7ef0d50e11`은 자동 승인 검토에서 native dispatch 전에 거부. 재시도/우회 없음. exact action 준비·확인은 별도 관측 |
| Q-F forensic | native 읽기로 요청 key 순서와 request_digest 차이 입증. 기록된 development snapshot과 현재 native snapshot도 일치. 이것을 QA 성공·무효과 증명·unknown 해소로 승격하지 않음 |
| Q-C v5 | 사용자 후속 지시에 따라 별도 Codex project `m7-qa-codex-v5` 준비. describe/dispatch 전체 bytes와 native action digest 일치 검사. 실제 QA 두 case PASS, verify/verify_authorized 성공. receipt `ad46e9aff4b2313a1b9a9a506fcb07d3eda58a8e2ceded9f7dc07f06c0006510`, request `d08d14ff9137497c8d32e803c70a4321`. r6 당시 완료는 RECONCILE_EXECUTION/SUBMIT_RESULT, acceptance=false였으며 r8의 현재 DONE은 아래에서 구분한다. 기존 execution_request를 이용한 재조회는 BLOCKED 이력을 보존한다. r7에서 별도 읽기 전용 stored_result 경로를 구현·설치하고 Codex 실제 조회에 성공했다. receipt 기반 verify 성공을 이 조회의 대체 근거로 쓰지 않았다 |

Codex v5의 첫 저장 결과 재조회는 자동 승인 검토에서 차단됐다. 사용자가 정확한 동일 ID 호출 1회를 명시 승인한 뒤 실제 호출했으나 기존 대화에서 `Transport closed`로 응답을 받지 못했다. native Work 파일 55개와 immutable 결과 hash가 모두 그대로임을 확인했다. 새 대화 `01a178d2-08a0-76a0-98fb-705cb1180e02`에서 같은 서버의 projects_list 읽기가 정상 응답하여 연결을 복구했다. 승인 횟수를 자동 확대하지 않았다. 사용자가 복구된 연결에서 동일 인자 재조회 1회를 추가로 명시 승인했으나 자동 승인 검토가 실행 가능 tool과 cached-result-only/추가 실행 금지 조건의 충돌을 이유로 다시 거부했다. 약속대로 추가 호출 없이 중단했다. 두 승인 후 시도는 각각 transport 오류와 승인 검토 거부이며, 당시 성공한 desktop 동일 ID QA 재조회는 없었다. 이후 사용자가 안전한 읽기 전용 코드 수정을 요청하여 아래 r7에서 해소했다. native 파일 55개와 원 immutable 결과 hash는 최종 거부 후에도 모두 동일하다. transport 오류를 QA 결과 변경이나 native 결과 재조회 성공으로 기록하지 않는다.

v4의 원래 Work·request·owner decision·approval·intent·dispatch-intent·result-ref와 예약을 보존했다. Claude의 native execution-attempts 디렉터리는 읽기 관측 시 없었지만 이를 전체 부작용 부재나 종료 증명으로 해석하지 않는다. 같은 ID 또는 새 ID로 그 Work를 다시 실행·repair·reconcile하지 않았다. v5는 별도 Work/승인/정책이며 v4 승인 bytes를 교체하지 않았다.

Claude는 추가 QA 요청 뒤 Free 사용량 제한 UI에 도달했다. UI 표시 재개 시각은 2026-10-27 02:30 Asia/Seoul이었다. 유료 전환·계정 변경·예정 자동 재시도를 하지 않았다. 이후 사용자가 Claude 검증 종료를 명시했으므로 더 진행하지 않는다. 기본 read/claim/replay 성공을 QA 성공으로 바꾸지 않는다.

QA owner 계약의 raw job log 정책은 `DISCARD`, max_bytes=0, require_complete=false다. wrapper stdout/stderr·receipt·case 관측을 보존하되 raw job log 전체를 확보했다고 표시하지 않는다. 원래 owner/native 계약과 별도 helper/network/credential 권한은 구분했다.

## r7: 안전한 저장 결과 조회 해소 — 2026-10-27

- `execution_read(operation="stored_result")`는 project/Work/action/request 네 ID만 받는다. D2 공개 범위와 현재 D4 정확한 action/owner/asset pin을 모두 검사하며, 기존 `_admit(existing_only=True)`와 `_result`를 재사용한다. native command·subprocess·승인 적용·intent 생성·repair·fallback이 없다. 결과 누락/손상/철회/다른 ID는 차단하고, 기록된 COMMIT_UNKNOWN은 그대로 보존한다.
- 원본 JSON bytes를 bounded base64·SHA-256과 함께 반환한다. outer AVAILABLE/native_state_changed=false는 이번 읽기의 전달/효과이며 inner native_state_changed=POSSIBLE은 원 실행의 과거 기록이다. 현재 QA·acceptance·완료는 false로 구분한다. execution_request 자체의 실행 annotations/승인 검사는 변경하지 않았다.
- 원 QA 정책·승인 bytes는 수정하지 않았다. 새 producer hashes와 transfer pin만 반영한 별도 정책을 만들고 actions·grants가 원본과 정확히 같음을 확인했다. 읽기 ceiling을 적용한 launcher에서 모든 D4 action tool이 접근 불가하다. 새 권한을 추가하지 않았다.
- Codex `golem@golem-m7-history` **0.2.3**, 설치 cache `~/.codex/plugins/cache/golem-m7-history/golem/0.2.3`, runtime `r7/installed-runtime`. 파일 9개가 생성 원본과 byte 동일하며 inventory SHA `0dd10720aa3aea0c8f2bb487982a1d330324731d827dded9d74f231e5fa8b0d5`이다. 전체 inventory는 archive hash와 구분한다.
- 기존 대화는 새 서버를 노출하지 않아 호출 없이 NOT_RUN으로 남겼다. 새 실제 대화 **M7 Golem 0.2.3 읽기 전용 저장 결과 검증**, ID `01a17aac-b2b5-74a0-8678-f8e66e8a155d`에서 `golem-m7-history.golem_execution_read`를 정확히 **1회** 호출했다. turn `01a17aac-b3cd-7623-8989-aadb563fcbe8`, tool call `exec-137524be-0253-45c5-97df-a2a1b1484f82`.
- 원 project `m7-qa-codex-v5` / Work `example-work` / action `reviewed-qa-run-v5` / request `d08d14ff9137497c8d32e803c70a4321`의 **11,643 bytes**, SHA **`c09a431f9178777d2c0750cc007a673bec6a1468bd70bf0de01aa3c8202892cf`** 일치. 역사적 QA PASS, 이번 읽기 native_dispatch_performed=false. 실제 trace의 bytes를 원 immutable 파일과 대조했고, agent 진술만으로 판정하지 않았다.
- 원 QA Work **55개 파일**, mutation evidence **328개 파일**, 원본 저장소 baseline **897개 파일**의 hash가 유지됐다. Claude 주 설정/테스트 설정과 원 QA 정책도 그대로다. 기존 M7 Work의 실행 재호출·승인 적용·repair·commit/push는 하지 않았다. 허용된 회귀 suite의 별도 disposable Work 실행/승인과 구분한다.
- modern/legacy SDK에서도 성공·미존재 ID 차단·원본 hash 일치와 annotations/실행 도구 미노출을 확인했다. 단위 fixture는 파일 생성 및 native capture가 호출되면 실패하도록 검사한다. 정적 공격 fixture는 existing_only 해제·실행 분기 주입·미존재 차단 삭제를 검출한다.
- 중간 검증 로그의 sandbox AF_UNIX/shebang 문제, 테스트 대상/quote 불일치, 갱신 전 fixture hash 불일치를 보존했다. 원 검사를 완화하지 않고 짧은 격리 runtime·host 검증·정확한 snapshot과 fixture로 해소했다. 최종 결과는 성공 로그만을 근거로 집계한다.

## r8: Codex QA 결과 제출과 native 현재 완료 — 2026-10-27

현재 패키지는 Codex **0.2.5**, feature MCPB **0.1.8**이다. 5개 최종 archive는 `r8/final/artifacts`와 행렬의 `artifact_index`에 있으며 각 payload 81개다. task SHA-256은 `f377f2d3a1b9d30bcb6210c269234af2c68ea5bb51cfe0ca84a4bb7fb2af4fb4`이다. Claude 설치본은 기존 0.1.5를 유지했다.

| 단계 | 실제 client 근거 | native 결과 |
| --- | --- | --- |
| 기존 QA 결과 제출 | `golem-m7-finish-qa` / 대화 `01a17ab7-4355-74d1-a910-7348da1b1b6d`, request `d2c27ac77507433287d8cdc90ebdc220` | native renderer의 schema-5 qa-result r1, gen8, manifest `16aa89f980c4157167ce296df2acec1c29c1c02a703d2830dcc5a86d84769692`; 원 QA receipt 재사용 |
| completion 문서 | `golem-m7-finish-complete` / 대화 `01a17ac9-4e84-7b72-9a98-aac2c32210bd`, request `bd56f3b5f26e4c6196eeea72d6ed8db8` | completion r1, gen9, manifest `04755756a2ae31603ccf14c06332439c868f3f20bc8bdad9ac8616076cda2e37`; 후속 VERIFY_COMPLETION |
| native finalize | 같은 0.2.5 대화, request `b348e135e0e64dbf80139dae5593ca9f` | golem.completion.development.v1 / RECORDED, completion receipt `dc83b75b24e2b20abd1e3a65fde2f3f01572954d442777cb52f47e6577b9751c`; 후속 RECOVER_REPORT |
| 보고서 물질화 | 같은 대화, request `aa0175328de841cebad3f359629fc922` | sequence1 report `6ca30d5dc49fe4a00da9a2ce664b8a550dcaa0a5918eed50fc751d6d7562e5a4`; client stdout·Work 파일·CAS bytes 일치 |
| 현재 완료 조회 | 실제 client 마지막 completion_check 및 부모의 독립 read-only completion_check | inner DONE, acceptance_verified=true, generation9, completion_sequence1, QA CURRENT/PASS. outer AVAILABLE는 여전히 전달 상태 |

네 개 action은 각각 M2 approved_action_prepare → plan_read → action_confirm → 반환된 원 invocation의 **1회** 호출을 관측했다. 새 세션·claim·QA attempt·native 승인 적용은 없었다. 첫 QA 제출 대화는 스킬 파일 읽기에 read-only shell 1회를 사용해 자체 테스트 prompt의 더 엄격한 shell 제한과 불일치했다. Work/정책 쓰기는 없었으며 이후 prompt는 필요한 스킬 읽기를 명확히 허용했다. 이를 native 결과나 승인의 추가 근거로 사용하지 않는다.

이 DONE은 `m7-qa-codex-v5 / example-work / selection`의 선언된 합성 C gate와 전체 필수 문서 closure에 한정된다. parent가 수행했던 prepare/fix/finish와 client가 수행한 QA·등록·완료를 구분한다. 전체 Golem 제품/모든 API·다른 OS·독립 검토·Claude 완료를 뜻하지 않는다. issues=[]는 agent 선언이며 native predicate는 원 source/QA/gate/attempt/session/permission 조건을 그대로 적용했다.

### 시작 충돌 수정과 승인 경계

completion 전용 연결의 시작 실패는 실제 진단의 **REGISTRY_BUSY**였다. 단일 시작 지연만으로 해소되지 않았고, 후속 로그는 MCP 초기 연결 후 tools/list에서도 같은 read-lock 충돌을 보였다. 이를 native action 실패/재실행으로 처리하지 않았다. 중간 document/final/serial/ready 대화는 action 미호출 NOT_RUN 이력을 보존했다.

`integration_distribution_entry`는 configure 및 기존 lifecycle.participation 진입에서만 REGISTRY_BUSY를 기다린다. `integration_mcp.listed_tools`는 service.tools 메타데이터 조회만 기다리며 D2/D4 callback이 같은 helper를 사용한다. 각 단계는 monotonic deadline **5초**, 50ms 간격이며 반복 사이에서 deadline을 검사한다. 이미 진행 중인 파일 I/O를 강제 선점하는 전체 응답 시간 보장은 아니다. 다른 오류·pending·quota·stale·COMMIT_UNKNOWN은 기다리거나 재시도하지 않는다. 요청 handler와 native action은 이 loop 밖에 있다.

추가된 runtime 회귀 8건은 동일 owner pins 재검사, timeout, 비대상 오류, participation 해제, server 시작 이후 오류의 무재진입, metadata receiver/오류/한도를 검사한다. 정적 공격 회귀는 이 helper를 service.call로 바꾸거나 error whitelist·시간 한도·exception 범위를 확대하면 pin 갱신 후에도 차단한다. D4 `_admit`/`_mutate`, native parser/approval, core lock 구현은 r7과 byte 동일하다.

새 producer pin은 새 private 정책 파일에만 기록했다. 기존 native action/승인 bytes와 D2 grant는 그대로다. 최종 연결은 정확한 completion 문서/finalize/report 세 action만 허용하고 execution_request·helper·session획득은 노출하지 않는다. 이번 턴에 새로 만든 중간 연결 5개만 설치 identity와 설정 백업 후 지원 CLI로 철회했다. 기존 Golem, r5 QA 및 r7 history 연결은 유지했다. 참여 기록/증거를 삭제하거나 128개 한도를 올리지 않았다.

원 Work의 기존 **55개 파일**, 원 QA evidence **328개 파일**, 원본 저장소 baseline **897개 파일**의 SHA가 모두 유지됐다. Work에는 문서·완료 receipt/보고서용 **14개 파일**이 추가됐고 runner 표식은 여전히 `x`다. QA receipt/result bytes·host/decision pin·소스 19개 root 파일·Claude 설정도 유지됐다.

## M8 정적·fixture·회귀 정합성

| 검사 | 결과 |
| --- | --- |
| 최종 integration 전체 | **376 PASS / skip0**. r7 368건에 startup/metadata 대기 회귀8건 추가 |
| 최종 capability 전체 | **366 PASS / skip0**. startup 및 metadata helper 공격 회귀2건 추가 |
| native 계약 단위 | 이전 39 PASS 유지. native source/binary 동일 확인, r7에서 재실행하지 않음 |
| 현재 native D2 modern/legacy SDK | 9 PASS. 수정된 schema 포함 |
| 현재 native D4·QA·불확실성 SDK | 15 PASS. 기존 임시 QA 결과에서 읽기 경로의 subprocess 금지·Work hash 유지 추가 확인 |
| package/version 부분 | 26 PASS. 전체 integration과 중복이므로 합산하지 않음 |
| package entrypoint | 1 PASS |
| Setup/Work 공식 skill validator | 각각 PASS. 이전 PyYAML SKIP 해소 |
| repository/source-role 보고서 검사 | 16 PASS; 최종 문서 후 재검증 로그 별도 보존 |
| 현재 5 profile SDK stdio | 최종 runtime의 별도 disposable discovery fixture에서 profile/owner 교집합·공개 목록·미허용 Work 차단·helper/host 비활성 PASS. 기존 registry/Work/참여 기록에는 영향 없음. native Work E2E나 desktop으로 집계하지 않음. r7의 실제 Work 읽기 profile 관측은 별도 이전 근거로 유지 |
| 5 archive·설치 inventory | allowlist·asset·스킬·schema·import closure, 추가/private 파일 거부, 현재 source와 byte 재현 |
| 원장 고정 산출물 | 8개 byte 재현 일치 |
| 원장 대조 | source 552 / observation 2,282 / capability 1,187 / product surface 444, selected/repository blocker 0 |
| 도구 선언 | D2 43 / D4 37 / union 80. 노출은 profile와 현재 owner 정책의 교집합 |

r7 검사 source를 고정했다. execution_read 저장 결과 경로·D4 서비스의 existing_only 연결·읽기 annotations·Work skill을 수정하여 전체 integration/capability와 native D2/D4·5 profile·설치 bytes를 재검증했다. r6와 r7 runtime bytes가 동일하다고 주장하지 않는다. native 코드를 변경하거나 기존 M0~M6 검사·ID·거부 조건을 약화하지 않았다.

정적 생성기의 `client_e2e=NOT_RUN`, `native_execution_verified=false`는 그 명령 자체가 실행을 인증하지 않는다는 계약이다. 실제 M7 관측은 행렬의 해당 capability/case에만 연결하고 원장 전체를 실행 인증으로 바꾸지 않았다. 원격 CI·다른 OS·공개 release의 근거로 로컬 검사를 사용하지 않는다.

부모의 최종 native 읽기는 workspace sandbox에서 macOS `sysctlbyname` EPERM(`session.boot_identity_clock`)으로 한 번 실패했다. 원 진단을 보존하고 명시적인 host 권한으로 읽기 전용 state/next/완료 관측을 완료했다. Git의 DARWIN_USER_TEMP_DIR confstr 경고도 원래 stderr 거부 guard가 차단했으며, 정적 대조 역시 명시 host 환경에서 검사했다. 이를 Work 손상이나 native mutation으로 해석하거나 guard를 우회하지 않았다.

## 남은 의무·usage·보존

- facade delivery backlog 0, owner-management 83, unsupported 17을 유지한다. 대표 E2E 성공으로 owner83개 전체를 완료 처리하지 않는다.
- M5 task DAG scheduler, typed edge evidence acceptance, resource receiver broker, merge queue, integration workspace/fresh QA, target ref CAS broker, merge publication receipt는 NOT_IMPLEMENTED다.
- P7 self-contained runtime·전체 동적 closure·서명/trust root·정식 OS/host qualification·업데이트/유통은 미구현/미결이다.
- Linux/Windows·remote CI·Hosted/remote·실제 target merge·공개 배포는 NOT_RUN이다. task 외 profile의 desktop 검증과 이번 기록 밖의 다른 native CTest integration suite도 NOT_RUN이며, 39개는 선택한 native 단위 검사다. client가 직접 prepare/finish한 전체 흐름도 검증 범위 밖이다. 실행을 시도한 QA 실패를 NOT_RUN으로 숨기지 않는다.
- Codex usage는 명시적으로 만든 테스트 대화의 cumulative token_count만 기록한다. parent/Claude와 청구액 전체를 포함하지 않는다. cached input과 reasoning output은 다른 counter와 중복될 수 있어 합산하지 않는다. Claude usage와 양쪽 billing cost는 null/UNKNOWN이다.
- 개발 HEAD `2e690091a55f366d5f99580ee375fca7610f2f77`, 원본 HEAD `e583b17469c50edd1e18df90880df07940c77b69`를 유지한다. 원본 baseline 897개 파일의 SHA가 모두 일치하고 기존 `assets/Golem-codex-plugin.png` 수정도 보존했다. staging은 비어 있다.
- Claude 주 설정 파일은 원 백업과 byte 동일하다. 테스트 확장만 승인한 파일로 업데이트하고 정책 path/SHA를 UI로 선택했다. Codex의 의미상 config 변경은 이번 `golem-m7-*` 테스트 항목으로 한정한다. 생산 Work 전체를 읽어 전후 hash 조사한 것은 아니다.
- 테스트 Git fixture는 기존 개발 HEAD를 fetch/checkout하여 재사용했다. 이 durable C QA 준비에서 새 Git commit은 만들지 않았다. 기존 회귀 suite의 disposable fixture baseline commit과 개발/원본 commit을 구분한다. 개발/원본 commit/push·PR·공개 배포는 하지 않았다.
- 중간 테스트 plugin/cache와 launcher는 private 백업 후 지원 CLI로 철회·교체한다. process 정리는 명령 identity·PID·귀속을 확인하여 이번 작업의 transport만 대상으로 한다. 기존 사용자 process·native claim/lease·unknown 예약은 변경하지 않는다. 이번 후속 정리에서 명령 identity를 확인한 중간 transport 16개와 이전 launcher 2개의 실제 종료를 확인했다. 최종 plugin의 구성 상태와 process 수를 혼동하지 않으며, 이 정리로 현재 feature process 수를 추론하지 않는다. process 종료·lease 만료를 Work 완료나 unknown 해소로 표시하지 않는다.

초기 private-log mode 정리에서 신규 테스트 Work의 불변 파일 257개 mode에 영향을 준 실행 실수가 있었다. native dw_publish/CAS 생성 규칙으로 0400을 복원하고 모든 bytes/hash와 현재 status/next를 다시 대조했다. 생산/기존 사용자 Work에는 적용되지 않았다. private `test-file-mode-correction.json`에 보존했다.

최종 Codex 설치의 9-file inventory SHA는 `1510d2624385cd6dab35450ec23295843379ad0a04e3c3c3bb55782b90155d25`다. 이는 archive SHA와 구분되는 파일 inventory identity이며 실제 설치 bytes와 source를 대조했다. r6 당시 추가 테스트 plugin은 `golem@golem-m7-qa-reviewed` 한 개였다. r7에서는 이를 보존한 채 `golem@golem-m7-history` 0.2.3 읽기 전용 연결을 추가했다. 기본 검증용 skills 및 중간 release/QA/diagnostic plugin은 백업 후 철회했고 원래 Golem은 보존했다.

M7의 기본 두 client 흐름 및 Codex의 실제 QA·읽기 전용 동일 ID 조회·QA 결과 제출·현재 native DONE이 해당 범위에서 통과했다. Claude QA와 client/OS 전체 의무가 남으므로 전체 M7 완료로 선언하지 않는다. M8은 현재 macOS source/artifact·정적·fixture·회귀·관측 결과의 정합성 범위로 한정한다.

## 상세 증거 경로

- source 보고서: `/Volumes/Extreme SSD/golem-project/mcp-counter-semantics-src/docs/mcp-m7-m8-validation.{ko.md,json}`
- 현재 artifact/index: `/Volumes/Extreme SSD/golem-project/m7m8-validation-20261026/r8/final/artifacts/` (Claude 설치본은 r6 유지)
- 현재 private 행렬·trace·native 결과·보존: `/Volumes/Extreme SSD/golem-project/m7m8-validation-20261026/r8/private/`, 실제 최종 client 근거 `r8/final/current/`; 이전 r6/r7 실패와 조회 해소 이력 유지
- 원 로그·보존·회귀: `/Volumes/Extreme SSD/golem-project/m7m8-validation-20261026/private/`
- 불변 claim·v4 unknown: `/Volumes/Extreme SSD/golem-project/m7m8-validation-20261026/r5/private/{codex,claude}-v4/registry/`
- 수정 Codex QA·owner review·재생성 launcher: `/Volumes/Extreme SSD/golem-project/m7m8-validation-20261026/qa-stage-v5/`

원시 자료는 owner-private이며 공개 배포 대상이 아니다. synthetic identity와 무결성 hash만 공개 보고에 연결한다.


## r9 — Claude 보류 해제·0.1.8 업데이트·별도 Work 완료

이 절과 JSON의 `qa_fresh_v9`가 최신 Claude 판정이다. 앞의 보류/NOT_RUN/COMMIT_UNKNOWN 기록은 당시의 역사적 결과로 보존한다. 기존 UNKNOWN의 성공 전환이나 재실행으로 해석하지 않는다.

- 실제 client: Claude Desktop 3.6556.2, Free, Sonnet 5.5 medium. 대화 [Claude Desktop M7 QA 격리 실행](https://claude.ai/chat/3138e426-e0df-41a2-87e2-cc1e0e33e85a).
- task 0.1.8 SHA-256 `f377f2d3a1b9d30bcb6210c269234af2c68ea5bb51cfe0ca84a4bb7fb2af4fb4`. 사용자의 해당 파일 업데이트 확인을 받고 실제 Update/Install을 적용했다. 설치 archive 82개 엔트리(81개 payload와 package inventory)가 승인 파일과 전부 일치했다.
- 새 project `m7-qa-claude-v9`, Work `example-work`, selection `selection`. 새 registry와 새 Work를 생성했고 이전 Work를 복제하지 않았다. parent가 pre-fix C 실패 재현·native prepare·수정·finish를 수행했다. 실제 Claude는 QA 실행과 후속 문서/완료 절차를 수행했다.
- 처음 준비 스크립트가 native approval action의 키 순서를 재정렬해 승인 host가 `policy denied`로 거부했다. 해당 요청/거부 capture는 미승인 PENDING으로 보존했다. native describe의 순서를 그대로 담은 별도 요청을 기존 host로 승인했다. native parser/승인 조건을 바꾸지 않았다. 실제 dispatch의 native bytes와 action pin은 M2 준비 및 승인한 bytes와 동일했다.
- 각 action마다 Claude의 approved_action_prepare → plan_read → action_confirm을 새로 거쳤다. 준비/확인은 `execution_authorized=false`, `approval_created=false`다. M2가 제안한 wrapper request ID와 owner가 선택한 실제 ID는 별도로 기록했고 native action/body/승인 pin은 같음을 파일 SHA로 대조했다.
- 모든 Claude 도구 허용은 1회였다. 항상 허용·승인 검사 완화·helper/host/resource 권한 추가는 없었다. QA 이후 연결을 결과 제출 전용, 최종 완료 전용 정책으로 재로딩해 execution_request 노출을 제거했다.

| 단계 | 실제 결과 |
| --- | --- |
| 새 QA 실행 | 정확한 action/request 1회, NATIVE_RESULT_RECORDED, 두 declared case PASS, exit 0, runner marker `x` |
| 저장 결과 재조회 | execution_read/stored_result 동일 ID 1회 성공. execution_request 재호출 없음 |
| receipt 검증 | verify·verify_authorized 각각 읽기 1회. hash/무결성과 진실성·provider 인증은 구분 |
| QA 결과 문서 | native renderer/schema 5와 native parser 사용, document_submit 1회, generation 7→8. 현재 QA CURRENT/PASS |
| completion 문서 | 검증한 고정 문서 action 1회, generation 8→9. 다음 native action VERIFY_COMPLETION |
| finalize | 정확한 selection/key/generation/issues 고정 action 1회. native 완료 receipt 기록 |
| report | sequence 1 보고서 물질화 1회. Work/CAS/immutable native reply/readonly inspect bytes 일치 |
| 최종 현재 조회 | DONE, acceptance_verified=true, generation 9, completion_sequence 1. session sequence와 다른 카운터를 섞지 않음 |

새 QA receipt는 `0003d3446cbd14dea7dcc8163ab99aef10a52f3368e88a936c96ce0ffde55851`, completion receipt는 `c1e2324980fd71f0fa97a98c1719554734f4a363bb7612b35b47bfc3c51a22f4`, report digest는 `e788c4a2ce553a752c9e3aee694ac42e0e617799187a45529968f4f7a3754838`다. native predicate는 `golem.completion.development.v1`, independent_review=false이며 declared synthetic gates 범위다.

최신 설치본에서 실제 존재하는 Codex synthetic DONE Work(m7-qa-codex-v5/example-work)의 status 조회를 Claude task로 1회 시도했다. 펼친 실제 tool Error 원문은 TRANSFER_SCOPE / NOT_DISPATCHED / native_state_changed=false였고 NOT_FOUND가 아니었다. 해당 Work의 원파일 69개 hash는 그대로다. 다른 Golem 서버로 우회하거나 재시도하지 않았다. 도구로 이미 전달된 gate 값 duration_ms=2405, stdout_size=95, stderr_size=0, cases=2로 계산한 `(duration_ms mod 1000)+stdout_size-stderr_size+cases`의 agent 응답은 502이며 immutable native 값의 독립 계산과 일치했다. 프롬프트에 수치나 정답을 제공하지 않았다. 도구 입력 의존의 한 사례만 관측한 것이며 내부 이해/진실성을 인증하지 않는다.

task transport의 실제 tools/call metadata는 총 30회다(projects_list 1, M2 준비/읽기/확인 15, 정확한 D4 action 5, execution_read 3, completion_check 5, scope 거부 work_inspect 1). 실제 설치된 .venv Python process와 uv parent를 식별했고 canonical interpreter는 uv의 CPython 3.11.14, 해당 .venv의 MCP distribution은 2.3.0이다. native QA gate는 별도 pinned Homebrew Python 3.14.7과 C compiler를 사용했다. 승인된 task MCP server는 의도적으로 활성 상태로 남겼고 gate는 reaped=true다. 추가 candidate/helper host를 시작하지 않았다. Codex의 qa-reviewed 0.2.2/history 0.2.3/finish-complete 0.2.5와 원래 두 client Golem 연결을 보존했다.

실제 UI의 정확한 도구 인자와 성공 trace, task transport의 method/id/result metadata, immutable native 결과, 서버의 receipt/완료 read delivery, 독립 native current 조회를 대조했다. Claude 기본 logger는 전체 tool payload를 저장하지 않아 raw client 응답 bytes 전체의 별도 복사/해시 일치는 주장하지 않는다. 저장 결과 재조회 성공은 실제 UI에서 관측했고 원 immutable 결과 hash를 대조했다. Claude native Skills 자동 로드는 관측하지 않았고 manifest/tool 안내를 사용했다. usage·비용은 확보되지 않아 null/UNKNOWN이다.

M8은 같은 source inventory에서 원장 8개·패키지 5개 재생성 일치를 재확인했다. 552 sources / 2,282 observations / 1,187 capabilities / 444 surfaces / D2 43 / D4 37이다. selected/repository/delivery blocker는 0이고 owner backlog 83·unsupported 17은 유지했다. 현재 승인·불확실성·읽기 재조회·M2·패키지/재로딩 회귀는 96개 고유 검사 PASS다. 최초 96개 중 CLI 미지정으로 skip한 1개는 명시 CLI의 순수 validator 검사로 보완해 미해소 skip은 0이다. 기존 r8 전체 integration 376 / capability 366 / native SDK D2 9·D4 15 / repository/source-role 16 결과는 같은 source hash의 기록으로 보존했으며 r9에서 전체를 재실행했다고 표시하지 않는다.

기존 UNKNOWN evidence 100개·Work 44개·policy/action/decision 각 1개, Codex DONE Work 69개와 원본 저장소 897개 원파일의 SHA가 그대로다. Claude main config와 원본 Golem 연결을 보존했고 테스트 extension policy/digest만 새 scope로 전환했다. native src/include, 양쪽 HEAD·staging, Codex QA marker `x`, 새 Claude QA marker `x`를 대조했다. 기존 UNKNOWN은 계속 미해결이며 새 Work 성공으로 해소되지 않는다. 전체 생산 Work를 전수 inventoried했다고 주장하지 않는다.

Linux/Windows/remote CI/Hosted, 실제 target merge, public distribution, 실제 desktop가 수행하는 prepare/finish, task 이외 profile의 desktop 종단 검증, 서명/trust root 및 기존 M5/P4/P5 미구현 범위는 계속 NOT_RUN 또는 NOT_IMPLEMENTED다. commit/push는 수행하지 않았다. 세부 실행 ID·hash·검사·보존 원장은 JSON의 `evidence_paths_r9`와 `r9-claude/private/validation-matrix.json`에 있다.

문서 갱신 후 현재 repository/source-role 검사 16개도 PASS(skip 0)였다. Claude UI의 공유 5시간 한도 90% 이상 사용 배너를 관측했으며, 이 비율을 해당 테스트의 token·비용으로 환산하지 않았다. 정상 모델 호출은 마지막 입력 의존/권한 차단 확인 뒤 추가하지 않았다.


## 검증 후 설치 정리와 개발 규칙

2026-10-27 사용자가 각 client에 검증된 최신 Golem만 남기도록 별도 요청했다. Codex는 `golem@golem-m7-finish-complete` 0.2.5만 남기고 구 plugin 3개·오래된 marketplace 17개·비활성 direct MCP `golem`을 지원되는 관리 기능으로 제거했다. Claude Desktop은 구 Golem 0.1.3을 UI에서 제거하고 Golem task 0.1.8만 남겼다. 남긴 설치 bytes와 최신 Claude 설정은 그대로다. 이전 절/JSON의 설치 보존 내용은 M7/M8 검증 당시의 역사적 관측이다. 현재 목록은 workspace의 `.golem-plugin-installations.json`을 따른다.

제거 전 프로그램/설정 복구 자료를 owner-private `m7m8-validation-20261026/cleanup-latest-20261027/private`에 보존했다. 기존 COMMIT_UNKNOWN evidence 100개·Work 44개·승인 policy/action/decision, Codex DONE Work 69개·새 Claude DONE Work 71개의 원파일 hash가 모두 동일하다. 권한·정책 범위는 이전하지 않았고 Work 실행/모델 호출/commit/push도 하지 않았다. 공식 Codex CLI가 무관한 `node_repl.args=[]`를 기본 빈 인자 목록의 생략 형태로 직렬화한 한 건을 별도 기록했으며 다른 유효 설정은 동일하다.

후속 사용자 지시에 따라 workspace 공통 `AGENTS.md`와 `CLAUDE.md`에 개발 시작·설치 변경·종료 시 최신 검증본 한 개 유지, 중복 정리, 실제 bytes/권한/보존 검사와 원장 갱신을 필수 규칙으로 추가했다. 설정·원본·승인·evidence 삭제로 검증/정리를 성공 처리하거나 미검증 버전을 최신본으로 승격하지 않는다. 자세한 정리 결과는 `m7m8-validation-20261026/cleanup-latest-20261027/summary.json`에 있다.
