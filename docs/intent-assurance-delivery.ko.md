# 수용 기준·실패 주입·구현 WBS

상태: **미래 구현의 수락 시험 계획**. 이 문서의 행은 실행 결과가 아니며 모두 NOT_RUN이다. [개발계획](intent-assurance-plan.ko.md), [계약](intent-assurance-contracts.ko.md), [병렬/병합](intent-assurance-parallel.ko.md), [배포](intent-assurance-distribution.ko.md)의 동일 ID를 사용한다.

## 1. 시험의 네 층

1. pure model/schema: 잘못된 bytes·version·전이·범위·integer·graph를 결정적으로 검사한다.
2. native store/CLI: 실제 disposable Work/CAS/journal·session/execution/completion과 연결하고 fault 경계를 조사한다.
3. application/MCP: 같은 fixture의 native 결과·권한·disclosure·unknown 의미를 보존하는지 실제 wire로 검사한다. mock만으로 전이 권위를 증명하지 않는다.
4. package/actual host: compiler 없는 clean machine·실제 지원 host의 설치/등록/reload/도구 호출과 승인 경계를 확인한다. local SDK client는 실제 GUI/Hosted 활성화의 대체가 아니다.

AI 의미 검토의 성능 평가는 위 deterministic conformance와 별도다. domain별 원문·확정 변경·참조 해석·오류 삽입·전문가 adjudication corpus를 고정하고 omission/반전/제약 약화/허위 scope 탐지 recall·false-positive·abstention·질문 적절성·해석 변경률을 평가한다. 같은 source/task의 변형은 평가 split을 분리하지 않아 leakage를 막는다. judge 순서·producer/self label을 바꾸고 reviewer 간 불일치를 보존한다. threshold와 표본 수는 구현 전 평가 protocol에서 확정하며 테스트 통과를 사용자 의미 완전 증명으로 발표하지 않는다. [S03/S04](intent-assurance-references.ko.md)

## 2. 수용·실패 주입 행렬

모든 행에서 snapshot 전후 authoritative inventory/hash/mode·event head·실행 횟수·외부 효과·resource reservation·native 진단을 기록한다. `거부`의 oracle은 상태 불변 또는 명시적 보존 intent/unknown이며 단순 비정상 exit만으로 충분하지 않다.

| ID / 요구 | 입력·주입 | 반드시 관측할 결과·evidence |
| --- | --- | --- |
| A01 / R01 | baseline 없는 최초 source 생성, source envelope 필수 필드 누락/금지 baseline 역참조, body 바이트/채택 범위 변경·가짜 user-approved | root 생성의 비순환 shape 검사, 누락/unknown 필드·digest/지정 scope mismatch 거부, 승인 승격 0; 원래 source 보존 |
| A02 / R01 | clarification assertion 위조·다른 question/Work/scope·stale baseline·nonce 재전송/다른 답 | trusted boundary 검증 실패 또는 exact replay 원래 receipt; 새 승인 0 |
| A03 / R02/R03 | requirement ID는 전부 있으나 원문 부정/조건 구간 누락 | source coverage 또는 review/oracle blocker; PASS 불가 |
| A04 / R02 | REQUIREMENTS/DESIGN/TASK/IMPLEMENTATION/TEST 단계에 원문 없이 직전 요약만 제공 | incomplete required input; 모델 소비/검토 완료 허위 표시 0 |
| A05 / R03 | 요구 반전·범위 추가·제약 완화, 전부 NON_NORMATIVE 분류 | 별도 review·사용자 확인·oracle 비교; native는 누락 의무 차단 |
| A06 / R04 | 검토 subject 영향 closure에 적용되는 unresolved 질문/의무와 stage verdict PASS 동시 제출 | `PASS_WITH_OPEN_OBLIGATIONS`; accepted event 0. 해당 범위의 resolution control 기록은 차단하지 않음 |
| A06a / R04 | 질문 OPEN에서 정당한 답변 접수→resolution review/impact→RESOLUTION_READY→명시 해결, baseline 변경 없는 경로와 resolve_and_activate 경로 각각 | control 기록은 접수되고 관련 product begin/publish는 해결 전 계속 차단. close/carry 검증 후 단일 project event로만 해결; 별도 새 gate 전 자동 dispatch 0 |
| A06b / R04 | 부분 답변·상충 답변·stale manifest·새 의무, resolution append/fsync 실패, 무관 local 질문과 미판별 전역 의무 | 임의 해석/의무 소거·partial activation 0. scoped blocker 유지, 불확실시 lookup/reconcile. 무관 control/허용 local 작업은 정책대로 진행하고 GLOBAL/UNKNOWN은 확장 차단 |
| A07 / R04 | local/unknown 질문, 세 typed edge별 증거 대기·QA FAIL·cancel·stale·cycle과 무관 read 동시 요청 | edge별 current evidence 조건 일치; 탐색 관측이 제품 수락 edge를 열지 못함, cycle revision 전체 거부, affected begin/publish 차단 |
| A08 / R05 | trace edge 없는 전역 제약 activation, 이미 RUNNING인 job | 전역 impact barrier·epoch 증가·신규 시작/old 결과 publish/merge 거부 |
| A09 / R06 | model JSON에 approve=true·가짜 human/reviewer label·외부 문서 명령 | closed schema/issuer/purpose 거부; 실행 권한 확대 0 |
| A10 / R06 | producer가 reviewer로 재등록, 별도 model 이름만 변경, issuer 폐기 | independence policy와 current issuer 검증; fallback PASS 0 |
| A11 / R07 | legacy fixture와 새 enrollment의 direct CLI/C/MCP 쓰기 비교 | legacy 의미 보존; 신규 Work는 gate 없는 direct write 거부 |
| A12 / R07 | old schema receipt/report, 새 predicate 미지원 binary·historical QA | 원래 replay bytes 유지; old PASS의 신규 보증 승격 0 |
| A13 / R08 | 두 분할 task rendezvous, distinct Work/tree/build/temp; main dirty | 실제 작업 겹침·독립 tree·main dirty bytes 보존; simulation은 별도 |
| A14 / R08 | candidate A code + B QA/review, best-of-N 결과를 task 합성으로 위장 | exact candidate/group/attempt/tree mismatch; 선택·통합 거부 |
| A15 / R09 | lease 만료·재할당 뒤 old worker의 DB/file/ref write·늦은 완료 | 수신 broker에서 stale fence 거부; historical observation만 보존 |
| A16 / R09 | port/DB/cache 미fenced backend, logical quota만 지원 | strict task 거부 또는 명시적 isolation/직렬 adapter; OS 보증 허위 표시 0 |
| A17 / R10 | QA 뒤 rebase/충돌 해결/한 byte 변경·oracle/executable 변경 | integration snapshot/review/QA stale; 새 tree 검증 필요 |
| A18a / R10 / P5 exit | QA 후 target 이동·target_ref_cas 실패, force/새 key 우회 | 게시전 `TARGET_MOVED`; force path 없음, 새 prepare/검증 없이는 publish 불가 |
| A18b / R10 / P6 exit | COMMITTED 뒤 live target OID/broker version 변경·version 부재 상태에서 completion finalize/current DONE 조회 | `REVALIDATE_TARGET/TARGET_VERSION_UNKNOWN`; 과거 COMMITTED 보존, 정확한 current target applicability 재검증 전 DONE 불가 |
| A18c / R10 / P8 exit | 실제 qualified native/CLI/MCP 경로에서 A18a→게시 성공→A18b→재검증/추가 target 이동을 연결 | 각 경계 동일 거부·historical/current 의미, stale Python cache/patch-id 증거 이전·중복 merge 0 |
| A19 / R10 | patch-id 동일하지만 target tree/index/환경 다름 | receipt 이전 불가; 정확한 integration tree QA만 수용 |
| A20 / R10 | intent 직후/ref 갱신 직후/journal 기록 직전 SIGKILL·I/O 실패 | COMMIT_UNKNOWN/quarantine; exact ref·intent 조사, 중복 merge 0 |
| A21 / R11 | compiler/CMake/Conan/system Python 없는 clean 계정 설치 | self-contained 실행·stdio 연결·synthetic 승인 read; source build fallback 0 |
| A22 / R11 | MCPB/Codex/Claude Code 설치·부분실패·remove·기존 hook/주석 | 비관리 bytes 보존, 실제 host reload·tool 호출 별도 evidence |
| A23 / R12 | signature/dependency 변조·폐기 key·expiry·clock 불확실·wrong platform | install/update 차단; 기존 runtime/Work 보존 |
| A24 / R12 | update freeze 뒤 old client 잔존·active/unknown effect·새 schema 후 downgrade | switch 보류 또는 명시 복구; old writer 효과 0 |
| A25 / R12 | 두 설치 경로·repo alias·copied Work·별도 namespace 자동 생성 시도 | canonical identity/단일 lock·PIN/AUTHORITY 충돌; 경쟁 writer 0 |
| A26 / R12 | stale/tampered Python cache, cache 삭제·cursor mismatch | native 재조회/deny·bounded FULL resync; cache 기반 승인 0 |
| A27 / R12 | disk full/OOM/partial write·output overflow·capacity 한도·missing committed CAS | poison/reopen/lookup·fail closed; truncation 성공/자동 GC 0 |

추가 통합 공격 시나리오: tool 결과에 가짜 사용자 변경을 넣고 → lease를 재할당하고 → old worker 완료를 늦게 전달하고 → target을 이동시키고 → stale Python cache로 admission/publish를 요청한다. 각 경계에서 independently 거부돼야 한다. 최종 승인/새 효과/merge는 0이며 원래 attempt·변경 제안·unknown evidence는 남아야 한다. 한 경계의 거부만으로 나머지 검사를 생략하지 않는다.

## 3. Crash matrix와 불변조건

CAS body 전후, intent fsync 전후, event publication 전후, external dispatch 직전/직후, worker spawn/reap, QA receipt commit, ref CAS, completion receipt/report materialization의 경계를 개별 주입한다. file fsync와 directory fsync 실패·EINTR·short write·cancel/자연 종료 경쟁·clock rollback·boot 변경도 포함한다. 실제 power loss·network filesystem·malicious same-UID는 이 fixture만으로 검증됐다고 하지 않는다.

| 불변조건 | oracle |
| --- | --- |
| active baseline의 사용자 결정 provenance는 모델이 생성할 수 없음 | 모든 ACTIVE event가 유효 issuer/purpose/question/scope에 연결 |
| subject 영향 closure의 unresolved 필수 의무가 있으면 protected publish/merge/DONE 없음. 정당한 답변·review/impact·해결 control은 진행 가능 | scoped gate·control/protected 구분과 prospective close/carry 상태의 모든 bounded reachable state 검사 |
| old epoch/lease/attempt는 새 효과를 게시할 수 없음 | effect receiver의 실제 reject receipt와 authoritative head |
| QA가 검증한 tree와 게시 commit tree가 같음 | exact tree/inventory/environment/QA/review tuple |
| target 이동 후 stale verification으로 ref 변경 불가 | expected old OID 실패와 새 preparation 필요 |
| 불확실 외부 효과는 retry 허가가 아님 | intent당 dispatch 횟수·receiver evidence·reservation 보존 |
| legacy replay·report는 신규 보증으로 재해석되지 않음 | 고정 historical golden bytes·version routing |

bounded state exploration은 순서·fence·cancel·기준변경·merge 경쟁의 작은 모델을 검사한다. fairness/liveness는 자원 가용·eventual settlement·정책 승인·receiver 응답 가정을 명시한다. TLA+/상태 탐색 결과를 C·OS·filesystem 구현의 정형 증명으로 쓰지 않는다. [B04](intent-assurance-references.ko.md)

## 4. 단계별 구현 WBS

기간·인원은 실제 구현 ADR 이후 산정한다. 표는 dependency와 review 가능한 완료물을 정의한다. 각 단계는 기존 contract regression을 그대로 유지하고 이번 문서 작성에는 실행하지 않는다.

| 단계/작업 | 선행 | 변경 경계·산출물 | exit gate |
| --- | --- | --- | --- |
| P0 계약 동결 | 사용자 설계 검토 | ADR-D01–D08·ADR-M01, schema registry, issuer/assurance와 release 지원표 | 열린 보안/의미 정책에 default 승인 없음 |
| P1a source/baseline | P0 | `src/intent/model,baseline,store`; exact bytes·range·journal·reader | A01/A03/A05/A27 pure/native |
| P1b decision/issue/impact | P1a | trusted issuer adapter·question binding·global barrier·비순환 resolution control | A02/A06/A06a/A06b/A07–A10·통합 공격 일부; 열린 질문의 정당한 해결 경로 |
| P2 native gate/enrollment | P1 | 기존 document/workflow/session additive hook, version guard | A11/A12/A15/A26; direct CLI/C도 동일 거부 |
| P3 review/oracle/MCP | P2 | exact stage manifest·review receipt·D2 read/D4 typed action | A04/A09/A10/A26; native/MCP 결과 동등성 |
| P4a task graph | P2 | task-to-Work mapping·derived readiness·impact propagation | cycle/missing/orphan·A07/A08/A14 |
| P4b executor/resource | P4a | existing admission/workspace/worker 조합·세 adapter·receiver fence | A13/A15/A16/A27; 실제 overlap/격리 별도 |
| P5 merge queue | P3/P4 | integration snapshot·QA·review·ref CAS·recovery | A14/A17/A18a/A19/A20; 병합전 CAS·uncertainty 재실행 0. A18b 완료 gate를 선행 요구하지 않음 |
| P6 completion/migration | P5, M01 결정 | 새 predicate/renderer·side-by-side migration·old reader deny·live target applicability | A11/A12/A18b/A24; 병합후 current/historical 구분 |
| P7a runtime package | P0 이후 병행 | hermetic bundle·lock/SBOM/license·launcher·signing | A21/A23/A25/A27 |
| P7b host adapters/update | P3/P7a | MCPB/Codex/Claude Code registration·D1/D5 연결 | A22/A24, 실제 host evidence |
| P8 qualification | 관련 단계 | 문서/지원표·failure recovery runbook·버전별 evidence bundle | A18c 통합 경로 + 전체 필수 행/하위 사례·남은 NOT_VERIFIED 명시 |

순서를 줄이려 generic dispatcher부터 만드는 것은 금지한다. 처음에는 읽기 source/trace view와 순수 schema를 먼저 완성하고, mutation은 native gate 후에 노출한다. P7a packaging은 contract 연구와 병행 가능하지만 검증되지 않은 native 확장 기능을 release manifest에 지원으로 표시하지 않는다.

## 5. 열린 결정과 착수 조건

아래 권고는 사용자 확정이 아니다. 미결 관련 작업은 대안 설계·읽기 준비만 가능하며 dependent 실행 정책을 임의 선택하지 않는다.

| ADR | 결정할 내용 | 권고·착수 차단 범위 |
| --- | --- | --- |
| ADR-D01 | project authority 위치·identity·lock·multi-install enrollment | 명시 등록한 단일 local authority; P1 store/동시 writer 계약 확정 전 동결 |
| ADR-D02 | trusted user boundary·issuer·key custody·local cooperative/strong mode | model과 승인 발급 권한 분리; P1b activation/clarification 전 확정 |
| ADR-D03 | reviewer 독립성·필수 stage·사용자 수용 oracle·분쟁 해소 | 별도 provenance reviewer + 실제 oracle; P3 PASS 정책 전 확정 |
| ADR-D04 | executor별 자원 격리·외부 receiver fence·manual 보증 | 미fenced 자원 strict task 거부; P4b 실제 dispatch 전 확정 |
| ADR-D05 | 최초 OS/arch/libc·embedded Python·native dependency bundling·license | self-contained macOS arm64/Linux x86_64 우선 검토; P7 release 전 확정 |
| ADR-D06 | publisher trust root·서명·expiry·revocation·TUF 적용 범위 | 감사 가능한 신뢰 체계; 무인 download/update 전 확정 |
| ADR-D07 | integration ref·commit/merge 전략·quiescence·rollback·remote push 범위 | 별도 integration ref·정확한 tree QA·conditional ref update; P5 publish 전 확정 |
| ADR-D08 | bounds·retention/rollover·cursor·source 형식/OCR·digest domain registry | bounded fail closed·불명 evidence 보존; P1 schema 동결 전 확정 |
| ADR-M01 | immutable acceptance 유지한 successor Work vs 새 amendable schema | [대안 A 권고](intent-assurance-contracts.ko.md); P2 enrollment/P6 migration 전 확정 |

## 6. 검증 결과 기록 형식

미래 qualification 보고서는 source SHA/dirty diff, runtime/package·dependency hashes, schema/policy/predicate/renderer/adapter versions, OS/arch/filesystem/host version, exact fixture/명령·exit code·stdout/stderr refs·JUnit, before/after authoritative heads, external effect counter, 미검증 범위를 묶는다. test 결과와 사용자 acceptance·실제 provider 정확도·비용·성능을 섞지 않는다.

이번 문서 산출물의 검증은 링크 대상/근거 경로, JSON code fence 구문, 내부 ID 대응, Markdown/Mermaid block 구조, 용어·proposal 표시와 docs-only diff로 제한한다. 제품 build/test 결과를 이 문서에 새로 기재하지 않는다. 실제 Mermaid renderer를 실행하지 못한 경우 문법 구조 확인과 렌더링 검증을 구분해 보고한다.
