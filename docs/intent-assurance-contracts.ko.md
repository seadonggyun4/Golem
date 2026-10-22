# 원문·변경·검토·차단 데이터 계약

상태: **새 versioned 계약의 설계 제안**. [아키텍처](intent-assurance-architecture.ko.md)와 함께 읽는다. 아래 JSON은 synthetic 문서 예시이며 현재 CLI에 입력할 수 있는 schema나 실제 승인·receipt가 아니다. 반복 hex 값은 구문을 보여주기 위한 가짜 digest다.

## 1. 공통 envelope와 한도

신규 권위 객체의 공통 envelope는 `schema`, `project_id`, `work_id`(project-only 객체는 null), `created_by_assertion`, `body`다. `created_by_assertion`은 provenance 식별자이며 필드의 존재나 모델이 적은 값 자체가 인증은 아니다. host는 별도 assertion/이벤트에서 정확한 객체 digest와 issuer·purpose·scope를 대조한다. 서명 bytes를 자신이 서명할 객체 안에 넣어 self-hash를 요구하지 않는다.

| 객체 계열 | 추가 envelope 필드 | 생성 순서·순환 방지 |
| --- | --- | --- |
| Root: source/capture, 최초 source adoption decision, requirement/constraint 정의, baseline manifest | `baseline_digest` 필드 없음. 넣으면 unknown field로 거부 | 최초 source는 baseline 없이 생성한다. requirement/constraint 정의는 source refs를 고정하고 baseline은 그 정의 refs를 열거한다. baseline manifest의 이전 baseline ref는 `body.previous_baseline_digest`에 null 또는 기존 digest로 기록 |
| Baseline-bound: review, issue/question, change proposal, impact, gate 및 activation decision | `baseline_digest`가 필수이며 정확한 기존 baseline digest | baseline이 존재한 뒤 생성한다. root 정의의 현재 적용성은 해당 baseline의 membership과 이 bound 기록을 함께 검사하며 root 정의에 미래 baseline digest를 역기입하지 않음 |

source adoption decision은 채택할 **raw body CAS·범위·목적·project/Work**를 대상으로 발급한다. 최종 source envelope나 아직 없는 baseline을 미리 참조하게 만들지 않는다. capture assertion은 source 객체 생성 후 외부 기록에서 그 digest를 결합할 수 있다. baseline activation decision도 baseline proposal 생성 후 별도로 기록한다. baseline body의 decision refs는 이미 존재하는 adoption/변경 결정만 가리키며 그 baseline을 승인할 미래 activation decision을 포함하지 않는다. 따라서 원문→정의→baseline→review/activation의 참조 순서에 순환이 없다. Root는 자동 승인이나 전역 적용을 뜻하지 않는다. scope와 인증 검증은 그대로 필요하다.

mutable revision 대신 불변 object digest와 append-only event가 head를 이동시킨다. event는 `schema_version`, `sequence`, `previous_event_digest`, `operation_id`, `request_digest`, `expected_generation`, `constraint_epoch`, `type`, `object_digest`를 고정한다. 뒤의 mutation control envelope·result 및 다른 모듈의 record 예시는 이 권위 객체 envelope와 다른 schema다.

digest는 `SHA256(domain || uint64_le(byte_length) || exact_utf8_bytes)`로 제안한다. domain은 schema별 고정 ASCII와 NUL 종결을 포함하고 registry에 버전별 정의한다. signature는 object digest·issuer·purpose·audience를 포함한 별도 고정 envelope에 적용한다. 기존 CAS key는 기존 raw SHA-256 그대로이며 domain digest와 혼동하지 않는다. JSON member 순서가 달라도 같은 객체로 취급하는 정규화는 하지 않는다. 원본 exact bytes를 보관하고 duplicate/unknown field·잘못된 UTF-8·수치 overflow를 거부한다. 기존 json-c compact digest의 뜻을 바꾸지 않는다.

초기 제안 한도: control JSON 256 KiB, project 활성 요구 1024, trace node 4096/edge 16384, 한 node parent 64, unresolved issue 256, review observation 256, source body 16 MiB/객체, source 총 64 MiB/baseline, 한 dispatch manifest 32 MiB. source 원문은 CAS body와 분할 구간 manifest로 보존한다. 초과는 `LIMIT_EXCEEDED`, 누락 없는 명시적 scope 분할이나 새 policy 검토가 필요하다. 조용한 truncation·limit 상향은 금지한다. event retention/rollover는 구현 전 용량 실험과 ADR-D08에서 확정한다.

## 2. 기준 자료·baseline

| 객체 | 필수 identity·필드 | 검증과 권위 |
| --- | --- | --- |
| `golem.intent.source.v1` | body CAS, raw byte length/hash, media/encoding, origin type, capture ref, designation scope, authority assertion | 모델이 만든 user label은 권위 없음. 외부 문서는 인증된 사용자가 지정한 구간·목적에서만 기준 |
| `golem.intent.baseline.v1` | source refs, 이전 baseline, decision refs, requirement refs, constraints, coverage manifest, issuer policy | PROPOSED는 제안. ACTIVE 전 trusted user boundary와 review·unresolved 검사 |
| `golem.intent.requirement.v1` | stable ID, exact text, source spans, modality/quantifier/negative/conditions, acceptance oracle refs, derivation rationale | 사용자 발언의 반전·한정 조건 누락은 reviewer 판단 대상으로 명시 |
| `golem.intent.constraint.v1` | LOCAL/GLOBAL/UNSCOPED, applies_to selectors, source span, affected domains, explicit exclusions | “링크 없음=영향 없음” 금지; GLOBAL/UNSCOPED는 project impact barrier |
| `golem.intent.change.v1` | exact proposed delta, base digest, effect ADD/REMOVE/WEAKEN/STRENGTHEN/CLARIFY, impacted scope proposal | effect 분류도 AI 판단. scope/권한 확장은 인증된 결정 없이는 적용 불가 |

source `origin`은 `TRUSTED_USER_INPUT`, `USER_DESIGNATED_DOCUMENT`, `TOOL_OBSERVATION`, `EXTERNAL_REFERENCE`, `MODEL_DRAFT`를 구분한다. 신뢰된 capture adapter만 첫 유형의 assertion을 발급한다. tool 결과가 “사용자가 변경했다”고 써도 `TOOL_OBSERVATION`이다. designation은 원문 문서 전체 권한 위임이 아니라 명시한 제품 범위 채택이다. 실행 권한은 여기에 포함하지 않는다.

다음은 root 계열 source의 **완전한 객체 shape** 예시다. 원문 bytes·실제 assertion/decision 객체는 포함하지 않은 synthetic 참조이므로 자체로 인증/수락을 통과하는 fixture는 아니다. `baseline_digest`는 이 타입에 요구하지 않는다.

```json
{
  "schema": "golem.intent.source.v1",
  "project_id": "demo",
  "work_id": "work-a",
  "created_by_assertion": "capture-7",
  "body": {
    "body_cas": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "byte_length": 640,
    "media_type": "text/plain",
    "encoding": "UTF-8",
    "origin": "USER_DESIGNATED_DOCUMENT",
    "capture_ref": "capture-7",
    "designation": {
      "scope_id": "checkout-flow",
      "ranges": [{"start": 0, "end": 640}],
      "purpose": "PRODUCT_REQUIREMENT",
      "decision_ref": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    },
    "execution_authority": false
  }
}
```

baseline 상태는 `PROPOSED → UNDER_REVIEW → READY_FOR_USER → ACTIVE → SUPERSEDED`다. `REJECTED`는 재활성화하지 않고 새 proposal을 만든다. READY_FOR_USER는 사용자 승인 아님. activation은 **기준/해결을 기록하는 control 전이**이며 모든 질문이 이미 RESOLVED여야 한다는 전제는 두지 않는다. expected head/generation·issuer·정확한 사용자 결정·coverage/review/oracle-plan 및 §4의 명시적 resolution manifest를 검사한다. 같은 전이에서 해결할 의무와 계속 차단할 의무를 모두 열거하고, post-state에도 미해결 의무의 barrier를 보존한다. ACTIVE는 기준의 채택 상태이지 모든 subject의 실행 가능/PASS가 아니다. dispatch/accepted publish/merge/DONE은 §7의 별도 protected gate를 통과해야 한다. 기존 source·baseline bytes는 보존한다.

## 3. 원문 구간 coverage와 초기 분해 검토

UTF-8 원문의 byte offset은 `[start,end)`다. start/end는 문자 경계, 원본 digest/byte length와 함께 검증한다. UI의 줄 번호는 파생 locator이며 해시 identity를 대체하지 않는다. PDF/이미지는 원본 bytes와 추출기 버전·변환 body digest를 함께 남기고 OCR 미판독 영역을 `UNKNOWN`으로 둔다. 지원하지 않는 형식을 자동으로 완전 텍스트로 간주하지 않는다.

source별 coverage row는 다음 중 하나다: `REQUIREMENT`, `CONSTRAINT`, `CONTEXT`, `EXPLICIT_NON_GOAL`, `NON_NORMATIVE`, `QUESTION_REQUIRED`. 겹치는 의미 연결은 허용하지만 union 구간의 gap/범위 초과를 별도로 계산한다. 공백·표지 같은 비규범 부분도 근거와 검토 ref를 남긴다. 모델이 모든 문장을 NON_NORMATIVE로 분류하는 공격을 막기 위해 baseline approval은 coverage classification 자체의 별도 review와 사용자 가시 요약을 요구한다.

native가 검사하는 것은 구간 유효성·gap·required review·UNKNOWN 잔존이다. 어떤 문장이 제품 요구인지의 정확성을 native가 증명하지 않는다. reviewer는 요구 목록만 보지 않고 **원문 전체/채택 범위**와 분해를 함께 본다. acceptance oracle은 설계자 구현과 독립된 원문 예제·반례·운영 시나리오를 포함하고 사용자/권한 있는 검증자가 검토한다. oracle 자체가 제약을 약화하지 않았는지도 review한다. [S01/S02/S03/S04/S13/B02](intent-assurance-references.ko.md)

검토 예: “로컬에서만 보관하며 클라우드 전송 금지”가 분해 과정에서 “저장 지원”으로 바뀌면 ID가 전부 연결돼도 PASS가 아니다. 원문의 부정·only·수량·조건 구간과 derived requirement의 차이를 `CONSTRAINT_WEAKENING`으로 보고 질문/수정해야 한다. 외부 참고 문서가 전송 허용이라고 주장해도 사용자 기준을 변경하지 못한다.

## 4. 질문·인증된 답변·결정

question은 immutable `question_id`, project/Work, baseline digest, scope revision, exact question bytes/hash, affected subject refs, requested decision kind, nonce, expiry, status를 갖는다. scope revision은 **신규 intent 계약의 revision**이며 기존 document metadata `scope_revision:1`과 다른 필드다.

답변은 trusted user boundary가 `question_id + project_id + work_id + baseline_digest + scope_revision + exact_answer_digest + nonce + audience + issuer + subject + policy_epoch`에 결합해 발급한다. 모델 tool schema에는 human approval 발급 필드를 두지 않는다. issuer key는 모델의 filesystem/IPC 권한에서 분리하거나 assurance가 낮음을 표시하고 정책상 거부한다. 원문 adoption·답변·범위변경·실행승인은 서로 다른 purpose다.

| 전이 | 필수 조건 | 실패 |
| --- | --- | --- |
| OPEN → ANSWER_PENDING_REVIEW | 인증된 답변 assertion, 정확한 질문·scope·nonce 일치 | 위조·다른 Work·stale baseline·expired 답 거부 |
| ANSWER_PENDING_REVIEW → RESOLUTION_READY | 정확한 답변·해석 일치의 resolution review, 영향 평가, 필요한 baseline proposal/권한의 준비 | 실행/PASS 허가는 아님. 일부 답변이면 pending 유지 또는 명시적 잔여 질문 보존 |
| RESOLUTION_READY → RESOLVED | `commit_resolution` 또는 필요한 경우 `resolve_and_activate`의 단일 project journal event에서 명시한 의무 해결 | expected head/증거/사용자 결정 불일치면 전이 전체 거부; barrier 유지 |
| OPEN → SUPERSEDED | 새 질문 ref·교체 이유, 새 barrier 유지 | 질문 삭제로 unblock 금지 |
| RESOLVED → historical | 기준/질문/범위 변경 | 과거 답으로 새 질문 자동 해결 금지 |

동일 assertion의 exact replay는 원래 receipt만 반환한다. 같은 nonce의 다른 답, 다른 operation_id로 같은 assertion 재소비, 다른 Work·scope 재사용은 거부한다. 서로 충돌하는 유효 decision은 단순 latest-wins로 합치지 않고 DISPUTED barrier를 유지하며, 새 결정이 정확한 이전 decision을 supersede하도록 사용자에게 확인한다. 사용자 “진행해”처럼 답의 적용 범위가 불명확하면 구체 질문으로 돌아가며 임의 범위확정을 하지 않는다.

### 답변 접수·해결의 비순환 control 경로

열린 질문이 있어도 source/답변 접수, 제안·resolution review·impact 기록, `RESOLUTION_READY` 준비, 명시적 해결은 진행할 수 있다. 이 control lane은 project 권위 ledger에 자료·판단을 등록할 뿐 product session begin·코드 변경·QA 실행·accepted 산출물 게시·merge·DONE을 허가하지 않는다. 외부 reviewer의 읽기/판단을 받기 위해 product claim의 질문 0 조건을 선행 요구하지 않는다. 별도 실행 효과가 필요한 검토는 그 효과의 승인/격리 정책을 먼저 만족해야 하며 control 명칭으로 product 실행을 우회할 수 없다.

resolution review는 별도 제안 schema `golem.intent.resolution-review.v1`에서 단계 산출물 PASS와 구분해 `resolution_supported:true/false`와 근거를 기록한다. native는 그 판단의 의미적 정답을 증명하지 않고 요구된 reviewer/사용자 결정의 권한·정확한 입력·증거·상태를 검사한다. unresolved가 남아 있는 stage를 PASS로 제출하는 것은 여전히 §5에서 거부한다. `RESOLUTION_READY`는 의미가 자동 확정됐다는 상태가 아니라, 인증된 사용자 답변/결정과 정확한 제안·영향평가가 조합돼 **명시적 control commit을 요청할 준비**가 됐다는 뜻이다.

제안 `golem.intent.resolution-manifest.v1`은 `expected_project_head/generation/epoch`, `current_baseline`, `proposed_baseline|null`, `question_ids`, `exact_answer/decision_refs`, `resolution_review_refs`, `impact_ref`, `close_obligation_ids`, `carry_obligation_refs`, `affected_subject_refs`, `expected_work_heads`, `operation_id/request_digest`를 고정한다. close 집합의 각 의무는 답변이 실제로 다뤘고 권한 있는 해석/변경으로 결정됐다는 검토가 필요하다. 일부 답변·미판별 의미·미결 ADR을 상태 정리 목적으로 닫지 않는다. carry 집합은 현재 의무에서 close를 뺀 나머지 및 새로 생긴 의무를 빠짐없이 포함한다. baseline 변경 시 carry의 원래 질문/답변 provenance는 유지하고 새 baseline에 대한 **적용 mapping**을 명시한다. 옛 답변을 새로운 질문의 답으로 재사용하지 않는다.

`commit_resolution`은 baseline 변경 없이 이 해결·carry·barrier 상태를 기록한다. `resolve_and_activate`는 제안 baseline의 채택 결정까지 준비됐을 때 아래 post-state를 **하나의 versioned project journal event**로 commit한다: 명시한 의무의 해결, 새 baseline head, epoch 증가, carry/영향 barrier, 과거 gate/permit의 stale 상태. validator는 이 prospective post-state를 계산해 close 증거·carry 누락·영향 범위를 검사한다. 해당 close 의무가 **pre-state에서 이미 RESOLVED**일 것을 요구하지 않으므로 `RESOLVED → activation → RESOLVED` 순환이 없다. 이 전이 직후에도 product gate를 새로 검사하기 전까지 실행은 열리지 않는다.

원자성의 범위는 단일 project journal의 검증된 한 event와 그 replay 상태다. CAS object publication은 event 이전에 수행해 orphan 가능성을 보존하며, 개별 Work journal·Git ref·외부 효과·successor Work 생성은 이 event와 원자적이라고 주장하지 않는다. 별도 ledger의 후속 처리가 필요하면 pending binding/barrier를 남기고 receipt 확인 후 별도 전이로 진행한다. append/fsync 결과 불확실 시 reopen·동일 operation lookup 전 재시도하지 않는다. 상충하는 head·stale 사용자 결정·새 의무가 발견되면 manifest 전체를 거부한다. 유효 답변이 없거나 의미가 여전히 불명확한 상태는 계속 차단하는 것이 맞으며, 이 경로는 절차적 deadlock만 제거한다.

## 5. 단계별 의미 검토와 oracle

각 review는 아래 튜플을 고정한다.

`(baseline, source coverage, requirement set, stage, subject refs, artifact digests, code tree/inventory, oracle plan, policy, rubric, reviewer assertion, input delivery manifest)`

대상 stage는 REQUIREMENTS, DESIGN, TASK_DECOMPOSITION, IMPLEMENTATION, TEST_DESIGN, INTEGRATION, FINAL_VALIDATION이다. 모든 stage에서 원문/확정 변경을 직접 참조한다. 직전 산출물만 대조하면 앞 단계의 오류가 그대로 전파되므로 허용하지 않는다. source가 너무 크면 complete chunk manifest를 수신해 단계별 검토 범위를 명시하며 일부만 읽은 review는 해당 범위 이상을 덮지 않는다.

review observation은 `source_spans`, `subject_refs`, `category`, `claim`, `supporting_refs`, `status`, `blocking`, `question_id|null`을 갖는다. category: OMISSION, CONTRADICTION, UNSUPPORTED_ASSUMPTION, SCOPE_ADDITION, REQUIREMENT_INVERSION, CONSTRAINT_WEAKENING, ORACLE_GAP, IMPLEMENTATION_MISMATCH. status: SUPPORTED, DISPUTED, UNKNOWN, RESOLVED. 최종 verdict는 PASS/REVISE/QUESTION_REQUIRED/INCONCLUSIVE다.

**검토 대상 subject와 그 영향 closure에 적용되는 unresolved obligation이 있는 stage PASS는 native가 거부한다.** 다른 범위에만 적용됨이 검토·기록된 질문까지 project 전체 PASS의 전제로 강제하지 않는다. GLOBAL/UNSCOPED 또는 영향 미판별 의무는 그 평가가 끝날 때까지 관련 project 전체 closure에 적용한다. 답변/impact/resolution review의 control 기록은 PASS 선언과 다르며 이런 의무가 열린 상태에서도 §4의 경로로 진행한다. `blocking:false`로 이름만 바꾸는 것은 허용하지 않는다. 필수 요구 해석·미채택 scope·미판별 영향은 정책상 nonblocking으로 downgrade 불가다. 허용된 nonblocking issue도 권한 있는 분류와 근거를 요구한다.

reviewer와 producer의 credential/session/role provenance를 host가 확인한다. 단순 다른 model 이름·별도 대화만으로 독립성을 인증하지 않는다. reviewer는 producer self-assessment를 권위로 받지 않고 baseline·원문·실제 artifact를 읽는다. 같은 모델 계열의 상관 오류, judge position/verbosity bias와 intrinsic self-correction 한계를 명시하고 LLM PASS를 기계적 증명으로 승격하지 않는다. [S03/S04](intent-assurance-references.ko.md)

oracle result는 기존 execution/QA receipt 또는 인증된 사용자 시나리오 검증 assertion에 연결한다. result 종류와 coverage를 구분하고 “사용자 시나리오 검증”을 자동 QA receipt로 변환하지 않는다. 고정 gate가 모두 PASS해도 raw intent 충족을 보장하지 않으므로 두 evidence lane을 completion에서 함께 검사한다.

## 6. 영향 추적과 차단

기존 document DAG는 정확한 문서 revision의 handoff·freshness·Work completion을 소유한다. 신규 task DAG는 분할 task의 선후행·실행 readiness·자원/통합 dependency만 소유한다. task node는 Work·selection·문서 refs를 연결하고 기존 workflow가 요구한 document/QA 상태를 읽어 readiness에 합성한다. task DONE을 따로 작성해 Work DONE을 대체하지 않는다. 신규 trace graph는 원문→요구→설계/task/code/oracle/test 관계를 담지만 문서 freshness reducer를 복제하지 않는다. Task edge의 `ARTIFACT_OBSERVED`, `QA_ACCEPTED`, `INTEGRATION_ACCEPTED` 및 cancel/stale/failed 처리의 정확한 충족조건은 [병렬 계약 §2](intent-assurance-parallel.ko.md)에 정의하며 단순 선행 결과 도착으로 모든 종류의 edge를 열지 않는다.

변경 처리 순서:

1. change proposal을 보존한다. 인증되지 않은 외부 변경은 baseline에 적용하지 않는다.
2. trusted scope change intent가 수락되면 `IMPACT_PENDING`과 dispatch/publish barrier를 먼저 기록한다. 의미가 미확정이어도 보호적 stop은 가능하며 그것이 새 해석 채택은 아니다.
3. local change는 trace reverse edges와 document/task transitive closure를 계산한다. GLOBAL/UNSCOPED는 **모든 활성 task·resource domain·merge item·완료 후보**를 영향평가 대상으로 열거한다. orphan/no-edge도 포함한다.
4. 각 subject에 AFFECTED/UNAFFECTED/UNKNOWN을 기록하고 근거·검토·baseline 버전을 고정한다. UNKNOWN은 관련 실행·publish·merge 차단이다. UNAFFECTED도 모델 선언만으로 면제하지 않고 정책에 맞는 review가 필요하다.
5. baseline activation 시 epoch를 증가시키고 affected review/gate/dispatch permit를 stale 처리한다. 실행 중 job의 결과는 historical로 보존할 수 있지만 publish/merge/current completion에 사용할 수 없다.
6. 문서 개정·새 Work mapping·재검토·재QA 후 새 gate를 발급한다. 이전 결과의 read는 가능하나 권한 갱신은 아니다.

blocked 중 허용: 승인 범위의 읽기 조사, 영향 평가, 질문 초안, 미확정 대안을 나란히 기록한 설계 초안. 금지: 한 대안을 임의로 확정하는 제품 변경·새 dispatch·의존 산출물의 accepted 게시·병합. “되돌릴 수 있다”는 성질은 의미 선택/사용자 승인 권한이 아니다. 현 RUNNING 효과 중지·복구 관측은 기존 승인 및 recovery 계약을 따른다.

## 7. Native gate와 원자적 전이

gate snapshot은 `project generation/baseline/constraint epoch/policy + Work generation/session fence/input digest/runtime binding + subject artifacts + review/oracle refs + open issues + task dependency refs`를 묶는다. read-only `gate_check`는 설명용 snapshot이며 후속 실행 허가가 아니다.

native mutation을 다음 두 계열로 나눈다. 양쪽 모두 closed schema·actor 권한·exact bytes·expected head/version·idempotency·기존 store 무결성을 검사하지만, **모든 mutation에 unresolved 0을 요구하지 않는다.**

| 전이 계열 | unresolved 처리 | 허용 효과 |
| --- | --- | --- |
| Control: source/답변 접수, proposal, review/impact 기록, RESOLUTION_READY, commit_resolution/resolve_and_activate, 명시 recovery 기록 | 열린 의무가 있어도 접수·검토·해결 가능. close/carry·issuer·범위·증거·prospective state를 검사 | 자료·판단·명시 결정과 barrier의 project 상태 기록. product 작업 권한·stage PASS를 암묵 발급하지 않음 |
| Protected: product dispatch/session begin, accepted document/result publish, merge 및 current DONE | 해당 subject에 적용되는 unresolved obligation이 0이어야 함 | 기존 lease/승인·freshness·QA 등도 모두 충족한 product 전이만 |

protected subject `s`의 적용 집합은 (a) `s`가 요구하는 typed input dependency closure, (b) 해당 산출물을 소비하는 declared effect/수용 의무, (c) 새 변경이 영향받는 것으로 판정했거나 UNKNOWN인 document/task reverse closure, (d) GLOBAL/UNSCOPED barrier의 합집합으로 계산한다. 의무가 그 집합에 직접 지정됐거나 그 집합과 영향 범위가 겹치면 적용된다. graph에 연결이 없다는 이유만으로 제외하지 않으며 검토된 UNAFFECTED mapping만 해당 범위를 제외할 수 있다. project 완료의 subject는 모든 필수 deliverable/task/target 수용 closure라서 그 범위의 미해결 의무를 전부 포함한다. 독립적인 다른 local subject의 질문은 무조건 합산하지 않는다.

protected transition은 project guard와 Work lock을 정해진 순서로 얻고 현재 snapshot·적용 집합을 다시 계산한다. 그 집합의 미해결 의무 0, 필요한 source/review/oracle coverage, reviewer/decision issuer 권한, artifact freshness와 typed readiness를 검사한 뒤 intent/event를 commit한다. control 전이의 해결은 §4의 별도 validator를 거친다. stale cache나 미리 받은 gate digest만으로 어느 경로도 통과할 수 없다.

| 보호 지점 | 추가 검사 | 기존 유지 검사 |
| --- | --- | --- |
| session claim/begin·worker start | baseline/epoch와 target task gate | owner·sequence·lease·boot·input·binding |
| 문서/결과 accepted publish | 정확한 task·source·review tuple와 current epoch | document generation·parents·execution receipt |
| merge prepare/verify/publish | 통합 tree·target old OID·epoch·review·QA | repository identity·승인·resource fence |
| completion finalize/current check | current baseline/전체 의무·최종 raw-source review·통합 증거 | 현 source·QA·세션 quiescence·report 계약 |

## 8. 제안 API와 오류

신규 native는 `validate/query/transition`을 분리하고 query는 native store를 쓰지 않는다. MCP read가 private audit를 쓰는 기존 경계는 그대로 표시한다. 모든 변경 MCP는 native 전이를 거친다. Python cache는 완전히 삭제해도 권위를 복원할 수 있는 파생물이며 cache에서 permit·human decision·completion을 만들지 못한다.

| 제안 도구/owner 경로 | 효과·입력 | 승인 경계 |
| --- | --- | --- |
| `golem_intent_inspect`, `trace_read`, `issues_list`, `gate_check` | 등록된 project/Work·bounded cursor; read | D1/D2 disclosure, 임의 path/hash traversal 없음 |
| `golem_intent_propose`, `review_submit`, `impact_submit` | approved_action_id + exact input CAS refs + operation_id | 별도 D4 action·native validator; 제안/검토만 |
| owner-side `decision_attest` | 정확한 question/change bytes·trusted user authentication | 모델 tool로 제공하지 않음 |
| owner-side `baseline_activate`, `enroll` | exact proposal/decision/impact·expected head | owner 권한 + native atomic checks |
| owner-side `commit_resolution`, `resolve_and_activate` | exact resolution manifest·trusted decision·expected project head | §4 control validator와 단일 project event; product dispatch 승인 아님 |
| `golem_task_request`, `merge_request` | 등록 task/change와 승인된 action ID | 실행·merge typed policy 추가, raw shell 없음 |

제안 mutation control envelope의 JSON Schema 예시다. native action body는 승인된 action ref에서 읽고 각 operation의 별도 closed schema로 검증한다. 아래 shape가 generic operation dispatcher를 허용하는 것은 아니다. 기존 D4 schema를 제자리 변경하지 않고 새 tool/profile 버전으로 노출한다. 인증된 actor/decision은 모델 request 필드로 받지 않고 host의 별도 control boundary에서 검증한다.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Proposed intent mutation control envelope",
  "type": "object",
  "additionalProperties": false,
  "required": ["schema", "project_id", "work_id", "approved_action_id", "operation_id", "expected_generation", "expected_epoch", "expected_head"],
  "properties": {
    "schema": {"const": "golem.intent.mutation-request.v1"},
    "project_id": {"type": "string", "minLength": 1, "maxLength": 64, "pattern": "^[A-Za-z0-9_-]+$"},
    "work_id": {"type": "string", "minLength": 1, "maxLength": 64, "pattern": "^[A-Za-z0-9_-]+$"},
    "approved_action_id": {"type": "string", "minLength": 1, "maxLength": 64, "pattern": "^[A-Za-z0-9_-]+$"},
    "operation_id": {"type": "string", "minLength": 1, "maxLength": 63, "pattern": "^[A-Za-z0-9_-]+$"},
    "expected_generation": {"type": "integer", "minimum": 1, "maximum": 65536},
    "expected_epoch": {"type": "integer", "minimum": 1, "maximum": 65536},
    "expected_head": {"type": "string", "pattern": "^[a-f0-9]{64}$"}
  }
}
```

action lookup은 project/Work/tool/purpose/current issuer policy를 함께 묶는다. 같은 operation_id의 다른 bytes는 `REQUEST_CONFLICT`로 거부하며 exact replay receipt도 current gate 재사용 권한이 아니다. API의 error/output ownership·ABI를 고정하기 전 header 구현은 시작하지 않는다.

예시 오류 결과:

```json
{
  "schema": "golem.intent.result.v1",
  "state": "BLOCKED",
  "code": "QUESTION_REQUIRED",
  "operation_id": "begin-task-12",
  "scope": {"project_id": "demo", "work_id": "work-a", "task_id": "task-12"},
  "observed": {"generation": 18, "constraint_epoch": 4},
  "blockers": [{"question_id": "q-9", "reason": "UNRESOLVED_SCOPE"}],
  "native_state_changed": "NO",
  "automatic_retry_allowed": false,
  "next_operation": "READ_QUESTION_AND_REQUEST_TRUSTED_USER_ANSWER"
}
```

| 제안 code | 의미·다음 처리 |
| --- | --- |
| `SOURCE_COVERAGE_GAP`, `ORACLE_GAP` | raw source/oracle coverage 보완·별도 review |
| `QUESTION_REQUIRED`, `IMPACT_UNKNOWN`, `GLOBAL_REVIEW_REQUIRED` | 답변/영향 평가 전 dependent mutation 차단 |
| `DECISION_UNTRUSTED`, `DECISION_SCOPE_MISMATCH`, `DECISION_REPLAY_CONFLICT` | owner issuer/질문/scope 확인; model flag 우회 금지 |
| `REVIEW_NOT_INDEPENDENT`, `PASS_WITH_OPEN_OBLIGATIONS` | 정책에 맞는 새 review; 선언 변경으로 은폐 금지 |
| `BASELINE_STALE`, `GATE_STALE`, `RESOURCE_FENCE_STALE`, `TARGET_MOVED` | current 읽기·새 준비/검증; 옛 token 갱신 금지 |
| `AUTHORITY_CONFLICT`, `UNSUPPORTED_SCHEMA`, `UNSUPPORTED_ASSURANCE` | 지원 runtime/authority 선택·owner ADR 필요 |
| `COMMIT_UNKNOWN`, `RECOVERY_REQUIRED` | 원래 operation lookup·quarantine·명시 reconcile |

기존 native diagnostic code/phase/원본 evidence ref는 덮지 않고 새 domain blocker와 함께 반환한다. 상태 변경이 불확실하면 `native_state_changed:UNKNOWN`, 성공/NO로 추측하지 않는다. state idempotency는 같은 key/bytes의 상태 전이 중복 방지이며 외부 exactly-once 보장이 아니다.

## 9. Completion과 migration ADR

제안 predicate `golem.completion.intent.v1`은 기존 development/role acceptance 평가 결과와 신규 baseline/source/review/oracle/issue/통합 참조를 합성한다. finalize와 current DONE 조회는 [병렬 계약 §9](intent-assurance-parallel.ko.md)의 live target OID·검증 가능한 broker version과 publication/applicability receipt 대조도 요구한다. 이후 target 변경은 역사적 publication 성공을 취소하지 않지만 현재 수락 증거의 적용성을 재검증하게 한다. 기존 v1 receipt를 새 보증으로 승격하지 않는다. summary에는 `semantic_review:REVIEWED_NOT_PROVEN`, 실제 reviewer trust class, user validation 범위, gate 종류, 미검증 항목을 남긴다. DONE은 이 선언된 predicate 범위의 current 수락이며 무결점 보증이 아니다.

**ADR-M01: Work acceptance 변경 방식 — 열린 결정, 권고 A.**

| 대안 | 장점 | 비용·실패 위험 |
| --- | --- | --- |
| A. project baseline은 versioned, acceptance 변경 시 successor Work 생성 | 기존 immutable spec·schema·receipt 보존; old/new 비교 명확 | Work 간 mapping·handoff·새 QA/enrollment 필요 |
| B. 새 Work schema에 acceptance amendment stream 추가 | 같은 Work identity에서 변화 이력 연결 | 모든 replay·workflow·session·completion·구형 writer 차단 수정; 복잡도 큼 |
| C. Python sidecar만 수정 | 초기 구현은 작음 | 직접 native 우회·이중 권위·기존 완료 의미 불일치로 수락 불가 |

A에서 단순 annotation/검토 수정은 acceptance를 바꾸지 않는 새 baseline revision으로 처리할 수 있으나 그 분류는 review와 명시 정책이 필요하다. 요구 추가·제거·완화·범위 변경은 successor Work가 원칙이다. 새 Work에 old docs를 복사해 current QA로 취급하지 않는다. exact immutable 참조는 historical evidence로만 import하고 새 source/baseline에서 재검증한다.

**구형 writer 차단 조건:** A/B 어느 대안도 기존 schema-1/2 Work에 sidecar enrollment만 붙여서는 구형 binary의 직접 쓰기를 차단하지 못한다. 강제 gate를 적용할 successor Work는 구형 reader가 fail closed하는 새 top-level Work schema/contract marker로 생성해야 한다. 기존 Work spec를 제자리 수정하지 않는다. legacy Work의 외부 관측-only 연결은 허용할 수 있으나 강제 gate 완료로 표시하지 않는다. 새 Work schema 번호·read/export compatibility는 ADR-M01에서 함께 확정한다.

migration plan은 old/new Work spec hash, baseline refs, requirement mapping(동일/분할/통합/폐기/신규), 이유·사용자 decision, orphan 목록, quiescence·uncertainty 확인, compatible reader/writer 버전, 신규 enrollment/predicate를 고정한다. owner 검토 후 side-by-side 생성→read verification→명시 handoff→새 claim 순서로 진행한다. 이전 active/COMMIT_UNKNOWN을 지우지 않는다. 중간 실패는 partial로 남기고 old Work를 자동 resume하지 않는다. A/B 선택과 schema 번호는 구현 착수 전 확정해야 한다.
