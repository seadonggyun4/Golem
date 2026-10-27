# M0 전수 inventory·정적 출구 검토

상태: **M0 정적 inventory 출구 충족**. 2026-10-26. 실제 Codex/Claude E2E·실제 Work·native 실행: **NOT_RUN**.
이 문서는 개발·정적/fixture 검토 기록이며 설치·권한·producer pin·제품 인증이 아니다.
권위 있는 capability 원본은 `mcp-m0-observations.json`이며 생성 보고서는 원본이나 검토 pin을 자동 갱신하지 않는다.

## 1. 출구 조건과 전수 범위

| 의무 | 근거·현재 결과 |
| --- | --- |
| source 전수·제외 경계 | 고정 tracked 897개 = 생산/계약 source 424개 + 명시 경계 473개. 경로 추가/삭제·미검토 untracked는 차단 |
| source 전체와 선택 함수 구분 | 424개 파일마다 역할·선언·함수/메서드·literal 비교·문법 모델 검토. 선언 symbol 2,212개. 실행 의미의 전수 증명을 뜻하지 않음 |
| 실제 입력 bytes | source/근거/계약 513개. 이 중 build/package 경계 28개는 entrypoint 변경을 숨기지 못하도록 내용도 고정 |
| 공개 API·callback | 48 public header의 직접 API 344개 모두 원장·별도 capability·단일 고정 정의에 연결. public callback 선언 30개도 별도 분류 |
| operation·검토 분류 | 관측 2,107개, capability 1,078개. 원본/재추출 차이·미분류·미검토·미해석·효과 UNVERIFIED 차단 항목 0 |
| 실제 정적 gate | `capability_check --repository-sources`의 selected와 repository blockers 모두 빈 목록, exit 0. 기본 실행도 같은 전수 native 정의 검사 수행 |
| MCP 미제공 분리 | 검토된 facade backlog 312개: M1 120, M3 57, M4 88, M5 47. action은 M2 입력 준비 의존. M6 owner/배포 검토 83개 별도 |
| 지원 제외 | 역사적 Python prototype 등 명시 UNSUPPORTED 분류 17개. 미래 MCP 제공 backlog로 승격하지 않음 |

관측·capability·함수·backlog 수는 서로 다른 분모다. 여러 low-level API를 하나의 typed
facade로 묶을 수 있으며 312개의 독립 MCP tool을 만들겠다는 약속이 아니다. 현재 D2/D4
선언·handler·transport와 목표 경로를 대조했지만 설치된 정책 교집합·실제 client 노출·호출
성공을 확인한 것은 아니다. 그 의무는 실제 E2E/후속 단계에 남는다.

재계산 원본 [JSON](mcp-m0-reconciliation.json)은 파일별 symbol/선언/분기/operation,
제외 이유, 개발 코드 검토, native 정의, 연결 결과, milestone별 backlog를 포함한다.
[생성 표](mcp-m0-repository-scope.md)와 [원장 표](mcp-m0-observations.md)는 표시용이다.
[public projection](mcp-m0-public-observations.json)은 원본의 검토 분류를 보존하는 부분집합이며
별도 repository 완료 판정이 아니다.

## 2. 남은 27 C scope·119 효과의 해소 근거

기존 C scope 27개는 성공적으로 추출한 함수에도 일괄 부여되던 marker였다. 이를 단순
삭제하지 않고 다음 독립 의무로 대체했다.

- CLI 24개 root(기존 events 1개 포함)의 291개 helper 정의와 4,377개 호출 위치·인자·직접/간접 receiver를 고정 모델에 대조한다. 따라서 잔여 CLI 23개가 이 근거로 해소된다.
- native operation 표면 4개는 공개 API·capability와 22개 고정 operation 계약의 실제 API→schema 호출 경로에 연결한다. 49개 경로 node를 대조하며 native 구현 전체의 재귀 실행 분석으로 확대하지 않는다.
- `resume_context`는 resume 1개, receipted execution은 prepare/run/finish 3개, 일반 execution은 verify 포함 4개다. 넓은 호출 집합을 좁은 API에 복사하지 않는다.
- research의 case/attempt/outcome/cohort, execution bundle inspect/verify, work history/record, agent binding attach/inspect, adapter noop 및 Python literal/한정 loop 명령, FFI 3 operation을 별도로 목록화한다.
- 도달한 native API는 고정 public 선언·인자 수·별도 capability·operation 계약으로 종료한다. 내부 helper는 정의·전체 본문/호출 모델·인자 수를 검사하고 임의의 external로 바꾸지 못한다.

사용자가 채택한 public callback 경계는 선언·signature·호출 인자·호출 위치·parameter와
receiver의 타입 binding·별도 capability를 검사한다. 실제 receiver 신원·callback 실행 효과·
정책 충족·실행 성공은 false/미확인으로 남긴다. 30개 callback 선언 중 CLI 그래프에
도달하는 두 member 경계만 명시 지원한다. 두 TRY 정의는 runtime.c의 status와
 daemon_worker.c의 s token 본문만 지원하며 내부 call을 따로 대조한다. 임의 macro 확장은 없다.

사용자는 추가로 private publication guard의 두 고정 값 계약도 채택했다. 별도
`capability_publication` profile은 등록된 `as_commit → dw_record_event_guarded →
event_publish → publish`와 `dw_record_event → event_publish → publish`를 대조한다.
NULL은 unguarded writer 경로만, literal `as_publication_guard`는 guarded 경로만 허용한다.
함수 선언 4개·정의 6개·전달 4개, callback/context 인자·호출 위치·fenced 분기·clock 전달,
CAS 검증 → guard → 실패 시 return → reference publication 순서를 검사한다. guard 대상의
두 고정 호출(as_clock_read/as_live)도 대조하며 실행하지 않는다.

새 내부 capability `internal.publication_guard.fixed_values`는 HOST_INTERNAL 전용이다.
이 profile은 등록된 호출 위치에 한정하며 다른 진입점 `dw_event_write_guarded`와 그
callers까지 인증하지 않는다. 일반 alias/포인터 분석·native 전체 재귀 분석으로 확대하지
않으며 실제 receiver/하위 동작/정책 충족/실행 성공은 계속 false다. 기존 CLI NULL 그래프와
native 공개 계약 종료 경계도 유지한다. 전체 파일의 source/operation 검토는 별도다.

119개 effects UNVERIFIED는 CLI branch·인자·native operation 계약을 검토한 잠재 효과로
대체했다. ledger 효과/target/source-selector 연결을 별도 고정 review와 비교한다. 새
operation·효과 누락·source drift는 차단한다. 효과는 실행 관측이 아니며 group의 효과는
명시된 member operation의 잠재 합집합이다.

추가로 바로잡은 실제 분류 오류는 다음과 같다.

| 발견 | 수정 |
| --- | --- |
| cost enable/plan/report/settle을 조회로 분류 | src/cost/ledger.c의 실제 상태 변경을 근거로 host 내부 변경으로 분류 |
| completion/reentry report를 읽기로 취급 | project=true의 projection 생성·복원 효과를 action으로 유지 |
| native store open/recorder의 부수효과 누락 | writable 인자에 따른 초기화와 named wrapper의 조건부 AUDIT_WRITE를 구분 |
| CLI read의 compact 저장 누락 | stdout/stderr DISCLOSURE와 compact output-store NATIVE_WRITE를 포함. 미래 MCP read는 full output·native read-only 인자 필요 |
| Python command를 helper로 묶거나 export를 read로 취급 | 모든 노출 command에 read/action/owner 또는 역사적 지원 제외를 명시. export/capture/process/network 잠재 효과 분리 |
| package metadata 제외로 entrypoint drift를 숨길 수 있음 | 명시 build/package 경계 28개에 별도 내용 pin/모델을 적용 |
| 함수 cast/control 종료를 indirect call로 오인 | 한정 C cast spelling·control과 실제 pointer/member 호출을 구분. 범용 typedef 추론은 하지 않음 |
| source bytes와 결과 렌더 중 원장이 다를 수 있음 | inventory digest 및 후속 source batch digest를 대조하고 다르면 생성 중단 |

이전 수정의 prototype/local/static/typedef 거부, wrapper forwarding, C branch polarity·인자,
reference digest/명시 locator, D1/D2/D4의 선언→handler/argv/policy 구조 검사는 그대로 유지한다.

## 3. 파일 경계와 증거의 한계

소스 선택은 검토한 고정 상대 경로다. 다른 프로젝트·활성 설정·승인·Work/CAS/journal을
탐색하지 않는다. source reader의 1 MiB/파일, 64 MiB/묶음, 4,096개 한도·no-follow·변경
검사를 유지한다. 원장만 기존 JSON decoder의 16 MiB domain을 사용하는 고정 전용 reader로
읽으며 일반 source 한도는 늘리지 않았다. symlink/hardlink·과대 입력 fixture를 검사한다.

공개 API는 선언·정의·operation 계약, private C 구현은 API에 종속된 내부 역할, Python
helper는 명시 symbol/CLI 문법, binding은 기존 native 3종 facade, historical prototype은
pyproject.toml의 unsupported 설명, tests/samples/fuzz/bench/docs/assets는 각각 검토한
비생산 경계로 분리했다. 새 경로를 파일명 규칙으로 자동 제외하지 않는다. 선언/shape/hash는
정적 모델 drift의 근거이지 함수 동작이나 테스트 충분성의 인증이 아니다.

테스트/doc ref의 null locator는 파일 단위 근거이며 실행·요구사항별 충분성 주장이 아니다.
명시한 selector/anchor가 사라지면 차단한다. 실제 production/native 동작은 승인된 공개 계약
경계에 남으며, 이를 미해석 source marker와 섞어 M0를 영구 차단하지 않는다. 반대로 미지원
동적 구문을 지원 완료로 바꾸지도 않는다. 모든 behavior/receiver/policy/execution flag는 false다.

## 4. 조사 근거 → 결정 → 구현 → 검증

아래의 열람 범위를 구분한다. 유료 학술저서 전체를 읽었다거나 정적 검사기가
일반 C/Python에 대해 sound/complete하다고 주장하지 않는다.

| 설계 문제 | 일차 자료·실제 열람 범위 | 채택·비채택 이유 | 구현·검증 |
| --- | --- | --- | --- |
| tool 발견과 권한 혼동 | [MCP Tools 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/server/tools), 도구 schema·authorization subset·annotation 신뢰 절 | 선언 이름과 실제 client 노출·허가를 분리. spec/SDK migration은 이 M0 수정에서 하지 않음 | backend/transport 관측의 authority·delivery·실행 flag는 false; prefix/slice/guard 변형 시험 |
| 요구·검토·검사 추적 | [NIST SP 800-218](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-218.pdf), PO.4/PW.7/PW.8 관련 본문 | 판정 기준, 발견 이슈, 검사 결과를 별도로 남김. NIST 인증 주장은 비채택 | 원본 ledger·검토 registry·생성 보고서 분리; source/operation/reference 누락 gate |
| parser와 검토·표시의 결합 | [Parnas 1972 대학 제공 본문 재인쇄](https://www.cs.lafayette.edu/~gexia/cs301/resources/parnas.html), 서론·Criteria 절의 본문 발췌 열람. 재인쇄 전체를 전수 검토한 것은 아니며 재인쇄 정확성 보증 없음 | 변하기 쉬운 C 문법·검토 값·판정·renderer를 분리. 매 profile마다 C prototype parser를 복사하는 방식은 비채택 | 공통 C syntax, public/native observer, source-role registry, repository audit 재사용 |
| lexical call을 실행/도달 가능성으로 과장 | [Nielson·Nielson·Hankin, Principles of Program Analysis](https://link.springer.com/book/10.1007/978-3-662-03811-6), 출판사 소개·목차·chapter 소개만 열람. 별도로 저자 [Program Analysis: An Appetizer](https://arxiv.org/pdf/2012.10086) §1.6·§2.1 관련 본문 발췌 열람 | 경로 근사와 실제 실행을 구분. 일반 데이터 흐름/간접 receiver/정책 domination 증명은 비채택 | 한정 predicate/argv/callback 관측, 미지원 구문 차단; behavior/execution flags false |
| 선언·CFG·data-flow의 층위 구분 | [Aho 등 Compilers 출판사 자료](https://www.pearson.com/en-us/subject-catalog/p/Aho-Compilers-Principles-Techniques-and-Tools-2nd-Edition/P200000003472), 소개·목차의 §9/§12만 열람. 교재 본문 전체 미열람 | prototype/직접 edge와 interprocedural 분석을 구분. 범용 compiler나 macro expansion 구현은 비채택 | 직접 선언·정의 signature·긍정 분기 문법; 간접 호출·동적 조건은 의무로 보존 |
| tests 수를 적정성으로 대체 | [Ammann·Offutt 저자 목차](https://www.albany.edu/faculty/offutt/softwaretest/contents.html)와 [저자 자료 목록](https://www.albany.edu/faculty/offutt/softwaretest/), 공개 목차·자료 안내만 열람 | graph/logic/syntax criteria와 oracle·회귀를 구분. 정식 mutation score나 책 전체 검토 주장은 비채택 | guard·branch polarity·인자·receiver·pin·신규 operation을 변형해 기대 거부를 확인; 먼저 실패 재현 |
| provenance를 내용 진실성으로 승격 | [W3C PROV-DM](https://www.w3.org/TR/prov-dm/), abstract·entity/activity/agent 설명 절 | 출처는 평가 근거이지 결과 진실성 자체가 아님. 새 native evidence 형식은 비채택 | 선언/정의 위치·source hash는 관측으로만 기록. 테스트 실행·충분성·현재 완료와 분리 |
| schema 확대·adapter drift | 기존 채택 v1 ledger/decoder와 위 MCP schema 규정 | core/native schema를 바꾸지 않고 내부 분석 결과를 별도 생성. unknown enum/field 허용 완화는 비채택 | 기존 bounded decoder·ID·no-follow reader 사용. 신규 tool 등록·자동 입력 탐색 없음 |

## 5. 재생성·검증

명시한 단일 개발 repository에서 다음 명령을 사용한다. refresh는 검토된 원장/registry를
바꾸지 않고 고정된 개발 JSON/Markdown 8개만 재생성한다. 출력 symlink/hardlink·임의
경로·원장 덮어쓰기는 거부한다. exit 0은 M0 정적 목록 정합성이고 native 성공이 아니다.

```sh
python3 tools/capability_check.py --root "$PWD" --repository-sources --format json
python3 tools/capability_refresh.py --root "$PWD"
python3 -m unittest discover -s tools -p 'test_capability_*.py'
python3 -m unittest discover -s tools -p 'test_integration.py'
python3 -m unittest discover -s tools -p 'test_integration_d2.py'
python3 -m unittest discover -s tools -p 'test_integration_mutations.py'
git diff --check
```

최종 macOS host capability 회귀: **310/310 통과**. 기존 D1 25/25,
D2 15/15, D4 19/19 통과. 실제-source 정적 fixture와 합성 변형 fixture를 구분했다. 신규
callback signature/arity/별도 capability/receiver binding, TRY 변형, API-schema 경로 삭제,
새 함수·operation·효과 누락, build/package drift, 출력 경로 보호의 거부 사례를 포함한다.
검사 전용 명령이 보고하는 test_execution_status는 계속 NOT_RUN_BY_THIS_COMMAND다.
별도 unittest 실행 결과와 혼동하지 않는다. managed sandbox의 Git stderr 거부 시 검사를
약화하지 않고 macOS host에서 실행했다. 실제 E2E·실제 Work·CI·Linux/Windows: NOT_RUN.

## 6. 단계 상태·보존·Git

| 단계 | 현재 상태 |
| --- | --- |
| M0 | 코드·원장·정적/fixture 검증·전수 source/operation 누락 gate 구현. 정적 출구 충족 |
| M1–M6 | 이번 요청에서 기능 확장 미착수. 검토된 미제공 facade와 owner 관리 backlog 유지 |
| M7 | 새 client harness 확장 미착수. 실제 Codex/Claude·실제 Work NOT_RUN |
| M8 | 제품 전체 delivery·CI·플랫폼 최종 수락 미완료. commit/push 미수행 |

원본 Golem producer, 활성 연결/설정/launcher/승인/registry/policy/pin, 기존 증거·CAS·journal·
receipt·문서 revision, QA lock/owner/sequence/binding, TRAP·VM·UACTT는 변경하지 않았다.
추가 복구 계층·Work 재개/실행/마이그레이션·기존 증거 삭제/변조도 없다. 변경 범위는 기존
개발 worktree의 M0 tools/tests/docs이며 README·제품 runtime/CLI에는 변경이 없다.

개발 HEAD 2e69009와 원본 HEAD e583b17을 유지한다. 개발 worktree의 기존 미커밋/미추적
작업을 포함한 상태를 보존했으며 stage/commit/push/reset을 하지 않았다. 원본의 기존
assets/Golem-codex-plugin.png 수정도 그대로다. tracked 변경은 기존 설계 문서 2개이며
M0 개발 파일은 미추적 상태다. 정확한 파일 수는 아래 최종 기록에 남긴다.

최종 기록: capability 310/310, D1 25/25, D2 15/15, D4 19/19 통과. 고정 산출물 8개의
재계산/렌더 결과를 비교하며, 정적 gate exit 0과 테스트 실행 결과를 별도 기록한다.
최종 Git 상태는 tracked 설계 문서 2개 수정·미추적 개발/문서 104개다. 이 수치는 인계받은
기존 미커밋 작업을 포함한다. 제품 소스 변경·stage/commit/push는 없다.

## 7. private guard 추가 채택 반영 — 최신

동일한 두 승인 답변은 하나의 한정 계약으로 반영했다. 새 내부 관측/capability 각 1개를
추가하여 관측 2,107개·capability 1,078개다. 등록된 경로에서 alias, cast, 동적 대상,
다른 context, 순서/조건/실패 return 변경, clock/fenced 변경, 다른 함수 선언, 새 간접
호출, MCP route/effect 확대를 거부하는 독립 변형 fixture를 추가했다. source와 본문/edge
snapshot을 함께 재고정한 fixture에서도 값·조건·순서 위반을 거부한다.

해당 capability는 실제 `PrivatePublication.test_actual_two_value_contract_and_static_limits`
선언을 근거로 연결한다. 새 fixture 한 파일만 `REVIEWED_NEW_SOURCES`에 명시해 기존
bounded reader/evidence 검사로 선택하며 다른 미추적 파일의 읽기를 자동 허용하지 않는다.
입력은 513개, facade backlog 312개·owner 관리 83개·지원 제외 17개이며 권한 확대는 없다.
추가 한정 계약 fixture 15/15와 전체 capability 310/310가 macOS host에서 통과했다.
selected/repository gate는 blocker 0이며 생성물 8개의 재현성을 확인했다. 실제 E2E·native 실행·
commit/push·설치/승인/연결 변경은 수행하지 않는다.

추가 최종 확인: private guard fixture **15/15**, 전체 capability **310/310** 통과.
선언/정의는 parameter 이름(frame/out, log/context) 차이를 제외한 lexical type/callback
선언도 직접 비교한다. typedef/ABI 해결이나 실제 실행 proof는 아니다. 산출물 8개의
재계산 결과가 동일하며 M0 selected/repository blocker 0을 유지한다.
