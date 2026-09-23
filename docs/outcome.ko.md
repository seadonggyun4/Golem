# OutcomeAdjudication (29B)

[English](outcome.md) · **한국어**

`PASS`라는 문자열이나 오류 0개만으로 작업을 완료하지 않는다. 필수 항목을 먼저
등록하고, 증거가 연결된 관측에 고정된 규칙을 적용하며, 실제 QA와 함께 completion을
검증한다. 기존 current-agent 흐름과 같은 Work CAS/journal을 사용한다.

## 사용 흐름

1. ResearchCase와 development stage-selection을 등록한다.
2. QA 전에 필수 검증 항목을 `outcome-enroll`로 고정한다.
3. 실제 QA를 실행하고 QA Markdown을 등록한다.
4. 관측 항목을 정리해 `adjudicate`로 제출한다.
5. 실패·누락·blocker를 해결하고 새 판정에서 이전 `record_digest`를 `supersedes`로 참조한다.
6. 기존 `completion finalize`와 `completion resume`으로 완료 여부를 확인한다.

```sh
golem research outcome enroll "$WORK" policy.json enrollment-1
golem research outcome adjudicate "$WORK" adjudication.json adjudication-1
golem research status "$WORK"
golem research inspect "$WORK" 3
golem research report "$WORK" 3
```

`3`은 예시 research sequence다. 실제 receipt의 `event.sequence`를 사용한다.
Markdown은 stdout으로 반환하며 자동 공개하지 않는다. JSON envelope는 기존
`research call`과 C API `golem_research_call`도 지원한다. 구조 검증은
`golem research validate REQUEST.json`이며 실제 증거 검증이나 완료를 대신하지 않는다.

## Enrollment

모든 필드는 필수다. 요청 envelope는 `{schema_version:1,operation,key,record}`다.
operation은 `outcome-enroll`이다. [구조 예제](../samples/research/outcome-enroll-request.json)의
0 digest를 실제 ResearchCase receipt의 `record_digest`로 교체한다.

| record 필드 | 계약 |
| --- | --- |
| schema_version | 정수 1 |
| work_id, case_id, case_digest | 같은 Work의 등록된 ResearchCase |
| selection_id | 등록된 development selection ID |
| gate_id | 실제 QA receipt 안에서 확인할 gate ID |
| adjudication_rule | `golem.required-cases.v1`만 지원; 알 수 없는 버전 거부 |
| required_cases | 1–64개 `{id,requirement_id}`; ID 중복 금지; requirement는 selection에 포함 |

case당 enrollment 하나이며 변경·축소·해제하지 않는다. 잘못 등록한 의무는 조용히
삭제하지 않고 새 Work로 옮겨 설계를 바로잡는다. 모든 enrollment는 **Work 전체의
완료 의무**다. 다른 selection ID로 우회할 수 없다. 독립된 pipeline은 Work를 분리한다.
같은 selection ID의 문서 개정은 가능하며 기존 최신성 검사가 계속 적용된다.

기존 Work 호환성을 위해 등록 전에는 기존 completion 규칙이 유지된다. 29B 보호를
사용하려면 enrollment가 필요하다. 등록한 뒤 판정이 없으면 완료를 차단한다.
사후 등록도 허용하지만 이를 사전 등록 실험이라고 주장하지 않는다.

## Adjudication

operation은 `adjudicate`. [요청 템플릿](../samples/research/adjudication-request.json)은
placeholder이므로 실제 receipt와 evidence digest로 치환해야 한다.

| record 필드 | 계약 |
| --- | --- |
| schema_version, work_id, case_id, case_digest | 정수 1과 기존 case 참조 |
| policy_digest | enrollment receipt의 record_digest |
| qa_receipt | 같은 Work에서 실행 엔진이 발급한 QA receipt digest; noop/임의 CAS 불가 |
| supersedes | 최초 빈 문자열, 이후 같은 case의 최신 adjudication record_digest |
| raw_status | 도구가 보고한 원시 상태를 보존하는 1–256 bytes 설명; 판정 권한 없음 |
| rationale | 정규화 근거, 1–4096 bytes |
| observations | 최대 64개 `{id,status,failure_domain,evidence_digest}` |
| open_blockers | 최대 32개 중복 없는 blocker ID |

관측 ID는 required_cases에 있어야 한다. 누락은 `NOT_EXECUTED`로 계산한다.
각 digest는 같은 Work CAS에서 hash 검증한다. 필요 최소 보고서만 evidence API로
저장하고 비밀정보·원시 로그 전체를 무분별하게 복사하지 않는다.

status: `PASS`, `FAIL`, `ERROR`, `SKIPPED`, `NOT_EXECUTED`, `UNKNOWN`.
failure_domain: `NONE`, `PRODUCT`, `HARNESS`, `ENVIRONMENT`, `UNKNOWN`.
PASS는 NONE만 허용하며 다른 상태에는 NONE을 허용하지 않는다. PRODUCT는 FAIL에만
허용한다. 원인 분류 자체는 관측자의 선언이며, Golem이 인과관계를 입증하지 않는다.

## 계산 규칙

| 파생 필드 | 의미 |
| --- | --- |
| normalized_status | 우선순위 FAIL > ERROR > UNKNOWN > NOT_EXECUTED > SKIPPED > PASS |
| required_case_complete | 모든 필수 항목이 PASS 또는 FAIL로 실행 결과를 갖춤; 성공과 다름 |
| completion_eligible | 모든 필수 항목 PASS + QA 전체와 지정 gate PASS + blocker 없음 |
| work_outcome | eligible이면 PASS, 그 외 NOT_DONE; Work DONE을 부여하지 않음 |
| *_count | 관측으로부터 계산; caller가 합계·eligible을 직접 제출하면 거부 |

제품/하네스/환경 count는 해당 domain을 선언한 비통과 항목 수다. 환경 ERROR를
제품 버그로 계산하지 않는다. SKIPPED는 fail_count/error_count가 0이어도 통과가 아니다.
관측 모두 PASS여도 native QA FAIL이면 완료가 불가능하다.

## 완료·복구·호환성

- 최신 판정의 QA digest는 완료 대상 QA 문서의 receipt와 정확히 같아야 한다.
- 문서·source 최신성, 실제 gate/case PASS, 권한·세션·미제출 실행 검사를 대체하지 않는다.
- 완료 receipt에 policy/adjudication digest를 고정하고 완료 Markdown에 표시한다.
- 완료 뒤 blocker나 새 판정이 생기면 현재 상태는 REVALIDATE_COMPLETION이다.
- 옛 receipt의 동일 key 재시도는 역사적 RECORDED 응답이며 새 DONE 주장이 아니다.
- blocker 해소 판정을 추가하면 같은 문서 generation에서도 새 key로 재완료할 수 있다.
- 단순 29A 로그 추가는 완료를 무효화하지 않는다.
- outcome event는 journal schema 2다. replay는 입력과 증거로 assessment를 재계산한다.
  저장된 eligible 변조, 잘못된 supersedes, 누락·변조 CAS는 거부한다.
- 이전 schema-1 기록과 enrollment 없는 completion의 byte-level assessment 계약은 유지한다.
  구형 엔진은 새 outcome event를 해석하지 못하면 fail closed한다.

## 신뢰 경계

v1 source_kind는 `DECLARED_OBSERVATIONS`다. 외부 결과 포맷을 범용 자동 파싱하거나
보고서 prose를 AI로 판정하지 않는다. 관측값과 evidence의 의미 대응은 작성자의 책임이다.
실제 QA receipt 존재와 gate 결과는 엔진이 검증하지만, 첨부한 증거가 주장한 사실을
입증하는지 독립 리뷰까지 수행하는 것은 아니다. `independent_review=false`다.
안전 인증, 무결점 증명, 도구 결과의 진실성 증명으로 사용하지 않는다.

기존 journal의 로컬 신뢰 모델을 따른다. 서명/외부 checkpoint 없는 전체 저장소 재작성·
마지막 suffix 삭제 방어는 별도 문제다. 판정의 읽기 전용 집계는 [29C 지표](metrics.ko.md)를
따른다. 29D–F의 비교군·공개 export는 추가하지 않는다.

## 근거와 설계 해석

- Barr 외 (2015), [The Oracle Problem in Software Testing: A Survey](https://discovery.ucl.ac.uk/id/eprint/1471263/):
  테스트 실행 자동화와 정답 판정 자동화는 별개라는 oracle 문제를 검토했다.
  실행 성공/관측/의미 판정/완료를 분리하고 미확인 항목을 PASS로 추정하지 않는 근거로 삼았다.
  v1의 선언형 정규화는 범용 oracle 문제를 해결한 것이 아니다.
- Smith·Lin (2024), [Using Assurance Cases to Guide Verification and Validation of Research Software](https://arxiv.org/html/2411.03291v1):
  주장과 증거, 요구사항·설계·테스트의 추적, 운영 가정과 리뷰를 분리한다.
  Golem에서는 필수 항목/증거/파생 판정을 구분하는 설계로 적용했다. 독립 리뷰를 구현했다는 뜻은 아니다.
- Jeff Tian, [Software Quality Engineering: Testing, Quality Assurance, and Quantifiable Improvement](https://onlinelibrary.wiley.com/doi/book/10.1002/0471722324):
  공개 소개·목차에서 테스트 외 예방·검증·측정의 구분을 확인했다. 유료 본문 전체를 읽지 않았다.
  실행 여부와 제품 실패, 하네스·환경 제약을 서로 다른 필드로 둔 것은 이를 참고한 설계 결정이다.
- [W3C PROV-CONSTRAINTS](https://www.w3.org/TR/prov-constraints/):
  식별·순서·일관성 제약을 참고해 immutable enrollment와 supersedes chain을 재검증한다.
  이는 PROV 적합성 구현도, provenance만으로 내용의 진실성을 증명한다는 주장도 아니다.

규칙과 상태 우선순위는 위 자료에서 직접 인용한 표준이 아니라 Golem의 보수적 제품 계약이다.
재현 가능한 검증은 `tests/c/outcome_integration.py`의 실제 C QA fixture를 사용한다.
