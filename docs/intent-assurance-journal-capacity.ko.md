# P1 Journal 용량 실험과 D08 결정 제안

2026-10-22. **보존 방향·전체 관리 파일 다중 한도 회계·초기 수치 v2는 후속 승인됨.
순수 회계 primitive까지 구현하며 실제 inventory·store 게시·layout은 아직 미구현이다.**
기반 HEAD는 `f681d74c0eb77622374da7ddd0ec79c861214f59`이며 기존 P1 작업 변경이 있는 상태다.
[P1 schema 현황](intent-assurance-p1-schema.ko.md),
[제안 계약](intent-assurance-contracts.ko.md)과 함께 읽는다.

## 실제 코드에서 확인한 구조

- `src/document/record.c`: 80-byte frame(magic, sequence, 이전 frame digest, payload digest),
  CAS 준비 후 참조 게시. 게시 불확실성은 handle을 poisoned로 만든다.
- `src/document/storage.c`: no-replace link 게시, 파일과 디렉터리 fsync,
  재개 시 sequence 순서로 event를 읽고 reducer를 적용한다.
- `include/golem/admission.h`의 65536은 admission 한도이지 신규 project journal 승인값이 아니다.
- 기존 QA writer lock 및 보호 검사는 그대로 유지한다. 이번 실험은 authority를 생성하지 않는다.

## 재현 방법과 한계

[실험 도구](../tools/benchmark_intent_journal.py)는 Python 표준 라이브러리로
80-byte hash-chain frame + 개별 raw CAS 파일 배치를 모사한다. 실제 native API 호출은 아니다.
합성 payload의 previous_event_digest는 placeholder이며 frame chain만 실제 연결한다.
따라서 P1 event schema conformance·reducer·실제 journal 복구의 증명이 아니다.
임시 디렉터리만 생성·삭제하며 기존 evidence를 읽거나 수정하지 않는다.
한 case payload는 최대 256 MiB로 제한한다. 원문 source·외부 참조 객체는 생성하지 않는다.

```sh
python3 -m unittest discover -s tools -p test_benchmark_intent_journal.py
python3 tools/benchmark_intent_journal.py --parent build --counts 256 1024 4096 --sizes 1024 16384 > build/intent-journal-capacity.json
python3 tools/benchmark_intent_journal.py --parent build --counts 256 --sizes 1024 262144 --sync > build/intent-journal-capacity-sync.json
ctest --preset dev -R '^execution_boundary_cli$' --output-on-failure
```

측정 플랫폼: macOS 26.5.2 arm64, Python 3.14.7, 기존 외장 SSD의 build 디렉터리.
두 측정 명령이 일부 시간 겹쳤으므로 write 시간은 경합 영향을 포함한다.
결과 JSON은 harness SHA-256, 플랫폼, case 매개변수, 실제 bytes, head와 replay 3회 원값을 보존한다.
당시 harness SHA-256: `e77b25a5d7f25b33d9e252806c1cfc5872cf7aaf7273d0c29823543ac913f828`.
fsync는 OS syscall 성공만 확인한다. 전원 손실·장치 캐시 영속성 보장은 측정하지 않았다.
비동기 case는 파일 배치 비용 측정용이며 제품에서 fsync 제거를 제안하지 않는다.
replay는 쓰기 직후 캐시가 있는 상태이며 cold-start 결과가 아니다.
할당량은 파일별 st_blocks 합이고 디렉터리·파일시스템 메타데이터·snapshot 비용은 제외한다.

## 측정 결과

| 이벤트 | payload/개 | fsync | 논리 bytes | 파일 할당 MiB | 게시 초 | replay 중앙값 초 |
| ---: | ---: | --- | ---: | ---: | ---: | ---: |
| 256 | 1 KiB | 없음 | 282624 | 2 | 0.284 | 0.024 |
| 1024 | 1 KiB | 없음 | 1130496 | 8 | 1.290 | 0.098 |
| 4096 | 1 KiB | 없음 | 4521984 | 32 | 5.937 | 0.493 |
| 256 | 16 KiB | 없음 | 4214784 | 5 | 0.232 | 0.021 |
| 1024 | 16 KiB | 없음 | 16859136 | 20 | 1.185 | 0.091 |
| 4096 | 16 KiB | 없음 | 67436544 | 80 | 5.390 | 0.499 |
| 256 | 1 KiB | 있음 | 282624 | 2 | 1.948 | 0.020 |
| 256 | 256 KiB | 있음 | 67129344 | 65 | 6.609 | 0.154 |

4096개 case는 각각 8192개 파일이다. 작은 payload에서도 할당량과 파일 수 부담이 있다.
첫 replay는 4096개에서 1.12~1.51초, 이후 0.43~0.50초여서 중앙값만으로 지연 상한을 약속할 수 없다.
1 KiB case의 실제 파일 할당량은 논리 bytes의 약 7.42배다.

계산상 65536개 x 256 KiB는 payload만 **16 GiB**, 4096개도 **1 GiB**다.
이는 실측값이 아닌 산술 상한이며 source/CAS의 참조 폐쇄·orphan·pending은 별도다.
baseline당 source 64 MiB 제한으로 전체 보존 이력의 저장량까지 제한되지는 않는다.
따라서 event 개수만 제한하거나 baseline 한도를 lifetime quota로 오해하면 안 된다.

## 승인된 보존 방향과 미결 운영 한도

**후속 사용자 승인:** `무삭제·한도 거부, 초기 rollover 제외`를 채택했다.
P1은 자동 삭제·TTL·자동 compaction 없이 모든 committed event와 참조 증거를 보존하고,
한도 초과는 명시적 거부한다. 초기 store는 자동·명시적 rollover 모두 구현 범위에서 제외한다.
이 방식은 장기 무제한 운영을 제공하지 않는다. 한도 도달 시 읽기·진단·operation 조회를 유지하고,
추가 intake를 중지한다. 해결·복구도 예약량을 소진하면 거부하며 무한 진행을 보장하지 않는다.
기존 Work lock이나 보호 검사를 풀어서 진행하지 않는다.

초기 store부터 손실 없는 명시적 rollover를 구현하는 대안은 이번 결정에서 선택하지 않았다.
향후 별도 승인으로 추가할 경우 아래 segment 연결·복구 계약과 별도 crash test가 필요하다.
자동 TTL 삭제는 unresolved/COMMIT_UNKNOWN/과거 증거와 감사 연속성을 손상할 수 있어 권하지 않는다.

### 수치 후보: 다음 결정에서 검토, 아직 미승인

| 예산 | 검토 시작값 | 의미와 조건 |
| --- | --- | --- |
| 일반 intake | 4096 event 및 64 MiB event payload 중 먼저 도달 | 실험한 범위에서 시작하는 후보; 성능 보장 아님 |
| 해결 control 예약 | 256 event 및 64 MiB payload | 256 의무당 최대 1 event 가정의 산술값; 실제 resolution은 다단계여서 충분성 미증명 |
| 복구/종결 예약 | 16 event 및 4 MiB payload | 예시 여유; reducer별 최악 경로 산정 전 확정 금지 |

총 후보는 4368 event/132 MiB payload다. 파일 allocation·CAS 원문·manifest·pending/orphan은 포함하지 않는다.
따라서 이 수치를 authority 총 디스크 quota로 사용해서는 안 된다.
후속 계약 검토에서 **256 의무에 256 event 예약이 충분하다는 가정은 철회**했다.
위 표는 초기 비교값으로만 보존하며 구현 상수나 권장 확정값으로 사용하지 않는다.
수치 확정 전 resolution을 구성하는 source/answer/proposal/review/impact/event의
최악 참조 크기·단계 수와 별도 authority bytes/inodes 예산을 산정해야 한다.
일반 intake는 예약량을 사용할 수 없고, 해결 lane은 기존 의무와 정확히 연결된 허용 동작만 사용한다.
새 의무를 만드는 해결도 post-state 제약을 적용하고, lane 이름만으로 무제한 intake를 허용하지 않는다.
예산 검사는 CAS publication 전 및 owner lock 안 commit 직전에 수행해야 한다.
이미 존재하는 동일 operation의 결과 조회는 새 공간을 소비하지 않아야 한다.
disk free 조회는 경쟁 writer/다른 앱 때문에 예약 보장이 아니다. ENOSPC/uncertain fsync는
기존처럼 실패 또는 COMMIT_UNKNOWN 처리하고 재개 후 operation lookup으로 확인해야 한다.

### 후속 승인: 무엇을 계산할 것인가

해결 경로에는 source/답변, proposal, resolution review, impact,
RESOLUTION_READY 준비와 최종 commit이 있다. 최종 전이는 한 event여도 준비 객체는 하나가 아니다.
여섯 논리 단계가 각각 한 control 객체를 만든다는 단순 시나리오만으로도
256 x 6 x 256 KiB = 384 MiB가 된다. 이는 최악 상한이 아니며 stage별 event 수의 계약도 아니다.
반복 답변·검토 횟수에는 현재 유한 상한이 없으므로 의무 개수만으로 모든 해결의 예약량을 도출할 수 없다.

사용자는 `전체 관리 파일 회계·다중 한도 채택`을 승인했다.
아래 회계 방향은 승인되었으나 **구현·수치 확정은 아직 아니다.**

| 계산 축 | 제안 |
| --- | --- |
| event | committed event 개수와 event payload bytes를 각각 제한 |
| authority 저장량 | 관리 대상 journal/CAS/source/manifest/index/control 파일의 논리 bytes 및 파일 엔트리 수 제한 |
| 중복 | 검증된 기존 CAS 객체의 재사용은 추가 bytes 0; 별도 임시 복사·파일 엔트리는 공간을 별도 계산 |
| pending/orphan | 참조되지 않아도 존재하는 동안 계산. 자동 삭제하거나 예산을 반환하지 않음 |
| 해결·복구 | 위 각 축에 일반 intake가 사용할 수 없는 예약량. 완성된 요청의 새 객체 및 게시 중 임시 중복까지 사전 계산 |
| 물리 디스크 | 논리 quota와 별도 관측·오류 처리. 파일시스템 allocation·metadata·다른 프로그램의 사용량을 논리 예약으로 보장하지 않음 |

장기 보존 source가 event payload 한도 밖에서 계속 증가하는 것을 막기 위한 구분이다.
관리 대상 범위의 layout은 store 설계에서 명시해야 하며, 경로 밖 Work·TRAP·기존 evidence를
스캔하거나 quota에 편입하지 않는다. 예상 밖 엔트리는 조용히 무시하거나 제거하지 않고 진단한다.
실제 bytes/엔트리·예약 상태를 authoritative lock 아래 검증해야 하며,
충돌·불확실 publication 뒤 reopen 시 재계산 또는 검증 가능한 회계 복원이 필요하다.

첫 P1 구현의 예약량은 **제한된 추가 처리 여유**이지 모든 의무 해결의 보장이 아니다.
공간 부족 시 요청 전체를 거부하고 barriers를 유지한다. 같은 operation lookup·읽기 진단은
새 event를 요구하지 않아야 한다. 이 안은 journal 쓰기 거부·디스크 장애 시에도
읽기가 항상 성공한다는 가용성 약속은 아니다.
아래 수치안은 이 승인에 따른 후속 제안이다. 저장 layout·신원·operation별 권한을 대신 확정하지 않는다.

### 후속 승인: 초기 운영 수치 v2

사용자는 `초기 수치 v2 채택`을 승인했다. 이 표는 이전 비교값을 대체한다.
승인 이후 private 순수 회계 primitive의 상수로 반영했다. 실제 store 제한 enforcement는 아니다.
각 축은 독립적으로 적용하고 하나라도 초과하면 해당 쓰기를 거부한다.
authority bytes에는 event payload도 포함하므로 두 bytes 열을 합산하지 않는다.
예약량은 일반 intake에 대여하지 않고, 해결 lane도 복구 예약을 사용할 수 없다는 안이다.

| 처리 구분 | event 수 | event payload 합 | authority 관리 파일 논리 bytes | 파일 엔트리 수 |
| --- | ---: | ---: | ---: | ---: |
| 일반 intake 한도 | 4096 | 64 MiB | 1024 MiB | 16384 |
| 해결 control 전용 예약 | 2048 | 512 MiB | 1024 MiB | 16384 |
| 복구 전용 예약 | 64 | 16 MiB | 128 MiB | 1024 |
| 합계 | 6208 | 592 MiB | 2176 MiB | 33792 |

근거와 한계:

- 일반 event 수/bytes는 실측한 4096 x 16 KiB 범위다. 실제 native reducer 처리시간은 아직 미측정이다.
- 해결 event 수는 256 의무 x 8 event를 검토 시나리오로 잡았다.
  최대 control 크기를 적용하면 2048 x 256 KiB = 512 MiB다.
  여섯 논리 단계에 추가 준비 여유를 둔 운영 후보이며 8 event로 해결할 수 있다는 계약은 아니다.
  사용자 답변·review가 반복되면 예약량을 소진할 수 있다.
- 해결 authority 1024 MiB 중 위 최대 payload를 제외한 512 MiB는 원문 source·추가 객체·
  임시 게시·index 등에 사용할 후보 여유다. source/manifest 전체 이력 수용을 보장하지 않는다.
- 일반 authority 1024 MiB와 16384 entries는 관리 파일을 포함하기 위한 운영 시작값이다.
  baseline source 64 MiB를 반복하면 event 수보다 bytes 한도가 먼저 도달할 수 있다.
  이 값은 측정으로 찾은 최적값이나 디스크 용량 권장값이 아니다.
- 복구 64 event/16 MiB는 이전 예시 16 event보다 여유를 둔 유한 한도다.
  128 MiB 관리 파일 예산은 32 MiB manifest의 준비·게시 중복 등도 고려한 후보이며,
  recovery operation 목록과 객체 참조량 검증 전 충분성을 약속하지 않는다.
- 실험의 event+payload 두 파일 모델에서 일반 8192, 해결 4096 entries가 필요하다.
  나머지 entries는 원문·index·pending 여유다. 실제 layout에서 파일 증가가 더 크면
  store를 억지로 수락시키지 않고 부족한 축을 진단한다.
- 총 6208 event와 전체 2176 MiB 배치는 실측하지 않았다. 합계는 산술값이며
  물리 디스크 preallocation·공간 확보·장기 운영 보장이 아니다.

native store 구현 전 예약 회계 fixture에서 각 축의 직전/상한/초과,
정수 overflow, ordinary의 예약 침범, 중복 CAS, pending/orphan, staging 최고 사용량,
충돌 후 재계산 및 실패 시 상태 불변을 검증해야 한다.
모든 한도를 소진한 뒤의 읽기/operation lookup은 새로운 event를 게시하지 않아야 한다.
회계 값은 파일 신뢰·issuer 검증을 대체하지 않으며 lane 선택은 caller 문자열만으로 허용하지 않는다.

### 후속 lossless rollover의 필수 조건

1. 단일 authority writer lock 아래 old head·generation·epoch·operation index와
   참조 폐쇄를 검증하고, old segment 마지막 digest와 새 segment 시작을 연결한다.
2. checkpoint는 파생 가속 자료이며 의미·서명·승인 근거를 대신하지 않는다.
   현재 권위 segment 포인터와 전환 commit point를 정의하고 crash 경계마다 검증한다.
3. old/new 양쪽 용량을 사전 확보한다. 이전 segment는 immutable로 보존하며 자동 삭제하지 않는다.
   새 segment만 replay해도 unresolved barriers·idempotency·COMMIT_UNKNOWN이 사라져서는 안 된다.
4. 복사 중 실패·pointer 게시 불확실·양쪽 head 충돌은 quarantine한다.
   수동 파일 삭제·sequence 초기화·새 authority 생성으로 해결하지 않는다.
5. archive export의 존재만으로 원본 삭제를 허용하지 않는다. 삭제/외부 archive 신뢰 정책은 별도 승인이다.

결정 순서: **보존/초기 rollover 범위(승인) → 회계 범위(승인) → 예약량·총 quota 수치(승인)**.
rollover wire/commit 계약은 초기 P1의 선행 결정에서 제외하고 향후 별도 제안으로 남긴다.
아직 issuer/review/activation 또는 store 생성 승인을 대신하지 않는다.

## 검증 범위

실험 도구 단위 테스트 4개 통과: 크기 경계, replay/accounting, 잘린 frame 거부, no-replace.
이 실험에서 crash injection·native replay 성능·실제 ENOSPC·Linux/Windows·rollover를 검증하지 않았다.
기존 core·writer lock·보호 파일·원본 설계 7개 문서·TRAP·실제 Work는 수정하지 않았다.
이번 기록은 초기 용량 판단 자료이며 P1 baseline/store 완료 판정이 아니다.

## 승인 후 순수 회계 구현

`src/intent/quota.h`와 `quota.c`는 private API이며 filesystem·journal·권한 검사를 수행하지 않는다.
`gi_quota_project`는 현재 3개 lane의 4개 축 전체를 먼저 검사하고, 선택 lane의
추가 최고 사용량(peak)이 한도 안인지 확인한 뒤 추가 보존량(retained)만 결과에 더한다.
peak는 retained 이상이어야 한다. 차감 검증 후 덧셈하므로 uint64 overflow를 피한다.
일반·해결·복구 간 자동 대여는 없고 read-only zero-delta는 한도에 도달해도 검사 가능하다.
기존 상태 자체가 상한을 넘으면 다른 lane 호출이어도 INVALID_STATE를 반환한다.
실패 시 output은 그대로이고 성공 시 input/output 동일 주소도 지원한다.

진짜 CAS 재사용·pending/orphan·임시 게시 목록을 계산하는 inventory 구현은 아직 없다.
이 함수에 zero-delta를 전달하는 것만으로 중복 검증이나 operation idempotency가 성립하지 않는다.
caller가 lane 권한·현재 inventory·정확한 delta를 authority lock 안에서 검증해야 한다.
이 primitive는 불확실한 publication 후 임시 자원 해제나 reserve 반환을 수행하지 않는다.
실제 retained 판정은 store가 commit 상태를 확인한 뒤 수행해야 하며, 순수 결과만으로
pending/orphan을 장부에서 제거해서는 안 된다. native writer lock·증거·보호 검사는 변경하지 않았다.

`tests/c/test_intent_quota.c`는 승인된 모든 상수, 12개 lane/축의 경계·UINT64_MAX,
실패 output 보존, peak/retained 관계, 예약 침범 거부, 잘못된 전체 상태·인수,
포화 상태의 zero-delta와 성공 alias를 검사한다. 실제 fsync·동시 writer 검증을 뜻하지 않는다.

승인 후 회계 테스트 결과(macOS arm64): Debug·ASan/UBSan·Release 각각 `intent_quota`
1/1 PASS. 결과는 각 `build/{dev,asan,release}/intent-quota.xml`에 기록했다.
Debug의 기존 `execution_boundary_cli`도 PASS(42.92초)로 QA writer lock·보호 경계를 재확인했다.
원본 설계 7개 문서 SHA-256은 P0 기록과 모두 같고 `git diff --check`도 통과했다.
Linux/Windows·실제 inventory·store recovery는 이번 테스트 범위가 아니다.

## 후속 실제 파일 inventory와 게시 경로의 선행 결정

`src/intent/inventory.{h,c}`에 읽기 전용 descriptor-relative scanner를 추가했다.
실제 디렉터리와 파일을 읽으며 regular file의 논리 bytes·파일 이름 수·디렉터리 수를
따로 반환한다. pending/orphan·dotfile도 누락하지 않는다. 같은 inode의 hardlink 이름은
각각 계산하는 보수적 원시 inventory이며 CAS 의미적 중복 제거를 수행하지 않는다.
symlink·특수 파일·다른 device·탐색 budget/depth 초과·관측된 변경은 실패하고 output을 보존한다.
depth의 구현 안전 한도는 64이며 호출자가 entry budget을 지정한다. 탐색 budget은
디렉터리까지 포함해 빈 디렉터리에 의한 무제한 탐색도 막는다. 이는 v2 파일 quota의 변경이 아니다.
root는 제외한다. directory listing용 descriptor를 별도로 열어 원본 fd의 탐색 offset을 바꾸지 않는다.
파일 내용을 쓰거나 삭제하지 않지만 OS가 접근 시간을 갱신할 수는 있다.

이 scanner는 root 등록·Git identity·신원·lane·CAS hash·event framing을 검증하지 않는다.
호출자는 신뢰할 수 있는 authority root와 owner lock을 제공해야 한다. 경로/metadata의
검출 가능한 변경은 거부하지만 같은 uid의 적대적 동시 수정에 대한 snapshot 보장은 아니다.
실제 authority·TRAP·Work에는 실행하지 않고 새 임시 fixture에만 실행한다.

### 게시 경로 연결 전 필요한 결정: 최초 비용 귀속

현재 승인된 한도만으로는 shared CAS 및 불확실한 pending의 lane을 재개 시 결정할 수 없다.
lane을 파일명이나 모델 request에서 임의 추정하면 일반 intake가 예약량으로 비용을 옮길 수 있다.
사용자는 **최초 lane 고정·준비 기록 기반 귀속**을 후속 승인했다.
아래는 승인된 의미 계약이며 아직 journal writer에 구현하지 않았다.

1. 새 객체의 비용은 신뢰된 operation 검사로 정한 **최초 게시 lane에 고정**한다.
   이후 다른 lane의 검증된 재사용은 새 객체 비용 0이며 기존 비용을 이동·환급하지 않는다.
   동일 digest의 실제 복사·임시 파일은 추가 점유로 계산한다.
2. 데이터 생성 전에 immutable preparation 기록에 operation/request identity,
   lane, expected head, 생성 예정 객체·peak를 결합한다. 기록 자체도 quota에 포함한다.
   prep 내 lane은 caller의 주장만으로 신뢰하지 않고 authority의 operation 허용 검사를 거친다.
3. 준비 기록과 연결된 pending/orphan은 최초 lane에 계속 청구한다.
   재개 시 귀속이 없는 파일·상충 preparation·검증할 수 없는 항목은 raw inventory에는 포함하되
   임의 lane에 청구하거나 삭제하지 않고 쓰기를 차단하고 근거를 반환한다.
4. preparation 게시 자체의 중단도 처리해야 한다. partial prep는 신뢰된 귀속으로 취급하지 않는다.
   불확실 상태에서 journal 재시도·추정 cleanup·quota 환급을 하지 않는다.
5. 최종 journal 게시 전 같은 authority owner lock에서 inventory와 expected head 및 peak를
   다시 검사한다. quota 성공이 issuer 승인이나 stale/보호 검사 통과를 대신하지 않는다.

이 선택은 영속 회계의 의미를 정한다. 다음 구현은 preparation의 closed schema,
registry·failure windows·lock-held 재검사와 journal publish fixture를 이어서 구현한다.
현재 legacy Work/document journal에 신규 v2 quota를 덧씌우지 않았다.

읽기 전용 inventory 검증(macOS arm64): Debug의 inventory·quota·기존 QA 보호 경계
3/3 PASS, ASan/UBSan inventory 1/1 PASS, Release inventory 1/1 PASS.
결과 XML은 각 build preset의 `intent-inventory.xml`이다. 테스트는 빈 root, 반복 스캔,
pending/orphan 하드링크의 보수적 계산, symlink/FIFO 거부, entry/depth budget,
실패 output 보존을 포함한다. 실제 cross-device fixture·적대적 동시 수정·Linux/Windows는 미검증이다.

후속 [P1 준비 기록과 journal 구현](intent-assurance-p1-journal.ko.md)을 추가했다.
private event writer에서는 준비 기록 검증·불변 게시·재시작 비용 복원·owner lock 아래
게시 직전 quota 재검사를 구현했다. 위의 writer 미구현 표시는 그 이전 단계의 이력이다.
source/baseline 객체 store 전체·D01 실제 host 등록 연결·교차 객체 CAS 재사용과 구별한다.
