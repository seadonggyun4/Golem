# QC owner 초기 설정 host

2026-11-04 설계를 바탕으로 구현한 소스·격리 native fixture와 CI 연결을 다룬다.
실제 client 설치와 업무 기준선 채택·QA 수락·완료는 별도의 검토·검증 대상이며,
이번 CI 연결은 기존 실행 **HOLD**를 해제하지 않는다. 합성 fixture의 검토 진술을
사람의 승인이나 제품 의미 검증으로 재사용하지 않는다.

## 연결 범위

QC6의 `intent_read`는 이미 요구사항 등록을 마친 Work의 제품 scope를 요구한다.
따라서 schema3 Work 생성과 D01 등록만으로 QC를 사용할 수 없다. 설치용 host에
빠져 있던 선행 경로를 owner 전용 로컬 adapter로 연결한다.

| 작업 | 제공 경로 | 효과 |
| --- | --- | --- |
| 기준선·원문 저장 | 기존 `intent_authority.object_store_plan/store_objects` | 정확한 intake proposal 게시; 채택 아님 |
| 검토·활성화 | `intent_bootstrap` → `--bootstrap-fd`, operation=`review` | 기존 `gi_review_host_publish`의 검토·purpose·역할·CAS 검사 후 게시 |
| 등록 상태 관측 | operation=`enrollment-inspect` | native Work spec/head/sequence와 authority head/sequence 관측 |
| 정확한 등록 digest 계산 | operation=`enrollment-digest` | 기존 `gi_product_enrollment_approval`; 승인 발급 아님 |
| Work 요구사항 등록 | operation=`enroll` | 기존 `gi_product_enroll`; 별도 digest와 양쪽 CAS 검사 |

새 MCP 도구·승인 발급·정책 적용·QA runner·완료 endpoint는 추가하지 않는다.
MCP Intent adapter는 이 모듈의 packet schema와 한정된 `enrollment-inspect` 전달만
재사용한다. 모듈이 패키지에 포함되거나 import되는 것과 owner의 `plan/apply`·
review·enroll 변경 경로를 노출하는 것은 다르다. 변경 경로는 기존 MCP host 계약과
별도로 local owner가 검토한 설정만 사용한다.

## 입력과 실행

`python3 tools/intent_bootstrap.py schema`로 닫힌 packet schema를 확인한다.
로컬 config는 repository, registration, git, bridge, packet, review_root,
audit_root, action_id만 받는다. 파일은 owner-private이어야 한다.

```text
정확한 원문·정의·대상·검토 정책 준비
  → 해당 기준선의 native identity 확인
  → 기준선과 일치하는 새 Work의 불변 spec 준비
  → D01 등록 / 기준선 저장의 별도 owner 계획
  → 검토자가 제공한 실제 검토 자료 + 정확한 control
  → intent_bootstrap plan --config CONFIG
  → owner가 plan digest 선택
  → intent_bootstrap apply --config CONFIG
       --reviewed-plan-sha256 DIGEST --approve-local-owner
  → native 결과 기록 확인
  → 별도 QC 조회 / 수락 / 완료 계약
```

adapter는 reviewer/owner evidence, PASS, activation을 자동 작성하지 않는다.
정책·bundle의 원본 파일 bytes와 packet 안 문자열이 같아야 한다. plan에는
adapter·Git·bridge·packet 지문, D01 등록 record, Work 및 review/audit 디렉터리
identity와 action ID가 포함된다. native도 전달된 packet SHA를 검사한다.

Work를 먼저 만들고 다른 대상의 합성 baseline 참조를 나중에 바꾸는 절차는 허용하지
않는다. 초기화 후 spec은 그대로 보존하고, 잘못된 초기화는 별도 역사 기록으로 둔다.
올바른 project/work의 원문→정의→기준선 순으로 참조를 고정한 뒤 새 Work를 준비한다.

## 보호·불확실 결과

- Python은 pin·경로·전달 한도만 검사한다. baseline/review/enrollment 의미는 native가 판단한다.
- D01 shared lock → Work lock → authority lock 순서를 유지한다. review 게시에는 Work를 열지 않는다.
- owner 동의와 검토한 plan digest가 없으면 전달하지 않는다. 같은 action audit 디렉터리가 있으면 재전달하지 않는다.
- 새 출력 디렉터리에 dispatch-intent를 먼저 기록한다. 실패·timeout·postcheck 불일치는
  `COMMIT_UNKNOWN`을 보존한다. 실패라고 단정해 지우거나 재시도하지 않는다.
- native 종료 code 0은 의미적 QA PASS·현재 완료 판정이 아니다. 결과는 `NATIVE_RETURNED`다.
- LOCAL_COOPERATIVE 경계다. 같은 OS 사용자나 CLI flag만으로 사람의 신원을 인증한다고 주장하지 않는다.
- packet/각 출력은 기존 transport LIMIT, native 호출은 30초로 제한한다. 검토 bundle은 기존 native 만료 검사를 유지한다.

## 검증

`tools/test_intent_bootstrap.py`는 별도 임시 Git/authority/Work에서 실제 host를 사용한다.
정상 검토·활성화·native digest·등록, 동의 누락, packet 변경, 만료, 교차 Work,
동일 action 동시 요청, stale CAS, 불확실 결과 보존 및 재호출 거부를 검사한다.
`GOLEM_INTENT_HOST`와 `GOLEM_NATIVE_CLI`로 같은 빌드의 host와 `golem` 경로를
각각 명시한다. 두 실행 파일이 같은 디렉터리에 있을 필요는 없다. host를 선택했는데
CLI를 명시하지 않으면 테스트는 실패하며 임의의 PATH 실행 파일을 대신 사용하지 않는다.

CTest `intent_bootstrap_host`는 두 build target의 정확한 경로를 전달해 7개 host
시나리오를 실행한다. 일반 Python-only 실행에서 host가 없으면 이 7개는 skip이지만,
네이티브 CTest와 MCP contracts CI에서는 실제 실행한다. MCP contracts CI는
`integration_managed_bootstrap`의 별도 8개 시나리오도 함께 실행하며, 두 CTest 이름이
누락되면 `--no-tests=error`로 실패한다. CI의 기존 full 선택 조건은 변경하지 않는다.
fixture 외 기존 Work나 설치 설정은 입력으로 받지 않는다. 테스트에서 만든 진술은
명시적 합성 자료이며 실제 owner/reviewer 증거가 아니다.

## 설치 단계의 읽기 전용 관측

`intent_read`의 owner-pinned `enrollment-inspect` binding은 기존 bootstrap native의
동명 관측만 전달한다. exact packet·D01·Work·review 파일·producer pin을 검사하고,
`action_id`는 빈 값, `action_sha256`·approval은 zero digest, enrollment는 빈 문자열만
허용한다. review/enroll/QA action을 이 경로로 전달할 수 없다.

반환되는 Work spec/head/sequence·definitions digest·authority sequence는 관측값이다.
등록 여부·기준선 활성화·현재 QA PASS·완료를 이 응답의 성공만으로 추론하지 않는다.
제품 QA 조회에 필요한 후속 자료와 단계 검토가 없는 설치 준비 Work도 이 제한된
메타데이터 관측을 할 수 있으며, 기존 제품 gate·QA 수락·완료 조건은 바꾸지 않는다.
review bundle의 native 유효기간은 그대로 적용한다. 만료 시 새 owner 선택 없이는
자동 갱신하거나 다시 호출하지 않는다.

## 공개 schema와 관측 계약 대조

공개 QC schema의 `integration-intent-host` binding에도 `enrollment-inspect`를
명시한다. 중복 binding, 64자 digest 한도, ASCII ID와 경로의 제어문자 거부는
기존 runtime 규칙과 맞춘다. 정상 Unicode 경로와 기존 `action_id` 문자열 규칙은
유지한다. `product-host-packet`의 operation은 늘리지 않으며, 별도 private bootstrap
packet을 공개 제품 packet이나 승인 계약으로 바꾸지 않는다.

원래 golden 324개의 bytes와 기대값을 보존하고, 관측 양성·미지원 enroll·중복 binding·
digest/ID/경로 말단 개행의 6개 구조 사례를 추가했다. `test_intent_schema_golden.py`는
이 구조 판정을 실제 Python runtime과 비교한다. 형식 통과는 owner 선택이나 전달
승인이 아니며, 위의 `INTENT_INSPECTION_ONLY`·정확한 action 검사는 별도로 유지한다.

2026-11-10 격리 확인: 구조 동등성 5개와 기존 Intent 경계 14개, 문맥 collector 6개가
통과했다. 전체 golden 330개는 구조 295개와 native probe 지원 61개를 대조했으며,
문맥이 필요한 native 269개는 `NOT_RUN`으로 남겼다. 따라서 대조 결과는 `PARTIAL`,
`authority_verified=false`이며 전체 native 의미 동등성·현재 QA PASS·완료를 주장하지 않는다.
설치·정책·기존 Work·승인·증거는 이 검증의 변경 대상이 아니다.
