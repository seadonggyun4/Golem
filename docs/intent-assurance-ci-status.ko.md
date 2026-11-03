# Intent QC CI 반영 상태

상태: VALIDATION_IN_PROGRESS. 설치·실사용 승인으로 해석하지 않는다.

2026-11-03 사용자 선택으로 기존 실행 HOLD를 **새 격리 CI fixture와 의존성 설치**에 한해 해제했다.
기존 TopSolar·정책·승인·Work·증거와 Codex/Claude 설치·실제 client E2E는 변경하지 않는다.

## CI 변경

- Intent schema/fixture 변경을 native·Python·integration 선택에 연결한다.
- release native job에 별도 QC 빌드, QC 단위/정상/crash/경합 및 D01 writer 검사,
  pure schema/golden 검사와 collector 회귀를 추가한다.
- jsonschema 4.23.0 고정 의존성을 사용하고 QC JUnit/JSON 결과를 artifact로 보존한다.
- 기본 CMake opt-in은 OFF로 유지한다. 실제 ENOSPC disk-image는 자동 CI에 추가하지 않았다.
- 기존 capability/보안 검사와 CI Ready 판정을 약화하지 않는다.

## 확인된 수정

- QA 내부 헤더의 execution 응답 타입 include 누락 수정.
- macOS fixture의 mkdtemp 선언과 JSON deep-copy 목적지의 해제 후 초기화 수정.
- object-only native JSON parser에 배열/scalar root를 전달하던 단위 fixture 수정.
- v3 fixture에 필수 native runtime profile을 추가.
- v3 문서 기반 실행은 앞선 exact product gate를 통과한 경우만 허용한다.
  기존 session이 있으면 token/live/current 검사, token만 전달한 미등록 세션은 거부한다.
- pending authority 조회가 거부되는 실제 계약을 fixture 기대 결과에 반영.

## 결과와 남은 차단

로컬 빌드 성공. 정상 QC7 단독 실행 성공. schema/golden 324개 비교 및 collector 6개,
Intent MCP 경계 10개 회귀 성공. schema 전체 문맥 coverage는 별도 PARTIAL이며
schema runner의 종료 성공을 모든 native/host/E2E 검증 완료로 승격하지 않는다.

최초 병렬 QC 32개 실행은 27개 성공/5개 실패였다. 두 fixture 결함은 수정했고,
나머지 정상 흐름·observation 경계는 새 격리 Work에서 순차 재확인한다.
원래 실패/시간초과 자료는 삭제하지 않는다.

초기 capability 원장은 새 QC MCP 소스와 source/function 지문 불일치로 차단됐다.
후속 소스 대조에서 QC 실행 소스 18개와 문서·fixture 368개를 구분하고, 새 MCP 도구
3개의 제공 경로·권한·효과를 등록했다. 기존 API→schema 인자와 경로를 보존했고,
추가된 exact Intent host 동의·action·읽기 제한 및 QC3 publication 계약 검사를 보강했다.
선택 capability와 repository 대조는 모두 차단 0개다. 이는 정적 목록 정합성 결과이며
실제 설치·client E2E·기존 Work의 QA 수락을 인증하지 않는다.

후속 확인: 최초 실패 5개를 수정 후 새 fixture로 순차 실행한 결과 **5/5 통과**했다.
기존 실패 기록은 그대로 보존했다. 이는 최초 병렬 실행을 소급 PASS로 바꾼 것이 아니다.
main `e8f6c936d6acbaf4587895714f05cf7cec8de0bc`의 GitHub CI run
`41603004340`이 시작된 것을 확인했다. 전체 원격 CI 통과 및 capability 원장 정합성은
아직 확인되지 않았으므로 설치 차단 상태를 유지한다.

## 후속 원장 검토 범위

- `intent_product_host.inc`를 실행 소스로 명시해 fixture 제외 경로로 빠지지 않게 한다.
- v3 publication의 `gi_product_record`는 고정 선언·정의·인자와 필수 guard를 대조하는
  한정 계약 경계다. 임의 private 함수·callback을 허용하지 않으며 callee 실행 성공은 주장하지 않는다.
- 깨끗한 validation source export에 고정 host include·MCP 모듈·QC2 native fixture를
  명시적으로 포함한다. 임의 include/fixture 제외 검사는 유지한다.
- capability 회귀 375개가 통과했다.
- 해시를 다시 맞춰도 owner 동의·exact action·read-only 제한 또는 native record guard를
  제거하면 회귀 검사가 차단한다. 기존 M0~M6 부정 검사는 유지한다.
- 기존 85개 도구에 Intent 조회 1개·exact action 2개가 추가돼 정적 선언은 88개다.
  설치 정책·producer pin은 갱신하지 않는다.
- 초기 원격 전체 실행 `41603099168`은 M0 단계에서 실패했다. 이후 커밋의 실제 결과는
  [GitHub CI 기록](https://github.com/seadonggyun4/Golem/actions/workflows/c.yml)에서
  해당 source SHA로 대조한다. 과거 실패를 소급 성공으로 변경하지 않는다.

## Linux·Python CI 후속 수정 (2026-11-03)

전체 run `41605798265`의 M0 대조는 통과했으나 Linux 빌드는 GCC의
`-Werror=misleading-indentation`, Python은 Intent host의 공통 실행 기록 우회와
기본 비활성 host 인자 기대값 누락으로 실패했다. 실패 기록은 보존한다.

- QC C/header/include 48개는 서식만 정리했다. 전후 C 토큰의 동일성을 확인했으며
  경고 억제·컴파일 옵션 완화는 하지 않았다. byte pin만 해당 새 bytes에 맞췄다.
- Intent host는 `execution_record.run_private`로 실행한다. 정확히 선택한 두 FD만
  전달하고 D01 lock·등록 bridge pin·review root identity·종료 후 최신성 검사를 유지한다.
  stdout/stderr와 입력을 동시에 처리해 큰 packet의 pipe 교착을 방지한다.
- 제한 시간·출력 한도·자식 정리와 불확실 결과 보존을 유지한다. 실행 기록을
  권한이나 성공 증명으로 해석하지 않으며 자동 재시도는 추가하지 않았다.
- 양방향 대용량 packet·실행 후 stale·FD 검증·spawn 실패 기록 회귀를 추가했다.
  Intent host 기본값 `None` 검사는 새 인자를 포함해 명시적으로 검사한다.
- 선택 capability와 전체 repository 정적 대조는 차단 0개다.
  전체 Python/native 및 새 원격 CI는 진행 중이며 완료 전 PASS로 표시하지 않는다.

설치된 Codex·Claude 프로그램, launcher, owner 정책과 producer pin은 갱신하지 않았다.
실제 client/Work 검증 HOLD는 계속 유지한다.

후속 fixture 확인: QC native 32/32, capability 375/375, 새 실행 기록/FD 경계
14/14, schema/golden 및 collector 6개가 통과했다. 전체 Python 첫 실행의
4개 실패는 서식 변경 후 변조할 원문을 찾지 못한 fixture 결함이었다.
공백 차이를 허용하되 실제 토큰 변경과 기존 guard 거부 assertion은 유지했다.

원격 `bffd48c` 검증에서 추가로 확인한 Linux POSIX 선언 순서를 수정했다.
`document/registry.c`와 `candidate/controller.c`의 feature macro를 모든 include
앞으로 옮겼으며 POSIX guard를 제거하지 않았다. macOS 진단에서 검출한
QC5 renderer 1개와 guarded/legacy 대체 publication을 정확한 목록에 반영했다.
새 QC3/QC4 writer 두 개도 prepare/publication 개수를 각각 검사한다.
전체 최신 원격 CI의 최종 판정은 아직 진행 중이다.

추가 로컬 결과: 전체 Python 1,542개, 실패 0개, 기존 opt-in skip 188개.
D2-only MCP fixture는 QC6 host가 없으므로 `intent_read` 미노출을 명시적으로 검사한다.
modern/legacy stdio와 폐기 후 차단을 포함한 해당 9개 검사는 통과했다.
이는 합성 Work의 로컬 protocol 검사이며 Codex·Claude Desktop 설치/E2E가 아니다.
