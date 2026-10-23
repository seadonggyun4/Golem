# P1a Object Store 승인 계약과 구현 현황

2026-10-23. 기존 baseline 구조/원문 coverage 구현 이후의 사용자 승인 기록이다.
실제 authority·Work 등록/변경 승인이 아니며 저장 완료는 사용자 채택·ACTIVE·실행 허가가 아니다.

## 승인된 범위

- 동일 등록 authority와 owner lock을 사용한다. 초기 proposal 쓰기는 intake만 허용한다.
  resolution/recovery 신규 객체 생성은 활성화하지 않는다. D01 등록·pin·trusted host guard를 유지한다.
- 원문은 `objects/v1/raw/sha256/<digest>`, JSON은
  `objects/v1/domain/<등록된-schema-이름>/<digest>`에 원본 bytes 그대로 저장한다.
  실제 object 대상은 원문·source·baseline이며 registry 등록만으로 다른 객체 저장 권한이 생기지 않는다.
- digest는 소문자 64자리다. 기존 파일의 종류·owner·보호 mode·digest·요청 bytes를 검증해야
  재사용할 수 있다. 덮어쓰기·symlink·알 수 없는 파일·허용되지 않은 hardlink는 거부한다.
- baseline.v1과 object-preparation.v1을 명시 domain registry에 추가한다.
  `SHA256(schema ASCII + NUL || uint64_le(JSON 길이) || exact UTF-8 JSON)` 규칙이다.
  baseline 전용 identity 함수는 구조 검증을 먼저 한다. 저장에는 source identity/scope/coverage도 필요하다.
- authority 루트의 `<8자리 sequence>.objects-prep`는 닫힌 JSON
  `golem.intent.object-preparation.v1`이다. 게시 중 이름은 `.objects-prep.pending`이다.
  필드는 schema·operation_id·request_digest·lane·expected_sequence·expected_head·baseline_digest·
  objects·new_directories다. objects 항목은 path·kind(raw/domain)·byte_length·digest·disposition(new/reuse),
  new_directories는 중복 없는 상대 경로 배열이다. 경로는 승인된 layout에서만 유도한다.
  256KiB 상한 초과는 분할·누락·자동 상향 없이 쓰기 전에 거부한다.
- journal payload는 `golem.intent.object-publication.v1`의 닫힌 5필드 JSON:
  schema·preparation_digest·baseline_digest·operation_id·request_digest다.
  preparation_digest는 objects-prep domain digest이고 payload는 기존 journal raw SHA-256으로 결합한다.
  publication schema는 객체 identity registry에 넣지 않는다. 기존 event frame·quota-preparation은 유지한다.
- reader는 event→기존 prep→payload→objects-prep→객체 bytes와 sequence/head/lane/operation/request를 검증한다.
  manifest만 있거나 객체만 있는 상태는 committed baseline이 아니다.

## 게시·중단·회계

같은 owner lock 아래 사전 guard·source 검증·귀속·peak quota 검사 → objects-prep 확정 →
예정 디렉터리·신규 객체 게시 → guard·실제 inventory·참조 재검사 → 기존 journal commit 순서다.
완료 재조회는 전체 연결을 검증하고 기존 receipt만 반환한다.

객체는 같은 디렉터리의 `<digest>.pending`을 exclusive 생성하고 원문 쓰기·read-only mode·file fsync,
no-replace hardlink·directory fsync 이후 해당 live 호출의 정확한 alias만 제거·directory fsync한다.
디렉터리는 manifest에 열거한 순서로 부모부터 owner-private 생성하고 부모를 fsync한다.
생성 중 예상 밖 경로가 있으면 재사용으로 바꾸지 않고 차단한다.

최초 준비 기록의 lane 귀속을 보존한다. 검증된 재사용만 추가 객체 점유가 0이고 새 manifest/event/
임시 파일 비용은 현재 operation에 계산한다. 한 게시당 event 1개, payload 축은 publication JSON 길이,
관리 bytes/entries는 실제 파일 이름별 점유다. 디렉터리는 entry 1·content bytes 0이다.
동일 operation의 같은 경로/bytes는 객체 하나지만 64MiB source 집합 검사는 중복 body도 각각 합산한다.
사전 peak는 신규 최종 파일·디렉터리·각 pending 이름이 동시에 존재하는 보수적 값이다.
hardlink의 두 이름도 각각 계산한다. 예약량 차용·자동 상향은 없으며 물리 공간 확보 보장이 아니다.

준비 게시 후 실패·미확정 상태는 원문과 귀속 가능한 점유를 보존하고 일반 쓰기를 차단한다.
object-store pending을 기존 D01 복구 API로 처리하거나 자동 재시도·rollback·삭제하지 않는다.
최종 승인 이후 추가 복구 계층과 보존 객체 재귀 복구 금지는 유지한다.

## 현재 구현과 남은 연결

구현: 명시 domain 두 이름 추가, `gi_baseline_identity`의 구조 검증 후 identity 계산,
미지원 버전/publication registry 거부, 실패 시 output 보존, 독립 Python hashlib preimage 비교.
`gi_object_preparation_validate`는 닫힌 manifest 필드·intake lane·객체 경로/종류/크기·중복·
대상 baseline·신규 directory 목록을 검사하고 원본 manifest의 identity와 예약 결합 정보를 반환한다.
실제 객체 bytes·기존 파일·source 집합의 완전성·재사용 귀속을 증명하지 않는다.
generic domain digest 성공은 manifest validator 성공을 대신하지 않는다.

`object.h`/`object.c`는 publication exact-byte encoder/decoder와 순수 예약 projection을 제공한다.
지정 필드 순서·공백/끝 개행 없음·원본 exact bytes 대조를 적용한다. 입력과 실패 output을 보존한다.
manifest로부터의 예약은 event 1개와 publication 길이다. trusted replay가 이미 계산한 journal
예약이 있으면 intake·sequence·head·payload가 정확히 같은 경우에만 추가 부과하지 않는다.
이 함수는 caller가 제공한 validated state를 계산할 뿐 실제 inventory를 읽거나 권한을 인증하지 않는다.

구현: manifest 생성 planner, 과거 object commit 전체의 journal 연결 검증, 실제 객체 게시와
journal commit, 별도 승인 기반 D01 host 저장 진입점까지 연결했다. 실제 프로젝트의 object 영역은
생성하지 않았다. 아래 과거 단계별 검증 기록은 당시 범위이며, 현재 연결은 문서 마지막 절을 따른다.

후속 승인: 유효한 objects-prep가 확정되면 journal prep가 아직 없어도 event/payload를 예약하고
같은 operation에는 한 번만 계산한다. publication JSON은 schema→preparation_digest→baseline_digest→
operation_id→request_digest 순서, 공백·끝 개행 없는 UTF-8로 생성한다. 원문·source/baseline JSON은
정규화하지 않는다. 준비 손상·귀속 불명확 시 추정·예약 해제 없이 차단한다.
관리 파일 bytes/entries와 peak 계산은 별도이며, replay 검증을 통과해야 저장 쓰기를 허용한다.

## 이번 identity 변경 검증

macOS arm64에서 `ctest --preset <dev|asan|release> -R '^intent_(baseline|schema_.*)$'
각 9/9 통과했다. 새 domain은 독립 Python hashlib preimage와 대조하며,
baseline 전용 identity의 잘못된 구조 거부·실패 시 output 보존도 확인했다.
기존 D01 복구·QA/execution·Work/document 코드 변경은 없다.
manifest 전체 validator·파일 게시·귀속 복원은 이 검증에 포함되지 않는다.
이번 변경의 원격 CI·Linux/Windows 검증 및 커밋·푸시는 아직 수행하지 않았다.

## 준비 manifest·publication·예약 계산 검증

같은 macOS arm64에서 후속 구현까지 포함해 다음 검사를 통과했다.

| 검사 | 결과 | 범위 |
|---|---|---|
| dev `^(intent_.*\|execution_boundary_cli)$` | 16/16 | manifest·codec·quota·inventory·journal·baseline·D01 host·QA writer 경계 |
| asan `^intent_(object\|baseline\|schema_.*)$` | 10/10 | ASan/UBSan 집중 회귀 |
| release 동일 집중 검사 | 10/10 | 최적화 빌드 집중 회귀 |

새 fixture는 manifest 경로·lane·중복·directory 순서·미지원 필드 거부,
publication의 모든 truncation 위치와 exact-byte 대조, journal 예약의 일치/불일치,
한도 경계·중복 계산 방지·실패 시 output 보존을 검사한다.
D01 host와 execution boundary 검사는 임시 fixture를 사용했으며 실제 TRAP·Work·증거는 변경하지 않았다.
기존 journal/inventory 회귀 통과는 새 object store의 파일 게시 연결 완료를 뜻하지 않는다.
객체 게시 이후의 재시작 회계와 파일 게시·host 쓰기 연결은 위 미구현 범위에 남아 있다.

## 첫 object 게시의 실제 재시작 조회 (이전 단계 기록)

`gi_journal_inspect`는 첫 object 게시의 마지막 `objects-prep`를 실제 파일에서
읽고 validator·codec·예약 함수를 재사용한다. owner-private·0400·단일 link인 완전한 파일만
허용하며 sequence/head·operation/request·필요한 모든 신규 부모 디렉터리의 선언을 검사한다.
해당 manifest bytes/entry는 intake에 귀속하고 event 1개와 정확한 publication 길이를 예약한다.
일치하는 journal prep가 이미 있으면 예약을 다시 더하지 않고, payload가 있으면 exact bytes도 비교한다.
이 상태는 `pending=true`이며 객체 존재·source coverage·저장 완료를 증명하지 않는다.

현재는 첫 object 게시 중단 상태의 read-only 경계만 연결했다. 검증되지 않은 재사용,
manifest alias/손상/잘못된 mode·sequence, 귀속 없는 파일은 계속 차단한다.
일반 append·visit·기존 D01 복구는 이 상태를 처리하지 않는다. host의 기존 pending 차단도 유지한다.
추가 복구 API나 실제 authority 생성은 없다. 이 연결을 전체 object inventory 또는 host 쓰기 완료로
표현해서는 안 된다.

### 객체 inventory 구현 (이전 단계 기록)

`gi_object_inventory_scan`은 journal caller가 binding을 검증한 순서 있는 manifest 집합을 받아
최초 생성 기록에 귀속된 object 영역을 실제 descriptor-relative 조회한다. 새 경로의 중복 생성은
거부하고 재사용은 앞선 committed manifest가 최초 생성한 같은 kind/길이/digest 객체만 허용한다.
디렉터리의 생성 귀속도 필수이며 등록되지 않은 경로를 발견하면 실패한다.

디렉터리는 owner-private 0700, final은 0400이며 device·owner·종류·symlink·관측 중 변경을 검사한다.
원문은 raw SHA-256, JSON은 원본 domain digest와 schema 경로를 대조한다. 정상 final/pending
hardlink 쌍은 정확한 동일 inode·두 link만 허용하며 두 이름의 bytes/entries를 각각 계산한다.
독립 복사본·외부 hardlink·잘못된 내용은 거부한다. 아직 짧은 pending은 manifest가 정한 경로·길이
상한 안에서 점유만 귀속하며 검증된 객체로 취급하지 않는다. 자동 삭제·완성·복구는 하지 않는다.
이 scanner는 owner lock 아래의 협력적 접근을 전제로 하며 hostile same-uid writer에 대한 snapshot은 아니다.

scanner의 committed 입력은 journal의 검증 결과여야 하며 사용자 선언을 승인으로 받지 않는다.
현재 journal 연결은 첫 미확정 object manifest의 디렉터리·파일·pending 실제 점유까지 지원한다.
과거 object commit의 전체 연결·재사용 이력은 아직 journal reader에 연결하지 않았다.
기존 quarantine 영역과 object 준비가 함께 있는 경우도 아직 연결하지 않았으며 안전하게 거부한다.
JSON domain identity는 source coverage·baseline 의미·사용자 채택 검증의 대체가 아니다.

다음 구현 순서는 다음과 같다. 아래 항목은 정책 승인을 기다리는 것이 아니라 아직 남은 코드다.

1. 구현된 inventory scanner를 과거 journal event→prep→publication→manifest 전체 연결 검증에
   연결하고 source/body/baseline의 완전성 검증을 결합한다. 알 수 없는 항목은 계속 거부한다.
2. source/body/baseline 원본과 coverage를 묶는 planner 및 보수적 peak 계산을 연결한다.
3. owner lock 아래 no-replace 게시·fsync·최종 guard/실제 inventory 재검사·journal commit을 연결한다.
4. D01 등록·pin 검증을 유지하는 host 쓰기/조회 진입점과 중단·동시성 fixture를 연결한다.

새 object-store 쓰기나 복구 권한은 현재 코드에서 활성화하지 않았다. 이 문서의 승인된 게시 순서와
중단 차단 계약을 충족하기 전에 기존 D01 복구 경로를 재사용하여 event를 확정해서는 안 된다.

후속 재시작 연결 검증(macOS arm64): 최종 dev 관련 CTest 16/16,
최종 ASan/UBSan 및 Release `intent_journal` 각각 1/1 통과.
13개 신규 native 재시작 시나리오는 manifest 단독/일치하는 journal 동반 상태의 중복 계산 방지,
손상·파일명·mode·alias·미검증 디렉터리·payload 불일치 거부 및 원문 무변경을 확인한다.
추가 host fixture는 임시 등록 authority에서 object 준비 상태의 host 접근 차단과 파일 무변경을 검사한다.
Linux/Windows·원격 CI와 실제 프로젝트 연동은 이번 검증 범위에 포함하지 않는다.

객체 inventory 후속 검증(macOS arm64): 관련 dev CTest 17/17, ASan/UBSan과 Release의
`intent_(object_inventory|journal)` 각각 2/2 통과했다. 신규 inventory fixture 18개는
최초 귀속·commit된 원본 재사용·중복 생성 거부·실제 bytes/entry 회계·정확한 hardlink 쌍·
독립 복사본/외부 link/잘못된 권한·digest·schema 경로 거부를 검사한다.
native journal fixture는 부분 디렉터리와 짧은 pending 객체의 점유 복원도 검사한다.
기존 D01 host 및 QA writer 경계 회귀가 포함되며 실제 파일 게시·journal commit·host 쓰기의
통과 증거는 아니다. 해당 쓰기 경로는 여전히 미구현이다.

## 현재 연결: 과거 commit 검증과 승인된 proposal 저장

위 단계 이후 `restore_object_reservation`은 모든 과거 object event의 prep/payload/manifest
결합과 최초 생성·재사용 귀속을 검증한다. `gi_object_graph_validate`는 baseline의 모든 source와
raw body를 owner-private descriptor 경로로 읽고, manifest의 객체 집합이 정확히 일치하는지,
identity·scope·실제 UTF-8 coverage가 맞는지 확인한다. extra/missing object를 거부한다.
기존 quarantine 회계와 함께 검증하며, 불명확한 항목은 쓰기·일반 조회에서 차단한다.

`gi_journal_store_objects`는 기존 owner lock 아래 intake만 사용한다. 원본 검증·planner·보수적
peak 검사 후 manifest, 디렉터리, 객체를 게시하고, guard·실제 inventory·graph 재검사 후 기존
prep/payload/event 형식으로 commit한다. event 직전에도 guard·quota·graph를 다시 검사한다.
같은 operation/request와 baseline의 완료 재조회는 전체 이력을 검증한 뒤 기존 receipt만 반환한다.
중간 실패는 handle을 poisoned 상태로 두며 재시작 이후에도 pending을 보존하고 일반 쓰기를 거부한다.
object pending을 기존 D01 복구로 마무리하지 않는다.

### 별도 host 승인 계약

사용자가 승인한 별도 진입점 `object_store_plan` / `store_objects`를 제공한다. 기존
`authorized_root`는 여전히 read-only다. 계획은 등록·요청 worktree/common-dir identity·Git/bridge/
producer pin·operation/request·expected sequence/head·baseline/source/raw exact bytes의 SHA-256과
길이를 묶는다. native에서 domain identity 및 coverage를 별도로 검증하므로 raw input hash가
domain identity를 대체하지 않는다. 계획은 저장 파일 형식이나 issuer 인증을 새로 정의하지 않는다.

`store_objects`는 검토한 계획 digest와 `approve_local_owner=True`를 모두 요구한다. EX common-dir
lock을 유지하고 immutable Python bytes를 private 임시 FD로 전달한다. pinned private bridge는 native
owner lock을 획득하고 현재 등록 chain을 확인한다. 네 번의 native guard마다 전용 pipe를 통해 host의
등록·identity·pin 재검사를 기다린다. 다른 owner, stale plan/head, 변경된 원문/pin, 승인 없는 요청은
거부한다. 이 private bridge는 신뢰된 local host 구성요소이며 외부 인증 API나 hostile same-uid
프로세스에 대한 보안 경계가 아니다.

bridge 중단·timeout·실패·commit 이후 host 검증 실패는 `OBJECT_STORE_COMMIT_UNKNOWN`과 원인을
반환한다. 자동 재시도·rollback·삭제하지 않는다. 실패 결과만으로 미게시를 추정하지 말고 보존된
native 상태를 확인해야 한다. 성공 결과에도 `execution_authorized=false`와 검토한 계획 digest를
반환한다. 검토 계획 digest의 영구 감사 저장 형식이나 외부 issuer 서명을 추가하지 않았다.

### 남은 경계

- 저장은 proposal 보존이다. 다른 requirement/constraint/decision/review/issuer-policy 참조 해석,
  사용자 채택·issuer 인증·ACTIVE 전이는 이 변경의 구현 범위가 아니다.
- 대중용 CLI/MCP로 자동 노출하거나 실제 프로젝트를 등록하지 않는다.
- object-store 중단 복구·추가 복구 계층·예약량 차용을 추가하지 않는다.
- QA writer lock·보호 계약·기존 증거·TRAP·실제 Work를 수정하지 않는다.
- macOS 외 플랫폼 및 원격 CI 결과는 별도 검증 없이는 통과로 주장하지 않는다.

### 현재 연결 검증 결과

macOS arm64에서 다음을 실행했다. host CTest는 여러 Python 사례를 포함하는 하나의 CTest다.

| 검사 | 결과 |
|---|---|
| dev `^(intent_.*\|execution_boundary_cli)$` | 17/17 PASS |
| ASan/UBSan `^intent_(object_inventory\|journal\|authority_host)$` | 3/3 PASS |
| Release 동일 집중 회귀 | 3/3 PASS |
| dev 실제 저장 후 event/payload/bytes/entries 회계 추가 대조 | PASS |
| `git diff --check` | PASS |

새 host 사례는 과거 commit의 변조·누락 coverage·다른 project·extra object 거부,
정상 proposal 저장·검증된 재사용·무변경 replay, 승인 누락·stale plan/head·변경된 입력/pin·
다른 owner lock 거부를 검사한다. manifest 직전 guard 거부는 무변경이며, 객체 게시 이후와
event 직전 guard 거부는 원문·pending 보존, event 미게시, 재진입 차단을 검사한다.
실제 파일 점유 및 journal payload 합계와 복원 usage를 대조하고 다른 lane 점유 0을 확인했다.
이는 모든 syscall 위치의 crash 행렬이나 전원 차단 내구성 검증은 아니다.

기존 QA writer 경계 검사도 통과했다. 실제 등록 authority·TRAP·실제 Work·제품 증거는 사용하지
않았으며, Linux/Windows·원격 CI·실제 프로젝트 설치는 미검증이다. 이 단계에서 커밋·푸시는
수행하지 않았다. 미승인 상태 전이와 추가 복구 계층은 활성화하지 않았다.
