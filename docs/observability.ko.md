# OTel/PROV 파생 Export

[English / 상세 계약](observability.md) | [비식별화 정책](bundle.ko.md)

29F는 연구 기록을 OTel/PROV로 읽을 수 있게 하는 **읽기 전용 파생 export**입니다.
CAS/journal이 원본이며 export는 완료 판정, 인증된 실행 trace, 공개 허가가 아닙니다.
Collector 연결, 네트워크 전송, SDK 의존성은 추가하지 않습니다.

## 사용법

```sh
golem research observability WORK --case CASE_ID --format otlp --redact samples/research/redaction-minimal.json
golem research observability WORK --case CASE_ID --format prov --redact samples/research/redaction-minimal.json
```

stdout으로 JSON, stderr로 오류를 출력합니다. 저장하려면 `umask 077`, shell의
`set -C`를 사용하고 원본 Work **밖의 비공개 새 경로**로 redirect하세요.
Shell은 실행 전 파일을 열기 때문에 오류 시 빈 파일이 남거나, 잘못 지정하면 원본을
덮어쓸 수 있습니다. CAS/journal로 redirect하면 안 됩니다. 전송은 자동 수행하지 않습니다.

## 매핑 범위

| 항목 | 구현 계약 |
| --- | --- |
| 입력 | 엄격한 replay와 CAS 검증을 거친 29E 구조적 redaction 결과 |
| OTLP | `resourceLogs → scopeLogs → logRecords`, 8개 payload와 manifest의 snapshot 로그 |
| 본문 | 각 redacted 파일을 `body.stringValue`에 그대로 보존, 파일명 attribute로 구분 |
| PROV | 원본 증거 alias → redacted bundle → 파생 projection의 변환 관계 |
| 관계 | `used`, `wasGeneratedBy`, `wasDerivedFrom`; 생성 관계는 파생 entity에만 부여 |
| 정책 | MINIMAL 기본 예제, LINKABLE은 명시적 동의 필요; Work의 export 권한 적용 |
| 한계 | 4 MiB 출력 제한, 직접 inventory만 표현, CAS 재귀 확장 없음 |
| 원본 보호 | journal/CAS 변경 없음, import·completion·QA 판정 변경 없음 |

실행 시각, trace/span ID, actor 인증, 원본 생성 activity는 추측하지 않습니다.
OTLP timestamp 부재는 unknown이며 downstream Collector가 관측 시각을 별도로 처리해야
합니다. PASS/FAIL은 원래 기록의 의미를 유지하고 실제 span 성공·실패로 승격하지 않습니다.
29C 집계도 시계열 counter로 가장하지 않습니다.

PROV-JSON은 W3C **Member Submission**이며 Recommendation 직렬화나 PROV-O JSON-LD로
표기하지 않습니다. 변환 관계는 전체 bundle 수준의 의존성입니다. 문서의 참조를 모두
실제 인과관계로 간주하거나 기록된 주장 자체를 검증했다고 해석하면 안 됩니다.

## 안전성과 재현성

- 매핑 버전은 `golem.observability.v1`; 29E bundle v1 계약은 그대로 유지합니다.
- 원문 ID·문장·경로·시각은 제외합니다. MINIMAL은 원본 hash/size도 제외합니다.
- LINKABLE의 원본 hash와 journal head는 연결 가능성을 높이며 익명화나 서명이 아닙니다.
- 두 형식 모두 `DERIVED_ONLY`, `PRIVATE_REVIEW_REQUIRED`입니다.
- manifest 내용 hash를 namespace로 사용합니다. 같은 redacted 내용은 같은 ID가 될 수
  있으므로 독립적인 실행·사례 수를 세는 ID로 사용하지 마세요.
- C API는 입력을 빌리고 출력 메모리 소유권을 반환합니다. 실패 시 output은 유지되며
  성공한 reply는 `golem_execution_reply_free`로 해제합니다.
- 동일 replay prefix·정책·engine version에서 동일 출력입니다. 다른 사례, orphan CAS,
  전이적 evidence는 포함하지 않습니다. 희귀한 분류 조합도 식별 위험이 남습니다.

테스트는 정책 거부, 손상 원본 거부, byte 보존, 원본 불변, 결정성, PROV 참조 방향을
검증합니다. 별도 개발 환경의 공식 OTLP protobuf 및 `prov` 파서로 parse/roundtrip도
검사할 수 있습니다. 이는 전체 PROV 제약 검증, 익명성 증명, 실제 Collector 배포 검증과
다릅니다. 구현 코드는 C이며 Python 패키지는 선택적 테스트 도구일 뿐입니다.

## 조사 근거

[OTel 로그 모델](https://opentelemetry.io/docs/specs/otel/logs/data-model/)과
[OTLP](https://opentelemetry.io/docs/specs/otlp/)의 시간·wire 계약,
[PROV-DM](https://www.w3.org/TR/prov-dm/)과
[PROV-JSON](https://www.w3.org/submissions/prov-json/)의 entity/activity/derivation을
기준으로 설계했습니다.

[Buneman·Khanna·Tan의 Why and Where (2001)](https://www.pure.ed.ac.uk/ws/files/16509989/Why_and_Where_A_Characterization_of_Data_Provenance.pdf)는
출처 위치와 결과 기여를 구별하는 근거입니다. 이 구현은 해당 논문의 query algebra나
인과 추정 전체를 구현하지 않습니다.
[Moreau·Groth의 Provenance: An Introduction to PROV (2013)](https://www.provbook.org/)는
저자 공개 소개·장별 설명 범위에서 검토했습니다. 전문 전체 분석으로 과장하지 않습니다.
구체적 매핑·검증·제외 범위는 영문 상세 계약에 함께 명시했습니다.
