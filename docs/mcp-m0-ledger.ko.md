# M0 operation 목록·누락 검사

상태: **M0 전수 정적 inventory 출구 충족**. 최신 근거는 §6.19와 재계산 보고서다. 실제 E2E·제품 전체 MCP 제공 완료는 아니다.
작성·조사일: 2026-10-26. 기준 native/integration 소스: `2e69009`.
상위 범위는 [통합 계획](mcp-full-coverage-plan.ko.md), 최초 입력은
[정적 소스 목록](mcp-capability-inventory.ko.md)을 따른다.

## 1. 채택과 미결

- COV-D01: 일상 작업 typed MCP와 owner 관리 경로 분리 — 채택.
- COV-D02 첫 결정: 버전 있는 닫힌 JSON, 소스 관측/검토 분류 분리, Markdown 생성 — 채택.
  미분류·미확인은 최종 coverage gate에서 실패시키고 ledger는 권한 설정으로 사용하지 않는다.
- COV-D02 두 번째 결정: §3의 닫힌 필드 구성 — 2026-10-26 사용자 채택.
- COV-D02 세 번째 결정: §3.1 기본 타입·내부 참조 — 2026-10-26 사용자 채택.
- COV-D02 네 번째 결정: §3.2 분류 값·미확인 처리 — 2026-10-26 사용자 채택.
- COV-D02 다섯 번째 결정: §3.3 설명·효과·근거 타입 — 2026-10-26 사용자 채택.
- COV-D02 여섯 번째 결정: §3.4 JSON decoder·입력 한도 — 2026-10-26 사용자 채택.
- COV-D02 일곱 번째 결정: §3.5 관측 ID·안정적 capability ID — 2026-10-26 사용자 채택.
- COV-D02 여덟 번째 결정: §3.6 명시적 소스 읽기 경계·용량 — 2026-10-26 사용자 채택.
- COV-D02 아홉 번째 결정: §3.7 한정 정적 profile·미해석 차단 — 2026-10-26 사용자 채택.
- COV-D02 열 번째 결정: 명시 선택 근거 파일 확인·실행/충분성 분리 — 2026-10-26 사용자 채택.
- COV-D02 열한 번째 결정: Python 직접 함수·메서드 선언 확인 — 2026-10-26 사용자 채택.
- COV-D02 열두 번째 결정: 명시적 Markdown 앵커 확인 — 2026-10-26 사용자 채택.
- COV-D02 열세 번째 결정: 기존 실행 기록의 명시적 연결부터 채택 — 2026-10-26.
- COV-D02 열네 번째 결정: 조사한 기존 기록 형식을 각각 구분해 지원 — 2026-10-26 사용자 채택.
- COV-D02 열다섯 번째 결정: 명시적 상대 이름→원본 bytes 입력·자동 조회 금지 — 2026-10-26 사용자 채택.
- 입력 한도·연결 필드·판정·근거 충분성·최종 gate는 미결이다.
  현재 보조 코드의 Python 반환값은 내부 값이며 승인된 JSON wire/store 형식이 아니다.

## 2. 조사 근거와 적용 한계

| 근거 | 직접 확인 범위 | 채택 이유·구현 대응 | 한계 |
| --- | --- | --- | --- |
| [MCP Tools 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/server/tools) | tool schema·목록·authorization에 따른 subset·annotation 신뢰 규정 | 정적 선언 관측과 실제 tools/list를 구분. ledger가 권한이나 client 노출을 증명하지 않음 | 현 transport/profile을 교체하지 않음. server annotation은 집행의 대체가 아님 |
| [JSON Schema object](https://json-schema.org/understanding-json-schema/reference/object) | required/properties/additionalProperties 설명 | 명시 필드와 미지 필드 거부를 분리해 설계. JSON key 중복 검사는 decoder에서도 별도 필요 | schema만으로 source 의미·분류 진실성·권한을 보장하지 않음 |
| [NIST SP 800-218](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-218.pdf), PO.4·PW.7 | 검사 기준·정보 수집·검토/분석과 발견 기록 절 | 추출 사실·검토·검사 결과 분리, 누락을 triage할 근거 경로 유지 | 이 구현을 NIST 인증/전체 SSDF 준수로 표시하지 않음 |
| D. L. Parnas, [On the Criteria To Be Used in Decomposing Systems into Modules](https://doi.org/10.1145/361598.361623), CACM 15(12), 1972; [대학 제공 재인쇄](https://www.cs.lafayette.edu/~gexia/cs301/resources/parnas.html) | ACM 초록·대학 HTML 재인쇄 본문 | 추출기·검토 분류·표시·권한 집행을 독립 모듈로 유지 | 대학 재인쇄는 원본과의 정확한 일치 보증이 없다고 고지됨. 성능 개선 증거로 사용하지 않음 |
| P. Ammann, J. Offutt, *Introduction to Software Testing*, 2nd ed., Cambridge, [출판사 공개 frontmatter](https://assets.cambridge.org/97811071/72012/frontmatter/9781107172012_frontmatter.pdf), [저자 목차](https://www.albany.edu/faculty/offutt/softwaretest/contents.html) | 공개 서문·목차의 criteria/model/coverage/oracle 구성. 유료 본문 전체는 읽지 않음 | 선언 수·모델 coverage·행동 적합성을 구분. 독립 기대값과 추가/삭제/변경 fixture 사용 | 16개 테스트를 모든 branch/operation의 완전성으로 일반화하지 않음 |
| Y. Jia, M. Harman, *An Analysis and Survey of the Development of Mutation Testing*, IEEE TSE 37(5), 649–678, 2011, [DOI](https://doi.org/10.1109/TSE.2010.62), [논문 재배포 PDF](https://kelloggm.github.io/martinjkellogg.com/teaching/cs684-sp24/assets/mutation-testing.pdf) | 검색 제공 초록·서지·첫 페이지 발췌. DOI/저자 URL 접근 실패, 큰 PDF 본문 열기 실패 | 의도적으로 새/삭제/변경 selector를 넣어 탐지 여부를 확인하는 한정 민감도 검사 | 전체 논문을 읽었다고 주장하지 않음. 정식 mutation score·equivalent mutant 분석·전체 검증은 수행하지 않음 |

위 근거는 구조 선택과 시험 설계의 참고다. 새로운 제품 승인·지원 OS·client 기능·
자동 정책 갱신의 근거가 아니다. 인용 문헌의 실험 수치를 Golem 효과로 가져오지 않는다.

## 3. 채택된 ledger 필드 구성

다음 닫힌 필드 집합은 사용자가 채택했다. 버전 이름 `golem.mcp-capability-ledger.v1`은
§3.1에서 함께 채택됐다.
현 core schema/domain registry에는 등록하지 않으며 CAS·native journal 형식과 무관하다.

| 객체 | 채택된 필드 | 의미 |
| --- | --- | --- |
| root | schema, sources, observations, capabilities | 소스 사실과 검토 분류를 분리 |
| sources 항목 | path, sha256 | 저장소 상대 source 경로와 검토한 bytes hash |
| observations 항목 | id, kind, source_path, entrypoint, selector | 어느 파일·함수/명령/선언에서 무엇을 관측했는지. selector 없는 진입점은 §3.1에 따라 null |
| capabilities 항목 | id, observation_ids, implementation, current_routes, target_routes, authorities, effects, constraints, test_refs, doc_refs, review_status, rationale | 실제 구현·현재 경로·목표를 분리. 권한/효과/한도는 검토한 설명이지 실행 설정이 아님 |

`current_routes`에 없지만 `target_routes`에 있는 MCP 경로는 제공 완료로 세지 않는다.
observation은 사실 수집이며 capability 분류·구현 완료·권한 판단을 자동 생성하지 않는다.
sources hash 변화는 재검토 사유이지 malicious drift나 의미 변경의 확정은 아니다.
line number는 편의상 표시할 수 있으나 stable identity로 쓰지 않는 안을 제안한다.

필드 구성 이후 기본 타입/참조·분류·metadata·입력 한도도 §3.1–3.4에서 채택됐다.
관측 ID는 §3.5를 따른다. 한정 scan profile은 §3.7에서 채택했으며 실제 근거 검증은 미결이다. 전수 coverage validator·auto writer는
추가하지 않는다.

### 3.1 채택된 기본 타입과 내부 참조

사용자가 “기본 타입·내부 참조 규칙 채택”을 선택했다. 아래 규칙만 기본 검사로 구현한다.

- schema는 문자열 상수 `golem.mcp-capability-ledger.v1`, sources/observations/capabilities는
  객체 배열로 한다. 채택된 객체 필드는 모두 필수이며 unknown field는 거부한다.
- sources의 path는 비어 있지 않은 POSIX 저장소 상대 경로로, 절대 경로·역슬래시·
  `.`/`..` 경로 요소·빈 경로 요소를 거부한다. 자동 정규화하지 않는다.
  sha256은 소문자 64자리 SHA-256 문자열로 한다. source path 중복을 거부한다.
- observation/capability id와 observation.entrypoint는 비어 있지 않은 문자열로 한다.
  id는 각 배열 안에서 유일하며 생성·변경 규칙은 §3.5를 따른다. 서로 다른 이름공간의
  id를 전역적으로 합치지 않는다. source_path는 sources.path 중 하나와 정확히 일치해야 한다.
- selector는 비어 있지 않은 문자열 또는 null로 한다. null은 하위 selector 없는 진입점을
  뜻하며, 파악하지 못한 operation을 null로 숨기는 용도가 아니다.
- observation_ids는 observation.id의 중복 없는 문자열 배열로 한다. 없는 id 참조는
  거부한다. 배열 순서는 보존하고 자동 정렬·중복 제거하지 않는다.
- 빈 배열은 구조상 허용하되 coverage 완료를 뜻하지 않는다. 실제 필요한 범위와 미분류
  검사는 별도 gate로 정한다. ledger 문자열/항목 한도는 §3.4를 따르며 source 파일 읽기
  경계/한도는 §3.6을 따른다. 실제 추출 profile은 아직 미정이다.

kind/implementation/route/review enum은 §3.2에서 추가로 채택됐다.
metadata 타입·ledger 한도는 §3.3–3.4에서 추가 채택됐다. source 추출 profile·한도는
별도로 확인한다. 이 기본 타입 결정도
새 권한이나 자동 실행·파일 탐색·설치를 승인하지 않는다.

### 3.2 채택된 분류 값과 미확인 표시

사용자가 “제시한 분류 값·미확인 처리 채택”을 선택했다. 아래 타입·값을 검사하되
자동 분류하거나 구현 완료·권한을 추론하지 않는다.

| 필드 | 채택된 타입·값 | 의미 |
| --- | --- | --- |
| observation.kind | 문자열: C_PUBLIC_DECLARATION, CLI_ROUTE, NATIVE_OPERATION, PYTHON_DECLARATION, MCP_TOOL_DECLARATION, UNRESOLVED | 검토한 추출 종류. 미해석 항목은 UNRESOLVED로 보존 |
| capability.implementation | 문자열: UNVERIFIED, IMPLEMENTED, PARTIAL, PROPOSED, UNSUPPORTED | native 구현 여부와 실제 MCP 제공 여부를 분리 |
| current_routes / target_routes | 중복 없는 문자열 배열: MCP_READ, MCP_REVIEWED_ACTION, OWNER_ONLY, HOST_INTERNAL | 현재/목표를 분리. PROPOSED_NOT_IMPLEMENTED는 route 대신 implementation=PROPOSED와 실제 current_routes로 표현 |
| review_status | 문자열: UNREVIEWED, REVIEWED | 목록 분류의 검토 여부. 인증된 issuer·독립 검토 증거가 아님 |

UNRESOLVED/UNVERIFIED/UNREVIEWED는 최종 coverage gate를 차단한다.
빈 route 배열은 알려진 현재 경로가 없다는 표현으로 허용하되 제공 완료를 뜻하지 않는다.
PARTIAL/PROPOSED/UNSUPPORTED를 전체 제공 완료에 합산하지 않는다. REVIEWED라고 해도
source 무결성·참조·실제 제공 경로·시험 근거가 부족하면 gate를 통과하지 못한다.
이 값만으로 구현 상태나 권한을 자동 결정하지 않는다. metadata 타입·ledger 한도는
§3.3–3.4를 따르며 최종 gate의 판정 계약은 후속 결정이다.

### 3.3 채택된 설명·효과·근거 필드 타입

사용자가 “설명·효과·근거 타입 채택”을 선택했다. 아래 구조를 검사하되
실제 권한·효과·시험 결과로 승격하지 않는다.

| 필드 | 채택된 타입·구조 | 경계 |
| --- | --- | --- |
| authorities | 중복 없는 비어 있지 않은 문자열 배열 | 권한 주체/계약의 설명 label. token/grant/issuer 인증이나 허용 설정이 아님 |
| effects | 중복 없는 문자열 배열: NATIVE_READ, NATIVE_WRITE, AUDIT_WRITE, DISCLOSURE, PROCESS, NETWORK, GIT, CLEANUP, UNVERIFIED | 여러 효과를 함께 표시. UNVERIFIED는 최종 coverage gate 차단 |
| constraints | 닫힌 객체: platforms, limits, notes | platforms/limits는 중복 없는 비어 있지 않은 문자열 배열, notes는 비어 있지 않은 문자열. 설명이며 OS 인증·실제 limit 설정이 아님 |
| test_refs | 닫힌 {path, selector} 객체 배열 | path는 source와 같은 상대 경로 규칙, selector는 비어 있지 않은 문자열 또는 null. 같은 (path, selector) 중복 거부 |
| doc_refs | 닫힌 {path, anchor} 객체 배열 | path는 같은 상대 경로 규칙, anchor는 비어 있지 않은 문자열 또는 null. 같은 (path, anchor) 중복 거부 |
| rationale | 비어 있지 않은 문자열 | 현재/목표 경로와 분류의 검토 이유. 내용에서 실행 권한을 생성하지 않음 |

배열 자체는 빈 배열을 허용하고 순서를 보존한다. 비어 있지 않은 문자열은
개별 문자열 조건이며 배열의 최소 원소 수 조건이 아니다. 빈 metadata는 근거 검증이나
제공 완료를 뜻하지 않는다. 참조만으로 파일 존재·test 실행·성공을 인증하지 않는다.
파일을 자동 읽거나 selector를 실행하지 않는다. 전체 gate가 요구할 근거 충분성·미확인
constraints·범위 검사는 별도 결정이다. ledger 수치 한도는 §3.4를 따른다.

### 3.4 채택된 JSON decoder·ledger 입력 한도

사용자가 “제시한 decoder·입력 한도 채택”을 선택했다. 아래는 ledger 입력만의
채택 한도이며 기존 native control JSON·CAS·journal·D08 quota나 MCP 출력 한도를 바꾸지 않는다.

| 축 | 채택 한도 |
| --- | --- |
| raw JSON | UTF-8 bytes 최대 16MiB, BOM·invalid UTF-8·중복 key·고립 surrogate·비표준 NaN/Infinity 거부 |
| 중첩 | 컨테이너 깊이 최대 16, root object를 깊이 1로 계산. 문자열 내부 괄호 제외 |
| root 배열 | sources 4096, observations 16384, capabilities 4096 |
| 항목별 배열 | observation_ids/test_refs/doc_refs/authorities 및 constraints.platforms/limits 각각 256. effects/routes도 256 이하이며 중복 거부와 enum 제한 유지 |
| id | UTF-8 256 bytes 이하. 생성/rename 알고리즘 결정과 별개 |
| rationale·constraints.notes | 각각 UTF-8 16KiB 이하 |
| 나머지 문자열 | 각 UTF-8 4096 bytes 이하. sha256·schema·enum의 기존 제약도 유지 |

decode 전에 raw bytes·깊이를 검사하고 승인된 구조 검사와 필드 한도를 적용한다.
어느 한 축이 초과해도 자동 절단·중복 제거·상향·분할 없이 거부한다. 원문 source bytes를
정규화하거나 새 CAS hash로 바꾸지 않는다. 같은 자료의 decode 성공도 의미 검토·파일
존재·coverage PASS가 아니다. 파일 자동 탐색/읽기·source 추출 한도는 별도 결정이다.

채택 수치의 참고 관측: 기준 checkout의 추적된 include/src/tools/plugins/tests 안 C/H/Python
파일은 643개, 논리 bytes 합계 5,074,212, 가장 큰 파일은 150,601 bytes였다. metadata
단일 capability fixture JSON은 887 bytes였다. 이는 완성 ledger의 크기·메모리/처리시간·
향후 증가량 보장이 아니며, root 개수와 16MiB 중 먼저 도달한 한도가 적용된다.

### 3.5 채택된 관측 ID와 capability ID

사용자가 “전용 domain 관측 ID·안정적 capability ID 채택”을 선택했다.
아래 규칙의 순수 생성·검사 함수를 제공하되 기존 목록을 자동 재번호화하지 않는다.

- observation.id는 kind·source_path·entrypoint·selector 네 필드만 담은 객체를
  key 정렬·ensure_ascii=false·공백/끝 개행 없는 UTF-8 JSON으로 표현하고,
  ASCII domain `golem.mcp-observation-id.v1` + NUL + 그 JSON bytes의 SHA-256에
  `obs-`를 붙인 값으로 한다. 문자열·상대 경로를 정규화하지 않고 selector null과
  문자열을 구분한다. source의 내용 hash·줄 번호·배열 순서는 ID에 포함하지 않는다.
- source hash가 바뀌어도 같은 관측 identity는 유지하되, hash drift는 별도 재검토
  대상으로 차단한다. ID 유지가 옛 분류·검토의 유효성이나 실제 구현의 동등성을 뜻하지 않는다.
- capability.id는 검토자가 부여한 안정적인 문자열로 유지한다. observation을 단순히
  하나씩 capability로 만들거나 자동 재번호화하지 않는다. rename/split/merge는 명시적
  검토와 참조 갱신 대상이며 자동 migration하지 않는다.
- 이 domain은 M0 목록 식별 전용이다. 기존 native CAS·D08 object identity/domain registry·
  승인 token을 변경하거나 공유하지 않는다. ID 일치는 내용의 진실성·권한 인증이 아니다.

### 3.6 채택된 소스 읽기 경계와 용량

사용자가 “명시적 소스 범위·읽기 한도 채택”을 선택했다. 선택 파일 reader를 구현하되
재귀 discovery·source extractor·CLI/MCP 도구는 추가하지 않는다.

- 호출자가 명시한 단일 Golem repository root를 기준으로 한다. 고정된 읽기 전용 Git
  index 명령으로 추적 경로를 확인하며 fetch/checkout/hook/pager를 실행하지 않는다.
  상속된 GIT 환경은 기존 안전 환경 구성 원칙에 따라 전달하지 않는다.
- 실제 파일 읽기는 호출자가 명시한 상대 경로 목록으로 한정한다. Git 추적 경로 또는
  검토자가 명시적으로 선택한 신규 개발 파일만 허용하고, 다른 미추적·ignored 파일이나
  다른 프로젝트를 자동 탐색하지 않는다. 선택 파일이 존재한다고 승인 범위를 넓히지 않는다.
- .git/.golem/.codex, .env 계열, 활성 승인·registry·Work 상태·캐시/빌드 산출물은 source
  읽기 대상에서 제외한다. 제외·미지원 영역은 목록/최종 gate에서 명시하며 숨겨진 완료로 세지 않는다.
  공개된 추적 test fixture는 실제 운영 Work/승인과 구분한다. `tests/` 경로만으로
  fixture라고 추정하지 않고 `reviewed_fixtures` 명시 선택과 Git 추적을 함께 요구한다.
  caller가 알고 있는 `protected_paths`는 fixture/new 선택보다 우선 거부한다.
  이 목록은 trusted caller의 검토 입력이며 모델의 새 승인 또는 자동 비밀정보 탐지가 아니다.
- root와 모든 경로 요소의 symlink, regular file이 아닌 대상, 복수 hardlink를 거부한다.
  파일별 identity/size/변경 상태를 읽기 전후 확인해 drift/교체/읽기 실패 시 해당 scan을
  불완전으로 중단한다. 같은 UID 공격자에 대한 OS sandbox·원자적 전체 snapshot 보장은 아니다.
- 최대 4096개 파일, 파일당 원본 bytes 1MiB, 합계 원본 bytes 64MiB로 제한한다.
  하나라도 넘으면 읽기/결과를 완성됐다고 반환하지 않고 자동 절단·상향하지 않는다.
  기존 ledger JSON·native CAS·D08 한도와는 별도다. 누락 파일을 자동 복구하지 않는다.

이 결정은 파일을 읽을 수 있는 경계와 용량에만 한정한다. 어떤 C/CLI/Python/manifest
구문을 operation으로 추출할지, 미해석 영역을 어떻게 표시할지, 참조 근거를 충분하다고
판정할지와 최종 gate의 범위는 후속 결정이다. 어떤 파일도 실행하거나 승인으로 사용하지 않는다.

### 3.7 채택된 초기 정적 추출 profile

사용자가 한정 정적 profile·미해석 차단을 채택했다. 아래 범위의 내부 driver를 구현하며, 전수 ledger 생성·최종 coverage 판정은 활성화하지 않는다.

- 첫 profile은 정적 선언과 literal dispatch의 lexical 관측으로 한정한다. C public 함수
  선언, 명시 등록한 CLI/native dispatcher 함수·비교 식의 문자열 literal, Python의
  명시 top-level literal mapping/tuple/list를 tokenizer/AST로 읽는다. 비교 문자열이
  있다는 이유만으로 실행 가능한 operation이라고 추론하지 않는다.
- source 파일·entrypoint·subject/선언 규칙을 명시 등록하고, 등록되지 않은 파일·미해석
  구간은 UNRESOLVED 또는 불완전 scan으로 차단한다. 명시 검토 없이 HOST_INTERNAL로
  자동 제외하거나 새 operation을 지원한다고 표시하지 않는다.
- macro·alias·table/switch/enum dispatch·동적 등록·불명확한 schema-version 분기·전처리
  조건의 실제 빌드 의미는 초기 지원 밖이다. 주석·문자열의 가짜 호출을 배제하고,
  비지원 형태·모호한 결과를 빈 목록/완료로 처리하지 않는다.
- 동일 operation 이름이라도 API/CLI/schema-version·현재 권한·실제 client 노출의 동등성은
  별도 근거가 필요하다. 서로 다른 observation.kind를 근거 없이 변환하지 않는다.
- source hash drift나 parser 등록 누락은 재검토 대상이다. lexical 관측이 같은 것과
  이전 review가 유효한 것은 다르다. profile 밖 영역이 남으면 전체 coverage를 선언하지 않는다.

이 결정은 초기 추출 지원 범위만 정한다. 완전한 파일/entrypoint registry, helper별
미해석 구간 표시 방법, 실제 근거 충분성·최종 gate는 이후 구현·결정으로 남긴다.

## 4. 구현된 독립 보조 코드

[capability_source.py](../tools/capability_source.py)는 pure 함수만 제공한다.

| 함수 | 구현 | 명시적 비지원 |
| --- | --- | --- |
| c_comparison_values | 호출자가 지정한 C 식과 strcmp하는 literal 관측. comment/string 분리, 양쪽 인자 순서, 연속 일반 문자열 지원 | 전체 C parser/preprocessor 아님. macro/cast/alias 추론, switch/enum dispatch, JSON operation 자동 의미 해석 없음 |
| python_literal_names | AST로 단일 top-level literal mapping key 또는 tuple/list 관측. 프로그램 import·값 평가 안 함 | dynamic tools/list·후속 dict mutation·환경에 따른 등록 추론 안 함 |
| observation_difference | 명시 기대 이름과 관측 이름의 추가/삭제 비교. 중복·잘못된 입력 거부 | capability의 의미 검토·policy·실제 기능 coverage 판정 아님 |

C의 computed comparand·선택한 subject에 대한 strncmp·지원하지 않는 escape·잘린
comment/literal/call은 부분 결과 대신 ExtractionError로 중단한다. 전처리 양쪽 branch는
lexical union이며 실제 빌드 profile 지원과 다르다. regex로 source 전체의 단어를 세지 않는다.

이 helper에는 filesystem scan, subprocess, network, import 대상 프로그램 실행,
MCP 설정, native mutation, ledger 쓰기, UI가 없다. source는 caller가 전달한 문자열이다.
선택 source 읽기 한도는 §3.6을 따른다. ledger JSON 한도를 source 읽기 한도로 전용하지
않으며 자동 추출 profile·외부 CLI/MCP를 새로 노출하지 않는다.

[capability_files.py](../tools/capability_files.py)의 `read_sources`는 명시 root/경로만 읽어
caller 순서대로 raw bytes·SHA-256을 반환한다. Git은 `/usr/bin/git` 고정 dependency와
격리된 환경·literal pathspec·pager/fsmonitor/hooks 비활성 설정을 사용한다. stdout/stderr는
수신 중 제한하며 비정상 출력·경고·timeout을 성공으로 무시하지 않고 자신이 만든 child만 회수한다.
파일은 root dirfd에서 O_NOFOLLOW로 열어 모든 경로 요소·단일 link·regular type·size·
identity/mtime/ctime/mode 등을 검사한다. 중첩 Git 저장소/submodule 경계도 거부한다.
초기 파일이 뒤에서 바뀌는 경우를 잡도록 마지막에 재검사하고 root identity도 대조한다.
native lock/QA writer lock·CAS/journal/승인·client 설정에는 쓰지 않는다. OS의 자연스러운
atime 변화까지 없다고 주장하지 않으며, 동일 UID 공격자에 대한 sandbox나 원자 snapshot이 아니다.

## 5. 한정된 실제 소스 관측

[test_capability_source.py](../tools/test_capability_source.py)의 RepositorySamples가 다음
6개 파일의 명시적 구문만 대조한다. native program은 실행하지 않는다.

| source/subject | 관측 |
| --- | --- |
| src/agent_session/coordinator.c / op | begin, claim, context, heartbeat, next, reconcile, reject_output, resume, start, status, submit |
| src/completion/model.c / dw_text(r,"operation") | finalize, resume |
| src/cli/workflow.c / argv[2] | inputs, next, select, template, trace |
| src/cli/main.c / argv[1] | 기존 정적 목록의 최상위 route 31개와 대조 |
| tools/integration_service.py / SCHEMAS | D2 도구 선언 7개 |
| tools/integration_mutation_contract.py / NAMES | D4 도구 선언 7개 |

`completion.resume`라는 native operation을 agent session resume와 혼동하지 않는다.
이 표의 원시 이름은 공개 CLI/API/MCP의 이름과 일대일 관계가 아니다. 버전·권한·
guard·지원 profile을 합친 기능 분류는 아직 없으므로 전체 제공률을 출력하지 않는다.

## 6. 검증과 남은 출구 조건

```sh
python3 -m unittest discover -s tools -p test_capability_source.py
python3 -m unittest discover -s tools -p test_capability_ledger.py
```

현재 16개 테스트 통과. 주석/문자열의 가짜 호출, 인자 반전·연속 문자열·중첩 subject,
전처리 branch, computed/잘린 입력, Python 중복·동적 이름·값 실행 방지, operation
추가/삭제/이름 변경의 탐지, 실제 6개 파일의 한정 관측을 검사했다.

[capability_ledger.py](../tools/capability_ledger.py)의 `validate_base_fields`와
[기본 필드 회귀](../tools/test_capability_ledger.py) 10개를 추가해 합계 26개가 통과했다.
필수/닫힌 객체·타입·상대 경로·SHA-256 형식·내부 참조·중복·순서·성공/실패 시 원본 불변을
검사한다. 성공 반환은 None이며 전체 VALID/PASS/COMPLETE를 반환하지 않는다.
기본 검사만 호출하는 fixture의 kind·implementation에는 의도적으로 null을 두어
부분 검사와 전체 구조 검사의 차이를 표시한다. 분류 검사에서는 이 입력을 거부한다. 파일을 읽어 hash를 인증하지 않으며 JSON
중복 key도 decode된 dict만으로 검출할 수 없다. raw JSON은 §3.4의 bounded decoder를 사용한다.

분류 검사 회귀 7개를 추가해 총 33개가 통과했다. `validate_classification_fields`는
기본 검사와 채택된 enum/route만 검사하고 None을 반환한다. `classification_blockers`는
미해석/미확인/미검토를 내부 (이유, id) 쌍으로 반환하며 capability에 연결되지 않은
UNRESOLVED observation도 누락하지 않는다. 반환이 비어도 최종 coverage PASS가 아니다.
PARTIAL/PROPOSED/UNSUPPORTED·빈 경로·미검증 근거를 제공 완료로 세는 함수는 만들지 않았다.
현재/목표 경로 순서·분리와 원본 불변도 검사했다. metadata의 null을 통과시키는 것은
분류만 보는 부분 validator의 한계다. metadata 검사에서는 거부하며 전체 유효성 선언이 아니다.

기존 `test_integration_*.py` 회귀는 146개 중 128개 실행 통과, 선택 의존성이 없는
18개 skip이었다. 이는 기존 integration 단위 계약의 회귀 결과이며 실제 MCP client
연동·native 전체 실행·새 ledger schema의 검증으로 취급하지 않는다.

metadata 구조 회귀 8개를 추가해 총 41개가 통과했다. `validate_metadata_fields`는 채택된
전체 field 구조를 검사하지만 None만 반환한다. `metadata_blockers`는 분류 미확인과
EFFECTS_UNVERIFIED를 함께 반환한다. 참조 파일은 열지 않고 selector도 실행하지 않는다.
중복·미지 field/type/effect·상대 경로·현재/목표 분리·원본/순서 보존을 검사했다. 빈 metadata나
없는 파일의 참조도 구조상 맞을 수 있음을 fixture로 명시하며, 전체 제공 완료로 세지 않는다.

bounded decoder 회귀 17개를 추가해 관련 테스트는 총 58개 통과했다.
원문 16MiB·깊이 16·각 root/항목 배열·UTF-8 문자열 한도는 정확한 경계와 초과를
검사했다. BOM/invalid UTF-8/중복 key/고립 surrogate/비표준 수/잘린 JSON·후속 JSON을
거부하며 정상 surrogate pair·문자열 안 괄호·배열 순서·Unicode 표현은 보존한다.
byte/depth는 json.loads 전에 확인하고, 현재 schema에 숫자 field가 없으므로 숫자는
큰 정수/float를 만들기 전에 거부한다. decode_ledger는 새 Python 객체만 반환하며
파일을 읽거나 hash를 인증하거나 coverage PASS를 추가하지 않는다. 메모리/CPU 보장은 아니다.

관측 ID 회귀 9개를 추가해 관련 테스트는 총 67개 통과했다. 독립 literal JSON의 고정
digest 벡터·domain/NUL 구분·각 identity field·null/문자열·Unicode 비정규화·인자 순서·
불일치 거부·원본 보존을 검사했다. source hash나 배열 순서는 ID를 바꾸지 않지만,
이 검사는 현재 파일 bytes나 과거 검토를 재승인하지 않는다. capability ID도 자동 변경하지 않는다.

`decode_ledger`는 bounded 구조 검사만 한다. `validate_observation_ids`가 명시 ID 결합을,
`decode_identified_ledger`가 두 검사를 수행한다. 하위 부분 검사 통과를 ID 검증으로
승격하지 않으며, 세 함수 모두 실제 source·근거·최종 coverage를 인증하지 않는다.

선택 source reader 회귀 21개를 추가해 관련 테스트는 총 88개 통과했다. 임시 Git fixture에서
정확한 4096파일·1MiB/파일·64MiB 합계 경계와 초과 거부, 신규/ignored 명시 선택, literal
pathspec, 보호 경로/명시 fixture, symlink/hardlink/FIFO/디렉터리 거부, 읽기 중 수정·같은
bytes의 inode 교체·directory 교체·나중 파일을 읽는 동안 초기 파일 변경을 검사했다.
상속 GIT 변수·출력/시간 한도·stderr warning 거부와 hash/mode/index 보존도 확인했다.

제한 환경의 최초 실제 Git fixture 실행은 macOS `confstr()` 임시 디렉터리 조회 실패
warning을 stderr에 받아 SOURCE_GIT_REFUSED로 실패했다. 종료 코드 0만으로 성공시키거나
warning을 무시하지 않았다. 동일 검사는 호스트 환경에서 통과했다. 위 88개는 호스트
실행 결과이며 제한 환경 통과로 재기록하지 않는다. macOS 실검증이며 Linux/Windows
실검증 주장이 아니다. 구현은 POSIX/O_NOFOLLOW를 요구하고 Windows에는 permissive fallback이 없다.

실제 Golem checkout의 기존 추적 source 6개(97,119 bytes)를 같은 reader로 읽기 전용
검사했으며 source hash/mode가 보존됐다. Work·활성 승인·연결·TRAP 자료는 읽지 않았다.
이 source 관측을 전체 저장소/전체 operation coverage로 승격하지 않는다.

이것은 M0 전체 완료가 아니다. 남은 것은 추출 profile과
추출 지원 profile, public header/CLI 하위 route/native schema operation/Python 제품 기능의
전수 분류, review 누락·source drift·dangling ref·허위 MCP 경로의 gate, 재현 가능한
문서 생성과 CI 연결이다. 지원하지 않는 extractor를 조용히 생략한 성공은 허용하지 않는다.

현재 source 문자 변경으로 새로운 비교 형태가 생겨도 이 helper만으로 모든 형태를
탐지한다고 주장하지 않는다. 최종 gate는 source inventory/fingerprint·지원 parser profile·
미해석 영역의 명시적 차단을 함께 설계해야 한다. 새 제안 schema를 기존 approved producer
핀에 자동 포함하거나 활성 client로 배포하지 않는다.

M0 코드 검증은 macOS의 Python으로 수행했다. 운영 Work·TRAP·CAS·journal·QA writer
lock·보호 규칙·승인 파일·활성 연결을 변경하지 않는다. 추가 복구 계층도 만들지 않는다.


### 6.1 정적 profile driver 검증 — 2026-10-26

[capability_profile.py](../tools/capability_profile.py)는 bounded reader의 SourceFile과
검토자가 명시한 Rule(path·source hash·kind·entrypoint·subject)를 소비한다. Rule은 내부
Python 값이며 새 wire schema나 승인 설정이 아니다. source bytes와 hash를 재검증하고,
등록 hash와 달라지면 관측 이름이 같더라도 SOURCE_REVIEW_DRIFT로 재검토를 요구한다.
C 직접 함수의 범위를 분리하여 다른 함수의 같은 subject를 섞지 않는다. 직접 public
prototype와 callback/typedef/macro wrapper를 구분하며 Python은 기존 AST helper를 재사용한다.

결과는 관측과 미해석 사유를 분리한다. 미등록 파일·미선택 source·잘못된 UTF-8·지원 밖
entrypoint·computed 비교는 명시적으로 남긴다. 성공적으로 관측한 경우에도 C의 나머지
구문/전처리 의미와 Python의 동적 등록은 미검증이다. 따라서 coverage_complete는 항상
false이며, 관측 존재를 구현·권한·실제 client 노출로 승격하지 않는다. 전체 repository의
고정 registry와 실제 근거 충분성·최종 gate는 아직 완성하지 않았다.

[profile 회귀](../tools/test_capability_profile.py) 12개를 추가했다. 함수 범위 분리,
prototype/definition 구분, callback·macro·table/switch·비literal·잘림, Python 비실행,
hash drift·누락·중복·identity 분리 및 실제 session macro wrapper의 미해석 처리를 검사한다.
기존 helper가 파일 전체에서 session 문자열 11개를 관측하는 것과 public API의 직접
function profile이 해석되는 것은 다르다. 이번 profile은 해당 wrapper를 추정 지원하지 않는다.

전체 capability 회귀 **100개 macOS 호스트 PASS**. 제한 환경에서는 기존 Git 경고 거부
경로 SOURCE_GIT_REFUSED 때문에 6 failure·10 error로 실패했고 같은 코드를 호스트에서
재검증했다. 경고 거부를 약화하거나 실패를 skip하지 않았다. Linux/Windows·CI·실제 client
검증 결과로 확대하지 않는다. core·활성 연결·승인·TRAP·실제 Work는 변경하지 않았다.


### 6.2 명시 선택 근거 파일 관측 — 2026-10-26

사용자가 test_refs/doc_refs의 첫 검증을 동일한 소스 읽기 경계에서 명시 선택한
근거 파일의 존재·bytes/hash 확인으로 한정하는 계약을 채택했다.
[capability_evidence.py](../tools/capability_evidence.py)의 `inspect_references`는
기존 metadata/한도 validator와 `read_sources`를 재사용한다. 참조 목록을 자동으로
읽기 목록에 추가하지 않으며 reviewed_new/reviewed_fixtures/protected_paths도 그대로
reader에 전달한다. reader의 batch가 실패하면 해당 선택 파일을 부분 성공으로 노출하지 않는다.
미선택 참조는 REFERENCE_NOT_SELECTED, 선택했지만 읽지 못한 참조는 reader의 진단과
함께 미검증으로 반환한다. 실패를 자동 재시도하거나 설정을 변경하지 않는다.

내부 ReferenceObservation은 capability·test/doc 구분·경로·원래 selector/anchor와
파일 관측 성공 여부·관측 SHA-256·byte 길이·진단을 보존한다. hash는 이번 읽기의
식별값이며 기존 승인 hash와의 일치 증명이 아니다. locator_unverified,
execution_unverified, sufficiency_unverified는 모두 true로 유지한다. null locator도
완료로 승격하지 않는다. 새로운 공개 wire/store schema나 권한은 추가하지 않았다.
빈 참조 목록은 빈 결과이며 coverage PASS가 아니다. ledger/파일 원문은 변경하지 않는다.

[근거 관측 회귀](../tools/test_capability_evidence.py) 8개를 추가했다. 선택 경계 전달,
미선택/제외/읽기 실패, partial 성공 방지, 원문 불변, 같은 파일의 서로 다른 참조 순서,
실제 임시 Git 저장소에서 bytes/hash 확인과 비실행을 검증했다. 전체 capability 회귀는
**macOS 호스트 108/108 PASS**. 기존 제한 환경 Git 경고 실패와 구분하며 Linux/Windows,
CI 및 client 실행을 검증했다고 주장하지 않는다. 다음은 locator 해석 범위 결정이다.


### 6.3 Python test selector 선언 확인 — 2026-10-26

`capability_evidence.python_declaration`은 선택된 `.py` 원문을 UTF-8로 decode하고 AST로
직접 top-level 함수 또는 `클래스명.메서드명`을 찾는다. 클래스와 함수가 정확히 하나일 때만
원문 선언 줄 번호를 반환한다. async 함수도 직접 선언에 포함한다. nested/conditional
선언·상속·동적 생성·pytest node ID·매개변수 suffix·다른 언어·null은 미검증으로 남긴다.
중복·문법 오류·UTF-8 오류는 원문을 실행하거나 추정 복구하지 않고 진단한다.

근거 관측 결과에는 declaration_line과 locator_diagnostic을 추가했다. 정확한 선언을
찾은 경우에만 locator_unverified=false이며 execution_unverified와
sufficiency_unverified는 계속 true다. decorator는 평가하지 않는다. 따라서 decorator가
있는 함수의 선언 위치를 찾더라도 parameterized case·수집 결과·런타임 binding을
확인한 것이 아니다. doc anchor는 아직 DOC_ANCHOR_UNVERIFIED다. 이 결과는 내부
Python 값이며 공개 wire schema나 완료 gate가 아니다.

[selector 회귀](../tools/test_capability_selector.py) 8개를 추가했고 전체 **macOS 호스트
116/116 PASS**다. 선언 위치·async·중복·상속/동적/조건부 제외·비실행·기존 reader 연결과
실행/충분성 미검증 유지를 확인했다. Linux/Windows·CI·실제 client 검증은 수행하지 않았다.
core·QA writer lock·기존 승인·증거·연결·TRAP·실제 Work는 변경하지 않았다.


### 6.4 명시적 Markdown 앵커 — 2026-10-26

[capability_anchor.py](../tools/capability_anchor.py)는 선택된 `.md` UTF-8 원문에서
단독 줄의 빈 `<a id="…"></a>` 또는 `<a name="…"></a>`를 정확한 문자열로 확인한다.
동일 앵커가 하나일 때만 원문 줄 번호를 반환한다. 자동 heading slug 생성·entity 해석·
대소문자 정규화·동적 HTML·문서 수정은 하지 않는다. null과 다른 파일 형식은 미검증이다.

이 구현은 전체 Markdown renderer가 아닌 보수적 profile이다. fenced code, HTML 주석,
완전한 한 줄 inline code의 예시는 제외한다. 닫히지 않은 fence/comment/code, 일반 HTML,
추가 속성·inline 앵커·목록/인용 container는 미검증으로 차단한다. 들여쓰기만으로 code인지
paragraph continuation인지 확정할 수 없는 HTML 줄도 차단해 가능한 중복을 숨기지 않는다.
지원 밖 문맥이 있으면 다른 곳의 앵커를 발견해도 성공으로 승격하지 않는다.

기존 근거 reader의 doc_refs에 연결하며 locator_unverified만 갱신한다. 실행 여부·
내용 타당성·근거 충분성은 검증하지 않는다. [회귀](../tools/test_capability_anchor.py)
9개를 추가해 Unicode·id/name·중복/누락·코드/주석·모호한 문맥·정규화 금지·reader 연결을
검사했다. 전체 macOS 호스트 capability 회귀 **125/125 PASS**. Linux/Windows·CI·client
검증은 수행하지 않았다. 기존 core·연결·승인·증거·TRAP·실제 Work는 변경하지 않았다.


### 6.5 실행 기록 연결 원칙과 기존 코드 조사 — 2026-10-26

기존 실행 기록을 검토자가 명시 선택해 읽고 연결하는 원칙을 채택했다. M0가 테스트를
자동 실행하거나 과거 기록을 재작성하지 않는다. 다음은 공개 소스 조사이며 실제 비공개
실행 기록·승인·Work를 읽은 결과가 아니다. 이 단계에서는 새 adapter를 활성화하지 않았다.

| 기존 계약 | 기록 내용 | M0 적용 시 남은 구분 |
| --- | --- | --- |
| `execution_record.capture` / `golem.execution-observation.v1`, `golem.execution-manifest.v1` | started/result의 invocation_id·상태, argv, source-before/after, 실행 파일 식별값, process reason/returncode, 파일·로그 hash/bytes | manifest 연결·현재 검토 대상 소스 일치·명시 선택 파일 집합을 별도로 확인해야 함 |
| `execution_record.source_identity` | commit·dirty·status/diff/tree SHA-256·파일별 식별값 | 비원자적 관측이며 ignored 파일 제외·submodule 미지원. commit만으로 dirty 소스 일치를 인정할 수 없음 |
| `execution_record.check` | 고정 inventory·manifest/log hash·시작/종료 invocation 연결 | 디렉터리 탐색·참조 파일 읽기를 수행함. M0 명시 선택 reader 대신 그대로 호출하지 않음. integrity PASS는 authenticity/product acceptance가 아님 |
| `agent_io.run/load_bundle` / `golem.agent-observation.v1` | plan·step·source 전후·로그와 manifest를 묶은 다중 명령 기록 | 별도의 bundle/step 연결 adapter 필요. 단일 process 형식으로 추정 변환하지 않음 |
| `execution_record.run_private` | redacted argv, streams 미보존, process 결과·source 전후 | 제한된 기록 관측으로 지원. 숨겨진 명령·미보존 로그와 무결성 연결 부재는 미검증 |

단일 execution 형식으로 한정하는 제안은 채택하지 않았다. 사용자는 조사한 기존 형식을
각각 구분해 지원하는 방향을 채택했다. 기존 writer·증거를 바꾸지 않고 형식별 adapter에서
실제로 존재하는 필드와 hash 결합만 재사용한다. 다만 현재 M0 source reader의
파일당 1MiB 한도와 기존 execution reader의 32MiB 한도는 다르며, private 출력 경로도
소스 repository 범위 밖일 수 있다. 이 차이를 묵시적으로 허용하거나 자동 복사하지 않는다.
지원 형식부터 결정한 뒤 입력 bytes 제공/경로 범위·한도·소스 매칭·capability/test 연결을
순서대로 결정한다. hash 무결성·기록된 exit 0·실제 테스트 수집/PASS·issuer 신뢰·근거
충분성은 서로 다른 판단으로 유지한다.


### 6.6 채택된 다중 형식 지원 방향과 입력 경계 제안

지원 대상은 앞서 조사한 단일 execution, agent_io 다중 step, private-process 기록이며,
manifest의 native_files가 가리키는 native 기록은 별도 하위 형식으로 구분한다. 알려지지
않은 schema를 자동 인식·지원한다는 뜻은 아니다. native 참조 처리의 정확한 규칙은 미결이다.

| 형식 | 확인 가능한 근거의 종류 | 확인됐다고 승격하지 않을 항목 |
| --- | --- | --- |
| 단일 execution | 제공된 manifest의 파일/log bytes·hash 결합, invocation 연결, 기록된 argv·종료 상태·소스 전후 | 기록자 인증·현재 대상과의 일치·테스트별 PASS·충분성 |
| agent_io bundle | 제공된 plan/record/manifest의 결합, step별 명령 및 상태·로그, source 전후 | NOT_RUN step의 실행·전체 bundle 성공으로 개별 test 실행 추정·누락된 child 기록 |
| private-process | 제공된 started/result/source의 필드·관측 hash, 기록된 종료 사유 | 원래 argv·미보존 streams·없는 manifest 결합·서명·개별 test 실행 |
| native 하위 기록 | 명시 제공된 manifest/시작/결과의 기존 결합과 상태 | 미제공 참조·불완전 scope·상위 process와의 검증되지 않은 관계 |

위 표는 adapter 구현을 위한 구분이지 실행 근거 검증 완료 결과가 아니다. 특히 private
기록의 파일별 현재 hash를 계산하는 것과 기록 당시 파일들이 함께 묶였음을 증명하는 것은
다르다. 모든 형식에서 기록자 신뢰·내용의 진실성·test coverage 충분성을 별도로 남긴다.

채택된 입력 경계: 초기 adapter는 호출자가 명시 제공한 상대 이름→원본 bytes
묶음만 소비한다. 기록 안의 절대 cwd/record_path/source root와 manifest 경로를 따라 파일을
자동 조회하지 않는다. 파일 수집기는 별도 결정 전까지 추가하지 않고, 테스트는 합성 bytes로
수행한다. 필수 누락·추가·native 참조 상태의 처리와 파일/총량/JSON 한도는 다음 결정이다.
이 결정은 기존 source reader의 경로나 quota를 확장하지 않으며 실제 비공개 기록 수집을
승인하지 않는다.


### 6.7 채택된 실행 기록 bytes/JSON 입력 한도

기존 execution_record와 verify_agent의 파일/JSON 한도는 32MiB이며 agent_io는
verify_agent의 LIMIT를 재사용한다. 이는 새 adapter의 총량이나 파일 수를 정하는
근거로 충분하지 않으므로 다음 값은 초기 운영 상한 제안이며 충분성 측정 결과가 아니다.

- 명시 묶음 최대 4096개, 파일당 32MiB, 전체 원본 bytes 합계 128MiB.
- 상대 이름은 기존 비정규화 상대 경로 규칙과 UTF-8 4096 bytes를 적용한다.
- JSON 원본도 파일당 32MiB 안에서 container depth 32, decode 결과 전체 JSON 합산
  value node 100만 개, 개별 문자열 UTF-8 1MiB로 제한한다. 객체 key도 문자열 상한에 포함한다.
- strict UTF-8, BOM·중복 key·고립 surrogate·NaN/Infinity·비유한 수 거부. 기존 실행 기록은
  elapsed_seconds 등 수치가 있으므로 숫자를 모두 금지하는 ledger decoder를 그대로 쓰지 않는다.
- 초과 시 절단·분할·자동 상향 없이 거부한다. 기존 writer의 유효 기록이어도 이 adapter
  한도를 초과하면 미지원이다. source reader/ledger/D08/native quota는 바꾸지 않는다.
- 원본 bytes 합계는 Python 객체 overhead·parser peak 메모리·처리시간 보장이 아니다.
  한도는 읽기/출력 권한이나 native 참조 자동 확장 권한이 아니다.

사용자가 위 수치를 채택했다(2026-10-26). 필수/추가 파일·native 참조·소스 일치와 결과 판정은 별도 결정으로 남긴다.


`capability_record_input.decode_record_inputs`에 승인된 한도를 구현했다. 명시적 상대
이름→bytes와 JSON 이름 목록만 받고 파일 조회·manifest 추적·실행은 하지 않는다.
JSON depth는 decode 전에 확인하며 중복 key·비유한 값·surrogate를 거부한다. node는
root/container/value를 세며 key는 문자열 한도를 검사한다. 개별 문자열과 전체 node 검사는
decode 후 수행하므로 parser의 peak 메모리 제한을 보장하지 않는다. 큰 정수는 전역 Python
digit-limit 변경 없이 정확한 Decimal로 보존하며 일반 정수는 int로 반환한다. 이는 내부
표현일 뿐 schema 필드 타입·종료 상태의 유효성 판정이 아니다. JSON 선택 외 raw 로그는
UTF-8로 강제 변환하지 않는다. 실패 시 부분 decoded 결과를 반환하지 않는다.

회귀 8개: 파일 수·32MiB/128MiB 경계·depth 32·문자열 1MiB·여러 JSON의 node 합산,
불량 JSON·명시 선택·경로 비추적을 검증한다. 실행 기록의 필수 파일·native 참조 처리와
필드 연결은 미승인으로 남아 있으므로 형식 adapter는 아직 활성화하지 않았다.


### 6.8 채택된 파일 집합 원칙 — 2026-10-26

형식별 필수 파일·manifest 참조를 명시 제공 bytes와 정확히 대조하고 누락·미등록 추가·
이름 충돌·지원 밖 native 참조를 전체 검증 완료로 처리하지 않는 원칙을 사용자가 채택했다.
`capability_record_inventory.compare_file_inventory`는 형식에 독립적인 이름 대조만
구현한다. 기존 bytes/경로 한도를 재사용하며 required와 referenced 내부 중복 및 파일이
다른 파일의 부모 경로가 되는 충돌을 거부한다. 필수 목록과 manifest 목록의 정상적인
중첩은 허용한다. 누락/추가 목록과 미해석 native 참조를 분리해 반환한다.

file_set_matches는 이름 집합 일치만 뜻한다. blocked=false여도 hash·schema·실행·근거
충분성을 검증한 것이 아니다. native 원문을 제공했더라도 하위 adapter 검증 전에는
미해석 참조로 남긴다. 이 helper에는 native 검증 성공을 임의 선언하는 옵션이나 파일
자동 조회·기록 수정 기능이 없다. 형식 adapter는 아직 활성화하지 않았다.

회귀 6개로 정상 중첩·누락/추가·native bytes와 검증의 구분·중복·경로 충돌·파일 비조회를
검증했다. 형식별 정확한 필수 목록과 연결 필드의 결정은 다음 단계다.


### 6.9 M0 대조·보고서와 명명된 wrapper 확장 — 2026-10-26

사용자는 M0 목록 완전성과 MCP 제공 완료를 구분하는 출구 원칙을 채택했다.
[capability_audit.py](../tools/capability_audit.py)는 selected source hash·fresh observation과
ledger를 대조한다. 누락·추가·drift·미분류·미해석·미검토·빈 경로·근거 참조 누락/bytes
미검증은 blocker이며 현재/목표 제공 경로 차이는 후속 delivery backlog로 별도 출력한다.
선택 scope 비교는 repository 전수 범위의 증명이 아니다. 참조 파일 존재는 test 실행·
내용의 진실성·충분성을 뜻하지 않는다. 최종 실행 근거 adapter는 여전히 미완료다.

[capability_report.py](../tools/capability_report.py)는 root/source/evidence 경로와 hash가
고정된 rule을 명시 받아 기존 safe reader를 사용한다. --draft는 capability 검토를
꾸며내지 않고 관측만 생성한다. JSON은 stdout, 미해석 진단은 stderr에 출력하며 draft는
항상 종료 코드 2다. --ledger는 검토 목록과 대조해 Markdown을 출력한다. 입력 오류는 1,
불완전 목록은 2이며 authority/설치/Work에 쓰지 않는다. renderer는 원문을 text로 escape한다.

사용자가 GOLEM_RECORDED_API에 한해 wrapper 확장을 채택했다. 정의 파일
src/common/record_internal.h와 호출 파일을 함께 hash 고정하고 이름 인자·네 인자 형태·
뒤따르는 함수 본문만 tokenizer로 관측한다. 다른 macro 및 정의 drift는 추정하지 않는다.
실제 session 파일의 전체 lexical operation 11개와 wrapper 본문 5개는 다르므로
prepare/query helper를 별도 등록했다. helper 호출 관계·preprocessor 의미는 여전히 미검증이다.

[고정 sample registry](../tools/capability_sample_registry.py)는 공개 7개 파일만 대상으로
한다. [관측 JSON](mcp-m0-observations.json)에서 [표](mcp-m0-observations.md)를 생성했다.
66개 관측, 미해석 9건과 미분류 항목을 그대로 공개하며 전체 coverage를 주장하지 않는다.
추가 회귀 10개 포함 전체 macOS 호스트 **149/149 PASS**. Linux/Windows·CI는 미검증이다.

연구 적용: Parnas의 정보 은닉 원칙에 따라 parser·파일 경계·대조·renderer를 분리했다.
NIST SP 800-218 PW.7의 발견 기록/검토 원칙은 blocker를 숨기지 않는 보고에 적용했다.
Ammann/Offutt의 coverage 기준과 시험 요구 구분을 참고해 선택 scope·M0 목록·제품 E2E를
서로 다른 판단으로 유지한다. 출처는 §2이며 2026-10-26 공식 NIST 및 저자/출판사 공개
자료를 재확인했다. 학술저서 전체 본문을 읽거나 인증을 획득했다고 주장하지 않는다.

사용자 최신 지시로 M0~M8 실제 E2E는 보류한다. 코드·탐색·정적/fixture/회귀를 계속하고
Codex/Claude 실제 호출·실제 Work 변경은 하지 않는다. M7/M8 검증 도구 구현과 실제 실행
결과를 별도 상태로 유지한다. 기존 보호 계약·추가 복구 계층 금지는 그대로다.


### 6.10 실행 기록 adapter와 분류 확대 — 2026-10-26

추가 개발 요청에 따라 기존 writer/checker의 실제 파일 결합을 재사용한
[capability_execution.py](../tools/capability_execution.py)를 구현했다. 공개 CLI/MCP로
노출하거나 기록을 수집하지 않고 명시 bytes만 처리한다. 이전 단일 형식 파일 목록 제안의
더 강한 조건을 승인된 것으로 간주하지 않는다. 원래 형식에서 가능한 누락/중단은 진단으로
남기며 stdout/stderr 부족을 실행 증거 완료로 승격하지 않는다.

| adapter | 구현한 확인 | 계속 미검증/차단 |
| --- | --- | --- |
| execution | 고정 execution JSON 집합, manifest files/logs hash·길이, invocation/schema/state, argv·종료 기록 | 미제공 파일·추가 파일·누락 stream, 실제 test 수집/PASS·issuer 신뢰 |
| agent | agent manifest와 원문 hash, compact ASCII+newline plan identity, command/step ID·순서, step log hash·길이, NOT_RUN 구분 | native child 전체 연결, 실제 개별 test 실행, 부분 기록의 완료 승격 |
| private | redaction 계약·제공된 process 종료 기록·원문 source 전후 | argv·streams·존재하지 않는 manifest 결합. file_integrity_verified=false 유지 |
| native child (execution 하위) | 부모 inventory의 directory/file 구분, scope id, native raw manifest hash, 시작/종료 id·상태·recording_status | source/executable 경로 추적·인증·외부 자식 전체 coverage·Work 완료 |

expected_source가 제공되면 commit·files·tree_sha256를 포함한 전체 기록 객체를 전후와
대조한다. 이는 호출자가 준 대상과의 일치이지 현재 저장소를 자동 읽거나 진실성을 인증한
것이 아니다. source 미제공/불일치와 파일 무결성은 구분한다. authenticity_verified,
test_execution_verified, sufficiency_verified는 false를 유지한다. malformed 기록은 부분
성공 없이 거부한다. native JSON과 상위 JSON의 node 합계도 승인된 한도 안에서 검사한다.

[capability_scope.py](../tools/capability_scope.py)는 고정 Git index 조회로 경로 추가/삭제를
검사한다. [경로 baseline](../tools/capability_scope_registry.py)은 기준 commit의 897개
tracked 경로이며 내용을 자동 읽을 권한이 아니다. 새 경로·삭제 경로는 명시 보고한다.
미추적 개발 파일은 기존 reviewed_new 방식으로 별도 선택하며 이 index snapshot의 전수
범위에 포함됐다고 주장하지 않는다. root symlink·교체도 기존 no-follow 방식으로 검사한다.

현재 [관측 표](mcp-m0-observations.md)는 구현/근거 파일 20개 hash, 관측 66개, 검토한
capability 30개를 포함한다. D2 7개·D4 7개와 session/completion/workflow 일부 native
operation을 분류했다. CLI root/template의 32개 관측은 아직 미분류이며, source 전체
전수 operation 분류가 아니다. 문서/시험 근거 파일까지 source hash에 결합했기 때문에
기존 검토 후 근거 변경도 source drift로 발견된다. 자동으로 HOST_INTERNAL에 몰아넣거나
미지원 scope를 제외해 완료율을 올리지 않는다.

실제 확인된 후속 backlog: completion.finalize, session.context/heartbeat/reject_output/start,
workflow.inputs/next/select/trace. reject_output은 owner 관리 경계에 두며, 이 목록이 새
도구 활성화나 owner 승인 대체가 되지 않는다. workflow.select는 읽기 전용 선택 계산으로,
Work 채택 mutation으로 분류하지 않았다. completion.resume는 D2 completion_check의 읽기이며
session resume와 구분한다. session.context와 D2 context_get의 candidate 경로도 다르다.

검증: capability 회귀 **162/162**, 기존 D2 fixture **15/15**, D4 fixture **19/19** macOS
호스트 통과. 모두 임시/합성 fixture이며 실제 Codex/Claude E2E·실제 Work는 실행하지 않았다.
CI·Linux/Windows는 미검증이다. M0 전체 완료는 아직 아니며, 현재 선택 표의 blocker 54개
(미분류 32개 + 미해석 범위 22개)를 유지한다. 생성 표는 검증 기준 변경 시 재생성한다.

### 6.11 agent step과 native child 연결

명시 제공된 agent bytes 묶음에서 각 실행 step의 하위 execution manifest를 검사하고,
기존 native inventory 검증으로 연결한다. 부모의 계획 argv와 종료 결과를 자식 기록과
대조하며, 상위 manifest를 다시 계산해도 이 연결이 불일치하면 거부한다. NOT_RUN에
하위 파일이 있으면 모순으로 거부하고, 실행 기록 누락은 CHILD_INTEGRITY_UNVERIFIED로
남긴다. 파일·경로를 자동 조회하거나 실제 프로세스를 실행하지 않는다.

JSON value-node 상한은 부모·모든 step·native 기록에 누적 적용한다. 자식의 source
미관측·대상 source 미지정은 별도 CHILD_* 진단으로 보존한다. 파일 무결성 검증은
native parent의 인증·실행 진실성·시험 충분성 확인이 아니다.

검증: 전체 capability 회귀 165개 통과 후 native child 연결 fixture를 추가했으며,
execution adapter 13개가 통과했다(macOS). 실제 E2E는 NOT_RUN이다.
전수 분류 32개와 미해석 scope 22개는 아직 해결하지 않았으며 기존 gate를 유지한다.
기존 연결·승인·TRAP·실제 Work는 수정하지 않았다.

### 6.12 CLI 분류 확대와 근거 파일 scope 분리

기존 미분류 32개는 CLI root 31개와 workflow template 위임 분기 1개였다.
이들을 개별 실행 operation 전체로 해석하지 않고, 현재 HOST_INTERNAL 진입점과
목표 경로를 가진 **dispatch 분기**로 분류했다. 새 하위 CLI profile 22개로 literal
분기 92개를 추가 관측했다. 현재 표는 source/근거 44개, 관측 158개, capability
154개이며 OPERATION_UNCLASSIFIED는 0개다. 모든 delegated native operation이나
public C API가 목록에 들어왔다는 의미는 아니다.

코드 대조에서 확인한 구분:

- main의 work history/record는 document handler보다 먼저 session-binding으로 분기한다.
- run은 `--noop` 전용이다. 범용 agent 직접 실행으로 표기하지 않는다.
- doctor admission은 disposable directory를 생성하는 writer 검사이며 읽기 도구가 아니다.
- session resume는 읽기가 아니다. completion check/resume와 구별한다.
- candidate serve/call은 host transport 관리 경계이며 단순 조회로 분류하지 않는다.
- research export는 새 목적지에 파일을 게시한다. Work 읽기와 목적지 쓰기를 구별한다.
- workflow template instantiate는 read-only store를 사용해 제안 bytes를 반환하며,
  해당 응답을 사용자 채택·ACTIVE 전이로 표시하지 않는다.

분기 capability의 빈 effects는 하위 호출의 효과를 아직 주장하지 않는다는 뜻이다.
읽기 전용 보증이 아니며 MCP 권한 설정에 사용할 수 없다. test_refs는 기존 CLI fixture
파일에 대한 근거 위치일 뿐 해당 분기의 실행 PASS나 충분성을 나타내지 않는다.

`capability_selected_scan.scan_selected`는 ledger에서 실제로 참조한 docs/test 파일만
operation 추출 대상과 분리한다. 전체 입력의 bytes/hash/중복/한도 검사는 분리 전에
수행하고, source hash drift와 근거 읽기 검사는 그대로 유지한다. source가 rule이나
observation에 등장하면 근거로도 쓰이더라도 추출 대상이다. production 파일은 test_refs에
넣어도 제외되지 않는다. CLI 보고서도 이 경로를 사용한다.

기존 22개 scope 중 근거 파일 10개는 이 분리로 해소했다. 나머지 12개를 검토 표시로
지우지 않았다. 22개의 하위 CLI profile을 추가하면서 각 함수의 transitive scope도
명시되어 현재 총 blocker는 34개다:

| 종류 | 개수 | 남은 검증 |
|---|---:|---|
| C_RESIDUAL_SCOPE_UNVERIFIED | 28 | literal 분기 밖 하위 호출·별도 selector·native operation 연결 |
| DECLARATION_ONLY_DYNAMIC_SCOPE_UNVERIFIED | 2 | 도구 선언과 Python handler 분기의 정적 연결 |
| UNREGISTERED_SOURCE | 4 | wrapper 정의와 integration backend/mutation 구현의 추출 역할 |

원래 32개 분류를 완료한 것과 미해석 scope 전체 해소는 별개다. **M0 전체는 INCOMPLETE**다.
기존 897개 Git 경로 snapshot은 경로 누락 탐지용이며 repository 전체 operation 검증이 아니다.
Python method AST 추출 확장은 기존 top-level literal profile 밖이므로 별도 정책 결정으로
제안했다. 이 결정 전에는 handler 연결을 검증한 것으로 기록하지 않는다.

검증: macOS host에서 capability 정적/fixture 회귀 **175/175 PASS**, `git diff --check`
통과. 테스트는 새 분기의 hash drift, 근거 파일의 중복·위조 hash, production 파일의
부당한 제외, 미해석 scope 보존을 포함한다. 실제 E2E·Codex/Claude 호출·Linux/Windows·CI는
실행하지 않았다. 활성 연결·승인·기존 증거·TRAP·실제 Work는 변경하지 않았다.

### 6.13 승인된 Python handler AST 비교

`capability_handler.py`는 명시된 class.method의 equality/literal tuple/list membership을
AST로 관측한다. 선언과 handler의 hash는 `capability_handler_registry.py`에 각각 고정한다.
파일 import/실행이나 계산된 이름 추론은 하지 않는다. nested scope는 분리하고 else,
계산된 비교, subject 별칭/할당, 미등록 helper 전달, decorator는 차단 사유로 남긴다.
source 전체 입력 한도·중복·hash 검사는 기존 profile 검사를 재사용한다.

`capability_report.py --handler-profiles`는 명시 선택한 source bytes만 이 검사에 전달하며
기존 scope blocker를 제거하지 않는다. 선언/handler가 미선택이면 조회로 보충하지 않는다.
실제 코드 관측은 `mcp-m0-handler-observations.json`에 기록했다:

- D2 Service._call_locked: 7개 선언 중 literal 비교 6개. history_read는 fallback이므로
  미연결로 표시한다. scope/조회 helper와 계산된 membership도 검증 완료로 추정하지 않는다.
- D4 Service.call: contract.NAMES 및 reads.SCHEMAS membership과 helper 위임이다.
  7개 도구의 literal 분기 연결은 이번 profile만으로 검증되지 않는다.

이는 제품 기능이 누락되거나 실행이 실패했다는 판정이 아니다. 정적 검사로 입증하지
못한 범위를 명확히 한 결과다. 기존 미해석 scope 34개를 삭제하거나 완료로 승격하지 않는다.
후속 helper/선언 참조 해석은 별도 범위 결정이 필요하며 이번에는 구현하지 않았다.
macOS host 정적/fixture 회귀 **182/182 PASS**, diff 공백 검사 통과. 실제 E2E는 NOT_RUN.
기존 연결·승인·증거·TRAP·실제 Work 및 core 파일은 변경하지 않았다.

### 6.14 D2 닫힌 집합 fallback / D4 직접 전달 (승인 범위)

두 후속 profile은 앞 단계의 literal-only 검사와 분리한다. 기존 검사 결과를 덮어쓰거나
전체 scope gate를 해제하지 않는다. `capability_report.py --connection-profiles`로 명시
선택한 소스에 적용할 수 있으며 필요한 파일을 자동으로 찾아 읽지 않는다.
관측 결과와 정확한 source pin은 `mcp-m0-connection-observations.json`에 보존했다.

D2(`capability_fallback.py`): integration_transfer.NAMES와 service.SCHEMAS의 닫힌 집합,
명시 import, 진입 membership guard, require의 raise 동작, `_call_locked(name,args)` 반환
전달을 검사한다. literal equality/membership의 참 분기와 잔여 집합을 계산하여 7개 이름의
경로를 귀속한다. history_read는 이름에 대한 예외 규칙 없이 잔여 분기로 도출된다.
source drift·name 재할당/직접 별칭·계산된 routing predicate는 차단한다.
이는 직접 name 분기만의 귀속이며 비-routing 조건·호출·부작용·출력 정확성은 인증하지 않는다.

D4(`capability_delegation.py`): 고정된 reads.SCHEMAS / contract.NAMES 및 import를 확인하고,
집합 겹침을 거부한다. 읽기 분기의 직접 반환을 제외한 7개 mutation 이름이 membership
거부 guard 뒤에서 등록된 `self._mutate(name,args)`로 그대로 전달되는 경계를 확인한다.
method signature, 직접 return, 인자 순서, subject 별칭/재할당, 미등록 전달을 검사한다.
`helper_body_verified=false`, execution/authority verified=false를 유지한다. helper의
정책·prefix 변환·native 실행까지 추적하는 계약은 이번에 승인되거나 구현되지 않았다.

전체 capability 회귀 **190/190 PASS**(macOS host, 정적/fixture). 추가 검사는 guard 제거,
계산된 predicate, 이름 변경 후 잔여 집합 재계산, 누락·hash drift, 동적 수신자, 인자 교환,
미등록 전달을 포함한다. 검사 자체는 source import나 native/client 실행을 하지 않는다.
기존 M0 전체 scope blocker는 유지한다. 실제 E2E·CI·Linux/Windows는 NOT_RUN이며,
기존 연결·승인·증거·TRAP·실제 Work·core 구현은 변경하지 않았다.

### 6.15 승인된 D4 mutation 그래프와 prefix 변환

`capability_mutation_graph.py`는 기존 D4 선언·직접 전달 검사를 선행한다. 승인된
`_mutate → _admit/_preflight/_argv → Policy.authorize/action → native_action → records.capture`
범위에서 10개의 등록된 호출 항목을 검사한다(동일 authorize 표현의 복수 호출은 별도
출현 위치로 보존). 각 edge는 정확한 수신자 표현·인자·개수·AST 소속 위치와 분기 조건,
with/lock 표현을 `capability_mutation_scope_registry.py`의 고정 검토 값과 대조한다.
주요 호출의 소스상 순서도 검사한다. 이 순서는 런타임 실행 순서나 모든 경로의 domination
증명이 아니다. registry는 검사 중 재생성하거나 자동으로 새 소스를 신뢰하지 않는다.

고정된 NAMES에 한해 `startswith("session_")` / `removeprefix("session_")`를 확인한다.
claim/begin/resume/reconcile/submit의 5개 대응, 빈 suffix·충돌·잔여 집합을 검사한다.
argv의 session_resume 우선 분기, 일반 session call, document submit, 잔여 execution_request의
QA host execute 경로를 분리한다. 다른 prefix·계산된 문자열은 미지원으로 차단한다.

`--connection-profiles` 보고서에 이 관측이 포함되며, 정확한 소스 pin과 edge별 결과는
`mcp-m0-mutation-graph.json`에 보존했다. 호출 표현의 CONFIRMED는 소스 구조의 확인만 뜻한다.
`self.policy`의 실제 런타임 신원은 인증하지 않으며, receiver_identity_verified,
policy_satisfied, native_execution_verified는 모두 false다. 미등록 helper를 추적하지 않고
native reducer·OS 실행·정책 충족·기존 M0 전체 scope 완료를 주장하지 않는다.

macOS host capability 회귀 **196/196 PASS**. 추가 fixture는 prefix 변경·계산된 prefix,
인자 변경·capture의 조건부 위치 변경·정책 edge 제거·resume 우선 분기 변경·exclusive lock
표현 변경을 검사한다. 실제 E2E·CI·다른 플랫폼은 NOT_RUN이다. core·실제 producer·연결·
승인·증거·TRAP·실제 Work는 수정하지 않았다.

### 6.16 M0 기본 누락 검사에 연결 profile 통합

`capability_connections.connect_inventory`를 보고서의 기본 경로에 연결했다. D2/D4 선언이
선택 목록에 있으면 fallback/직접 전달/mutation 그래프 검사는 옵션 없이 필수다. 필요한
소스가 미선택·누락·drift이면 결과를 보충하거나 생략하지 않고 차단한다.
`--connection-profiles`는 상세 JSON 출력 옵션이며 검사 활성화 옵션이 아니다.

승인된 C profile(`capability_c_edges.py`)은 고정된 caller/callee/declaration hash와
명시적인 `if (literal condition) return callee(argc, argv);`를 대조한다. 정확한 top-level
CLI prototype, callee 정의, caller 내 대상 호출의 누락/추가, 인자 순서와 selector를 검사한다.
브레이스형 분기·간접 호출·macro 선언 등 미지원 형태는 추측하지 않는다. 전처리 실행이나
컴파일된 플랫폼 의미는 인증하지 않는다. main dispatcher 및 workflow→template의
24개 명시 직접 edge가 현재 소스에서 확인됐다. registry는 검사 시 갱신하지 않는다.

통합 결과는 [관측 표](mcp-m0-observations.md)의 Static connection checks와
`mcp-m0-integrated-connections.json`에 제공한다. Python 3개 + C 24개 bounded profile이
확인됐으며 이는 27개 runtime 기능 PASS가 아니다.

해소 규칙은 exact obligation에만 적용한다. D2 fallback 검사 성공 시 SCHEMAS의 선언→분기
의무 1개, D4 direct+graph 성공 시 NAMES 의무 1개를 해소한다. 다른 entrypoint의 같은
진단 문자열, C residual scope, 미등록 production source는 제거하지 않는다. 누락 입력이면
기존 의무를 유지한다. fixture로 이 구분을 검사한다.

현재 source/근거/의존 파일 48개, operation 관측 158개·capability 154개이며 미분류는 0개다.
전체 M0는 여전히 INCOMPLETE: C residual 28개와 unregistered source 8개, 총 **36개**가
남는다. 기존 34개에서 새 의존 파일 4개를 포함하고 검증된 선언 의무 2개를 해소한 수치다.
남은 미등록 파일은 wrapper 정의, integration backend/mutation 구현, guard/declaration
의존 및 CLI header의 전체 추출 역할이며, 일부 사용한 함수/선언을 확인했다고 전체 파일을
면제하지 않는다. 897개 tracked 경로 snapshot도 전수 operation 증명이 아니다.

macOS host capability 정적/fixture 회귀 **206/206 PASS**, diff 검사 통과. 실제 E2E·CI·
Linux/Windows는 실행하지 않았다. 기존 연결·승인·증거·TRAP·실제 Work·native core는 보존했다.

### 6.17 승인된 native API 종료 경계·helper 검사·추가 named wrapper

C scope는 선택 dispatcher의 operation 분기와 명시 helper를 대조하고, 공개 native API의
고정 선언과 별도 capability 항목에서 종료하는 계약을 채택했다. 외부 C 라이브러리는
명시 경계로 기록하며 런타임 안전성/성공을 인증하지 않는다. 내부 helper는 소스 hash·정의·
호출 집합을 별도 검사한다. 새 호출·간접 호출·불명확한 위임·선언/capability 누락은 차단한다.

`capability_c_closure.py`와 고정 registry를 추가했다. 처음 적용한 events dispatcher의
호출 12개는 외부 경계 7개, 공개 native API 4개, cli_error_note helper 1개다. helper의
strcmp 호출도 따로 검사한다. runtime cursor parse/snapshot/export와 status string API를
고정 header 선언·별도 capability에 연결했다. 모든 조건이 충족되어 events의 잔여 scope
**1개만 해소**했다. 필요한 header/diagnostic source도 이 명시된 사용 범위의 등록된
의존으로 처리하며 전체 header·error 구현의 operation coverage를 주장하지 않는다.

현재 source/근거 53개, 관측 162개다. **남은 blocker는 35개(C residual 27 + 미등록 source 8)**다.
이는 M0 전수 완료가 아니다. 공개 선언 경계가 JSON operation 또는 미해석 간접 호출을
자동 해소하지 않으며, 아직 다른 C dispatcher에 대해 같은 근거가 모두 준비된 것은 아니다.

추가로 GOLEM_RECORDED_REQUIRED_API와 GOLEM_RECORDED_RELEASE_API 정적 profile을 승인받아
지원했다. 일반 wrapper의 begin 실패 시 중단, required의 실패와 무관한 본문 실행,
release의 void 정리 경로를 WRAPPER_SEMANTICS에서 구분한다. 정의/호출 소스 hash, 정확한
macro 이름·인자 수·본문 형태를 검사하고 임의 macro 실행이나 전처리는 하지 않는다.
실제 runtime_cancel/runtime_free 선언은 정적 fixture로 확인했으나 runtime 실행·소멸을
수행하지 않았다. 추가 wrapper 지원만으로 record_internal.h 전체를 면제하지 않는다.

macOS host 정적/fixture 회귀 **213/213 PASS**. fixture는 native capability/선언 누락,
helper drift, 신규 호출, 경계 미등록, wrapper 정의 drift·추가 인자·미지원 이름을 포함한다.
실제 E2E·CI·Linux/Windows는 NOT_RUN. 기존 core·연결·승인·증거·TRAP·실제 Work는 보존했다.

### 6.18 인계 재검증·잘못된 긍정 수정·저장소 gate

이 절은 전수 확장 이전의 인계 재검증 기록이다. 최신 상태는 §6.19다. 앞선 6.17의 53/162/35·213개 회귀는 인계 기준으로
재현했으며 현재 상태와 구분한다. 상세 결함·근거/결정/구현/시험 대응은
[재검토 기록](mcp-m0-review-2026-10-26.ko.md)을 따른다.

수정한 판정 결함은 public C prototype의 잘못된 인정, wrapper 본문/인자 전달 누락,
반대 조건·selector를 요구하지 않는 OR·중첩/모순 분기·callee signature의 잘못된 edge
인정, reference digest/명시 locator 미확인 수락, native/private helper의 외부 경계 위장이다.
실패 fixture를 먼저 재현하고 수정했다. callback parameter 선언/unsized array의 이름
전달은 지원하되 callback 실제 호출·receiver 신원은 확인하지 않는다.

미등록 source 8개에는 source 전체 interface 역할을 명시했다. private header 3개는
정확한 선언 집합과 recorder token model을, Python 5개는 함수/메서드·닫힌 CLI 선택지와
필수 D1/D2/D4 연결 profile을 대조한다. D1 backend의 4종 고정 argv, D4 stdio의 14개
선언 이름 변환·callback 전달 검사를 추가했다. 이름·source hash만으로 역할을 자동
신뢰하지 않으며, 신규 선언/선택지·source drift·필수 검사 누락은 다시 차단한다.

누락됐던 owner transfer `schema`/`plan` 2개를 추가하여 선택 관측은 164개,
capability는 160개다. source/근거는 53개다. 미등록 8개 의무는 해당 근거로 해소했지만
C scope 27개는 유지한다. completion/reentry report CLI가 `project=true`로 투영 파일을
생성·복원할 수 있음을 확인하여 MCP_READ target을 검토된 변경 backlog로 수정했다.
하위 효과를 아직 검토하지 않은 CLI 119개도 빈 effects 대신 UNVERIFIED로 기록했다.
따라서 **현재 선택 gate blocker는 146개(C scope 27 + effects 119)**다.

`capability_check.py --root "$PWD" --repository-sources`는 기존 bounded/no-follow reader로
후보 source 표면 424개와 선택 근거 14개, 총 438개 source bytes를 명시 선택해 검사한다.
자동 import·runtime/client 실행·기록 경로 추적은 하지 않는다. 고정 index 897개 중 다른
경로도 자동 제외하지 않는다. 미추적 경로는 별도 고정 Git metadata 조회로 대조하며,
이름 등록을 내용 coverage로 세지 않는다. `capability_report.py`도 repository gate를
기본 적용하므로 선택 sample 성공만으로 exit 0을 반환하지 않는다.

전체 public header 48개·344개 직접 선언을 재추출하고 각각 고정된 직접 정의 또는
세 named wrapper 정의 한 곳에 대조했다. 344개 연결에 blocker는 없지만 behavior,
callback receiver, 실행 검증 flag는 모두 false다. 이는 344개 기능 PASS가 아니다.
선택 ledger와의 연결이 없는 공개 선언은 340개이며, 후보 source 368개에는 전체
operation 검토가 남는다. 다른 tracked 경로의 제외/근거 경계 검토 459개, 미추적 개발
source 검토 40개도 gate에 남는다. 이 값들은 서로 겹치는 검증 의무이지 기능 수나
완료율의 분모가 아니다. [원본 재계산](mcp-m0-reconciliation.json)과
[생성 표](mcp-m0-repository-scope.md)를 권위 있는 최신 관측으로 사용한다.
[공개 선언 draft](mcp-m0-public-observations.json)는 동일 v1 schema의 **미분류 관측**이며
빈 capabilities를 성공으로 승격하지 않는다.

검증(macOS host): capability **268/268**, 기존 D1 fixture **25/25**, D2 **15/15**,
D4 **19/19** 통과. `git diff --check` 통과. source 실제 bytes를 검사한 정적 fixture와
합성 변형 fixture이며 실제 Codex/Claude E2E·실제 Work·CI·Linux/Windows는 **NOT_RUN**.
기존 연결·승인·producer·QA 보호·증거·TRAP·VM·UACTT·원본 저장소는 변경하지 않았다.
commit/push·설치·추가 복구 계층도 없다. M0 출구 조건은 미충족이며 M1로 진행하지 않았다.

### 6.19 전수 source·operation 검토와 M0 정적 출구 충족 — 최신

기존 C residual 27개와 effects UNVERIFIED 119개는 실제 source 계약으로 해소했다.
CLI 24 root의 291개 helper/4,377개 call 대조와 native operation 4개 표면의 별도 공개
API/schema 소유 경로를 구분한다. public API 344개·callback 선언 30개 모두 원장에
연결했고, 424개 source 전체의 역할·symbol·선언·분기·operation과 473개 제외 경계를
검토했다. package/build 경계 28개의 내용도 고정해 entrypoint drift를 차단한다.

원장: source/근거/계약 513개, 관측 2,107개, capability 1,078개. selected/repository
blockers 0, native 정의 344개 blocker 0. 이는 정적 inventory 출구 충족이며 모든 기능의
MCP 제공·실제 실행·권한·제품 인증 PASS가 아니다. 검토된 MCP facade backlog 312개와
owner/배포 83개, 역사적 prototype 등 지원 제외 17개를 구분했다. action은 M2 입력 준비에
의존하며 M1/M3/M4/M5 구현과 M6 owner/배포 검토로 연결한다.

사용자가 채택한 public callback 선언 경계·두 TRY 정의만 명시 지원한다. native 내부
private publication guard도 사용자 추가 채택에 따라 등록된 두 고정 값(NULL/as_publication_guard)
전달만 별도 profile로 지원한다. 선언 4개·정의 6개·전달 4개·인자/context·fenced/clock·
CAS 검증→guard→실패 return→publication 순서를 검사한다. 다른 진입점/alias/동적 대상과
실제 receiver·정책·실행은 인증하지 않는다. 기존 CLI literal NULL과 공개 API 종료 경계를 유지한다. source 1 MiB 한도는 그대로며
원장은 기존 decoder의 16 MiB domain을 고정 reader로 사용한다. 임의 전처리/동적 receiver
추론·설치/승인 변경·E2E·commit/push는 없다.

파일별 근거·효과 수정·문헌 열람 범위·검증·단계/Git 보존은
[최신 검토 기록](mcp-m0-review-2026-10-26.ko.md), 실제 재계산은
[JSON](mcp-m0-reconciliation.json)을 따른다. 재생성은 `capability_refresh.py --root "$PWD"`다.
검토 모델/원장은 자동 갱신하지 않는다. 실제 E2E·native Work·CI·Linux/Windows는 NOT_RUN.


## M1 구현 이후 최신 상태 — 2026-10-26

M1의 local typed 읽기 21개를 기존 D2 7개와 연결했다. 원래 M1 backlog 120개 ID를 유지하고 기능별 core/argv·resource·fixture 근거를 대조했다. 전체 표와 권한 경계는 [M1 읽기 검토](mcp-m1-read-coverage.ko.md), 실제 재계산은 [원장 대조](mcp-m0-reconciliation.json)의 `m1_read_coverage`를 따른다. 읽기 84·공통 core 7·내부 의존 20·owner 5·혼합 3·source 준비 1을 각각 구분한다. source capture M3, billing 독립 reconciliation M4, owner policy/config 계획·검사 M6 경계를 숨기지 않는다.

전체 source horizon은 기존 424에 새 runtime 읽기 모듈 3개를 추가한 427이다. 명시 source/근거 520개, 관측 2,156개, capability 1,106개로 확장했다. tracked index 기준 897개와 기존 boundary 검토는 유지한다. 새 runtime을 개발 분석 파일로 제외하지 않는다. 분석기/검토 모델/원장은 검사기가 자동 갱신하지 않는다. source·operation·효과·connection·전수 gate의 검토 모델을 명시적으로 갱신했다.

| 단계 | 이번 개발 상태 | 남은 검증·기능 |
| --- | --- | --- |
| M0 | 확장된 horizon의 목록·정적 gate 유지 | 실제 실행/권한 충족을 인증하지 않음 |
| M1 | 읽기 코드·정적 연결·임시 fixture 구현, 선택적 owner resource 계약 | 실제 설치·노출/client E2E NOT_RUN; owner/source/billing 경계는 표의 후속 단계 |
| M2 | 신규 준비 기능 확장 미착수 | 기존 typed action의 준비 의존 유지 |
| M3 | 본격 수명주기 확장 미착수 | context publish·fresh discovery source capture 포함 |
| M4 | 실행/QA 확장 미착수 | billing 검증/정확 join과 evidence 실행 권위 유지 |
| M5 | 병렬/병합 확장 미착수 | 기존 backlog 유지 |
| M6 | skill/패키징 확장 미착수 | 실제 owner 정책·설치·승인·설정 작업 유지 |
| M7 | 실제 client harness 확장 미착수 | Codex/Claude E2E NOT_RUN |
| M8 | 최종 전체 제공/CI 미완료 | Linux/Windows·CI NOT_RUN, commit/push 없음 |

과거의 M0 미완료/M1 미착수 절은 이전 checkpoint다. M1 코드 검증을 계획의 장기 출구 조건인 실제 client 노출 검증으로 바꾸지 않는다. 원본·활성 연결·기존 승인/pin/Work/evidence는 변경하지 않았다.


## M2 입력·준비 이후 최신 상태 — 2026-10-26

M2의 입력/초안/구조 검증/불변 plan/owner action 검토/확인 도구 6개를 기존 D2·D4에 연결했다. [구현·수명·검증 기록](mcp-m2-preparation.ko.md)과 원장 대조 JSON의 `m2_preparation_dependencies`를 따른다. 기존 준비 의존 134개 ID를 보존한다: D4 typed 초안/owner byte 검토 26, core artifact 구조 검증 22, 현재 입력 basis와 후속 native route 경계 86이다. 뒤의 86개를 operation-specific typed schema/실행 제공 완료로 계산하지 않는다. M3 60/M4 45/M5 29의 준비 의존이며 해당 단계의 native 권한·효과·실행 경로는 여전히 별개다.

COV-D03의 구현은 기존 private audit에 저장하는 동일 instance·30분·현재 등록 Work basis의 비권한 plan이다. 사용자 상관 ID는 재조회용이고 native key/D4 request ID를 대체하지 않는다. 같은 요청의 결과 유실 후 재조회는 원래 plan/key/bytes를 반환하며 stale/conflict/재시작 시 자동 복구하지 않는다. owner action 파일·승인·정책을 새로 작성/적용하거나 기존 승인 bytes를 고치지 않는다. 실제 dispatch는 기존 D4/core 검사를 유지한다.

전수 source/근거 525개·관측 2,171개·capability 1,115개, product source 429개로 horizon을 확장했다. source·operation·효과·기존 D2/D4/M1 및 새 M2 profile을 함께 검사한다. 기존 미제공 delivery 190개(M3 60/M4 83/M5 47), owner 관리 83개·역사적 지원 제외 17개는 보존한다. 새로운 준비안이 그 native 실행을 제공하거나 승인했다는 뜻이 아니다.

| 단계 | 현재 코드·검증 상태 | 남은 범위 |
| --- | --- | --- |
| M0 | M2 source/operation을 포함한 전수 정적 대조 | 실행/권한/실제 receiver 인증 아님 |
| M1 | 기존 읽기 구현·회귀 유지 | 실제 client 노출/E2E NOT_RUN |
| M2 | 공통 입력/불변 준비/owner byte 확인 구현·정적/fixture 검증 | 실제 client 사용성/노출 검증 NOT_RUN; operation별 새 native route는 M3~M5 |
| M3 | 신규 수명주기 확장 미착수 | creation/누락 operation별 권한·typed action·finalize |
| M4 | 신규 QA/실행 확장 미착수 | 원래 protected source/approval/evidence/native 실행 계약 |
| M5 | 신규 병렬/병합 확장 미착수 | host/runtime handle·source 범위·native 효과별 계약 |
| M6 | 신규 배포/owner 관리 확장 미착수 | 기존 launcher/정책/승인/pin 유지, 자동 적용 없음 |
| M7 | 실제 client harness 확장 미착수 | Codex/Claude/remote E2E NOT_RUN |
| M8 | 최종 전체 제공/CI 미완료 | Linux/Windows·CI NOT_RUN, commit/push 없음 |

이전의 M2 미착수 절은 과거 checkpoint다. 현재 code/정적/fixture 검증과 실제 client 검증·전체 native 기능 제공 완료를 구분한다.


## M3 완료 후 현재 상태 (2026-10-26)

[M3 구현 기록](mcp-m3-task-actions.ko.md): 고정 backlog 60개를 새 typed action 20개·기존 D4 7개 및 M2 준비 계약에 연결했다. source/근거 529개·관측 2,215개·capability 1,139개·product source 430개, 선택/저장소 blocker 0이다. tracked baseline 897개와 기존 callback/TRY/publication guard·boundary 계약은 유지한다. M4 83/M5 47, delivery 130개와 owner 83/unsupported 17은 남긴다. M1의 120개·M2의 134개 표는 당시 의존성 근거이며 M3 완료는 별도의 고정 60개 표로 대조한다.

검증: M3 제품 fixture 19개, M3 정적 fixture 9개, 전체 integration 272개(254 통과/18 skip), capability 334개, C API unit 25개 통과. 실제 client/Work E2E·Linux/Windows·CI·commit/push는 NOT_RUN이다. 기존 연결·승인·원본·Work·staging을 변경하지 않는다.


## M4 후 현재 기록 (2026-10-26)

[M4 계약·83개 처리표](mcp-m4-quality-evidence.ko.md): D2 read 4개·D4 action 7개를 추가하고 기존 core·M2·M3·QA host 및 별도 owner helper effects 계약에 연결했다. M4의 cost inbox는 첫 단계 disposable accounting이며 live run attach/정산이 아니다. 실제 외부 서비스·client/Work E2E는 NOT_RUN이다.

정적 source/근거 535개·관측 2,249개·capability 1,162개·product source 433개, 선택/저장소 blocker 0. 고정 M1 120/M2 준비 의존 134/M3 60/M4 83의 근거를 각각 유지하며, 남은 native delivery는 M5 47개다. owner 83개와 unsupported 17개를 유지한다. 기존 callback/TRY/publication guard·boundary·tracked baseline 897개를 약화하지 않는다.

M4 fixture 34개·정적 fixture 11개·helper 회귀 192개·C API unit 37개 통과. 전체 integration 306개(288 통과/18 skip), capability 345개 통과. 기존 연결·승인·원본 변경·Work·staging을 보존하고 install·승인 적용·실제 외부 서비스·E2E·CI·commit/push는 수행하지 않았다.


## M5 이후 현재 원장 (2026-10-26)

[M5 계약·고정47개 처리표](mcp-m5-parallel-candidates.ko.md): source/근거542·관측2275·capability1180·product437. 기존 47개 native facade는 명시 owner host/정확 action/읽기·준비 경로에 연결했다. delivery backlog0은 scheduler·merge 구현 완료가 아니다. P4/P5의 scheduler·typed edge acceptance·resource broker·merge queue·integration workspace/fresh QA·target ref CAS broker·merge publication receipt 7개 의무는 NOT_IMPLEMENTED로 별도 유지한다. owner 관리83개·unsupported17개·기존 M1~M4 고정 원장/guards를 보존한다. D2 read/preparation43개+D4 action37개이며 실제 노출 수·권한은 기존 owner 정책을 따른다. 실제 host/client/Work E2E·승인 적용·외부 서비스·merge·CI·commit/push NOT_RUN.


## M6 명시 범위 기록 (2026-10-26)

M6 이후: source552·관측2282·capability1187·whole-file surface444, M0~M6 blocker0. 5개 profile/스킬 분리/검토용 패키지/기존 Installer·D5 위임을 구현했다. owner83개는 고정 ID·current/target route·효과를 유지한 경계 검토이며 backlog에 남는다. 새 MCP 도구/권한은 추가하지 않았다. M5 미구현7개·unsupported17개·실제 설치/재로딩/운영 검증 경계는 유지한다. 상세 계약·처리표·검증은 [M6 기록](mcp-m6-distribution.ko.md)을 따른다.
