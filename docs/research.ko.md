# Research records (29A)

[English](research.md) · **한국어**

현재 agent가 Work와 시도별 가설, 개입, 관측, 다음 판단을 구조화해 남기는
선택적 로컬 기능이다. 자동 연구 수집이나 agent의 비공개 사고 과정 수집이 아니다.
현재 지원 범위는 `ResearchCase`, 사전 `AttemptPlan`, `AttemptDecision`과
[OutcomeAdjudication](outcome.ko.md)이다. [ResearchMetrics](metrics.ko.md)는 읽기 전용
replay 집계를 제공한다. [ComparisonCohort](cohort.ko.md)는 비교군 등록·관측·비교를
제공한다. [CaseStudyBundle](bundle.ko.md)은 redaction한 비공개 export를 제공한다.
자동 공개 승인과 OTel export(29F)는 포함하지 않는다.

## Quick start

빌드한 Golem으로 새 Work를 만든다. 아래는 합성 등록 예제이며 제품 QA가 아니다.

```sh
mkdir -p .golem/workspace
WORK="$(cd .golem/workspace && pwd -P)/research-example"
build/dev/golem work start "$WORK" samples/documents/work.json
build/dev/golem research case create "$WORK" samples/research/case.json case-first
build/dev/golem research status "$WORK"
build/dev/golem research inspect "$WORK" 1
build/dev/golem research report "$WORK" 1
```

`inspect`는 원래 JSON receipt, `report`는 읽기 전용 Markdown을 stdout으로
반환한다. Markdown을 파일로 남길 때는 작업의 비공개 출력 경로를 사용한다.
자동 공개·redaction·Markdown 등록은 수행하지 않는다. 재현 가능한 실행 예제는
`tests/c/research_integration.py`에서 사전 계획 → 관측 → 다음 시도까지 확인할 수 있다.

[attempt-request.json](../samples/research/attempt-request.json)은 구조 검증·fuzz용
템플릿이다. 등록하려면 0으로 채운 case/input digest를 실제 같은 Work의 digest로
교체하고 실제 관측 시간을 기입해야 한다. 빈 증거를 성공으로 바꾸면 안 된다.

## Commands and API

| CLI | 역할 |
| --- | --- |
| `research validate REQUEST.json` | 요청의 구조만 검증 |
| `research call WORK REQUEST.json` | JSON 요청 등록 |
| `research case create WORK CASE.json KEY` | case-create 요청 구성 후 등록 |
| `research attempt plan WORK PLAN.json KEY` | 선택적 사전 가설 등록 |
| `research attempt record WORK ATTEMPT.json KEY` | 관측과 판단 등록 |
| `research status WORK` | replay된 기록 목록 |
| `research inspect WORK SEQUENCE` | 원래 불변 receipt |
| `research report WORK SEQUENCE` | 재생성 가능한 escaped Markdown |

요청 envelope는 정확히 `schema_version:1`, `operation`, `key`, `record`를 갖는다.
operation은 `case-create`, `attempt-plan`, `attempt-record`, `outcome-enroll`, `adjudicate` 중 하나다.
KEY는 Work의 research namespace 안에서 유일하다. 같은 key와 같은 parsed JSON은
항상 원래 receipt를 반환한다. 공백·object key 순서는 무관하나 배열 순서는 유의미하다.
같은 key의 다른 내용, 다른 key의 같은 case/attempt identity 재사용은 거부한다.

C API는 [research.h](../include/golem/research.h)에 있다. 기존 Work store를 빌려
사용하며 모든 JSON 입력은 call 동안만 빌린다. 응답은 malloc 소유권을 갖고
`golem_execution_reply_free`로 해제한다. 실패 시 caller output은 변경하지 않는다.
store allocator는 handle을 관리하며 json-c·응답의 malloc까지 대체하지 않는다.
호출은 handle별 직렬화한다. `status/inspect/report`는 read-only handle을 지원한다.

## ResearchCase v1

모든 필드는 필수다. 상세 형태는 [case.json](../samples/research/case.json)을 따른다.

| Field | 계약 |
| --- | --- |
| `schema_version` | integer 1 |
| `work_id`, `case_id`, `project_id` | ASCII ID, 1–64 bytes; Work ID 일치 |
| `case_type` | REAL_SERVICE / BENCHMARK_TASK / FAULT_INJECTION / REGRESSION_CANARY |
| `research_questions` | 1–16개의 `{id, question}`; ID 중복 금지 |
| `unit_of_analysis` | 분석 단위, 1–2048 UTF-8 bytes |
| `context` | product/environment/tool/runner/constraints 각각 1–2048 bytes |
| `privacy_level` | PRIVATE / REDACTED_EXPORTABLE / PUBLIC_SYNTHETIC |
| `pre_registered_plan_digest` | 없으면 빈 문자열, 있으면 같은 Work CAS의 SHA-256 |

privacy와 preregistration은 작성자 선언이다. 공개 허가나 외부 사전 등록 시각을
증명하지 않는다. PRIVATE를 기본으로 사용한다. 원시 비밀정보를 넣지 않는다.
case를 조용히 변경할 수 없으며 새로운 연구 질문/설계는 새 case ID로 등록한다.

## AttemptPlan / AttemptDecision v1

Plan은 아래 공통 11개 필드만 갖는다. Decision은 추가 7개 필드를 갖는다.

| 공통 Field | 계약 |
| --- | --- |
| `schema_version`, `work_id`, `case_id` | v1 및 기존 Work/case |
| `attempt_id` | case 내 유일한 ASCII ID |
| `case_digest` | case 등록 receipt의 record_digest |
| `previous_attempt_digest` | 첫 시도는 빈 문자열, 이후 같은 case의 최신 Decision record_digest |
| `started_at` | 작성자 관측 UTC Unix milliseconds; 0–253402300799999 |
| `actor_kind` | CURRENT_AGENT / HUMAN_OPERATOR / RUNTIME / EXTERNAL_TOOL |
| `hypothesis`, `intervention` | 각 1–4096 bytes; 가설과 계획된 개입을 분리 |
| `input_refs` | 1–32개의 `{role,digest}`; 동일 항목 중복 금지 |

role은 DOCUMENT / SOURCE / CONTEXT / TOOL / CONFIG / EVIDENCE다. digest는
반드시 Work CAS에 있는 자료를 가리킨다. 외부 파일의 hash만 적는 것으로 충분하지
않다. 승인된 최소 자료를 evidence API로 저장하거나 기존 receipt/body digest를 쓴다.
role은 의미 검증이 아닌 분류다. 바이너리나 source 전체를 무조건 복사하지 않는다.

| Decision 추가 Field | 계약 |
| --- | --- |
| `ended_at` | started_at 이상, 같은 milliseconds 범위 |
| `observations` | 최대 32개 `{digest,summary,counts}`; digest 중복 금지 |
| `classification` | 아래 taxonomy 중 하나 |
| `next_action` | 아래 action 중 하나; 실행 명령이 아님 |
| `decision_rule` | 작성자가 사용한 versioned rule ASCII ID |
| `confidence` | LOW / MEDIUM / HIGH, 보정된 통계 확률이 아님 |
| `plan_digest` | 사전 Plan의 record_digest 또는 빈 문자열 |

observation summary는 1–2048 bytes. counts는 최대 16개 `{name,value}`다.
name은 중복 없는 ASCII ID, value는 0–INT64_MAX 정수다. 이 숫자는 제출된 관측값이며
Golem이 raw result에서 계산하거나 검증한 지표가 아니다.

classification: PRODUCT_PASS_OBSERVED, PRODUCT_FAILURE_OBSERVED,
TEST_HARNESS_LIMITATION, ENVIRONMENT_LIMITATION, UNCERTAIN_EXTERNAL_EFFECT,
STALE_EVIDENCE_REJECTED, FALSE_COMPLETION_PREVENTED, DUPLICATE_EXECUTION_PREVENTED,
INSUFFICIENT_EVIDENCE, OPERATOR_ABORTED.

next_action: CONTINUE, REVISE_DOCUMENT, RERUN_ALLOWED, RECONCILE, BLOCKED,
STOP_NOT_DONE, FINALIZE_CANDIDATE.

빈 observations는 INSUFFICIENT_EVIDENCE/OPERATOR_ABORTED에만 허용한다.
UNCERTAIN_EXTERNAL_EFFECT는 RECONCILE/BLOCKED/STOP_NOT_DONE만 허용한다.
FINALIZE_CANDIDATE는 PRODUCT_PASS_OBSERVED 선언에서만 허용되지만 **DONE을
부여하지 않는다**. 의미 판정과 completion blocker는 [29B 별도 계약](outcome.ko.md)이다.

사전 Plan이 있으면 Decision의 공통 필드는 모두 그 Plan과 일치해야 한다.
Plan digest를 생략해 기존 가설을 사후 변경하는 것도 거부한다. 사전 Plan 없이
등록한 Decision은 retrospective 기록이다. Plan의 journal 선행 관계는 확인하지만
실제 외부 행동 이전에 작성했다는 것까지 증명하지 않는다. wall clock은 권위가 아니다.
같은 case의 이전 Decision 참조는 등록 시 최신이어야 하며, 병렬 조사는 별도 case로
분리한다. 낡은 Plan을 임의 수정하지 말고 새 attempt ID로 기록한다.

## Storage, Replay, Recovery

`src/research/model.c`는 bounded schema 검증, `store.c`는 CAS/journal 등록·replay,
`report.c`는 Markdown 파생 보기를 담당한다. 별도 DB·서버 의존성이 없다.

기존 Work의 lifetime flock, no-replace atomic event publish, hash chain을 사용한다.
연구 event는 `schema_version/type/sequence/request`를 갖는 CAS 객체이며 Work journal이
그 digest를 참조한다. sequence는 research ordinal이다. document generation은 증가시키지
않는다. 29A 기록은 기존 문서 CAS 조건·세션·completion을 무효화하지 않는다.
29B enrollment와 adjudication은 문서 generation을 변경하지 않지만 completion을 재검증하게 한다.

매번 Work open에서 schema, ID, 시도 연결, Plan 일치, 모든 참조 CAS를 재검증한다.
누락·변조·알 수 없는 event는 fail closed. 기존 Work는 변경 없이 열 수 있고,
연구 event를 포함한 Work를 예전 엔진으로 열면 unknown event로 거부한다.
등록 요청/compact request 각각 64 KiB, Work당 총 256 research event로 제한한다.
Plan도 한 event를 소비한다. 제한 변경은 별도 호환성 검토가 필요하다.

CAS 저장 후 journal publish 전 중단된 객체는 미커밋 orphan이다. 집계 대상이 아니다.
publish 뒤 응답 손실/메모리 실패는 이미 커밋됐을 수 있다. handle을 닫고 다시 열어
**동일 key**로 재시도한다. 새 key로 재실행하거나 state를 직접 고치지 않는다.
기존 저장소처럼 마지막 suffix 전체 삭제는 외부 checkpoint 없이 탐지할 수 없다.
hash chain은 신뢰할 수 있는 주체의 서명이나 관측 사실의 진실성을 보장하지 않는다.

## Research basis

Runeson·Höst의 [사례 연구 지침 논문](https://doi.org/10.1007/s10664-008-9102-8)은
연구 질문부터 관측과 해석까지의 추적 가능한 근거를 강조한다. 여기서는 질문·분석 단위와
증거 참조를 분리하는 설계로 적용했다. 그 논문이 Golem의 효과를 검증한 것은 아니다.

[Case Study Research in Software Engineering](https://onlinelibrary.wiley.com/doi/book/10.1002/9781118181034)
학술저서의 공개 소개·목차에서 연구 설계, 자료 수집, 분석, 보고의 구분을 확인했다.
유료 본문 전체를 읽었다고 주장하지 않는다. case/attempt/report 경계는 이를 참고한
Golem의 설계 결정이다.

[PROV-DM](https://www.w3.org/TR/prov-dm/)의 Entity/Activity/Agent 구분을 참고해
evidence·attempt·actor를 분리했다. 현재 구현은 PROV serialization/conformance가 아니다.
[사례 연구 보고의 한계 분석](https://arxiv.org/abs/2402.08411)은 맥락·분류·일반화 한계의
명시를 강조한다. REAL_SERVICE 한 사례의 성공을 보편적 성능 향상으로 표시하지 않는다.
