# Research Metrics (29C)

**한국어** | [English](metrics.md)

검증된 Work journal을 replay한 뒤 읽기 전용 지표를 산출한다. agent가 observation의
`counts`에 적은 수치를 합산하지 않고, 등록된 기록과 29B 파생 판정에서 계산한다.
지표 조회는 완료나 실행 권한을 부여하지 않는다.

29D cohort 기록은 이 측정 집계에서 제외하지만 전체 Work 경계에는 포함한다.
비교군별 관측 집계는 [ComparisonCohort](cohort.ko.md)를 사용한다.

## 사용

```sh
golem research metrics "$WORK"
golem research metrics "$WORK" --case parser-case
golem research metrics "$WORK" --case parser-case --format markdown
```

기본은 JSON, Markdown도 stdout으로 반환한다. 보고서 파일·CAS·journal을 만들지 않는다.
저장할 때는 비공개 경로를 사용한다. 원시 prose를 제외해도 자동 redaction이나 공개
허가가 되는 것은 아니다. 없는 case, 빈 ID, 중복/미지원 옵션·format은 오류다.

C API는 [research.h](../include/golem/research.h)의 `golem_research_metrics`,
`golem_research_metrics_report`다. `case_id=NULL`이면 전체 case다. store와 filter는
호출 동안 빌리고, 성공한 reply는 malloc 소유권을 가지므로 `golem_execution_reply_free`로
해제한다. 실패 시 output은 유지한다. read-only handle을 사용할 수 있으며 handle별로
호출을 직렬화한다. 계산 대상은 해당 handle이 replay한 prefix다.

## 지표 계약

규칙 ID는 `golem.research-metrics.v1`이다. 의미가 바뀌면 규칙 버전을 올려야 한다.
Work와 ResearchCase는 다르다. 하나의 Work에 여러 case를 등록해도 task 수가 늘지 않는다.

| 그룹 | 의미 |
| --- | --- |
| counts | 선택된 고유 research 기록·case·plan·decision·판정 revision 수 |
| linked_plan_attempt_count | 앞선 plan을 정확히 참조한 decision 수 |
| retrospective_attempt_count | 사전 plan 참조 없는 decision 수 |
| unobserved_plan_count | 아직 decision이 없는 plan; 자동 실패 판정은 아님 |
| declared_*_counts | 시도의 classification·actor·next_action 선언별 빈도 |
| latest_*_case_count | case별 최신 판정만 사용; 개정을 성공 case로 중복 집계하지 않음 |
| ineligible_adjudication_revision_count | 계산된 eligibility가 false인 판정 revision 수 |
| pass_but_ineligible_revision_count | normalized PASS지만 eligibility가 false인 revision 수; 실제 완료 호출 거절 횟수와 다름 |
| required_case_coverage | 등록된 필수 검증 의무와 최신 판정 성분 합계 |
| adjudication_recovery | case 내부 부적격 구간과 이후 적격 판정으로 전환된 횟수 |
| declared_attempt_duration | 선언된 ended_at-started_at의 milliseconds 표본 수·합·최소·최대 |
| work_history | case 필터와 무관한 전체 Work의 역사적 완료·재진입 기록 수 |

미판정 enrollment는 `latest_unassessed_enrollment_count`와
`unassessed_required_case_count`에 남는다. PASS나 관측된 복구 episode로 취급하지 않는다.
미등록 case도 UNENROLLED로 남긴다. coverage는 SKIPPED/NOT_EXECUTED/UNKNOWN을 구분한다.
case별 동일 테스트 이름을 합쳐 고유 테스트 수라고 주장하지 않는다. 단위는 등록된 검증 의무다.

히스토그램에 없는 key는 해당 선언을 가진 등록 기록이 0개라는 의미일 뿐 실제 사건이
없었다는 뜻은 아니다. failure domain도 29B의 선언형 관측 한계를 유지한다.
시간 합계는 겹치는 구간을 제거하지 않는다. 전체 작업 소요 시간·청구 시간·생산성이 아니다.
시간 표본이 없으면 min_ms/max_ms는 null이며 임의 observation counts는 집계에 쓰지 않는다.

## 복구 분모

첫 부적격 판정이 episode를 연다. 반복 부적격은 같은 episode에 포함되고, 같은 case의
다음 적격 판정이 한 번 닫는다. 이후 부적격이면 새 episode다. 최초 PASS는 복구가 아니다.

`SKIPPED → SKIPPED → PASS → PASS → FAIL`이면 episode 2, recovered 1, open 1이다.
`rate_numerator=1`, `rate_denominator=2`, `rate_defined=true`로 정확한 분수를 제공한다.
분모 0은 정의되지 않은 값이지 0%나 100%가 아니다. 열린 episode도 분모에 포함하고 별도 표시한다.

이는 기록된 판정의 부적격→적격 전환이지 crash recovery, 제품 결함 수리, 독립 시행,
Golem의 인과적 효과를 입증하지 않는다. 서로 다른 case를 복구 쌍으로 묶지 않는다.
신뢰구간·제품 순위·비교군 효과 추정은 만들지 않는다.

## 미측정 지표

`unavailable`은 `value:null`과 사유를 제공한다.

- 실제 false completion/stale evidence/duplicate execution 차단 횟수:
  실패 호출·동일 key 재시도의 완전한 durable 사실 스트림이 없다.
- 실제 uncertain effect 조정·사람 개입: 기록된 선언은 실제 행동의 독립 증거가 아니다.
- 최초 실패·분류·완료까지 시간: 대응되는 신뢰 가능한 시작/종료 clock 계약이 없다.
- cloud/local 비용 및 unknown_cost_count: research에 연결된 비용과 모집단 계약이 없다.
- 단일 evidence completeness 점수: 초기 7점 제안은 타당성이 검증되지 않았다.
  대신 coverage 성분을 노출한다.
- 현재 task completion: 역사적 replay 지표만으로 평가하지 않는다.

실제 완료는 completion/resume 흐름에서 확인한다. 소스 변경이나 새 blocker 뒤에도 과거
완료 기록은 역사로 남는다. 지표의 `acceptance_verified`, `execution_authorized`는 항상 false다.

## 재현·보존

`boundary`는 전체 Work의 head, event 수, document generation을 고정한다.
`source_records`는 선택된 research sequence와 record/frame digest를 제공한다.
case 필터를 적용해도 전체 head는 같다. 문서 event가 추가되면 research 수치가 같아도
projection digest는 달라질 수 있다.

`projection_digest`는 해당 필드 추가 전, 출력 member 순서의 compact json-c JSON에 대한
SHA-256이다. 서명, JCS 표준, 새 CAS receipt가 아니다. 같은 head·규칙·필터·보존된 증거에서는
같은 JSON/Markdown을 재생성한다. 조회 시각·live source probe·provider·외부 쓰기는 넣지 않는다.

Work open이 기존 CAS와 journal을 검증한 뒤 집계한다. 누락·변조·의미 위조는 거부하고
pending 파일이나 미커밋 CAS orphan은 집계하지 않는다. 외부 checkpoint 없이 유효한 journal
suffix 전체 삭제를 탐지할 수 없는 기존 한계는 유지한다. 과거 prefix 조회 CLI, cohort,
공개 bundle, OTel export는 이번 단계 범위가 아니다.

## 구조·검증

`src/research/metrics.c`는 bounded reducer와 JSON, `metrics_report.c`는 같은 모델의
Markdown을 담당한다. 새 DB·event type·disk schema migration은 없다. 최대 256 research
event 내에서 case를 탐색한다. 최대 case fixture에서도 JSON 256 KiB, Markdown 1 MiB를 지킨다.

`tests/c/metrics_integration.py`와 `outcome_metrics_integration.py`는 분모 0,
최대 크기·시간, 필터·재시도, 변조 거부, 파일 비변경, prose 제외, 최신 revision,
복구 episode, 역사적 완료와 live source 차이를 검증한다.

## 조사 근거

- Fenton·Bieman, *Software Metrics*, 3판의
  [출판사 공개 preview](https://api.pageplace.de/preview/DT0400.9781439838235_A38252996/preview-9781439838235_A38252996.pdf)를 검토했다.
  개체·속성·수치 대응의 구분을 모집단·단위와 검증되지 않은 단일 품질 점수 배제에 적용했다.
  책 전체를 읽었다고 주장하지 않는다.
- [Teaching Software Metrology](https://arxiv.org/html/2406.14494v1)의 재현성과 측정 타당성
  구분을 참고했다. 동일 수치 재생성이 Golem의 효과를 입증하는 것은 아니다.
- Runeson·Höst의 [사례 연구 지침](https://doi.org/10.1007/s10664-008-9102-8)을 참고해
  case 맥락과 일반화 한계를 유지한다.
- Fowler의 [Event Sourcing](https://martinfowler.com/eaaDev/EventSourcing.html)은 기록 기반
  재구성과 외부 작용 분리의 설계 참고다. Golem 평가 논문으로 취급하지 않는다.

정확한 episode 규칙과 JSON 계약은 위 문헌에서 그대로 가져온 표준이 아니라 Golem 설계다.
