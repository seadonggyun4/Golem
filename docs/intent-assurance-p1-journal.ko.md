# P1 준비 기록과 quota-aware journal

2026-10-22. 승인된 D01·D08/v2 및 최초 lane 고정 계약을 사용하는
**private native journal 경로**다. baseline reducer·제품 CLI·실제 authority 설치 완료는 아니다.
[결정·용량 기록](intent-assurance-journal-capacity.ko.md)을 따른다.

## 구현 범위

[journal.h](../src/intent/journal.h), [journal.c](../src/intent/journal.c)는 별도의
등록 대상 root descriptor를 받아 독립 descriptor를 열고 exclusive owner flock을 수명 동안 유지한다.
root를 자동 생성하거나 프로젝트 안에 대체 authority를 만들지 않는다.
private owner/mode를 검사하며 fork로 상속된 handle은 원래 PID와 달라 거부한다.
host는 호출 전에 D01의 실제 등록·Git common-dir identity·pin을 확인해야 한다.
이 검증을 대신하는 새 registry나 신뢰된 host endpoint를 이번에 만든 것은 아니다.

이번 writer는 operation당 **하나의 bounded event payload**를 준비·게시한다.
source/baseline 다중 객체 CAS publication 전체가 아니다. 같은 operation/request/payload/lane의
확인된 완료 재조회는 파일을 만들지 않는다. 별도 operation의 같은 bytes는 별도 payload 파일로
보존하고 각각 계산한다. shared CAS 객체의 교차 operation 재사용·최초 소유 lane index는
후속 object store가 구현해야 하며, 현재 writer가 이를 검증했다고 표시하지 않는다.

## 준비 기록

파일명은 sequence에 따른 `00000001.prep`, `00000001.payload`, `00000001.event`다.
각 게시의 임시 이름에는 `.pending`이 붙는다. 파일명에 사용자 경로를 넣지 않는다.
이 flat layout은 private prototype이며 과거 Work 형식의 변경·마이그레이션이 아니다.

준비 기록은 닫힌 JSON `golem.intent.quota-preparation.v1`이며 다음 8개 field만 허용한다.

| Field | 계약 |
| --- | --- |
| schema | 정확한 등록 이름 |
| lane | 0 intake, 1 resolution, 2 recovery |
| sequence | 실제 연속 sequence, 1..6208 |
| payload_bytes | 실제 payload의 길이, 최대 256 KiB |
| operation_id | caller의 정확한 operation identity digest |
| request_digest | 정확한 승인 요청의 identity digest |
| previous_event_digest | 앞 event의 raw digest, 최초에는 zero |
| payload_digest | 실제 payload bytes의 raw SHA-256 |

중복/unknown key·타입 불일치·잘못된 digest·sequence gap을 거부한다.
`gi_domain_digest`의 명시 registry에 preparation schema를 추가했다. 원본 JSON을 정규화하지 않고
승인된 `schema ASCII + NUL || uint64_le(length) || exact UTF-8 JSON` 규칙으로 identity를 구한다.
registry 등록은 digest 계산 지원이며 standalone digest 성공이 전체 shape·issuer 인증은 아니다.
source와 기존 raw CAS digest 의미는 바꾸지 않았다.
80-byte `GIQEV001` event frame은 sequence·이전 event digest·준비 기록 domain digest를 담는다.
준비 기록의 lane을 변경하면 event의 binding 검증이 실패한다.

## 게시 순서

1. 같은 owner lock에서 필수 trusted host guard를 호출하고 전체 journal/inventory를 재검증한다.
   guard는 실제 issuer·owner·binding·보호·policy 검사를 담당해야 한다. no-op guard는 테스트 전용이다.
2. expected sequence/head, operation idempotency, v2의 모든 lane/축 및 staging 최고 사용량을 검사한다.
3. immutable 준비 기록을 file fsync → no-replace link → directory fsync로 게시한다.
4. payload를 같은 방식으로 게시한다. 이 단계는 아직 event commit이 아니다.
5. host guard를 다시 실행하고 **같은 lock 아래 실제 파일을 다시 읽어** 준비 기록 identity·payload·head와
   quota를 재검사한다. event와 pending alias의 추가 bytes/entries도 예산 안이어야 한다.
6. event frame을 게시한 뒤에만 receipt를 반환한다. 각 성공한 live 게시만 자신의 staging 이름을 제거한다.

guard 재진입은 거부하며 callback이 handle을 닫아서는 안 된다.
동일 handle의 다중 thread 사용은 caller가 직렬화해야 한다. 별도 handle/process의 writer 경쟁은
동일 root의 flock으로 차단한다.
quota 성공은 의미 검토·제품 실행·completion 승인이 아니다. byte projection으로 guard를 우회하지 않는다.
기존 QA Work writer lock의 수명을 바꾸거나 Work/document journal에 새 quota를 덧씌우지 않는다.

## 복원과 실패

- `.prep`가 있으면 준비 slot과 계획된 payload bytes를 원래 lane의 사용량에 포함한다.
  관리 파일 bytes/entries에는 실제 prep/payload/event/pending의 점유를 모두 계산한다.
- prep가 유효한 중단 상태는 pending으로 조회되며 자동 이어쓰기·삭제·환급하지 않는다.
  event commit만 없는 payload도 orphan으로 남아 동일 lane에 계속 계산된다.
- 부분 prep만 있고 귀속할 수 없거나, 알 수 없는 파일·손상·gap이 있으면 쓰기를 거부한다.
  추정 lane 분류·복구를 수행하지 않는다. raw inventory는 별도 API로 관측할 수 있다.
- 준비 게시를 시작한 뒤의 실패는 handle을 poisoned로 만든다. 동일 handle의 추가 append를 거부한다.
  `inspect`/`lookup`은 읽기만 수행하며 poison을 해제하지 않는다.
- `gi_journal_lookup`은 정확한 operation/request에 대해 committed/pending 상태를 반환한다.
  reopen 자체가 재실행 승인은 아니다. pending은 reopen 후에도 새 append를 막는다.
- 실패 시 API 결과 output을 보존하지만 이미 생성된 준비 파일은 남을 수 있다.
  I/O 오류는 commit 여부가 불명확할 수 있으므로 단순 재시도하면 안 된다.
- signed issuer attestation이나 같은 uid의 악의적 파일 조작에 대한 방어를 새로 제공하지 않는다.
  owner lock을 지키는 writer와 private root, trusted host guard가 전제다.

## 검증 및 남은 범위

[테스트](../tests/c/test_intent_journal.c)는 실제 임시 파일을 사용한다.
정상 게시/reopen/lookup·동일 operation의 중복 비용 방지·lane/request/payload 변경·stale head,
guard 전후 거부, 게시 직전 예상 밖 파일 및 payload 제거, pending 점유 유지,
준비 후 자식 프로세스 종료·reopen, 별도 프로세스 lock 경쟁·상속 handle 거부,
실제 recovery 64-event 포화 후 65번째 거부 및 다른 lane 여유 유지,
committed prep의 lane 위조, 부분 prep의 미귀속 차단을 검사한다.

현재 실제 플랫폼은 macOS arm64다. Linux/Windows·전원 손실·실제 ENOSPC·모든 fsync/link 경계의
fault injection, 장기 6208-event 성능은 미검증이다. 파일시스템 성공을 장치 영속성 보장으로 확대하지 않는다.
full source/baseline object store·cross-object CAS 재사용·issuer 정책·
승인 기반 pending 복구 절차는 후속 범위다. 이 문서는 전체 P1 완료를 주장하지 않는다.

```sh
cmake --build --preset dev --target golem_test_intent_journal golem_test_intent_schema golem_intent_schema_helper --parallel 2
ctest --preset dev -R '^(intent_journal|intent_inventory|intent_quota|intent_schema_.*|execution_boundary_cli)$' --output-on-failure --output-junit intent-journal.xml
cmake --build --preset asan --target golem_test_intent_journal golem_test_intent_schema --parallel 2
ctest --preset asan -R '^(intent_journal|intent_inventory|intent_quota|intent_schema_domain)$' --output-on-failure --output-junit intent-journal.xml
cmake --build --preset release --target golem_test_intent_journal golem_test_intent_schema --parallel 2
ctest --preset release -R '^(intent_journal|intent_inventory|intent_quota|intent_schema_domain)$' --output-on-failure --output-junit intent-journal.xml
```

실행 결과: Debug 집중 회귀 **12/12 PASS**, ASan/UBSan **4/4 PASS**, Release **4/4 PASS**.
최종 결과는 각 preset의 `intent-journal.xml`에 기록했다. Debug에는 기존 QA writer lock·보호 경계
테스트가 포함되어 있으며 21.92초에 통과했다. 독립 Python hashlib로 preparation domain vector도
native helper와 대조했다: `1aeff27242801a4091e16e982fc29cb4978ac07088b16e34eaadda1b12b16537`.
원본 설계 7개 문서의 SHA-256은 P0 기록과 같고 기존 document/execution/agent-session
보호 코드 diff는 없다. 실제 Work·TRAP·증거에 새 journal을 설치하거나 기록하지 않았다.

후속 [D01 host 연결 기록](intent-assurance-d01-host.ko.md)에 기존 registry와의 차이,
승인된 common-dir locator 등록·pin 검사와 native 읽기 전용 연결을 정리했다.
첫 native event에 고정 authority 등록 binding을 기록하고 intake quota에 계산한다.
이는 host 연결 구현이며 실제 프로젝트 설치나 baseline/issuer 권한 승인은 아니다.

후속 D01 lifecycle은 검증된 metadata를 한 번 순회하는 `gi_journal_visit`를 사용해
등록 변경 chain의 최신 digest를 확인한다. callback 중 재진입을 거부하며 기존 writer
guard·quota·prepare/commit 형식은 유지한다. 일반 변경만 intake event로 추가하고,
committed-only locator 복구는 native journal을 다시 게시하지 않는다.

후속 승인에 따라 complete-preparation D01 복구가 추가되었다. 내부
`gi_journal_pending_plan_get`/`gi_journal_pending_finish`는 마지막 intake prep+payload가
완전하고 event/staging이 없는 상태만 다룬다. private D01 bridge가 operation 의미를 제한하고
host가 immutable owner 승인 intent를 먼저 보존한다. snapshot/guard/inventory/quota를
owner lock 아래 재검사하고 기존 prep/payload를 바꾸지 않은 채 event만 게시한다.
완료된 event 재게시와 staging 정리는 지원하지 않는다. 이는 일반 Work 복구 API가 아니다.

후속 alias 해제 예외는 별도 `gi_journal_alias_observe`/`gi_journal_alias_remove`로 제공한다.
마지막 intake sequence의 final/pending 동일 inode 쌍만 검사하며 guard·owner lock·snapshot을
재검증한다. pending 이름 제거 전후 실제 inventory를 비교해 staging bytes/entry만 해제한다.
final/event/payload 귀속은 유지한다. D01 의미와 새 owner 승인 기록은 private host가 담당한다.
부분 파일이나 final 없는 staging을 이 API로 정리하지 않는다.

후속 승인된 독립 staging 복구는 `gi_journal_partial_observe`/
`gi_journal_partial_quarantine` 및 별도 `gi_journal_payload_replace`로 분리한다.
기존 flat 파일 외에 `quarantine/`의 검증된 `GIQUA001` envelope만 명시적으로 인식한다.
320-byte header와 원문을 함께 검증하고 모든 이름의 bytes/entry를 최초 intake에 계산한다.
디렉터리 entry도 quota에 포함하며 알 수 없는 파일·부분 envelope는 여전히 쓰기를 차단한다.
원문 보존 게시 완료 전에는 활성 staging을 제거하지 않는다. 격리 후 payload 대체는
새 계획·owner 승인과 정확한 prep digest/길이 검사를 요구하고 event는 게시하지 않는다.
기존 prep/event/CAS bytes·identity·QA 보호 계약은 변경하지 않는다.
상세 지원 범위, 중단 후 명시적 마무리와 미지원 상태는
[D01 host 계약](intent-assurance-d01-host.ko.md)의 독립 staging 격리 절을 따른다.

후속 완전한 envelope 게시 마무리는 별도의 `gi_journal_envelope_*` 경로로 제공한다.
일반 restore는 pending envelope를 계속 거부한다. 전용 복구 restore만 검증된 마지막
sequence의 pending-only 또는 정확한 final/pending 동일 inode 쌍을 읽고 실제 이름별 점유를
intake에 계산한다. 원문과 기존 owner 승인에 연결된 envelope를 다시 쓰지 않고 final
hardlink 게시·pending 이름 제거만 수행한다. 원래 staging과 event/locator는 그대로 남는다.
잘린 envelope와 독립 복사본을 수선하거나 정상 파일로 승격하지 않는다.

## 잘린 보존 객체 codec과 제한 복구 연결

`src/intent/fragment.c`의 `gi_fragment_damage_*`는 `GIQFR001`의 검증된 strict
prefix를 보존하는 순수 codec과 quota 계산이다. 기존 `GIQUA001`과 `GIQFR001` 형식은
변경하지 않는다. 파일 읽기/쓰기·owner 승인·inventory 귀속·journal 복구 권한을 제공하지
않으며, 일반 restore의 손상 거부도 완화하지 않는다.

새 `GIQFD001`은 384바이트 header와 잘린 원문을 담는다. 정수는 uint64 little-endian이다.

| offset | 내용 |
|---|---|
| 0 | magic `GIQFD001` |
| 8/16/24 | sequence / 최초 intake lane / kind |
| 32/40/48/56 | 잘린 객체 device / inode / 길이 / 기대 완전본 길이 |
| 64/96/128/160 | prep / 원래 격리 승인 / fragment 보존 승인 / 새 승인 digest |
| 192/224 | 잘린 원문 / 기대 완전본 SHA-256 |
| 256 | 원래 상대 경로, 64바이트 NUL padding |
| 320 | reserved zero, 32바이트 |
| 352 | 이 필드를 zero로 둔 전체 객체 SHA-256 |
| 384 | 잘린 원문 bytes |

기대 완전본은 별도로 제공된 원래 source·잘린 envelope·binding으로 기존 encoder를
재사용해 재구성한다. 입력 header를 승인 근거로 신뢰하지 않는다. 320바이트보다 짧은
prefix·완전본 자체·불일치 bytes·재귀적인 `GIQFD001` 입력은 거부한다. 실패 시 호출자의
출력 포인터/길이는 바꾸지 않는다. digest 일치는 owner 승인이나 출처 인증을 대체하지 않는다.

codec의 quota 계산은 이미 실제 inventory에 포함된 원본 점유를 전제로 한다. 새 게시에는
객체 한 개의 영구 점유와 두 이름의 peak를, pending-only 마무리에는 추가 이름 하나의
peak를 검사한다. 다른 lane 예약량은 사용하지 않는다.

전용 `gi_journal_damage_observe/visit/apply`는 마지막 D01 대상에서 실제 inventory를
검증하고 원래 staging·잘린 envelope·잘린 fragment·보존 객체의 각 이름별 점유를 최초
intake에 귀속한다. 기존 준비 기록과 event/payload 비용은 이동하거나 환급하지 않는다.
`apply`는 기존 fragment 게시 상태 기계를 재사용하며 owner lock 아래 guard·snapshot·
실제 quota를 두 번 확인한다. preserve(0), finish(1), detach(2)는 별도 호출이다.
호스트 연결과 승인·receipt 계약은 D01 host 문서의 GIQFD001 연결 절을 따른다.

새 객체 자체의 잘림과 잘린 승인·receipt JSON은 계속 차단한다. 완전한 fragment/damage
host 기록의 게시만 중단된 경우에는 D01 host 문서의 승인 기반 게시 복구를 사용할 수 있다.
분리 후에도 원래 staging·잘린 envelope·기존 승인 marker를 남기므로 일반 journal 접근은
여전히 차단된다. 이 경로는 남은 fragment 재생성이나 기존 승인의 재기준화를 허가하지 않는다.
