# D01 host 등록과 읽기 전용 native 연결

2026-10-22. common-dir locator 방식은 사용자 승인됨. 임시 저장소에서 등록과
native 조회를 구현했다. 실제 프로젝트 등록, D02 issuer 승인, 제품 실행 권한은 포함하지 않는다.

## 재사용과 경계

`tools/intent_authority.py`는 기존 integration registry의 `real_path`, `identity`,
`file_pin`, private regular-file 검사와 closed schema 도구를 재사용한다.
기존 `.golem` project registry, Work journal, QA writer lock은 변경하지 않는다.
이 API는 trusted local host용이며 MCP나 공개 CLI의 새 쓰기 권한이 아니다.

## 등록 계약

1. host가 실제 Git 실행 파일, 기존 private external authority, dependency pins를 명시한다.
2. `registration_plan`은 root/common-dir inode, linked worktree 목록, authority inode,
   Git/dependency pin 및 host producer hash를 관측한다. 파일을 생성하지 않는다.
3. `register`는 검토한 plan digest와 명시적 local owner 승인을 요구한다.
   common-dir exclusive flock 아래 계획을 재검증한다.
4. pinned `golem_intent_authority_host`에 authority fd와 등록 digest를 전달한다.
   native authority owner flock 아래 고정 등록 operation을 첫 event로 게시한다.
   등록 payload와 준비 기록을 포함한 비용은 intake quota에 부과한다.
5. common-dir의 `golem-intent-authority.json`을 private pending 파일에서 fsync와
   no-replace link로 게시한다. 정상 게시의 자기 pending만 제거한다.

locator는 authority path/identity, common-dir identity, record digest와 pins를 결합한다.
동일 common-dir의 다른 authority는 충돌로 거부한다. 다른 repository가 같은 authority를
선택하는 것도 native 첫 등록 operation의 request digest 불일치로 거부한다.
등록된 linked worktree는 같은 locator와 authority를 사용한다.
동일 계획 재등록은 native binding 조회만 하며 기존 bytes를 다시 쓰지 않는다.
native 조회는 최초 등록뿐 아니라 아래 변경 chain의 최신 등록 digest까지 확인한다.

등록 record digest는 host의 canonical encoded record에 대한 raw SHA-256 binding이다.
신규 intent 객체의 schema-domain identity와 구분한다. issuer 인증을 의미하지 않는다.
producer는 명시한 host 파일들의 이름과 hash로 구성하며 설치 경로만 다른 동일 코드가
일치할 수 있다. Git 및 native bridge 등 실행 dependency의 path/hash pin은 별도로 유지한다.

## 조회와 lock 순서

`authorized_root`는 기대 등록 digest, locator, producer, root/common-dir/authority inode,
worktree 범위와 pins를 검사하고 common-dir shared flock을 유지한다.
`native_inspect`는 pinned native helper에 열린 fd를 전달하고 native가 authority owner
flock을 획득한다. 고정 등록 operation을 확인한 뒤 journal 상태와 quota 사용량을 반환한다.
host는 반환 전 locator와 관측값을 다시 검사한다. `execution_authorized`는 항상 false다.

lock 순서는 common-dir SH/EX → native authority EX다. Python에서 authority flock까지
잡고 native가 다시 획득하게 하지 않는다. 기존 QA writer lock을 대체하거나 우회하지 않는다.
local cooperative owner 경계이며 같은 uid의 적대적 파일 변경을 막는 attestation은 아니다.

## 실패와 미구현 범위

- locator 누락, digest/identity/pin 충돌은 조회를 차단한다. 자동 생성·repin·재신뢰하지 않는다.
- pending locator 또는 진행 중 변경 intent가 있으면 `LOCATOR_COMMIT_UNKNOWN`으로
  중단하고 보존한다. 아래 명시적 복구 API만 승인된 조건에서 마무리할 수 있다.
- native 등록과 locator는 서로 다른 저장 영역이다. 하나의 원자적 transaction이 아니다.
  native 성공 후 locator 게시 실패가 가능하다. 자동 rollback이나 pending 삭제는 없다.
  pending 생성 전 실패라면 owner가 동일 plan을 명시적으로 다시 승인한 재등록은 native의
  동일 operation replay를 사용할 수 있다. 자동 재시도는 하지 않는다.
- 기존 locator가 있지만 native binding이 사라졌으면 재등록도 거부한다. 빈 journal에
  binding을 몰래 재생성하지 않는다.
- linked worktree 목록·producer·dependency 변경은 기존 승인과 불일치한다.
  자동 update/repin은 없다. 아래 동일 identity 재승인과 committed-only 복구만 제공한다.
- generic append, baseline store, D02 issuer/product mutation 권한은 연결하지 않았다.
  native helper의 고정 등록 capability는 host의 local owner 검사를 신뢰한다.

## 승인된 등록 해제

`revocation_plan(root, registration_sha256, git=...)`은 읽기 전용 계획을 반환한다.
`revoke`는 그 계획 digest와 `approve_local_owner=True`를 요구한다.
현재 locator, 등록 digest, producer, Git pin, authority identity와 dependencies를
재검증한다. common-dir exclusive lock으로 host 조회가 끝날 때까지 경쟁을 거부하고,
authority exclusive flock으로 native owner와의 경쟁도 거부한다. 강제 인수하지 않는다.

기존 locator 및 authority의 journal/preparation/payload는 쓰거나 삭제하지 않는다.
common-dir에 `golem-intent-authority.revoked.json`을 immutable no-replace 게시한다.
폐기 기록은 계획과 계획 digest를 포함하며 재활성화를 허용하지 않는다.
조회·등록 계획·등록·추가 해제 모두 marker 존재 시 `AUTHORITY_REVOKED`로 차단한다.
손상되거나 symlink인 marker도 활성 상태로 해석하지 않는다. 이 오류는 차단 근거이며
손상된 marker의 내용을 인증한 해제 증거라고 주장하지 않는다.

게시 실패 시 자기 pending을 보존하며 `LOCATOR_COMMIT_UNKNOWN` 또는 marker 존재에
따른 폐기 상태로 중단한다. 자동 삭제·rollback·복구는 없다. marker 게시 후 fsync 실패는
성공으로 반환하지 않는다. 재호출은 자동 idempotent 성공이 아니라 폐기 상태 차단이다.
native quota는 변경하지 않는다. marker는 Git metadata에 있는 host 승인 상태이며
authority 관리 파일이 아니다. 기존 native 직접 API 자체에 해제 정책을 추가한 것은 아니다.
모든 협력 설치는 이 host gate를 사용해야 한다. 구버전 host의 직접 접근이나 동일 uid가
marker를 삭제하는 것을 막는 보안 경계는 아니며 구버전 혼용을 안전하다고 주장하지 않는다.

producer/pin 변경으로 기존 승인과 불일치한 경우 해제 역시 검사 우회 없이 중단한다.
그 상황은 아래 명시적 재승인 계약을 사용한다. 재활성화와 root 이동은 허용하지 않는다.

## 동일 identity 등록 변경

`tools/intent_authority_lifecycle.py`의 `change_plan`과 `change`는 기존 등록 digest,
새 dependency pins, 명시적 Git 실행 파일을 받는다. 계획에는 변경 전후 record 전체와
digest를 담으며 apply는 계획 digest 및 local owner 승인을 요구한다.
root/common-dir/authority의 경로와 inode는 동일해야 한다. pin·producer·worktree 목록만
재승인할 수 있다. 기존 pin을 읽지 못한다는 이유로 자동 재신뢰하지 않는다.
이전 4-file producer record의 closed shape는 읽기와 명시적 변경 대상으로만 지원한다.
현재 5-file producer에는 lifecycle 구현도 포함한다. 이전 bytes는 재작성하지 않는다.

게시 순서는 common-dir EX 아래 다음과 같다.

1. 현재 native binding과 변경 가능성을 읽기 전용 검사한다.
2. 변경 전후 locator와 승인 계획 digest를 담은 immutable `golem-intent-authority.change.json`을 게시한다.
3. native owner lock 아래 이전 등록 digest에 결합된 operation으로 변경을 intake에 게시한다.
4. 이전 locator bytes를 history에 보존한 뒤 candidate를 현재 locator로 원자 교체한다.
5. 변경 intent bytes도 history에 보존하고 활성 intent 이름을 제거·fsync한다.

native change payload는 이전 digest 32 bytes와 새 record 원문을 보존한다. request digest는
새 record, operation digest는 domain과 이전 digest에 결합된다. `gi_journal_visit`는
검증된 journal metadata를 순서대로 한 번 순회하며 현재 등록을 복원한다. pending journal은
거부하고 조회의 기대 digest가 최신과 다르면 거부한다. locator만 과거 bytes로 되돌려도
native 조회는 통과하지 않는다. 과거 등록 digest를 다시 사용하는 변경도 거부한다.
이 제한은 별도 generation/reinstatement 정책을 임의 도입하지 않고 stale digest 재활성화를
막기 위한 것이다. 동일 설정으로 복귀하는 새 generation 정책은 제공하지 않는다.

변경 event·준비 기록·payload는 intake 비용이며 예약 lane으로 넘기지 않는다.
common-dir의 locator/history는 host metadata로 authority root quota와 별개다.
변경 준비 후 native 게시가 실패하면 intent를 남기고 차단한다. 자동 재시도·rollback은 없다.
기존 Work/QA writer 및 public API 계약은 변경하지 않는다.

## 확정된 게시의 명시적 복구

`recovery_plan`은 대상 등록 digest와 승인된 bridge를 받아 파일별 digest, native head/sequence,
repository identity를 포함한 읽기 전용 계획을 생성한다. `recover`는 이를 다시 관측하고
계획 digest 및 owner 승인을 확인한다. 두 함수 모두 폐기 marker를 우회하지 않는다.

최초 등록은 native 최신 등록과 정확히 일치하는 완전한 pending locator만 지원한다.
변경은 native의 정확한 이전→새 digest transition이 committed되고 새 digest가 최신이어야
한다. 단순히 새 digest가 어딘가 존재하는 것만으로는 통과하지 않는다. 승인된 producer,
Git/bridge/dependency pin, root/common-dir/authority identity도 다시 검사한다.

pending bytes를 history에 별도로 보존한 뒤 활성 quarantine 이름을 정리하고 locator 게시를
마무리한다. 정상 게시 도중 생긴 pending↔final hardlink는 정확한 내부 alias 2개임을 확인하는
복구 전용 reader에서만 허용한다. 일반 regular-file 검사는 약화하지 않고 외부 hardlink,
부분 JSON, 다른 내용, 폐기 기록은 복구로 통과시키지 않는다. 복구 중 추가 실패도 보존·차단한다.
history와 정상 최종 파일에 남은 bytes가 증거이며 활성 pending 이름의 영구 유지를 뜻하지 않는다.

native event/preparation/payload는 복구에서 수정하거나 추가하지 않는다. 따라서 native quota
사용량과 head는 바뀌지 않으며 recovery 예약량도 사용하지 않는다. 모든 협력 host가 common-dir
lock/gate를 사용한다는 전제다. 직접 native API를 호출하는 비협력 프로그램을 인증·통제하는
기능은 아니다. 이 locator-only API는 미확정 native pending을 복구하지 않는다. 아래 별도
승인된 complete-preparation API와 구분한다. 삭제된 원본, 모호한 이력, 폐기 재활성화, authority 이동,
전원 손실의 모든 경계 복구와 전역 daemon 설치는 이 범위 밖이다.

## 승인 기반 native pending 마무리

`native_recovery_plan(root, target_record, git=..., bridge=...)`과 `recover_native`는
**D01 최초 등록 또는 등록 변경**만 대상으로 한다. 최초 등록의 `target_record`는 원래
검토한 등록 계획의 record이며, 변경은 보존된 change intent의 after record와 일치해야 한다.
대상 파일을 추측하거나 Work/제품 명령을 재실행하지 않는다.

지원 상태는 마지막 sequence의 검증된 완전한 prep와 payload, event 없음, staging alias
없음, intake lane이다. native bridge는 고정 D01 operation·request·payload digest와
기존 등록 chain을 대조한다. 일반 operation, 부분 파일, 불명확한 귀속, 다른 owner,
폐기 상태는 거부한다. root·common-dir·pin·producer 검사와 기존 QA/보호 경계는 유지한다.

읽기 전용 `gi_journal_pending_plan_get`은 sequence, payload bytes, operation/request,
직전 head, preparation/payload digest 및 snapshot digest를 반환한다. 이것은 관측값이며
승인이 아니다. snapshot은 `GIRCV001` + 두 uint64_le 값 + 위 5개 digest bytes의 SHA-256이다.
계획 생성은 복구 성공이나 이후 quota 여유를 보장하지 않는다.

host는 검토한 복구 계획 digest와 명시적 owner 승인을 요구하고 common-dir EX 아래
`golem-intent-authority.native-recovery.json`을 native 쓰기 전에 immutable 게시한다.
파일 게시 실패 시 native event를 쓰지 않는다. 기록은 대상 등록·native snapshot·관련
host 파일 digest와 승인 계획 digest를 포함한다. local owner 승인 기록이지 외부 issuer
인증이나 서명이 아니다. 미완료 intent가 있으면 정상 조회/등록 경로를 차단한다.

`gi_journal_pending_finish`는 native owner lock을 유지한 채 기존 guard와 restore를
두 번 수행하고 승인된 snapshot이 정확히 같은지 확인한다. 각 재검사에서 실제 usage에
event 최종 80 bytes/1 entry 및 게시 peak 160 bytes/2 entries를 적용한다. 이미 귀속된
event slot·payload 비용은 중복 청구하거나 환급하지 않는다. 최초 intake를 유지하며
여유 부족 시 resolution/recovery 예약량을 사용하지 않는다. 기존 prep·payload를
재작성하지 않고 해당 event만 게시한다. 이미 event가 생긴 상태는 다시 게시하지 않는다.

native 확정 뒤 host는 정확한 event head와 sequence를 재확인하고 locator를 마무리한다.
복구 intent bytes는 history에 보존한 뒤 활성 intent 이름을 제거한다. native event가
확정되고 host만 중단된 경우, 새로운 읽기 전용 계획과 owner 승인으로 host 마무리만
수행할 수 있다. 새 승인도 history에 남기며 native event를 중복 게시하지 않는다.
이 경로 역시 자동 retry가 아니다. 승인 record와 host history는 common-dir metadata로
native recovery 예약량을 사용하지 않는다.

이 native event 마무리 API가 지원하지 않는 상태는 계속 차단한다: staging alias/부분 파일, 아직 귀속할 수 없는
prep, 손상된 payload, 중간 sequence, event 게시 실패 후 남은 불명확한 staging,
복구 intent/history 자체의 부분 게시로 생긴 host pending, 삭제된 승인 원본 등이다.
이들의 삭제·취소·정리·재게시 정책을 이번 구현에서 임의로 추가하지 않았다.

## 검증된 native staging alias 해제

후속 승인으로 별도 `alias_recovery_plan`/`recover_alias` API를 추가했다. target record와
kind(0=prep, 1=payload, 2=event), 변경 기록이면 previous 등록 digest를 명시한다.
D01 마지막 sequence의 intake 기록만 대상으로 하며 native bridge가 고정 D01 operation,
request, 승인된 record payload digest와 이전 등록 chain을 검사한다.

`gi_journal_alias_observe`는 final과 pending이 정확히 동일 device/inode이고 nlink=2인
경우만 제거 대상으로 인정한다. 같은 sequence의 다른 staging도 모두 검증된 alias여야
한다. 독립된 동일 바이트 복사본, final 없는 staging, 외부 third hardlink, 부분 staging
혼합, symlink·특수 파일·소유권 불일치는 거부한다. 기존 일반 read/보호 검사를 완화하지 않는다.
계획에는 kind/sequence, device/inode, final bytes/digest, operation/request, prep/payload
digest, head, 실제 usage 및 snapshot을 포함한다. final 없는 경우를 추측해 보완하지 않는다.

host는 검토한 계획과 owner 승인을 확인한 뒤 immutable
`golem-intent-authority.alias-recovery.json`을 먼저 게시한다. 게시 실패 시 alias를 제거하지
않는다. 활성 intent는 정상 조회/등록과 다른 복구 진입을 차단한다. native owner lock 아래
두 번의 기존 guard·restore·snapshot 검사를 거쳐 선택한 pending 이름만 unlink하고
directory fsync한다. final bytes/inode, 확정 event/head는 바꾸지 않는다.

제거 후 inventory를 다시 읽어 intake의 논리 bytes가 final 크기만큼, file entry가 1만큼만
감소했는지 확인한다. event slot·payload 귀속·다른 lane은 그대로여야 한다. 이는 명시적으로
승인된 staging 점유 해제 예외이며 일반 데이터 비용의 이동·환급이 아니다. 감소 전후 usage와
alias identity/digest를 원래 승인 intent 및 actual after receipt로 history에 보존한다.

unlink 이후 host가 중단됐으면 final identity/digest와 정확한 usage 감소를 재검증한 새 계획과
owner 승인으로 기록만 마무리할 수 있다. 다시 unlink하거나 두 번 점유를 해제하지 않는다.
final의 nlink=1 관측은 이 기록 마무리에만 사용하며 새 제거 승인을 대신하지 않는다.
원문 receipt와 승인은 owner-private host metadata다. 외부 issuer 서명으로 주장하지 않는다.

이 API는 event 게시·locator 변경·Work 재개를 실행하지 않는다. prep alias만 있었고 payload가
없었다면 제거 후에도 payload를 생성하지 않고 불완전 상태를 유지한다. 완전한 prep/payload가
남았더라도 event 마무리는 별도 `native_recovery_plan`과 새 승인을 거쳐야 한다.
독립 부분 파일 및 불명확한 host pending의 격리·대체·정리 정책은 여전히 미결이다.

## Git 환경과 플랫폼

고정 read-only Git 명령만 실행하며 상속된 GIT_DIR/GIT_WORK_TREE/GIT_PAGER 등을 전달하지
않는다. global/system config와 prompt를 차단한 최소 환경을 사용한다. 다른 snapshot API의
환경 승인 정책은 그대로다. macOS `/usr/bin/git` hardlinked launcher는 기존 pin 검사에서
거부되어 테스트에서는 `xcrun --find git`이 반환한 실제 binary를 명시했다.
hardlink 검사를 약화하거나 전역 설정을 수정하지 않았다.

POSIX fd/flock 기반이다. macOS arm64에서 검증하며 Linux는 이 변경에서 실제 실행하지
않았다. Windows 지원 구현이나 검증으로 주장하지 않는다. 실제 Golem/TRAP/Work 등록 없음.

## 회귀 실행

`golem_intent_authority_host` target을 빌드한 뒤 CTest `intent_authority_host`를 실행한다.
Python 단독 실행은 `GOLEM_INTENT_HOST`에 빌드한 helper의 절대 경로를 지정해야 한다.
미지정 시 native 연결 사례는 skip이므로 전체 검증으로 간주하지 않는다.

16개 사례: linked worktree identity/공유, read-only bytes 불변, 상속 환경 격리,
pin/inode/scope/symlink/private-mode 거부, owner 승인·stale plan·단일 authority 충돌,
locator digest/pending 거부, common-dir/native lock 충돌, 사용 중 pin/common-dir 변경,
다른 repository의 동일 authority 거부, 게시 실패 보존, 동일 등록 replay와 native binding
소실 거부를 포함한다. 기존 journal·inventory·quota 및 QA execution boundary 회귀도 실행한다.

실행 결과: macOS arm64 Debug 집중 CTest **5/5 PASS**, ASan/UBSan **2/2 PASS**,
Release **2/2 PASS**. 각 구성의 host CTest 안에서 Python **16/16**을 실행했다.
Debug 5개에는 기존 QA execution boundary 회귀가 포함된다. 원본 설계 7개 문서의
SHA-256은 기존 기록과 같고 기존 execution/agent-session/QA/integration registry 코드의
diff는 없다. 전체 suite나 Linux/Windows 검증으로 확대 해석하지 않는다.

해제 API 추가 후 후속 검증: Debug host/journal/QA execution boundary **3/3 PASS**,
ASan/UBSan host **1/1 PASS**, Release host **1/1 PASS**. 각 host 내부 **21/21 PASS**.
추가 5개는 해제 후 원본 불변·접근/재등록 차단, 승인/계획 검증·계획 조회 무변경,
shared reader/native owner lock 경쟁, 부분 게시 실패 보존, 손상 marker 차단이다.
임시 저장소에서만 실행했고 실제 프로젝트에 폐기 기록을 생성하지 않았다.

최종 변경·복구 확장 검증: macOS arm64 Debug 집중 CTest **5/5 PASS**,
ASan/UBSan **2/2 PASS**, Release **2/2 PASS**. 각 host CTest 내부 **37/37 PASS**.
추가로 legacy producer 명시적 재승인, 연속 변경·intake 귀속, 과거 locator/digest 거부,
정확한 native transition 검증, stale 복구 계획·owner 승인, native 미확정 차단,
locator 교체와 old/candidate/change-history 게시 실패, pending hardlink 마무리,
부분 JSON·FIFO·폐기 marker 차단 및 복구 전후 native bytes 불변을 검사했다.
journal visitor의 순서·오류 전파·재진입 거부도 native 회귀에 포함했다.
JUnit은 각 build preset 디렉토리의 `intent-authority-lifecycle.xml`에 저장한다.
원본 설계 7개 문서의 SHA-256 및 기존 QA/execution/agent-session 보호 코드 불변을
재확인했다. Linux/Windows, 전원 손실, 실제 ENOSPC 및 모든 syscall 실패를 검증한 것은 아니다.

완전한 native pending 복구 추가 후 최종 검증: Debug **5/5 PASS**, ASan/UBSan **2/2 PASS**,
Release **2/2 PASS**, 각 host 내부 **46/46 PASS**. 기존 QA execution boundary 내부
10개 테스트도 통과했다. native 테스트는 실제 guard 거부로 prep/payload만 남긴 뒤 재개하여
두 guard 검사·stale snapshot 거부·event만 추가·기존 비용 유지·중복 마무리 거부를 확인한다.
host 테스트의 최초/변경 pending은 임시 fixture의 event를 제거한 동일 바이트 crash image다.
실제 전원 손실 실험으로 해석하지 않는다. 승인 intent 실패 시 native 무변경, 다른 owner와
일반 operation 거부, event 확정 후 host 중단 및 locator 완료 후 중단의 명시적 재진입도 검사했다.
결과 파일은 각 preset 디렉토리의 `intent-native-pending.xml`이다. 실제 Golem/TRAP/Work의
등록·재개·복구는 수행하지 않았다. native 쓰기 복구의 승인 범위를 다른 pending 상태로
확장하지 않았으며 부분 파일·staging·host pending 정리 정책은 여전히 미지원이다.

검증된 alias 해제 추가 후: macOS arm64 Debug **5/5 PASS**, ASan/UBSan **2/2 PASS**,
Release **2/2 PASS**, 각 host 내부 **57/57 PASS**. native 테스트는 prep/payload/event
3종 alias의 guard 재검사, stale snapshot 거부, final identity/digest·event/payload 귀속 유지,
정확한 staging 점유 감소 및 중복 제거 거부를 검사한다. host 테스트는 독립 복사본·외부
hardlink·부분 staging 혼합·owner 충돌·폐기 거부, 승인 게시 실패 시 무변경, 제거 후
history 실패의 명시적 기록 마무리, 불완전 prep 상태 유지 및 변경 chain을 포함한다.
JUnit은 각 preset의 `intent-alias-recovery.xml`이다. 실제 프로젝트·TRAP·Work에 적용하지
않았고 Linux/Windows·실제 전원 손실/ENOSPC 검증은 수행하지 않았다. 앞선 staging 전체
미지원 기록은 이 동일 inode 예외 구현 이전의 이력이다. 독립 부분 파일·host pending은 별개다.

## 승인된 독립 staging 격리와 별도 payload 대체

2026-10-22 후속 구현은 승인된 격리 위치·최초 lane/peak 회계·payload 대체 조건을
private D01 bridge와 기존 common-dir/authority lock 경로에 연결한다. 이는 실제 프로젝트의
복구 실행이나 일반 Work 재시도가 아니다. 기존 QA writer lock·보호 계약은 변경하지 않는다.

### 대상과 보존

- 마지막 D01 등록/등록 변경 sequence의 완전한 immutable prep가 필요하다.
- `prep.pending`, `payload.pending`, `event.pending` 중 독립된 한 파일만 다룬다.
  다른 staging과 혼합되거나 외부 hardlink·symlink·귀속 불명이면 거부한다.
  정상 final과 같은 inode인 경우에는 기존 alias 복구 계약을 사용한다.
- native 준비 기록의 operation/request/payload와 명시 제공한 등록 원본 및 이전 등록 chain을
  비교한다. 다른 operation의 파일을 D01 복구로 처리하지 않는다.
- 동일 authority의 private `quarantine/` 아래 원문과 메타데이터를 한 immutable envelope로
  게시한다. 원래 상대 경로·device/inode·길이·원문 digest·최초 lane·prep digest·operation·request·
  owner 승인 계획 digest를 포함한다. envelope 무결성 hash도 검증한다.
- envelope와 디렉터리를 fsync하고 원문과 다시 대조한 후에만 활성 staging 이름을 제거한다.
  final 파일이나 이미 확정된 event는 덮어쓰지 않는다. 원문은 envelope의 원래 bytes 그대로 남는다.
- 기존 domain-separated intent 객체와 raw CAS identity는 바꾸지 않는다. envelope는
  `GIQUA001` 내부 저장 프레임이며 issuer 인증이나 외부 서명으로 취급하지 않는다.

### 승인 단계를 분리한 API

읽기 전용 계획은 `partial_recovery_plan(..., action="quarantine", kind=...)`으로 만든다.
그 계획 digest와 `approve_local_owner=True`를 명시한 `recover_partial` 호출만 격리를 수행한다.
`kind`는 prep=0, payload=1, event=2다. host는 immutable
`golem-intent-authority.partial-recovery.json` intent를 먼저 저장하고 완료 receipt를 history에
보존한다. 미완료 intent가 있으면 일반 접근과 다른 복구 진입점은 차단한다.

payload 대체는 **격리와 별도 계획·별도 승인**이다. 같은 API의 `action="replace", kind=1`을
사용하며 owner가 제공한 `target_record`의 정확한 직렬화 bytes(등록 변경은 이전 digest prefix 포함)를
원본으로 검증한다. 길이·digest·D01 binding이 prep와 일치하고 payload final/event/staging이
없는 마지막 pending sequence만 허용한다. 내용 추정·기존 final 덮어쓰기를 하지 않는다.
반환 결과는 `payload_ready=true`이지 committed 또는 등록 완료 판정이 아니다.

이 두 API는 `gi_journal_pending_finish`나 locator `_finish`를 호출하지 않는다.
**event 게시 및 locator 마무리는 기존 별도 승인 절차에 남겨 두며 자동 연결하지 않는다.**

### 회계 및 중단

첫 lane은 D01 intake로 고정한다. 격리 디렉터리 entry, envelope, pending/alias 이름을 모두
전체 inventory에 계산한다. 원본 크기가 N이면 envelope는 `320 + N` bytes이고 원문 N bytes의
기존 점유 외에 envelope 게시 중 두 이름의 논리 점유 `2 * (320 + N)`를 peak로 검사한다.
디렉터리가 없으면 entry 1개도 추가한다. 성공 후 원래 staging 점유는 사라지지만 원문은
envelope 안에 계속 계산되며 metadata 320 bytes가 추가로 남는다. event slot·payload 귀속과
다른 lane은 그대로다. payload 대체는 최종 N bytes/entry 1개와 게시 peak 2N bytes/entry 2개를
추가 검사한다. quota 부족을 resolution/recovery 예약량으로 넘기지 않는다.

native owner lock 아래 guard·snapshot·실제 inventory·quota를 재검사한다. 격리 envelope 게시 후
활성 이름 제거 직전에도 guard와 원문 identity/digest를 확인한다. 실패 후 handle은 쓰기를 차단한다.
완전한 envelope와 원문이 함께 남았거나 native 작업 후 host receipt만 미완료이면 새 계획·명시적
owner 승인으로 기존 승인 intent와 정확한 before/after 회계를 검증하여 마무리할 수 있다.
이미 완료된 payload를 재게시하지 않는다. 손상·모호한 상태는 자동 삭제나 rollback 없이 보존한다.

현재 구현은 sequence/kind별 envelope 하나를 인식한다. 격리 envelope 자체의 부분 게시,
격리 내부 pending alias, 대체 도중 다시 생긴 다른 부분 파일, 손상된 final/준비 기록,
불명확한 host pending의 후속 복구는 차단한다. 반복 격리 세대나 이들 상태의 정리·재개 정책을
이번 구현으로 승인한 것은 아니다. 별도 정책과 복구 계약이 필요하다.
협력하는 동일 owner 프로세스의 lock 계약이며 악의적인 same-uid writer 방어·실제 저장장치의
전원 손실 내구성·디스크 여유 보장을 의미하지 않는다. 원문/identity와 pin이 맞지 않으면
기존 검사대로 거부하며 구버전 엔진으로의 자동 downgrade/재신뢰는 없다.

### 격리·대체 검증 결과

macOS arm64에서 Debug 집중 CTest **5/5 PASS**, ASan/UBSan **2/2 PASS**,
Release **2/2 PASS**. 각 host CTest는 Python **71/71 PASS**, Debug의 기존
QA execution boundary는 내부 **10/10 PASS**다. JUnit은 각 preset 디렉터리의
`intent-partial-recovery.xml`에 보존했다. 최종 실행은 2026-10-22이며 전체 suite나
Linux/Windows 검증으로 확대하지 않는다.

native 회귀는 owner lock/재진입 거부, stale snapshot·두 번째 guard 거부,
envelope 저장 후 guard 거부와 재시작, 복사 후 상태 변경 시 staging 분리 전 거부,
정확한 peak bytes/entries 한도, 최초 lane 유지·중복 payload/event 비용 방지,
잘못된 원본·기존 final 재게시 거부와 후속 journal replay를 검사한다.
host의 추가 14개 테스트는 3종 staging 원문 보존, 계획 조회 무변경, 별도 대체 승인,
승인/receipt 저장 실패와 명시적 마무리, lock/외부 hardlink·symlink·권한 거부,
prep/격리 원문/메타데이터 손상·unknown 파일 거부, 폐기·host pending 거부,
등록 변경 시 기존 locator/intent bytes 유지 및 event 미게시를 검사한다.

모든 복구는 임시 repository/authority fixture에서만 실행했다. 원본 설계 7개 문서의
SHA-256은 기존 값과 같고 기존 execution/agent-session/work/QA/document 및
integration registry/contract 코드의 diff는 없다. 실제 전원 손실·ENOSPC·모든 syscall
실패를 검증한 것은 아니다. 부분 envelope와 불명확한 host pending의 복구 정책은
확정하지 않았으며 자동 삭제·대체·재게시 없이 계속 차단한다.

## 완전한 격리 envelope의 게시 마무리

후속 승인 범위는 **완전한 envelope**에 한정한다. 원래 staging, immutable prep,
기존 `partial-recovery` owner 승인 intent의 계획 digest와 등록 binding을 모두 검증한다.
잘린 envelope를 채워 넣거나 독립된 두 파일을 동일한 것으로 간주하지 않는다.

- pending만 존재하면 private/0400·단일 link·전체 길이·header/원문/hash를 검증한 후
  덮어쓰기 없는 final hardlink를 게시하고 fsync한다.
- final과 pending이 존재하면 정확한 같은 device/inode·link 수 2여야 한다.
  독립 복사본·외부 추가 hardlink·불명확한 이름은 거부한다.
- 새 계획과 owner 승인 후에만 실행하며, guard·snapshot·실제 inventory·quota를
  owner lock 아래 두 번 검사한다. final 게시 후 pending 제거 전에도 상태를 재검사한다.
- 원래 staging의 inode/bytes/digest, native head·committed 수, payload 상태는 유지한다.
  원래 staging 분리·payload 대체·event·locator 마무리는 호출하지 않는다.

내부 native API는 `gi_journal_envelope_observe`, `gi_journal_envelope_visit`,
`gi_journal_envelope_check_quota`, `gi_journal_envelope_finish`다. 일반 inspect/visit는
pending envelope가 있으면 계속 거부한다. 전용 읽기 경로만 검증된 완전한 publication
staging을 인식하며 앞선 sequence의 pending, 알 수 없는 파일, 손상 기록은 허용하지 않는다.
bridge는 별도 폐쇄 응답 schema `golem.intent-envelope.v1`을 사용한다.

host 진입점은 `envelope_recovery_plan`과 `finish_envelope`다. 기존 격리 intent는 그대로 두고
새 `golem-intent-authority.envelope-recovery.json`에 검토한 계획·승인을 먼저 보존한다.
완료 receipt를 history에 기록한 뒤 새 intent만 제거한다. 이 intent가 남아 있으면 일반 접근과
다른 복구는 차단한다. native 마무리 후 receipt 실패 시에도 새 계획·승인을 요구하며,
정확한 동일 envelope와 회계 변화만 확인하여 host 기록을 마무리한다.
기존 격리 intent와 원래 staging을 없애지 않으므로 다음 단계는 별도 격리 마무리 승인이다.

pending-only의 기존 envelope 점유는 이미 intake에 포함되며 final link를 추가하는 동안
envelope 크기/entry 1개를 peak로 추가 검사한다. 성공 후 이름 수는 같아 최종 점유는 그대로다.
기존 final/pending 쌍은 pending의 bytes/entry만 감소한다. event/payload 귀속·다른 lane은
바뀌지 않고 예약량을 빌려 쓰지 않는다. envelope 원문은 다시 직렬화하거나 재작성하지 않는다.

앞선 격리 절의 ‘격리 내부 pending alias 미지원’은 이 확장 이전의 제한이다.
**잘린 envelope, 독립 중복 파일, 불명확한 host pending, 재격리 세대 정책은 여전히 미지원**이며
보존·차단한다. 이번 승인으로 해당 상태의 복구 정책을 확정하지 않았다.

검증(2026-10-22, macOS arm64): Debug 집중 CTest **5/5 PASS**, ASan/UBSan **2/2 PASS**,
Release **2/2 PASS**. 각 host 내부 **80/80 PASS**, 기존 QA 경계 내부 **10/10 PASS**.
native는 stale/잘못된 승인·guard 거부, final link 게시 직후 중단과 재시작,
peak bytes/entry 한도, source 보존과 alias 점유 감소, 중복 마무리 거부를 검사했다.
host 추가 9개 테스트는 pending-only/동일 inode 쌍, 읽기 전용 계획, 승인/receipt 실패,
원래 intent/source 부재·변경, 잘린 envelope·독립 복사본·외부 link 거부, owner 충돌,
host pending 차단, 등록 변경 chain 및 3종 staging을 다룬다.
JUnit은 각 preset의 `intent-envelope-recovery.xml`에 보존한다. 원본 설계 7개 문서의 해시와
기존 QA/execution/agent-session/work/document·integration registry/contract 코드는 유지했다.
실제 프로젝트·TRAP·Work에는 적용하지 않았고 Linux/Windows·실제 전원 손실·ENOSPC는 미검증이다.

## 검증된 host pending alias 복구

후속 승인에 따라 `host_alias_recovery_plan(root, target_record, final_name, git=...)`과
`recover_host_alias(..., reviewed_plan_sha256, approve_local_owner=True)`를 제공한다.
대상은 native-recovery·alias·partial·envelope의 완전한 고정 intent와 해당 history 기록이다.
native recovery history는 기존 intent 형식을, 나머지 history는 기존 receipt 형식을 유지한다.
이 API는 native bridge를 실행하지 않는다.

계획은 등록 identity·producer/pin·폐기 여부, canonical JSON·폐쇄 schema·계획 digest·D01
operation/request/payload binding을 검증한다. final은 현재 owner의 0400 일반 파일이어야 하며,
pending은 게시기가 사용하는 이름이고 final과 정확히 같은 inode의 두 번째 link여야 한다.
다른 pending, 세 번째 link, 독립 복사본, symlink, 잘린 JSON, final 없는 pending은 거부한다.

common-dir lock 다음 authority owner lock 순서를 유지한다. 읽기 전용 계획은 파일을 만들지 않는다.
실행은 검토한 계획 digest와 명시 owner 승인을 요구하고, 새 host-alias intent를 먼저 보존한 뒤
동일 상태를 재검사하여 pending 이름만 제거하고 디렉터리를 fsync한다. final bytes/inode와
native 파일은 변경하지 않는다. receipt를 history에 보존한 후 새 marker만 제거한다.
원래 recovery intent는 남기며, 원래 복구·event 게시·locator 마무리를 호출하지 않는다.

승인 기록 게시가 실패하면 alias를 제거하지 않는다. alias 제거 후 receipt 게시만 실패하면
marker가 다른 경로를 차단하고 새 계획·승인을 통해 host 기록만 마무리할 수 있다.
이 새 host-alias intent/receipt 자체의 부분 게시 복구는 이번 지원 목록에 포함하지 않는다.
기록은 기존 host metadata이며 native lane 비용 이동이나 recovery 예약량 소비가 없다.
이는 협조적 local owner 계약이지 악의적인 동일 UID 쓰기에 대한 인증 보장이 아니다.

잘린 envelope, final 없는 host pending, 불명확한 귀속과 새 복구 기록 자체의 부분 게시 정책은
계속 미결이며 임의 삭제·내용 추정·자동 재시도하지 않는다.

검증(2026-10-22, macOS arm64): Debug 집중 CTest **5/5**, ASan/UBSan **2/2**,
Release **2/2 PASS**. host 내부는 각 **92/92**, 기존 QA 경계는 **10/10 PASS**다.
추가 12개 테스트로 원문/native 무변경, 읽기 전용 계획, 승인·stale·owner 충돌,
독립 복사본·세 번째 link·final 부재·잘린 JSON 거부, 승인/receipt 실패와 명시적 재진입,
native 변경 intent/history·alias/partial/envelope receipt·envelope intent를 검사했다.
JUnit은 `build/{dev,asan,release}/intent-host-alias-recovery.xml`에 보존한다.
원본 설계 7개 문서의 해시와 기존 보호 코드는 유지했다. Linux/Windows, 실제 전원 손실과
ENOSPC는 미검증이며 실제 authority·TRAP·Work에는 적용하지 않았다.

## final 없는 완전한 host pending의 게시 마무리

후속 승인으로 `host_publication_plan(root, target_record, pending_name, final_name, git=...)`과
`finish_host_publication(..., reviewed_plan_sha256, approve_local_owner=True)`를 추가했다.
owner가 두 이름을 명시하며 지원 대상은 기존 native-recovery·alias·partial·envelope의
완전한 intent와 history다. canonical JSON, 폐쇄 schema, 계획 digest, 등록 및 D01 binding을
기존 `_host_recovery_record`로 검증한다. 원문은 다시 직렬화하여 쓰지 않는다.

첫 계획은 final이 없고 현재 owner의 0400 일반 pending 파일에 link가 하나인 경우만 허용한다.
다른 pending, 추가 hardlink, symlink, 독립 복사본, 잘린 JSON과 지원하지 않는 대상 이름은
차단한다. 읽기 전용 계획 뒤 검토한 digest와 명시적 owner 승인이 필요하다.
common-dir lock 다음 authority owner lock을 잡고 `golem-intent-authority.host-publication.json`에
승인을 먼저 보존한다. 새 승인 기록은 기존 host metadata이며 native quota를 소비하지 않는다.

게시 순서는 pending fsync, final에 덮어쓰기 없는 hardlink, 디렉터리 fsync, 동일 원문·inode·
등록 binding 재검사, pending 이름 제거, 디렉터리 fsync, history receipt, 새 marker 제거다.
기존 final이나 native 파일을 덮어쓰지 않는다. 게시된 intent가 지시하는 복구는 실행하지 않으며,
원래 staging 분리·payload 대체·event·locator 마무리와 연결하지 않는다.

중단 시 marker가 일반 접근과 다른 복구 진입점을 차단한다. 새 계획과 owner 승인으로만
`PENDING -> PAIR -> FINAL`의 남은 단계를 마무리한다. PAIR는 정확한 동일 inode 두 link이고
FINAL도 최초 승인된 inode·원문 digest와 같아야 한다. 재진입 승인과 최종 receipt를 보존한다.
승인 기록 자체의 부분 게시, 잘린 envelope, 귀속이 불명확한 파일의 복구는 계속 미지원이다.
기존 host-alias 복구 기록과 새 host-publication 기록 자체는 이 게시 API의 대상이 아니다.

검증(2026-10-22, macOS arm64): Debug 집중 CTest **5/5**, ASan/UBSan **2/2**,
Release **2/2 PASS**. 각 host 내부 **102/102**, 기존 QA 경계 **10/10 PASS**다.
추가 10개 테스트는 읽기 전용 무변경·native 보존, intent/receipt 게시, 세 중단 상태의
명시적 재진입, 승인 게시 실패, 잘린 승인 기록, 추가 pending·독립 복사본·symlink·추가 link,
잘린 JSON·미지원 대상, stale 계획·승인 부재·owner 충돌을 검사한다.
JUnit은 `build/{dev,asan,release}/intent-host-publication.xml`에 보존했다.
기존 설계 7개 문서 해시와 QA/execution/session/Work/document 보호 코드는 유지했다.
실제 authority·TRAP·Work에는 적용하지 않았으며 Linux/Windows·실제 전원 손실·ENOSPC는 미검증이다.

## 잘린 envelope 보존: codec 단계

승인된 다음 범위의 첫 구현은 `src/intent/fragment.c`의 순수 codec과 quota 검사다.
**이 codec 단계 당시 실제 보존 객체 파일 게시·분리·복구 진입점은 연결하지 않았다.** 일반 journal은
잘린 envelope와 알 수 없는 보존 파일을 계속 거부한다. 이 절은 복구 기능 완료 주장이 아니다.

기존 `GIQUA001`의 encoder를 공유하여 등록된 준비 기록·원래 staging·기존 승인으로 기대
완전본을 계산한다. 320바이트 header가 온전하고 길이가 완전본보다 작은 정확한 앞부분만
`gi_fragment_encode`가 허용한다. bytes를 덧붙이거나 원본을 수정하지 않는다.
기존 정상 격리 경로도 같은 encoder를 사용하며 wire bytes는 기존 형식과 동일하다.

새 private `GIQFR001` 보존 객체는 320바이트 header 뒤에 잘린 원문을 그대로 둔다.
header는 sequence/lane/kind, 원래 envelope의 device/inode, 원문/완전본 길이,
prep·기존 승인·새 승인·잘린 원문·기대 완전본 digest, 원래 상대 경로, 전체 무결성 digest를
결합한다. 기존 정상 envelope와 혼용하지 않는다. `gi_fragment_verify`는 독립적으로 제공된
binding과 원래 staging으로 기대 bytes를 재계산하여 전체 객체와 대조한다.
성공은 owner 승인·현재 파일 신원·D01 chain 검증을 대체하지 않는다.

순수 `gi_fragment_check_quota`는 현재 inventory에 원래 잘린 파일이 이미 포함되었다고
가정한다. 신규 보존은 객체 1개를 유지하고 게시 중 두 이름의 peak를 검사한다.
pending-only 게시 마무리는 추가 final 이름 1개, 동일 inode pair의 이름 제거는 추가 점유
0으로 계산한다. intake 이외 lane으로 비용을 넘기거나 event/payload 비용을 환급하지 않는다.
실제 owner lock 아래 inventory와 함께 재검사하는 연결은 다음 구현 범위다.

당시 남은 코드: 전용 read-only replay/관측, 보존 파일의 inventory 귀속, native 게시·마무리·별도
분리 API, D01 bridge 및 host 승인/receipt 연결, 중단·재시작 통합 fixture.
보존 객체 자체의 잘림과 복구 승인 기록 자체의 부분 게시 정책은 기존 차단을 유지한다.

codec 단계 검증(2026-10-22, macOS arm64): Debug 집중 CTest **6/6**, ASan/UBSan
**3/3**, Release **3/3 PASS**. 각 host 내부 **102/102**, QA 경계 **10/10 PASS**다.
`intent_fragment`는 독립 wire fixture와 기존 encoder의 byte 동일성, 모든 허용 prefix 길이,
보존 객체의 각 byte 변조, 불완전 header·완전본·원문/승인/inode 불일치 거부, 실패 시 출력
보존, 최초 intake bytes/entry의 신규 게시·pending 마무리 peak 경계를 검사한다.
JUnit은 각 preset의 `intent-fragment-codec.xml`에 보존한다. 이 결과는 아직 연결하지 않은
파일 게시·중단 복구의 PASS가 아니다. Linux/Windows·전원 손실·ENOSPC는 미검증이다.

## 잘린 envelope 보존: 실제 journal·host 연결

후속 구현은 앞 절의 codec을 다음 경로에 연결했다. private API이며 일반 Work 복구나
공개 C API의 자동 재시도로 확장하지 않는다.

| 계층 | 진입점·책임 |
|---|---|
| Native 관측 | `gi_journal_fragment_observe`·`gi_journal_fragment_visit`: 마지막 sequence의 검증된 앞부분과 귀속·실제 점유 관측 |
| Native 변경 | `gi_journal_fragment_apply`: preserve(0), finish(1), detach(2)를 한 번에 하나만 수행 |
| D01 bridge | `--plan-fragment-fd`, `--preserve-fragment-fd`, `--finish-fragment-fd`, `--detach-fragment-fd`: 등록 chain·operation/request/payload 및 길이 재검증 |
| Host 계획 | `fragment_recovery_plan(..., action)`: 기존 격리 승인 intent와 관측을 결합한 읽기 전용 계획 |
| Host 실행 | `recover_fragment(..., action, reviewed_plan_sha256, approve_local_owner=True)`: 새 immutable 승인·단일 native 단계·receipt |

보존 객체는 기존 private `quarantine/` 안의 `<sequence>.<kind>.fragment`에 게시한다.
게시 중 이름은 `.fragment.pending`이다. sequence/kind별 한 객체만 허용하며 별도 세대의
재격리나 덮어쓰기를 지원하지 않는다. 실제 inventory는 각 이름의 논리 bytes와 entry를
최초 intake에 계산한다. 완전한 pending-only와 정확한 두 link만 전용 복구 조회가 허용한다.
불완전 보존 객체·독립 복사본·추가 link·unknown 파일은 정상 기록으로 분류하지 않는다.

preserve는 객체를 확정하되 원래 잘린 envelope와 원래 staging을 그대로 둔다. finish는
완전한 보존 객체의 게시만 마무리한다. detach는 보존 객체를 재검증한 뒤 원래 잘린 envelope의
pending 이름만 분리한다. 객체와 그 안의 원문은 계속 계산하며 사라진 이름의 점유만 감소한다.
원래 staging·정상 envelope·payload·event·locator에는 이 세 작업이 쓰지 않는다.

모든 변경은 owner lock 아래 guard·snapshot·실제 inventory·최초 lane의 peak quota를
재검사한다. 중단 후에는 자동 실행하지 않고 fresh plan과 owner 승인을 요구한다.
host는 기존 원본 격리 intent를 남긴 채 전용 `golem-intent-authority.fragment-recovery.json`을
먼저 게시하고 승인 재진입과 receipt를 history에 보존한다. 미완료 marker는 다른 복구와
일반 접근을 차단한다. preserve 중 완전한 객체 pending이 남으면 별도 finish 승인이 필요하며,
finish 뒤 detach를 자동 실행하지 않는다. 완료된 native 단계의 receipt만 실패한 경우에는
상태·회계·최초 승인 binding을 대조해 host 기록만 마무리한다.

일반 journal은 보존이 완료되고 원래 잘린 envelope가 분리된 뒤 보존 객체를 검증·계산할 수
있다. 이것이 Work 완료 또는 재실행 승인을 뜻하지는 않는다. 원래 staging의 격리 재시작이나
정상 envelope 재생성은 자동 연결하지 않으며, 기존 host 격리 intent의 후속 재기준화도 이
경로가 수행하지 않는다. 완전한 fragment 승인/receipt의 게시 중단은 아래 host 기록 게시
복구 절을 따른다. 잘린 JSON을 보충하거나 재생성하는 복구는 지원하지 않는다.

연결 검증(2026-10-22, macOS arm64): Debug 집중 CTest **6/6**, ASan/UBSan **3/3**,
Release **3/3 PASS**. 각 host 내부 **114/114**, 기존 QA 경계 **10/10 PASS**다.
native는 stale snapshot·승인 불일치·guard 거부, 보존 직후 중단, final link 생성 후 중단과
재시작, 별도 detach, 실패 시 출력 보존, 정상 조회 차단/복원, 실제 점유 감소와 event 미게시를
검사했다. host 추가 12개 테스트는 읽기 전용 무변경, 단계 분리, pending-only/pair 마무리,
receipt 실패 후 재진입, 잘린 header/객체·독립 복사본·extra link·추가 host pending 거부,
원래 승인 부재·owner 충돌·stale 승인·재진입 원문 변경·충돌하는 change intent를 다룬다.
JUnit은 `build/{dev,asan,release}/intent-fragment-recovery.xml`에 보존했다.
기존 설계 7개 문서의 해시와 QA/execution/agent-session/Work/document 보호 코드는 유지했다.
테스트는 임시 authority만 사용했다. 실제 프로젝트 등록·TRAP·Work·기존 증거에 적용하지
않았으며 Linux/Windows·실제 전원 손실·실제 ENOSPC와 전체 suite는 이번 검증 범위가 아니다.

## GIQFD001 inventory·native·host 연결

기존 `GIQFR001` 보존 객체 자체의 잘림에는 별도 terminal 보존 객체 `GIQFD001`을 사용한다.
지원 대상은 완전한 prep·원래 격리 intent·fragment preserve intent·원래 staging·잘린
envelope가 모두 남은 마지막 D01 sequence다. final 없는 `.fragment.pending`은 온전한
320바이트 header와 기대 완전본의 정확한 앞부분이어야 한다. 기존 승인 marker를 자동
재작성하거나 history에서 임의 선택하지 않는다. fragment intent가 없거나 다른 동작의
intent인 경우 이 경로를 사용하지 않는다.

| 계층 | 진입점 |
|---|---|
| Native 읽기 | `gi_journal_damage_observe`, `gi_journal_damage_visit` |
| Native 단일 단계 | `gi_journal_damage_apply`: preserve(0), finish(1), detach(2) |
| D01 bridge | `--plan-damage-fd`, `--preserve-damage-fd`, `--finish-damage-fd`, `--detach-damage-fd` |
| Host 읽기 | `damage_recovery_plan(root, record, kind, action, git=..., bridge=..., previous=...)` |
| Host 승인 실행 | `recover_damage(..., reviewed_plan_sha256, approve_local_owner=True)` |

bridge는 기존 D01 chain·등록 digest·operation/request/payload·길이 검증을 재사용한다.
응답 schema는 `golem.intent-damage.v1`이며 기존 fragment 관측 필드에
`ancestor_device/inode/bytes/digest`와 `fragment_approval`을 추가한다. ancestor는 원래
잘린 envelope이고, truncated는 이번 대상인 잘린 fragment다. `execution_authorized`는
항상 false이며 제품 실행 권한을 부여하지 않는다.

보존 경로는 `quarantine/<sequence>.<kind>.fragment.damage`, 게시 중 이름은 여기에
`.pending`을 붙인다. 최초 intake lane의 실제 bytes/entries와 공존 peak를 확인한다.
preserve는 원래 이름을 제거하지 않는다. finish는 완전한 pending-only를 no-overwrite
게시하거나 정확한 동일 inode 두 link의 pending 이름만 제거한다. detach는 완전한
보존 객체를 재검증한 뒤 원래 `.fragment.pending` 이름만 제거한다. 보존 bytes와 기록은
계속 계산하고 원래 staging·잘린 envelope·event·locator는 변경하지 않는다.

host는 native 변경 전에 `golem-intent-authority.damage-recovery.json`에 immutable
승인을 게시한다. `golem.intent-damage-plan.v1`은 등록 binding·기존 두 승인 digest·
현재 관측·action을 결합한다. 최초 intent와 재승인은 구분하며 history에 단계별 승인과
`golem.intent-damage-receipt.v1`을 보존한다. 미완료 marker는 일반 접근과 다른 복구를
차단한다. receipt만 실패했다면 새 계획·owner 승인과 exact 상태/회계 검증 후 host
기록만 마무리한다. preserve 중 완전한 pending이 남으면 별도 finish 승인이 필요하다.

새 보존 객체 자체의 잘림·독립 복사본·추가 link·unknown 파일·모호한 귀속·손상된 승인·
추가 host pending은 원문을 보존하고 거부한다. 완전한 승인/receipt의 게시 중단은 아래
host 기록 게시 복구 절을 따른다. 이 경로는 재귀 복구를 허용하지 않는다. 기존 fragment/partial intent는
그대로 남으므로 detach 성공을 일반 접근 복구나 Work 완료로 해석하지 않는다. 원래
fragment 재생성·이전 승인 재기준화·event 게시·locator 마무리를 자동 연결하지 않는다.

연결 검증(2026-10-22, macOS arm64): Debug 집중 CTest **6/6**, ASan/UBSan **3/3**,
Release **3/3 PASS**. 각 구성의 host 내부 **125/125**, Debug QA 경계 **10/10 PASS**.
native 추가 회귀는 owner lock 충돌, stale snapshot·잘못된 승인·guard 거부, 보존 후
중단, final link 생성 후 중단, reopen 후 별도 마무리/분리, 실패 시 출력 보존,
실제 점유 감소와 event/locator 미게시를 검사했다. host 추가 11개는 읽기 전용 무변경,
독립 단계, pending-only/pair, receipt 재진입, 잘린 terminal 객체·짧은 header·추가 link·
독립 복사본·변조된 부모 승인·stale 승인·추가 host pending·재진입 원문 변경 거부,
승인 게시 실패 시 native 무변경, 등록 변경 시 기존 locator 보존을 다룬다.

JUnit: `build/{dev,asan,release}/intent-damage-recovery.xml`. 첫 host 실행의 테스트 import
누락은 수정 후 위 세 구성에서 다시 검증했다. 기존 설계 7개 문서 해시와 보호 코드의
무변경을 확인했다. 실제 authority 등록·TRAP·Work·기존 증거는 조작하지 않았다.
Linux/Windows·실제 전원 손실·실제 ENOSPC·전체 suite·CI는 이번 검증 범위가 아니다.

## 완전한 fragment·damage host 기록의 게시 복구

기존 `host_publication_plan`·`finish_host_publication` 및 `host_alias_recovery_plan`·
`recover_host_alias`는 fragment/damage intent, history의 재승인 intent, receipt를 지원한다.
새 명령이나 별도 native 실행기는 추가하지 않는다. owner가 pending/final 이름을 명시하고
새 계획 digest와 `approve_local_owner=True`를 제공해야 한다. 자동 탐색·선택·재실행은 없다.

schema는 closed contract로 검증한다. canonical JSON, 원문 길이/digest, 등록 binding,
계획 digest, 대상 파일명, 원래 partial 승인과 damage의 부모 fragment 승인 연결을 확인한다.
receipt는 최초 intent와 실제 재승인, 이후 상태·점유 변화가 기존 단일 단계 전이와 맞아야 한다.
재승인 파일은 활성 intent와 불변 원문 identity/digest를 공유해야 한다. 과거 history에서
승인을 임의로 골라 대체하지 않는다. 이 검사는 local owner 기록의 정합성이지 외부 서명 인증이 아니다.

완전한 pending-only는 기존 no-overwrite hardlink 게시를 재사용한다. 정확한 동일 inode
final/pending 두 link는 pending 이름만 제거한다. final-only는 앞서 확정된 host 게시
승인에 대한 재진입에서만 허용한다. 독립 복사본·추가 pending/link·잘린 JSON·불명확한
파일명·다른 등록·잘못된 receipt 전이는 그대로 거부한다.

별도 HOST_PUBLICATION 또는 HOST_ALIAS_RECOVERY intent에 대상 원문의 identity/digest와
의존 승인 파일의 digest 목록(`bindings`)을 먼저 확정한다. 중단 후 새 계획·owner 승인을
받으며 의존 승인 파일이 달라졌으면 거부한다. receipt 실패 시 동일 원문이 FINAL임을
확인한 뒤 host 기록만 마무리한다. 기존 fragment/damage marker를 지우지 않는다.

lock 순서는 기존 common-dir lock 다음 authority owner lock이다. native 복구 API를
호출하지 않으며 authority bytes·quota lane·event·locator·Work는 변경하지 않는다.
게시된 intent에 담긴 preserve/finish/detach도 실행하지 않는다. 필요한 native 단계는
별도 계획과 승인으로 남는다. 새로운 host 게시 복구 승인/receipt 자체의 부분 게시,
잘린 JSON의 재구성, 보존 객체의 재귀 복구는 이 확장의 대상이 아니다.

후속 terminal 게시 경로는 아래 절처럼 완전한 host-publication/host-alias 기록만
한 단계 추가로 취급한다. 위 문단의 자기 기록 미지원은 해당 확장 이전 경계이며,
새 terminal 기록 자체는 여전히 복구 대상이 아니다.

검증(2026-10-22, macOS arm64): Debug 집중 CTest **4/4**, ASan/UBSan **3/3**,
Release **3/3 PASS**. 각 host suite **140/140**, 기존 QA 경계 **10/10 PASS**.
추가 15개 테스트는 fragment/damage의 intent·재승인·receipt 각각의 pending-only/pair,
읽기 전용 무변경·native 미호출·authority bytes 보존, 별도 alias API, target link 이후
중단과 final-only receipt 재진입, 승인 게시 실패·잘린 JSON·잘못된 receipt 회계·
의존 승인 변경·재승인 identity 변경·독립 복사본·게시 복구 자체로의 확장 거부를 다룬다.
의존 승인 변경 테스트는 대상 link 직전에 중단하도록 보강한 뒤 세 구성에서 각각
**1/1 추가 PASS**를 확인했다. JUnit은
`build/{dev,asan,release}/intent-host-preservation-publication.xml`이다.
기존 설계 7개 문서 해시 및 보호 코드 무변경을 확인했다. 테스트는 임시 Git/authority만
사용했다. Linux/Windows·실제 전원 손실/ENOSPC·전체 suite·CI는 이번 검증 범위가 아니다.

## Host terminal: 한 단계 승인 기록 게시 복구

`host_terminal_plan(root, record, pending_name, final_name, git=...)`은 읽기 전용 계획을
반환한다. `finish_host_terminal(..., reviewed_plan_sha256, approve_local_owner=True)`은
정확한 계획에 대한 local owner 승인을 요구한다. 대상은 host-publication/host-alias의
완전한 intent·history 재승인 plan·receipt로 고정하며 이름과 schema를 모두 검증한다.
이 API에서는 host-terminal 자체의 intent·재승인·receipt를 거부한다.
완전한 terminal 기록의 승인된 예외는 아래 고정된 host-final API만 담당한다.

원래 대상 기록을 다시 읽어 canonical JSON·schema·등록 binding·원문 길이/digest·
inode와 기존 승인 연결을 확인한다. receipt가 주장하는 완료 상태와 실제 파일 상태가
맞아야 하고, 재승인에 기록된 단계보다 실제 상태가 역행하면 거부한다. 이 검증은 native
작업을 실행하거나 대신 승인하지 않는다. 원래 대상이 없어졌거나 모호하면 자동 탐색하지 않는다.

`golem-intent-authority.host-terminal.json`을 native 밖 Git common-dir에 먼저 게시하고
계획/intent/receipt schema는 `golem.intent-host-terminal-{plan,intent,receipt}.v1`을 쓴다.
계획의 `bindings`는 원래 대상의 이름·관측 identity/digest·현재 단계·의존 승인 digest를
결합한다. 원래 대상의 pending이 아직 있다면 정확히 그 이름과 복구 대상의 pending만
허용하며, 그 외 pending은 차단한다. 원래 pending 이름은 변경하지 않는다.

common-dir lock 뒤 authority owner lock을 취득한다. 기존 no-overwrite 게시 상태 전이를
재사용하여 pending-only를 게시하거나 정확한 동일 inode 두 link의 pending만 제거한다.
final-only는 온전한 terminal intent에 대한 새 계획·owner 승인으로 receipt를 마무리할
때만 허용한다. 이전 단계의 marker·원래 대상·native bytes·quota lane·event·locator는
변경하지 않는다. terminal marker가 남으면 기존 common-lock 진입은 차단되고 terminal
전용 경로만 승인 기반 재진입을 허용한다. 완료 시 terminal marker만 제거한다.

terminal 승인 자체가 잘리면 복구하지 않는다. 완전한 게시 pending만 아래 예외를 따른다.
잘린 JSON 보충·독립 복사본 병합·서명/issuer 인증 추정·보존 객체 재귀 복구는 없다.
이 단계의 성공을 원래 복구나 Work 완료로 승격하지 않는다.

검증(2026-10-22, macOS arm64): Debug 집중 CTest **4/4**, ASan/UBSan **3/3**,
Release **3/3 PASS**. 각 host suite **153/153**, Debug QA 경계 **10/10 PASS**.
추가 13개 테스트는 두 host family의 intent·재승인·receipt 각각의 pending-only/pair,
읽기 전용 무변경·native 미호출·원래 pending과 authority bytes 보존, link 이후 중단과
final-only 재진입, 승인 게시 실패, 잘린 JSON·추가 pending·독립 복사본·역행 상태·
stale 승인·승인 부재·owner lock 충돌·terminal 자기 승인 손상/재귀 대상 거부를 다룬다.
JUnit: `build/{dev,asan,release}/intent-host-terminal.xml`.
기존 설계 7개 문서 해시 및 보호 코드 무변경을 확인했고, 임시 Git/authority만 사용했다.
실제 프로젝트·TRAP·Work·기존 증거에 적용하지 않았다. Linux/Windows·실제 전원 손실·
실제 ENOSPC·전체 suite·CI는 이번 검증 범위가 아니다.

## 고정된 최종 Terminal 게시 예외

`host_final_plan`은 읽기 전용 계획을 반환하고 `finish_host_final`은 검토한
`plan_sha256`과 `approve_local_owner=True`를 요구한다. 대상은 완전한
host-terminal intent·history 재승인 plan·receipt로 고정된다. 임의 schema나
복구 깊이를 받아 재귀적으로 실행하는 API가 아니다.

기존 common-dir lock과 authority owner lock 아래 canonical JSON·등록/pin·
계획 digest·원문 inode/길이/digest·원래 대상·의존 승인과 상태 전이를 재검증한다.
명시된 의존 pending 이름만 허용하며 추가 pending·독립 복사본·상태 역행은 차단한다.
native 호출 없이 기존 no-overwrite 게시 상태 전이만 재사용한다.

고정 marker는 `golem-intent-authority.host-final.json`, schema는
`golem.intent-host-final-{plan,intent,receipt}.v1`이다. 승인 게시 후 대상 게시,
history receipt 보존 후 이 marker만 제거한다. 원래 terminal marker 및 그 아래
복구의 marker는 보존한다. 중단 시 일반 진입을 차단하고 온전한 최종 승인에 대해
새 계획·명시적 owner 승인으로 pending-only·동일 inode 두 link·final-only의
남은 게시 단계만 처리한다. event·locator·원래 복구는 자동 연결하지 않는다.

**host-final 승인·재승인·receipt는 모든 게시 복구 대상 registry에서 제외한다.**
이 기록 자체의 부분 게시·잘린 JSON·불명확한 상태는 원문을 유지한 채 중단한다.
다음 복구 계층이나 보존 객체 재귀 복구는 제공하지 않는다. native quota lane은
변하지 않으며 이 성공은 원래 복구나 Work 완료를 의미하지 않는다.

검증(2026-10-22, macOS arm64): Debug 집중 CTest **4/4**, ASan/UBSan **3/3**,
Release **3/3 PASS**. 각 host suite **162/162**, Debug QA 경계 **10/10 PASS**.
이번 9개 추가 테스트는 terminal intent·receipt·재승인 각각의 pending-only/pair,
읽기 전용 무변경·native 미호출·authority bytes 보존, pair/final-only 중단 재진입,
잘린 JSON·자기 복구 대상·추가 pending·독립 복사본 거부, 명시적 승인·stale 계획,
최종 승인 손상 시 일반/terminal/final 진입 차단, 승인 게시 실패 시 원문 보존을 다룬다.
JUnit: `build/{dev,asan,release}/intent-host-final.xml`.
기존 설계 7개 문서 해시와 QA·실행·session 보호 코드 무변경을 확인했다.
임시 Git/authority만 사용했고 TRAP·실제 Work·기존 증거에 적용하지 않았다.
Linux/Windows·실제 전원 손실·실제 ENOSPC·전체 suite·CI는 미검증이다.

## D01 전체 복구 경계 감사 (2026-10-22)

| 경로 | 허용 범위 | 자동 연결하지 않는 단계 |
|---|---|---|
| 등록/변경 locator 복구 | 확정된 native 등록과 일치하는 host 게시 마무리 | native 재게시·rollback·재활성화 |
| native pending | 완전한 마지막 D01 준비·payload의 승인된 event 게시 | locator 마무리 |
| native alias | 검증된 동일 inode 두 이름의 pending 제거 | event 재게시 |
| partial/quarantine | 원문·귀속 보존 후 격리, 정확한 원본 payload 대체 | event·locator |
| envelope | 완전한 격리 객체의 게시 마무리 | 원래 staging 분리·payload 대체 |
| fragment/damage | 승인된 고정 형식 보존·게시·별도 분리 | 다음 보존 객체 손상의 재귀 복구 |
| host alias/publication | 지원 기록의 완전한 동일 bytes 게시 | 기록에 담긴 native 동작 |
| host terminal | 완전한 host-publication/alias 기록 게시 | 원래 host 복구 |
| host final | 완전한 terminal 기록 게시 | 원래 terminal 복구·새 복구 계층 |

최종 차단은 단순 schema 선언이 아니라 실제 진입점에서 검사한다. 최종 marker가
있으면 일반 공개 진입점 26개와 `authorized_root`는 공통 lock gate에서 거부한다.
예외인 final API도 온전한 승인과 정확한 의존 관계를 요구한다. final intent·재승인·
receipt 게시 중 절반만 기록된 pending을 각각 주입하는 회귀 검사는 원문 보존과
final/terminal/publication 재진입 거부를 확인한다. 세 게시 대상 registry 모두
host-final intent·재승인·receipt 이름을 받지 않는다.

native owner lock·guard·snapshot·quota 재검사와 host의 명시 승인·pin·등록 binding을
대조했다. 검사 우회나 추가 복구 계층은 필요하지 않아 이 감사에서는 회귀 테스트를
보강했다. 이는 trusted cooperative local host 계약 검증이다. 내부 C bridge를 직접
실행하는 동일 uid의 적대적 사용자까지 host marker로 통제한다는 의미는 아니다.

로컬 감사 검증: macOS arm64에서 Debug·Release·ASan/UBSan 각각 **14/14 CTest**
통과. 각 host suite **166/166**, QA 경계 **10/10**, benchmark 도구 **4/4** 통과.
최종 게시 집중 테스트는 EOF 공백 정리 후에도 **13/13** 통과했다.
JUnit은 `build/{dev,asan,release}/intent-d01-audit.xml`이다. 기존 설계 7개 문서의
해시와 QA·실행·session 보호 코드가 변하지 않았음을 확인했다. 이 결과는 임시 fixture
검증이며 실제 Work 복구·전원 손실·ENOSPC 검증을 의미하지 않는다. 원격 CI 결과는
해당 커밋에 연결된 GitHub Actions 기록으로 별도 확인한다.

CI 감사에서 D01의 직접 subprocess 호출 7곳(6개 함수)이 공통 실행 기록 경계의
미검토 호출로 검출됐다. Git identity/worktree 조회는 읽기 전용이며 native 호출은
pin·단일 FD·명시 환경·stdin 등록 bytes를 사용하는 내부 protocol이다. 기존 실행
기록기는 input/pass_fds를 지원하지 않고 파일을 생성하므로 해당 protocol을 무조건
대체하지 않는다. 이 6개 함수만 명시적으로 검토 예외에 등록하고 별도 AST 테스트로
정확한 호출 수·run 사용·timeout·capture·환경·단일 FD 인자를 고정했다.
mutation의 승인·receipt는 기존 host/native 경로에 보존한다. 이 예외는 일반 command
실행 관측 로그의 자동 수집을 제공하지 않으며 제품 실행의 새 예외가 아니다.

clean-source CI에서 새 native helper가 export allowlist에 누락된 것도 확인했다.
검토한 D01 도구 6개와 schema/fixture 2개만 validation export에 추가하고, export 후
파일 바이트 일치와 Python import를 검사한다. 실제 승인·authority·증거·개발문서는
이 allowlist에 포함하지 않는다. Conan의 제품 소스 export 범위는 확장하지 않는다.
