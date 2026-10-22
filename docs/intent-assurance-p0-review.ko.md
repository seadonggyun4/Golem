# Intent Assurance P0 착수 검토

검토일: 2026-10-22. 기준 HEAD: `f681d74c0eb77622374da7ddd0ec79c861214f59`.
상태: **인계 수신·P0 검토 수행, 계약 동결 및 제품 구현 미완료**.
이 기록은 native decision assertion, 실행 승인, 제품 수락 또는 배포 승인이 아니다.

## 1. 수신과 보존

아래 원본 7개 문서를 모두 읽었다. 합계는 970줄·128,776바이트다.
착수 시 7개는 untracked였고 tracked diff는 없었다. 이번 검토에서 원본을 수정하지
않았으며 읽기 전후 SHA-256이 각각 일치했다. 발신 측의 source/SSD 7쌍 비교와는
별개 관측이며, 본 검토가 발신 측 원본 사본까지 다시 해시 비교했다는 뜻은 아니다.

| 문서 | 수신 SSD bytes의 SHA-256 |
| --- | --- |
| [plan](intent-assurance-plan.ko.md) | `56f97e615c390ff9b69c2f376fbf1584732e6699302e7ed8ef56e310dd592889` |
| [architecture](intent-assurance-architecture.ko.md) | `bd43f112e406a704ad7b1f2734bb41757cf175e8e7931286532c7c9a959642c9` |
| [contracts](intent-assurance-contracts.ko.md) | `066de9420ae806fde63cbbf0dccb4222ff9df2a3fc90e0847a76f237b12996cb` |
| [parallel](intent-assurance-parallel.ko.md) | `eb9f3654a79d8428731bf98cb183b5fdce63821c2bb0f94959a00949e1196cab` |
| [distribution](intent-assurance-distribution.ko.md) | `f37a2fe5948b845923b988587b68596873dec746be29063fc45a1a6385642f03` |
| [delivery](intent-assurance-delivery.ko.md) | `80629a35a1d716fea023226a287e98fd9a611dfe3ec0bc983c4a0134ecbcb50a` |
| [references](intent-assurance-references.ko.md) | `2ab19c513780c63d6bf3bc1044df914c71ec0cd46587fdcf253783c56ca7b32f` |

`05de91e`의 문서 변경과 `f681d74`의 D1/D3/D4 손상 fixture 수정 3개를 구분했다.
이번 P0에서는 core, 기존 증거·CAS·journal·receipt·등록 revision, TRAP/Daybreak,
실제 Work, client 설정을 변경하지 않았다. CI 관찰·제품 빌드/테스트·credential 생성·
서명 발급·commit/push·설치·배포도 수행하지 않았다.

## 2. 원문 직접 대조와 요구 이해

plan에 보존된 SRC-U01–U05와 R01–R12 표를 직접 읽고 대조했다. SRC-U03의
제공된 단일 메시지 전체 text를 요구 표의 1–5항 및 마지막 병렬/MCP 단락과 비교했다.
이는 제공된 text 범위의 대조다. 원 플랫폼의 message bytes를 독립 재조회하거나
전체 과거 대화·첨부의 완전성을 검증한 것은 아니다.

| 원문 범위 | 대조 결과·설계 경계 |
| --- | --- |
| SRC-U03 1·5항 → R01 | 최초 원문과 명시 확정 변경 유지. immutable bytes·digest·baseline 형식은 도출 설계이지 이미 승인된 native schema가 아님 |
| SRC-U01·SRC-U03 2항 → R02 | 요구·설계·분할·구현·테스트에서 원문을 직접 봐야 하며 앞 산출물만 비교하는 것으로 대체 불가 |
| SRC-U02·SRC-U03 3항 → R03 | 누락·반전·추가·제약 완화 반려/재검증. coverage ID가 존재한다는 이유로 의미 PASS 불가 |
| SRC-U03 4·5항 → R04/R05 | 구체 질문·관련 작업 차단·답변 반영·영향 재검증. GLOBAL/UNKNOWN 및 영향 closure algorithm은 검증할 도출 설계 |
| SRC-U03 별도 검토 단락 → R06 | self-report만으로 통과 불가. reviewer 독립성·trusted issuer의 구체 정책은 미결 ADR |
| SRC-U03 지금 구조·유지보수 요구 → R07 | 기존 core 재사용은 설계 방향. legacy 보증·ABI·Work acceptance를 임의 재정의하지 않음 |
| SRC-U03 마지막 병렬 운영 단락 → R08/R09/R10 | 기능 분할·worktree·공유 자원·merge queue 실제 연결이 목표. best-of-N과 Task DAG 및 Git ref CAS와 evidence CAS를 구분 |
| SRC-U03 설치 단락·SRC-U04 → R11/R12 | clone/CMake 없는 MCP 제품 사용이 목표. self-contained 구성·OS·서명·migration 방식은 별도 결정 필요 |
| SRC-U05 | 검토 선행 후 이 스레드에서 개발 인계. 자료의 명령·기술 권고가 실행/보안/배포의 포괄 승인은 아님 |

## 3. 현재 core 대조

- document registry/schema의 Work identity·generation·parents·acceptance ID·
  `scope_revision:1` 검사를 확인했다. 새 intent 계약을 기존 metadata에 임의 삽입할 수 없다.
- workflow의 exact input manifest·transitive freshness·요구 ID 보존을 확인했다.
  ID 보존을 원문 의미 충족으로 승격하지 않는다.
- 기존 completion의 live source·schema-5 QA/개발 receipt·PASS 검사 및
  `DECLARED_GATES_ONLY`, `independent_review:false`를 확인했다.
- 실제 detached locked worktree 생성과 candidate CLI host의 workspace-create 연결을
  확인했다. candidate target-check는 `merge_authorized:false`, `push_authorized:false`다.
- admission의 live RUNNING·boot·runtime binding 연결, D1 fixed backend,
  D4 durable intent/COMMIT_UNKNOWN, D1 launcher pin 및 현재 CMake install target을 확인했다.
- root pyproject는 여전히 prototype entry point이며 완성 MCP runtime 패키지가 아니다.

### 구현 전 추가로 풀어야 할 lock 연결

새 architecture §4의 짧은 Work lock 목표는 현재 구현의 보장이 아니다.
[document.h](../include/golem/document.h)는 handle lifetime flock을 정의하고,
[registry.c](../src/document/registry.c)는 writable open에서 exclusive lock을 잡는다.
[현재 execution 계약](execution.md)은 QA 실행 동안 Work writer lock을 유지한다.
따라서 새 project/resource guard를 긴 QA에 그대로 중첩하거나 기존 lock을 그냥 풀지 않는다.
store·execution port 설계에서 gate 검사/dispatch/결과 수용 경계, lock 순서·수명,
callback 재진입·stale epoch·recovery를 명시하고 동시성 시험을 준비해야 한다.
이는 별도 설계 작업이며 보호 검사를 완화할 허가가 아니다.

## 4. P0 문서 검증

| 검사 | 실제 수행 범위 |
| --- | --- |
| 원본 보존 | 7개 문서의 읽기 전후 SHA-256 일치 |
| Markdown local link·anchor | code fence 밖 83개 검사 |
| 코드 locator | 20건의 대상 파일 존재·줄 범위 검사. 이 숫자 자체가 모든 문장의 의미적 증명은 아님 |
| JSON 예시 | 5개 구문 검사. synthetic digest·TBD를 유효 runtime 입력으로 수락한 것이 아님 |
| 포함된 JSON Schema | 제안 mutation envelope 1개를 Draft 2020-12로 검사, 정상 1건·거부 16건 확인 |
| Mermaid | 4개 실제 렌더링 완료. 미래 API와 제품 동작은 검증하지 않음 |
| 미래 수용 계획 | A01–A27의 하위 사례 포함 31개 named case를 계획으로 유지. 제품 시험은 모두 NOT_RUN |

source/baseline/review 등 나머지 신규 계약의 완전한 schema validator는 아직 없다.
예시 하나의 schema 검사를 신규 API 전체 conformance로 확대하지 않는다.
문헌 19개는 전달 문서의 확인 범위와 한계를 읽었으며, 이 P0에서 문헌 원문/저서 전체를
새로 재검증한 것은 아니다. 사용자 의미 정확도·비용·병렬 성능을 실증하지 않았다.

## 5. 설계 결정 현황

### ADR-D01: 본 대화에서 채택 확인

사용자는 단일 local authority 권고안 선택에 응답했다. 확인된 설계 범위는:

- repository마다 명시 등록한 프로젝트 밖 private authority root 하나를 사용한다.
- repository/Git common-dir identity와 공통 owner lock을 결합한다.
- 여러 설치는 같은 authority를 공유하고 identity/path/pin 충돌 시 쓰기를 거부한다.
- 자동 경쟁 authority 생성·암묵적 재신뢰·분산 HA를 기본으로 넣지 않는다.

실제 authority 경로·등록을 적용한 것은 아니다. 이 대화의 설계 선택 기록은
native human decision assertion이나 암호학적 issuer 인증을 대신하지 않는다.
D02의 신뢰 경계·key custody·허용 assurance는 여전히 미결이다.
원본 7개의 미결 ADR 표는 수신 snapshot으로 보존했고, D01의 후속 결정은 이 기록에 분리했다.

### ADR-D08: 본 대화에서 부분 채택, 나머지 명시 보류

사용자가 다음 두 선택에 응답했다.

- 초기 의미 검토는 UTF-8 텍스트 우선이다. PDF·이미지는 원본을 보존하더라도
  추출/OCR 검증 전 의미 검토 완료로 승격하지 않고 미지원으로 차단한다.
- 아래 문서 제안 상한을 채택하며 초과 시 자동 상향·조용한 누락 없이 거부한다.

| 항목 | 채택한 초기 상한 |
| --- | --- |
| Control JSON | 256 KiB |
| Source body / baseline 전체 source | 16 MiB/객체, 64 MiB/baseline |
| 활성 요구 | 1024 |
| Trace node / edge / node parent | 4096 / 16384 / 64 |
| 미해결 의무 / review observation | 각 256 |
| Dispatch manifest | 32 MiB |

이는 지원·한도 정책의 설계 결정이며 값이 실제 native API에 구현됐다는 뜻은 아니다.
기존 document body 상한·CAS hash·D2 전달 한도를 제자리 확대하지 않는다.
사용자는 event retention/rollover와 digest domain 세부의 동결을 보류했다.
이 미결을 임의 기본값으로 메우거나 domain hash를 legacy CAS key로 바꾸지 않는다.

### 아직 동결하지 않은 범위

P0 당시에는 D08의 digest domain registry·event retention/rollover가 P1 schema/store 동결의
남은 의존 결정이었다. digest 후속 승인은 아래 §7에 기록한다.
D02/D03/D04/D05/D06/D07/M01도 각각 activation/review/dispatch/
release/publish/migration을 막는다. D01과 D08 부분 선택만으로 이들을 승인 처리하지 않는다.

## 6. 다음 구현을 위한 fixture·상태 모델 준비표

아래는 설계 준비이며 모두 **예상 결과, native 실행 NOT_RUN**이다. 위 예시 schema
검사 결과와 혼합하지 않는다. 미결 정책의 선택을 요구하는 행은 구현/동결하지 않는다.

| 준비 단위 | 최소 fixture·예상 차단 | 선행 결정·경계 |
| --- | --- | --- |
| Source root shape | 최초 source는 미래 baseline 없이 생성; 금지 baseline 역참조·중복/unknown field 거부 | D08 digest domain 동결 전 authoritative object identity 발급 금지 |
| Exact UTF-8 / byte range | 한글 다중 byte 경계, 잘못된 UTF-8, `[start,end)` 역전·범위 초과·중간 byte 절단 | 한도/텍스트 정책은 채택됨. 원본 bytes를 정규화하거나 UTF-16 offset으로 대체하지 않음 |
| Coverage | union gap·범위 초과·겹침, 필수 구간 누락, 모든 구간 NON_NORMATIVE 위장 | 구간 계산과 의미 분류의 진실성 분리; D03 review 정책 없이는 의미 PASS 발급 불가 |
| Capacity | 각 상한 직전/정확히 상한/초과, 분할 source의 aggregate 초과·누락 manifest | 상한값만 확정; event 수·rollover 기본값은 미정이며 자동 GC 없음 |
| Root → baseline → bound object | source adoption·정의·baseline·review/activation의 비순환 참조, stale membership 거부 | trusted adoption/activation은 D02가 막으며 모델 label로 대체 불가 |
| Prospective resolution | OPEN에서도 답변/해결 control 접수, close/carry 누락·stale head·미해결 PASS 거부 | 실제 issuer/해결 정책과 project journal 경계가 확정되기 전 native 전이 없음 |
| Store concurrency / recovery | 두 설치의 같은 authority 사용, expected head 충돌, append/fsync 불확실·재open lookup | D01 방향은 채택됨. D08 retention, lock 수명·ABI/ownership 상세를 먼저 설계 |

기존 `struct_size/version`, allocator 수명, borrowed input, unchanged-on-failure output,
명시적 free와 strict JSON 관례를 ABI 검토의 출발점으로 삼는다. 아직 새로운 public header,
schema 지원표, product store, native mutation, typed dispatch 또는 release를 만들지 않았다.

## 7. 후속 P1 준비 구현

이후 사용자가 승인된 D01·D08 범위의 schema·fixture 구현을 요청했다.
[P1 구현 기록](intent-assurance-p1-schema.ko.md)에 순수 native source/구간/coverage/상한 검사와
실제 수행한 회귀를 구분해 기록한다. 위 P0 당시의 NOT_RUN·미구현 표시는 당시 snapshot이며,
후속 일부 fixture 수행을 P1 store·전체 수용 계획 완료로 승격하지 않는다.

### ADR-D08 후속 승인: 명시 registry와 domain 분리

사용자는 신규 intent 객체에만 다음 규칙을 적용하는 안을 채택했다.

`SHA256(등록된 schema 이름의 ASCII bytes + NUL || uint64_le(원본 JSON byte 길이) || 원본 UTF-8 JSON bytes)`

등록하지 않은 schema는 거부하고 JSON을 정규화하지 않는다. 기존 raw CAS SHA-256은
바꾸지 않는다. 이는 issuer 인증·전체 schema 동결·store 시작 승인이 아니다.
현재 private 구현의 registry는 source.v1 하나이며 미래 baseline 등은 미등록으로 거부한다.
event retention/rollover는 계속 보류한다. 그 값을 임의로 확정하지 않았다.

### ADR-D08 후속 승인: 무삭제·한도 거부·초기 rollover 제외

journal 용량 실험 이후 사용자는 `무삭제·한도 거부, 초기 rollover 제외`를 채택했다.
committed event와 참조 증거를 자동 삭제하지 않고, 용량 한도에서 intake를 거부한다.
초기 P1 store에 rollover를 포함하지 않는다. 장기 무제한 운영을 의미하지 않는다.
위의 retention/rollover 보류 기록은 이 결정 이전의 상태다.
해결·복구 예약량, 총 quota 수치 및 회계 상세는 아직 승인하지 않았다.
후속 [용량 실험·결정 기록](intent-assurance-journal-capacity.ko.md)을 따른다.
이 승인은 store provisioning·issuer 인증·기존 Work 변경을 승인하지 않는다.

### ADR-D08 후속 승인: 전체 관리 파일 회계·다중 한도

사용자는 event 개수·payload bytes 외에 신규 authority 관리 파일 전체의 논리 bytes와
파일 엔트리 수를 제한하고 각 축에 해결·복구 예약량을 두는 방향을 채택했다.
CAS source·manifest·index·pending/orphan을 포함하며 물리 디스크 여유는 별도로 확인한다.
예약량은 모든 의무 해결을 보장하지 않는다. 실제 quota·예약 수치는 아직 미승인이다.
후속 수치 v2와 산정 가정은 journal 용량 문서에 기록한다.

### ADR-D08 후속 승인: 초기 수치 v2

사용자는 용량 문서의 v2 일반/해결/복구 한도 표를 채택했다.
총 6208 event, event payload 592 MiB, 전체 관리 파일 2176 MiB, 33792 entries다.
payload는 전체 관리 파일 bytes에 포함된다. 자동 상향·삭제·rollover는 없다.
일반은 해결·복구 예약을, 해결은 복구 예약을 사용할 수 없다.
충분성·처리시간·실제 디스크 공간 확보의 보장이 아니다. 순수 회계 fixture부터 구현한다.
위 수치 미승인 표시는 이 결정 이전의 이력이다. issuer·store 실제 생성 승인은 별개다.

### ADR-D08 후속 승인: 최초 lane 고정·준비 기록 기반 귀속

새 객체 비용은 최초 게시 lane에 고정한다. 다른 lane의 검증된 재사용은 추가 비용 0이며
기존 비용을 이동·환급하지 않는다. 데이터 생성 전 immutable 준비 기록에 operation·lane·
예정 객체를 결합하고 pending/orphan도 최초 lane에 계속 계산한다.
재시작 후 귀속을 검증할 수 없으면 임의 분류·삭제 없이 쓰기를 차단한다.
이는 사용자가 채택한 후속 의미 계약이다. 준비 기록 자체의 issuer 신뢰·closed schema 및
actual journal writer는 아직 구현되지 않았으며 읽기 전용 inventory와 구별한다.

이후 [private native event journal](intent-assurance-p1-journal.ko.md)에 준비 기록의
closed JSON 검증·domain identity·immutable 게시·비용 복원·owner lock 안 quota 재검사를
구현했다. 이는 위 미구현 기록의 후속 상태이며 baseline/issuer/실제 D01 host 등록 완료는 아니다.

### ADR-D01 후속 승인: common-dir locator

사용자는 Git common-dir의 owner-private locator를 명시 등록하는 방식을 채택했다.
journal·CAS·증거는 승인된 프로젝트 밖 root에 유지한다. locator의 경로·identity·등록
digest 충돌이나 누락은 자동 생성·재신뢰하지 않는다. 실제 프로젝트 등록은 이번 범위가 아니다.
[D01 host 연결](intent-assurance-d01-host.ko.md)에 등록·단일 authority binding·native
읽기 전용 조회를 구현했다. 임시 저장소에서만 검증하며 issuer/product 쓰기 권한은 보류한다.

### ADR-D01 후속 승인: 해제는 이력 보존 tombstone

사용자는 locator 삭제로 미등록 상태를 만드는 대신 기존 authority·등록 이력을 보존하고
명시적 폐기 상태로 접근과 자동 재등록을 차단하는 방식을 채택했다.
재활성화·authority 이동은 승인하지 않았다. trusted host의 해제 plan/apply는
common-dir EX → authority EX 순서로 잠그고 원본 locator·native journal을 수정하지 않는다.
별도 private tombstone을 no-replace 게시한다. 부분 게시 실패는 pending을 보존하고 차단한다.
등록 변경 및 부분 게시 복구 정책은 별도 결정 전까지 구현하지 않는다.

### ADR-D01 후속 승인: 동일 identity의 명시적 재승인

사용자는 동일 Git common-dir·authority identity를 유지하면서 Git/bridge pin·producer·
worktree 목록을 명시적으로 재승인하는 변경 범위를 채택했다. 검토한 변경 계획과 owner
승인을 요구하고 이전 등록과 변경 이력을 보존한다. 폐기된 등록의 재활성화 및 authority
이동은 계속 금지한다. 이 결정은 변경 게시 프로토콜·비용 lane·부분 게시 복구 정책의
승인이 아니다. 해당 API 구현은 후속 게시 계약 결정 전까지 보류한다.

### ADR-D01 후속 승인: native 변경 이력 우선·불일치 차단

사용자는 이전 등록 digest와 새 등록 digest를 묶은 immutable 변경 이력을 native
journal에 먼저 게시하고 확인 후 locator를 갱신하는 방식을 채택했다. 두 저장 영역은
원자적이지 않다. 진행 중 표시 또는 양쪽 등록 상태 불일치가 있으면 접근을 차단하고
자동 rollback·재시도를 하지 않는다. 비용 lane과 승인 기반 복구 조건은 아직 미결이다.

### ADR-D01 후속 승인: 일반 등록 변경은 intake 귀속

사용자는 일반 등록 변경 이력과 준비 기록을 intake lane에 부과하고 quota 부족 시
변경을 거부하는 방식을 채택했다. 재승인을 이유로 resolution/recovery 예약량을 사용하지
않는다. 부분 게시 복구의 비용 처리와 승인 기반 복구 조건은 별도 결정으로 남긴다.

### ADR-D01 후속 승인: 확정 native 기록의 locator 마무리만 복구

사용자는 정확한 대상 등록/변경이 native에 committed된 경우에만, 검토한 복구 계획과
owner 승인으로 locator 게시를 마무리하는 범위를 채택했다. identity·pin·이전/새 digest를
재검증하며 폐기 상태·모호한 이력·native pending은 차단한다. 기존 증거를 보존하고
native 재게시·rollback·재활성화를 하지 않는다. native event를 추가하지 않으므로
recovery 예약량을 소비하지 않는다. 미확정 native 게시의 복구 정책은 승인하지 않았다.

후속 구현 상태: 승인된 동일 identity 재승인·tombstone 해제·committed-only locator
복구를 private host API와 임시 Git/native 테스트로 구현했다. 아래 API가 아닌
미확정 native pending 재게시·폐기 재활성화·authority 이동은 여전히 미지원이다.
구체적인 계약과 검증 범위는 [D01 host 기록](intent-assurance-d01-host.ko.md)을 따른다.

### ADR-D01 후속 승인: 미확정 native의 완전한 준비 상태만 복구

사용자는 D01 등록·등록 변경에 한해 마지막 sequence의 완전한 준비 기록과 payload가
검증되고 event 및 staging alias가 없는 경우만 복구 대상으로 채택했다. 새 복구 계획과
owner 승인, 기존 guard 재검사를 거쳐 해당 event를 게시하는 범위다. 제품 실행·일반
Work 재시도는 포함하지 않는다. 부분 파일·불명확한 귀속·다른 owner·폐기 상태는 차단한다.
비용 귀속과 복구 승인 기록의 보존 방식은 아직 미결이며, 이 승인만으로 native 쓰기
복구 API를 활성화하지 않는다.

### ADR-D01 후속 승인: native 마무리 비용의 최초 intake 유지

사용자는 완전한 D01 준비 기록의 event 마무리와 게시 중 임시 파일 비용을 최초
intake lane에 유지하는 방식을 채택했다. 기존 event·payload 비용은 중복 청구하거나
환급하지 않는다. owner lock 아래 실제 inventory와 추가/peak quota를 재검사하며,
intake 부족 시 recovery 예약량으로 전환하지 않고 차단한다. 별도 복구 승인 기록의
저장 방식과 비용 귀속은 아직 미결이다.

### ADR-D01 후속 승인: host intent/history에 복구 승인 보존

사용자는 Git common-dir의 owner-private immutable 복구 intent를 native event 전에
게시하는 방식을 채택했다. 대상 등록·operation·sequence·head·준비/payload digest와
검토한 복구 계획 digest를 결합하고 성공 후에도 history에 보존한다. host metadata이며
native recovery 예약량을 사용하지 않는다. 승인 기록 게시 실패 시 native 쓰기는 하지
않고 미완료 intent는 접근을 차단한다. local owner의 명시적 승인 기록이지 외부 issuer의
인증된 서명은 아니다. 앞선 비용·보존 미결 기록은 이 후속 승인 이전의 이력이다.

후속 구현: complete-preparation native 계획/마무리 API, D01 전용 bridge 의미 검사,
host 승인 intent/history와 확정 후 locator 마무리를 연결했다. 기존 guard·owner lock·
snapshot·실제 inventory/peak quota 재검사를 유지한다. 상세 범위와 macOS 검증 결과는
[D01 host 문서](intent-assurance-d01-host.ko.md)의 승인 기반 native pending 절을 따른다.
기존 미확정 native 전부 미지원 표시는 이 제한 복구 구현 이전의 이력이며, 지원 외
부분/staging 상태의 정리나 재게시를 승인한 것은 아니다.

### ADR-D01 후속 승인: 검증된 동일 inode staging alias

사용자는 D01 마지막 sequence의 검증된 final 파일과 동일 inode를 가리키는 staging
hardlink만 첫 확장 대상으로 채택했다. 정확히 final/pending 두 이름, digest·귀속·owner를
검증하고 새 계획·owner 승인과 복구 기록을 먼저 보존한 뒤 pending 이름만 제거한다.
최종 파일 bytes와 확정 event는 변경하지 않는다. 독립된 부분 파일·final 없는 staging·
불명확한 host pending은 계속 차단한다. alias 제거 후 비용 회계는 아직 미결이다.

### ADR-D01 후속 승인: 검증된 staging 점유만 해제

사용자는 제거된 pending 이름의 실제 논리 bytes·file entry 점유만 최초 intake에서
감소시키는 방식을 채택했다. final 파일·event slot·payload 귀속과 다른 lane은 유지한다.
감소 전후 usage 및 제거 alias의 identity/digest를 복구 기록에 보존한다. 이는 기존 비용
이동·환급 금지와 구분되는 명시적 staging 점유 해제 예외이며 다른 파일 정리에 적용하지 않는다.

후속 구현은 native alias 관측/제거 API와 private D01 bridge, host 승인 intent 및
before/after receipt를 연결했다. 정상 final과 확정 event는 변경하지 않고 실제 점유만
재검사한다. 미확정 event 게시나 제품 실행을 자동 연결하지 않는다. 검증 결과와 제한은
[D01 host 기록](intent-assurance-d01-host.ko.md)의 검증된 native staging alias 절을 따른다.

### ADR-D01 후속 승인: 독립 부분 파일의 원문·귀속 보존 후 격리

사용자는 독립 부분 파일의 원문 bytes·원래 경로·digest·최초 lane을 보존하는 immutable
격리 기록을 먼저 확정한 뒤에만 활성 staging 위치에서 분리하는 원칙을 채택했다.
귀속이 불명확하면 이동도 거부한다. 추정 내용 보충·자동 삭제·event 재게시를 하지 않는다.
격리 저장 위치·비용 회계·완전한 원본으로의 대체 조건은 별도 결정 사항으로 남긴다.
이 원칙 승인만으로 실제 파일 격리나 저장 형식 변경을 수행하지 않는다.

### ADR-D01 후속 승인: 동일 authority 내부 격리 영역

사용자는 기존에 등록된 동일 authority 내부의 전용 private 격리 영역을 채택했다.
기존 owner lock과 전체 관리 파일 inventory·quota에 포함하며, 원문과 immutable
격리 기록을 보존하도록 저장 형식을 명시적으로 확장한다. 프로젝트나 Git common-dir로
원문을 옮기거나 별도 authority를 만들지 않는다.
복사 중 peak 비용·영구 보존 비용의 귀속과 완전한 원본으로의 대체 조건은 계속 보류한다.
이 위치 승인만으로 실제 파일 격리나 미결 비용 정책을 적용하지 않는다.

### ADR-D01 후속 승인: 격리 비용의 최초 lane 및 peak 회계

사용자는 보존 원문·격리 기록·임시 파일을 모두 검증된 최초 lane에 귀속하는 방식을
채택했다. owner lock 아래 원본과 복사본이 공존하는 peak bytes·entries를 사전 검사한다.
활성 staging 분리 후에도 보존 원문·기록의 실제 점유는 계속 계산한다.
event slot·payload 귀속을 변경하거나 다른 lane 예약량으로 넘기지 않는다.
한도 부족이나 귀속 불명확 시 원본을 그대로 두고 거부한다.
완전한 원본으로의 대체 조건은 별도 결정 사항으로 유지한다.

### ADR-D01 후속 승인: 검증된 준비 기록의 payload 대체

사용자는 초기 대체 복구를 완전한 immutable 준비 기록이 남아 있는 마지막 D01
sequence의 payload로 한정했다. owner가 명시 제공한 원본의 길이·digest가 준비 기록과
일치하고 D01 대상 등록·operation·request까지 검증되어야 한다.
부분 파일 격리 완료 후 새 복구 계획·owner 승인·owner lock 아래 quota 및 guard
재검사를 거쳐 누락 payload만 게시한다. 기존 정상 파일은 덮어쓰지 않는다.
준비 기록 자체의 손상과 불명확한 원본은 차단하며, 추정 내용 보충은 허용하지 않는다.
event 게시와 locator 마무리는 기존 별도 승인 절차로 유지하고 자동 연결하지 않는다.
이는 대체 조건의 승인 기록이며 격리·대체 실행 경로의 구현 또는 검증 완료를 뜻하지 않는다.

후속 구현(2026-10-22): private D01 host/bridge와 native journal에 독립 staging 격리 및
별도 payload 대체 경로를 연결했다. 동일 authority 내 immutable 원문/귀속 envelope,
최초 intake의 보존·peak 회계, 복사 후 상태 재검사와 별도 owner 승인 경계를 검증했다.
event 게시·locator 마무리는 자동 연결하지 않는다. Debug 5/5, ASan/UBSan 2/2,
Release 2/2 및 각 host 71/71 PASS. 지원 범위·미지원 중단 상태와 검증 한계는
[D01 host 기록](intent-assurance-d01-host.ko.md)의 독립 staging 격리 절을 따른다.
실제 프로젝트·TRAP·Work·기존 증거에는 적용하지 않았다.

### ADR-D01 후속 승인: 완전한 격리 envelope 게시 마무리

사용자는 마지막 D01 sequence에서 기존 owner 승인 intent·prep·원래 staging과
envelope의 원문·digest·귀속이 모두 검증되는 완전한 격리 기록의 게시 마무리를 승인했다.
새 계획·owner 승인·owner lock 아래 quota/guard 재검사 후 final이 없으면 덮어쓰기 없이
게시하고, final/pending이 정확한 동일 inode 쌍이면 pending 이름만 제거한다.
최초 lane 및 peak 회계를 유지한다. 원래 staging 분리·payload 대체·event 게시·locator
마무리는 자동 연결하지 않는다. 잘린 envelope·독립 중복 파일·불명확한 host pending은
계속 차단하며 후속 정책 결정 사항으로 남긴다.

후속 구현은 전용 envelope 관측/게시 마무리 API와 기존 격리 승인 intent에 결합된 새
owner 승인·receipt를 연결했다. 일반 조회의 pending 거부는 유지하며 원래 staging을
분리하지 않는다. macOS arm64 Debug 5/5, ASan/UBSan 2/2, Release 2/2 및 각 host
80/80 PASS. 상세 범위와 미검증 사항은 D01 host 개발문서의 envelope 게시 마무리 절을 따른다.

### ADR-D01 후속 승인: 검증된 host pending alias

사용자는 이미 게시된 완전한 복구 intent/receipt와 정확히 같은 inode를 가리키는
host pending 이름부터 복구하는 범위를 승인했다. 허용된 대상의 schema·digest·등록
binding·owner와 정확한 두 link를 검증하고 새 계획·owner 승인 기록을 먼저 보존한 뒤
pending 이름만 제거한다. final bytes와 native 기록을 변경하거나 후속 복구를 자동
실행하지 않는다. final 없는 pending·잘린 JSON·독립 복사본·불명확한 귀속은 계속
차단하며 별도 결정 사항으로 유지한다.

### ADR-D01 후속 승인: final 없는 완전한 host pending 게시 마무리

사용자는 현재 지원하는 D01 복구 intent/receipt 중 final이 없는 완전한 host pending의
게시 마무리만 첫 확장으로 승인했다. owner가 pending 이름과 대상 final 이름을 명시하고,
canonical JSON·schema·계획 digest·등록 binding·owner·단일 link를 검증해야 한다.
새 계획·명시적 승인과 기존 lock 아래 덮어쓰기 없이 게시하며 원문 bytes를 보존한다.
native 복구·event 게시·locator 처리는 실행하지 않는다. 잘린 JSON·불명확한 대상·새 복구
승인 기록 자체는 계속 차단한다. 새 승인 기록의 보존 및 중단 복구 방식은 아직 미결이며,
이 범위 승인만으로 쓰기 경로를 활성화하지 않는다.

### ADR-D01 후속 승인: host 게시 마무리의 승인 보존과 재진입

사용자는 기존 host intent/history 방식을 채택했다. Git common-dir 전용 immutable intent에
등록 binding·pending/final 이름·inode·원문 digest·검토한 계획 digest를 먼저 확정한다.
성공 후 receipt를 history에 보존한다. 중단 시 marker가 일반 접근을 차단하며 동일 원문이
pending-only·정확한 두 link·final-only 중 하나임을 재검증한 경우에만 새 계획·owner 승인으로
남은 게시 단계와 receipt를 마무리한다. 승인 기록 자체의 부분 게시·독립 복사본·추가 pending은
계속 차단한다. native 기록이나 quota lane을 변경하지 않는다.

### ADR-D01 후속 승인: 잘린 envelope의 검증된 앞부분 보존·분리

사용자는 마지막 D01 sequence의 완전한 prep·기존 격리 승인 intent·원래 staging이 모두
남아 있고, final 없는 envelope pending이 이 근거로 계산한 완전한 envelope의 정확한
앞부분과 일치하는 경우만 초기 복구 대상으로 승인했다. 320바이트 header는 온전해야 한다.
새 계획·owner 승인 후 잘린 bytes와 귀속 증거를 먼저 보존하고 활성 pending에서 분리한다.
내용을 덧붙이거나 완전한 envelope를 자동 재생성하지 않는다. header까지 잘렸거나 bytes가
불일치하면 계속 차단한다. 보존 형식과 게시 중단 복구는 미결이며 이 승인만으로 해당 쓰기
경로를 활성화하지 않는다. 기존 QA writer lock·보호 계약·증거와 실제 Work는 유지한다.

### ADR-D01 후속 승인: 잘린 envelope의 단일 immutable 보존 객체

사용자는 동일 authority의 private 격리 영역에 별도 버전의 immutable 보존 객체 하나를
두는 형식을 채택했다. 잘린 원문 bytes·원래 경로/inode·길이/digest·기대 완전본 digest·
prep/기존 승인/새 승인 digest·최초 lane을 함께 보존하고 정상 envelope와 구별한다.
기존 보존 및 peak 회계에 포함하며 덮어쓰기·자동 삭제하지 않는다. 보존 객체를 확정하고
재검증하기 전에는 원래 pending을 제거하지 않는다. 이 객체 자체의 게시 중단 복구 조건은
계속 미결이며, 형식 승인만으로 해당 쓰기 경로를 활성화하지 않는다.

### ADR-D01 후속 승인: 완전한 보존 객체의 게시 마무리

사용자는 보존 객체 자체의 게시 중단 복구를 완전한 객체에 한정했다. 기존 승인·prep·
원래 staging·잘린 envelope와 원문/귀속이 모두 일치할 때만 새 계획·owner 승인으로
pending-only를 덮어쓰기 없이 게시하거나 정확한 동일 inode 두 link에서 보존 객체의
pending 이름만 제거한다. owner lock 아래 최초 lane·peak quota를 재검사한다.
원래 잘린 envelope의 분리는 별도 승인 단계로 유지하고 자동 연결하지 않는다.
보존 객체 자체가 잘렸거나 독립 복사본·불명확한 상태이면 모든 원문을 유지한 채 차단한다.

### ADR-D01 후속 승인: 잘린 보존 객체의 제한된 보존·분리

사용자는 마지막 D01 sequence의 prep·기존 승인·원래 staging·잘린 envelope가 모두
남아 있고, final 없는 보존 객체 pending이 온전한 320바이트 header를 포함하여 기대
완전본의 정확한 앞부분인 경우만 대상으로 승인했다. 새 계획·owner 승인 후 검증된
원문과 귀속을 보존하고 pending 이름을 분리한다. 내용 보충·자동 재생성은 하지 않는다.
이 단계에서 새로 만드는 보존 객체까지 잘린 경우의 재귀적 복구는 허용하지 않는다.

동일 authority의 private 격리 영역에 별도 버전의 단일 immutable 객체를 둔다.
잘린 bytes·원래 경로/inode·길이/digest·기대 완전본 digest·prep 및 기존/새 승인 digest·
최초 lane을 보존한다. 원본과 복사본의 공존 peak 및 영구 점유는 최초 lane에 계산한다.
확정·재검증 전 원래 pending을 제거하지 않으며 한도 부족·귀속 불명확 시 원문을 유지한다.

새 객체가 완전하고 기존 근거·원문·귀속이 모두 일치하는 경우에만 새 계획·owner 승인과
기존 lock 아래 quota/guard 재검사를 거쳐 게시 마무리를 허용한다. pending-only는
덮어쓰기 없이 게시하고, 정확한 final/pending 동일 inode 두 link는 pending 이름만
제거한다. 최초 lane·peak 회계를 유지하고 원래 잘린 보존 객체의 분리는 별도 승인으로
남긴다. 새 객체 자체의 잘림·독립 복사본·불명확한 상태는 차단한다.

이 절은 승인된 정책의 기록이며 해당 경로의 구현 완료 선언이 아니다. 새 복구의 host
승인·receipt 보존 및 재진입 계약, 승인·receipt 자체의 부분 게시 복구는 별도 결정으로
남긴다. native event·locator 마무리와 자동 연결하지 않는다.

### ADR-D01 후속 승인: 잘린 보존 객체 복구의 host 승인·receipt

사용자는 기존 host intent/history와 단계별 재승인을 채택했다. Git common-dir의 전용
immutable intent에 등록 binding·대상 원문 identity/digest·기존 승인·검토한 계획 digest·
동작(보존/게시 마무리/별도 분리)을 결합하고 native 변경 전에 확정한다. 성공 후 receipt를
보존한다. 중단 시 일반 접근을 차단하고 실제 상태와 이전 승인 결과를 재검증한 새 계획·
owner 승인으로 해당 단계만 마무리한다. 기존 fragment 승인 기록은 유지한다. 새 승인·
receipt 자체가 부분 게시된 경우의 복구는 별도 결정 전까지 차단한다.

최초 구현은 `GIQFD001` 순수 codec과 최초 intake lane의 게시 peak 회계까지였다.
후속으로 전용 inventory 관측, native 게시/마무리/별도 분리 API와 host 승인·receipt를
연결했다. 실제 프로젝트 등록이나 자동 복구는 활성화하지 않는다. 대상은 기존 fragment
preserve intent가 완전하게 남은 마지막 D01 sequence이며, 기존 승인 marker는 유지한다.
새 보존 객체나 새 승인·receipt 자체의 손상 복구 정책은 이 구현으로 확대하지 않는다.

### ADR-D01 후속 승인: 완전한 fragment·damage host 기록의 게시 복구

사용자는 fragment·damage의 완전한 승인 intent·재승인 기록·receipt를 기존 host 게시
복구 대상으로 추가하는 범위를 승인했다. canonical JSON·schema·등록 binding·계획
digest·기존 승인 연결을 검증하고 pending-only 또는 정확한 final/pending 동일 inode
두 link에서 새 계획·owner 승인으로 게시만 마무리한다. 기록에 담긴 native 복구·event·
locator 처리는 실행하지 않는다. 잘린 JSON·독립 복사본·불명확한 귀속은 차단한다.

기존 host intent/history·명시적 재승인을 재사용한다. 등록 binding·대상 이름·inode·
원문 digest·기존 승인 연결·계획 digest를 별도 immutable host intent에 먼저 확정하고
완료 후 receipt를 남긴다. 중단 시 일반 접근을 차단하고 동일 원문의 pending-only·
정확한 두 link·final-only만 새 계획·owner 승인으로 마무리한다. 기존 fragment/damage
marker는 보존한다. 이 게시 복구 승인·receipt 자체의 부분 게시와 보존 객체의 재귀
복구는 계속 차단하며 별도 정책을 임의로 확정하지 않는다.

### ADR-D01 후속 승인: host 게시 복구 기록의 terminal 게시 마무리

사용자는 host-publication·host-alias의 완전한 승인 intent·재승인 기록·receipt를 대상으로
한 단계의 게시 복구만 허용했다. 원래 대상 기록과 의존 승인이 남아 있고 schema·등록
binding·계획·원문 digest·상태 관계가 검증돼야 한다. 새 계획·owner 승인으로 pending-only
또는 정확한 동일 inode 두 link의 게시만 마무리하고 기록에 담긴 원래 복구는 실행하지 않는다.
잘린 JSON·독립 복사본·불명확한 상태는 계속 차단한다.

승인은 Git common-dir의 별도 owner-private immutable intent와 history에 보존한다.
대상 이름·inode·원문 digest·등록 binding·원래 대상/의존 승인 digest·계획 digest를 먼저
확정하고 완료 후 receipt를 남긴다. 중단 시 일반 접근을 차단하며 새 승인 기록이 온전할
때만 새 계획·owner 승인으로 동일 대상의 pending-only·두 link·final-only를 마무리한다.
기존 marker와 native 기록, quota lane은 보존한다. 이번 terminal 승인·receipt 자체의
부분 게시 복구와 보존 객체의 재귀 복구는 허용하지 않는다.

### Terminal 완전 기록 예외의 최종 경계 (2026-10-22 승인)

위 terminal 자기 게시 복구 금지에서 **완전한 terminal intent·재승인·receipt**만
예외로 허용한다. 원래 대상과 승인 연결을 검증하고 새 계획·명시적 owner 승인으로
동일 원문 게시만 마무리한다. 원래 복구를 실행하거나 잘린 JSON을 보충하지 않는다.

Git common-dir의 고정된 최종 승인 종류 하나에 대상 이름·inode·원문 digest·등록
binding·의존 승인·계획 digest를 결합하고 immutable 승인과 history receipt로 보존한다.
중단 후 최종 승인이 온전하고 대상이 pending-only·정확한 두 link·final-only인 경우만
새 계획·owner 승인으로 재진입한다. **최종 승인·재승인·receipt 자체의 부분 게시는
원문을 보존하고 차단하며 다음 복구 계층을 추가하지 않는다.** 기존 marker·native
기록·quota lane을 변경하지 않고 보존 객체의 재귀 복구 금지도 유지한다.
