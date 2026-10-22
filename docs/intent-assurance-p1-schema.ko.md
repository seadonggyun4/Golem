# Intent Assurance P1 Schema 준비 구현

기록일: 2026-10-22. 기반 HEAD: `f681d74c0eb77622374da7ddd0ec79c861214f59`.
상태: **승인된 D01·D08 일부에 기반한 순수 구조 검증 구현. P1 전체·권위 store·schema 동결 완료 아님.**
[수신 문서와 결정 기록](intent-assurance-p0-review.ko.md),
[제안 계약](intent-assurance-contracts.ko.md), [단계별 계획](intent-assurance-delivery.ko.md)을 구분한다.
수신 원본 7개는 변경하지 않았다. 이 문서는 그 이후 구현 상태다.

## 구현 경계

| 구성 | 구현한 검사 | 의미하지 않는 것 |
| --- | --- | --- |
| [private native schema](../src/intent/schema.h), [구현](../src/intent/schema.c) | borrowed immutable bytes, 성공 시에만 output 변경, 호출별 진단 | 설치된 public ABI·CLI·MCP·새 Work 지원 |
| Source root | 필수·닫힌 key, 타입, origin 구분, `execution_authority:false`, 미래 `baseline_digest` 금지 | adoption·capture·issuer·사용자 승인의 인증 |
| Source bytes | 기존 raw CAS SHA-256·실제 크기 일치, UTF-8 scalar와 byte 경계 | 신규 intent 객체 domain digest·의미적 정확도 |
| 객체 identity | 승인된 domain 규칙·명시 registry·exact JSON bytes | 서명·adoption·형식 전체 검증·gate 수락 |
| 초기 media | `text/plain`, `text/markdown` + 정확한 `UTF-8`; PDF·이미지·기타 media 거부 | OCR·HTML 해석·추출 검증·의미 검토 완료 |
| 구간 | `[start,end)`의 비어 있지 않은 문자 경계·범위, unordered/overlapping 구간 union | 줄 번호·UTF-16 offset·정규화된 문자열로 원본 대체 |
| Coverage | 지정 구간과 row union의 정확한 일치, gap·범위 이탈·분류값 오류 거부 | 분류·근거·reviewer의 진실성 또는 stage PASS |
| 한도 | 승인된 10개 상한 검사; 실제 source set 합산 | complete baseline manifest 검증·영속 graph 구축 |

Source는 빈/잘못된 참조·unknown field·중복 key·NUL 포함 control 문자열·잘못된 JSON과
짝이 없는 surrogate escape를 거부한다. json-c가 surrogate를 대체 문자로 바꾸는 사례는
실패 fixture로 먼저 재현한 후 intent 입력 경계에서 차단했다. 공통 parser는 변경하지 않았다.
BOM·CRLF·결합 문자·raw NUL은 유효한 UTF-8 원문 bytes에서 제거하거나 재작성하지 않는다.
원본 내용을 정규화하지 않고 해시·크기를 직접 비교한다.

Coverage 성공 결과에도 `classification_review_required:true`가 남는다.
전체 NON_NORMATIVE, CONTEXT 또는 QUESTION_REQUIRED로 덮었다는 이유로 의미 수락하지 않는다.
QUESTION_REQUIRED 존재는 별도 `has_questions`로 반환한다. 이 결과는 의무 상태 reducer가 아니다.
Coverage 함수 자체는 source 객체의 digest·신원·rationale·review ref를 검증하지 않는다.
향후 caller가 동일한 immutable source bytes·membership·정확한 review 입력을 결합해야 한다.

Control JSON 256 KiB, source 16 MiB/객체·64 MiB/집합, 요구 1024,
trace 4096 node·16384 edge·64 parent, 미해결 의무·review observation 각 256,
dispatch manifest 32 MiB를 초과하면 거부한다. 자동 상향·truncation·GC는 없다.
Source set은 제공된 항목을 각각 합산하며 중복 body를 공짜로 계산하지 않는다.
목록의 완전성이나 baseline의 권한·membership을 증명하지 않는다.
구간 scratch 크기는 control-byte ceiling으로 제한하며 journal retention 정책을 만들지 않는다.

[독립 JSON Schema 초안](../samples/intent/source.schema.json)은 위 source shape를 표현한다.
바이트 길이·정확한 body hash·문자 경계·관계식은 native의 추가 검사다.
JSON Schema의 수학적 integer와 달리 native wire grammar는 `3.0`을 정수 token으로 받지 않는다.
`decision_ref`의 hex shape가 유효해도 객체 존재·digest domain·issuer·scope는 미검증이다.
형식명이 v1이라는 이유로 production schema 지원표에 등록하거나 기존 CLI에 수락시키지 않았다.

### 후속 승인된 domain identity

사용자가 본 구현 중 ADR-D08의 명시 registry·domain 분리안을 추가 채택했다.
`gi_domain_digest`는 현재 `golem.intent.source.v1` 하나만 등록하며 다음 bytes를 해시한다.

`SHA256(schema 이름의 ASCII bytes + NUL || uint64_le(원본 JSON byte 길이) || 원본 UTF-8 JSON bytes)`

Registry에 없는 baseline/v2/임의 schema는 거부한다. 후속 schema를 자동 등록하거나
prefix로 수락하지 않는다. JSON member 순서·공백·escape를 정규화하지 않으며
원문 source body의 raw CAS SHA-256과 신규 객체 domain digest는 다르다.
Domain digest를 legacy CAS key로 직접 사용하는 store를 만들지 않았다.
`gi_domain_digest`는 JSON/scalar·registry 검사와 byte identity 계산만 하므로
필수 body가 없는 최소 JSON도 identity를 계산할 수 있다. 이는 schema 수락이 아니다.
`gi_source_identity`는 source shape·실제 body 검증을 선행하는 별도 편의 경로다.
둘 다 인증·의미 판단·저널 게시를 하지 않고 실패 시 output은 유지한다.

## 보존한 계약과 미결 사항

- D01의 단일 local authority 방향은 유지한다. 실제 root 등록·생성·pin·enrollment·owner lock은
  이번 구현 범위가 아니다. fallback authority나 프로젝트 내부의 경쟁 store를 만들지 않았다.
- 기존 Work writer lock·QA 실행·owner/binding/sequence·보호 파일·기존 hash/receipt 계약은 바꾸지 않았다.
  현재 QA가 긴 실행 동안 Work writer lock을 유지하는 동작을 회귀 테스트로 고정했다.
- D08의 domain 규칙은 후속 승인에 따라 위 primitive와 source registry로 구현했다.
  event retention/rollover는 **계속 미결**이다. baseline journal·append/replay·retention·activation은
  구현하지 않았으며 source 등록을 다른 schema의 자동 지원으로 확대하지 않았다.
- D02 이후 issuer/review/dispatch/release/publish/migration 정책을 대신 정하지 않는다.
  baseline·bound review 전체 schema, trusted adoption/activation, project store와 gate는 후속 작업이다.
- 기존 core/CAS/journal/receipt/등록 revision, TRAP·Daybreak·실제 Work·client 설정을 변경하지 않는다.
  테스트가 만드는 임시 Work/Git fixture는 제품 Work와 별개다.

## 회귀와 재실행

[Native fixture](../tests/c/test_intent_schema.c)는 10개 상한의 직전/정확한 상한/초과/SIZE_MAX,
실제 16/64 MiB 경계, UTF-8·문자 경계·원문 보존·실패 시 output 보존을 검사한다.
Coverage 모델은 독립 bit-set oracle과 **10,000개** 지정·coverage 조합을 비교한다.
[구조 conformance](../tests/c/intent_schema_conformance.py)는 정상·오류 shape 104건과
native wire/content 추가 거부 8건을 검사한다. 독립 validator는 CI와 같은 `jsonschema==4.23.0`이며
제품 runtime 의존성이 아니다. 표준 CTest는 이 dependency 없이 native 검사만 실행한다.
Domain identity는 별도 고정 known-answer와 Python hashlib의 독립 preimage oracle로
byte 길이·little-endian·NUL separator·Unicode·member 순서·공백·control 상한을 검사한다.

[QA 경계 회귀](../tests/c/execution_boundary_integration.py)는 실제 승인된 임시 QA가 대기하는 동안
다른 descriptor의 exclusive/shared lock 획득이 모두 거부되고, 실행 종료 후 획득됨을 검사한다.
기존 script 변경·보호 파일 변경·gate 사이 mutation 차단 테스트도 유지한다.

```sh
cmake --build --preset dev --parallel 2
ctest --preset dev -R '^(intent_schema_.*|execution_api|json_contract|evidence_digest|session_binding_api|agent_session_api|document_api|execution_change_cli|execution_boundary_cli)$' --output-on-failure --output-junit intent-p1-regressions.xml
cmake --build --preset asan --parallel 2
ctest --preset asan -R '^(intent_schema_.*|execution_api|json_contract|evidence_digest|session_binding_api|agent_session_api|document_api|execution_change_cli|execution_boundary_cli)$' --output-on-failure --output-junit intent-p1-regressions.xml
cmake --build --preset release --target golem_test_intent_schema golem_intent_schema_helper --parallel 2
ctest --preset release -R '^intent_schema_' --output-on-failure --output-junit intent-schema.xml
python3 tests/c/intent_schema_conformance.py --schema --native build/dev/tests/c/golem_intent_schema_helper
```

실제 결과는 아래 검증 기록에 한정한다. A01–A27 전체 수용·사용자 의미 충족·실제 authority
동시성·crash recovery 검증 완료로 확대하지 않는다. 새로운 기능의 원격 CI는 관찰하지 않았다.

## 검증 기록

실제 검증 플랫폼은 macOS arm64다. 전체 제품 suite가 아닌 위에 명시한 집중 회귀다.

| 검사 | 결과 |
| --- | --- |
| Debug 집중 회귀 | domain 포함 16/16 PASS, `build/dev/intent-p1-regressions.xml` |
| ASan/UBSan 집중 회귀 | domain 포함 16/16 PASS, `build/asan/intent-p1-regressions.xml` |
| Release schema | domain 포함 8/8 PASS, `build/release/intent-schema.xml` |
| 독립 Draft 2020-12 + native conformance | shape 104건 일치, 추가 native 거부 8건 |
| 독립 domain preimage | Python hashlib oracle 11개 vector 일치 |
| Coverage 작은 모델 | 10,000개 조합 일치; native/OS 전체 정형 증명이 아님 |
| 원본 7개 문서 | P0에 기록한 SHA-256과 모두 일치 |
| 기존 보호 코드 diff | document registry·execution·agent session·document public header 변경 없음 |

`jsonschema==4.23.0`은 임시 가상환경에만 설치했다. 전역 Python·client 설정은 변경하지 않았다.
독립 schema 검사는 기존 observation workflow에 추가했지만 push·원격 CI 관찰은 하지 않았다.
Linux·Windows 실행, 실제 project authority 동시 writer·journal crash 복구,
trusted issuer·activation·완전한 baseline schema는 이번 검증 대상이 아니다.
결과 XML은 로컬 build 산출물이며 별도의 release 증명·서명 receipt가 아니다.

event retention/rollover는 계속 보류한다. 다음 store 구현 전에는 bounded journal의 용량 실험과
일반 intake/해결 control/복구 여유·한도 도달 후 처리·보존 정책을 제안하고 별도로 결정해야 한다.
여기에 임의 event 수나 자동 rollover 기본값을 넣지 않았다.

후속 [journal 용량 실험과 D08 정책 제안](intent-assurance-journal-capacity.ko.md)을
추가했다. 측정된 합성 파일 배치 비용과 미승인 정책 후보를 구분하며,
production retention/rollover·store 구현은 여전히 미결이다.

후속 사용자 결정으로 **무삭제·한도 거부·초기 rollover 제외** 방향을 채택했다.
위의 retention/rollover 보류 표시는 이 결정 이전의 상태다. 예약량과 총 quota 수치·회계 상세,
baseline/store 구현은 여전히 미결이며 이전 비교용 숫자를 기본값으로 채택하지 않았다.
기존 QA writer lock·보호 검사·증거 및 원본 설계 문서는 변경하지 않는다.

전체 관리 파일의 논리 bytes·파일 엔트리 수까지 포함한 다중 한도와 해결·복구 예약 회계
방향도 후속 승인되었다. 수치 v2는 용량 문서의 미승인 제안이며 native 기본값은 추가하지 않았다.

이후 사용자 승인으로 v2 수치도 확정했다. private `quota.h`/`quota.c`와
`intent_quota` CTest를 추가했다. 이는 순수 회계 projection이며 inventory·journal 게시·
실제 authority quota enforcement·lane 권한·CAS 재사용 확인은 구현하지 않는다.
기존 core의 lock/보호 계약은 그대로다. 승인 및 경계는 journal 용량 문서를 따른다.

후속 `inventory.h`/`inventory.c`는 실제 디렉터리의 읽기 전용 원시 점유량을 계산한다.
lane 귀속·CAS 중복 검증·authority 등록·journal 게시 quota 연결은 아직 없다.
shared CAS 최초 비용과 pending 귀속의 승인 필요 사항을 journal 용량 문서에 분리했다.

그 귀속 계약이 승인된 뒤 [private journal](intent-assurance-p1-journal.ko.md)을 구현했다.
domain registry는 현재 source.v1과 quota-preparation.v1 두 이름을 명시 지원한다.
이 문서 앞부분의 source만 등록·writer 미구현 설명은 해당 단계의 이력이다.
새 준비 기록 registry를 baseline·review 등의 자동 지원으로 확대하지 않는다.
