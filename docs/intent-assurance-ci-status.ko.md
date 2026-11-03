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

기존 capability 원장은 새 QC MCP 소스와 source/function 지문이 불일치한다.
이는 release 차단이며 검사 제거·무조건 repin·기존 설치 policy pin 갱신으로 해소하지 않는다.
따라서 현재 소스를 "전체 CI 통과" 또는 "설치 준비 완료"로 표시하지 않는다.
