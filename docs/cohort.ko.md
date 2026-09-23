# ComparisonCohort (29D)

[English](cohort.md)

비사용·부분사용·전체사용을 비교하는 **불변 연구 기록 계층**이다.
실험 실행기나 무작위 배정기, 독립 검수자, 인과 효과 추정기는 아니다.

| 군 | 개발 과정에서 사용하는 기능 |
| --- | --- |
| NON_USE | agent 단독 또는 기존 수동 방식, Golem 실행 통제 없음 |
| PARTIAL_USE | Markdown 템플릿과 수동 증거 정리, Golem 실행 통제 없음 |
| FULL_USE | Golem 문서 그래프·실행 receipt·재진입·완료 조건 검사 |

비사용군 결과를 Golem에 기록하는 것은 측정이며 전체사용 처치가 아니다.
각 사례는 격리된 작업 공간과 agent 세션에서 실행하고 다른 군의 정답을 전달하지 않는다.
실제 격리나 사용 기능을 이 모듈이 독립적으로 입증하지는 않는다.

## 사용법

```sh
golem research cohort create WORK cohort.json cohort-key
golem research cohort observe WORK observation.json observation-key
golem research compare WORK study-id
golem research report WORK RESEARCH_SEQUENCE
```

앞의 두 명령은 schema-1 요청의 `cohort-create`, `cohort-observe`를 감싼다.
`research call/validate`도 사용 가능하다. 비교는 JSON, 개별 기록 보고서는 안전하게
이스케이프한 Markdown을 표준 출력한다. 파일 저장은 승인된 비공개 경로를 사용한다.

## 등록 계약

구조 예시: [등록 요청](../samples/research/cohort-request.json),
[관측 요청](../samples/research/cohort-observe-request.json).
0으로 채운 digest와 ID는 실제 Work CAS/record 참조로 교체해야 한다.

`cohort-create`의 정확한 필드는 `schema_version: 1`, `work_id`, `cohort_id`,
`design`, `protocol_digest`, `task_digest`, `acceptance_digest`, `environment_digest`,
`evaluation_digest`, `members`다. 알 수 없는 필드는 거부한다.

`design`은 `MATCHED_BLOCKS` 또는 `OBSERVATIONAL`이며 무작위 배정을 주장하지 않는다.
members는 3~48개이며 각 항목은 `case_id`, `case_digest`, `arm`, `block_id`만 가진다.
세 군 모두 필요하고 MATCHED_BLOCKS의 각 block에는 군별 한 사례가 있어야 한다.
OBSERVATIONAL은 비균형·시기별 block이 가능하나 인과적 비교로 해석하면 안 된다.

모든 사례를 ResearchCase로 먼저 등록한다. 해당 사례의 attempt·판정·enrollment보다
먼저 전체 명단을 한 번에 고정한다. 같은 Work에서 한 사례는 한 cohort에만 속한다.
등록 후 명단 추가·삭제·군 변경은 불가능하다. 늦게 등록한 연구를 사전 계획처럼
취급하는 모드는 제공하지 않는다. **로컬 journal 순서만 보장**하며 외부 실행 시점,
다른 ID를 이용한 중복 사례, 연구 전체의 선택적 공개는 탐지하지 못한다.

digest는 이 Work CAS에 존재하는 SHA-256 참조다. 각 계약에 다음 정보를 기록한다.

- protocol: 가설, 표본·배정 방법, 분석 계획, 중단·누락 처리, 격리 계획.
- task / acceptance / evaluation: 공통 과제·수용 조건·평가 도구 및 결과 해석 규칙.
- environment: provider/model 버전, 생성 설정, 입력 snapshot, token/비용 budget,
  timebox, operator/session, runner 및 테스트 도구 버전.

내용은 사용자 정의 JSON/Markdown이며 엔진은 바이트 무결성만 검증한다.
과학적 적절성이나 실제 조건 일치를 검증했다고 주장하지 않는다.

## 관측 계약

정확한 필드: `schema_version: 1`, `work_id`, `cohort_id`, `cohort_digest`, `case_id`,
`supersedes`, `status`, `observed_arm`, `environment_digest`, `evidence_digest`, `leakage`.

- supersedes: 최초에는 빈 문자열, 이후에는 해당 사례의 최신 관측 record digest.
- status: PASS / FAIL / SKIPPED / NOT_DONE / UNKNOWN. 각각 공통 평가 통과 선언,
  실패 선언, 의도적 미실행, 미완료, 해석 불가다. 관측이 없으면 NOT_RECORDED다.
- observed_arm: 실제 사용 수준 선언. 최초 배정은 바뀌지 않는다.
- environment_digest: 실제 조건. 계획과 다르면 편차로 집계된다.
- evidence_digest: 평가 출력·근거·누락 사유·정보 누출과 프로토콜 이탈 상세.
- leakage: 알려진 군 간 정보 오염을 선언하는 boolean.

최신 관측을 참조하지 않은 개정은 거부한다. 같은 key와 같은 JSON 요청은 최초
receipt를 반환한다. 관측 PASS는 29B 판정이나 completion을 대체하지 않는다.
개정으로 PASS가 되어도 한 번 선언된 누출·조건 차이·군 변경 이력은 남는다.
편차가 기록되지 않았다고 실제 준수가 검증된 것은 아니다.

## 집계와 경계

원래 배정군별 전체 인원, 관측 인원, 최신 상태별 수, 관측 개정 수, 과거 편차 수를
집계한다. 미관측·중단 사례도 분모와 명단에서 제거하지 않는다. 개별 사례와 원천
record/frame digest, Work head, 결정적 projection digest를 제공한다.
승률 순위·p-value·인과 효과·독립 acceptance 검증은 제공하지 않는다.

29C 측정 집계는 cohort 기록을 제외하지만 전체 Work 경계에는 포함한다.
29B 완료 조건은 변경하지 않는다. 연구 namespace의 256-event/64-KiB 제한과
기존 CAS·lock·권한·same-key retry 규칙을 공유한다. 신규 journal event는 schema 2다.
구형 엔진은 미지원 operation을 무시하지 않고 거부한다. projection digest는
자기 필드를 추가하기 전 compact json-c JSON의 해시이며 JCS가 아니다.

cross-Work join, 무작위 배정, 통계 검정은 범위 밖이다.
[비공개 case bundle](bundle.ko.md)에 선택한 사례의 관측을 포함할 수 있지만
전체 비교군 명단은 내보내지 않는다.
구조·명령·연구 자료는 [영문 계약과 참고문헌](cohort.md#research-basis)을 함께 참고한다.
