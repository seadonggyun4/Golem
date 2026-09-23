# CaseStudyBundle (29E)

[English](bundle.md)

하나의 ResearchCase를 **비공개 검토용 파생 bundle**로 내보낸다.
원본 문서·코드·로그는 복사하지 않고 허용된 구조 필드만 추출한다.
네트워크 공개, provider 실행, 완료 승인, 원본 Work 변경은 하지 않는다.

## 실행

```sh
golem research export WORK --case CASE_ID --output NEW_DIR --redact samples/research/redaction-minimal.json
golem research bundle-verify NEW_DIR
golem research bundle-verify NEW_DIR --expect-manifest MANIFEST_SHA256
```

마지막 명령에는 export가 반환한 `manifest_sha256`을 별도로 신뢰할 수 있게
보관한 뒤 전달한다. 출력 상위 경로는 존재해야 하고 출력 디렉터리는 새 경로여야 한다.
버전 관리 저장소 밖 비공개 경로를 사용하고 별도 공개 검토 없이 bundle을 커밋하지 않는다.
원본 Work 내부, 기존 경로, symlink 및 `..` 경로는 거부한다.
디렉터리 0700, 파일 0600이며 Work의 DENY/ASK_ALWAYS를 우회하지 않는다.

검증·redaction을 먼저 끝내고 저장한다. 파일은 덮어쓰지 않으며 fsync 후
manifest를 마지막에 게시한다. 중단 시 비공개 미완성 디렉터리가 남을 수 있다.
자동 삭제·복구·덮어쓰기하지 않으며 새 경로로 재시도한다. 마지막 게시 직후 I/O
오류가 발생했다면 verifier로 상태를 확인한다. 원본 journal/CAS는 수정하지 않는다.

## 포함 파일

| 파일 | 내용 |
| --- | --- |
| research-case.json | case 별칭·유형·문맥 생략 표시·증거 참조 |
| attempt-decisions.jsonl | plan/decision, 로컬 attempt 별칭, 통제된 분류 |
| outcome-adjudications.jsonl | enrollment 및 모든 과거 판정 개정 |
| cohort-observations.jsonl | 선택한 사례의 비교군 관측만 포함 |
| metrics.json | 29C의 사례 집계·coverage·복구·미측정 항목 |
| evidence-inventory.json | 검증한 원천 객체 목록과 명시적인 원문 제외 |
| redaction-policy.md | 적용 정책과 연결 가능성 경고 |
| narrative.md | 생성된 검토 안내·범위, 사람이 쓴 해석 아님 |
| manifest.json | 포맷·버전·정책·비공개 상태·payload 해시 |
| checksums.sha256 | payload 8개와 manifest 해시, 자기 자신 제외 |

자료가 없는 JSONL은 빈 파일이다. 누락·추가 파일, 변조, symlink, 크기 불일치를
거부한다. 파일명은 고정이며 입력 문자열로 경로를 만들지 않는다.

## Redaction 정책

```json
{"schema_version":1,"profile":"MINIMAL","acknowledge_linkability":false}
```

- MINIMAL: 원본 ID·경로·자유 서술·질문·가설·개입·근거·임의 count·raw status·시간·
  원본 digest/크기를 제외한다. 로컬 별칭, 분류값, 관측 수와 연결 구조는 남긴다.
- LINKABLE: 동일하게 제외하되 원천 SHA-256/크기와 Work head는 남긴다.
  `acknowledge_linkability: true`가 필수다. 해시는 추측·연결 공격에 사용될 수 있다.

알 수 없는 필드·버전·profile과 모순된 acknowledgement는 거부한다.
원문 export 우회 옵션은 없다. 모든 결과는 PRIVATE_REVIEW_REQUIRED이며 공개 승인,
독립 검수, acceptance를 주장하지 않는다. 원본 privacy label도 자동 공개 허가가 아니다.
MINIMAL에도 희귀한 분류·수량·연결 구조가 남으므로 익명성이나 differential privacy를
보장하지 않는다. 문자열 blacklist로 비밀값을 탐지했다고 주장하지 않는다.

## 증거 목록의 범위

**선택한 사례의 연구 기록과 그 안의 직접 CAS 참조**만 목록화한다.
각 원본 객체의 digest를 검증하고 누락·손상 시 export를 중단한다.
각 항목에 RAW_OMITTED / NO_TRANSITIVE_EXPANSION을 표시한다.
파생 기록은 원래 digest 대신 로컬 evidence 별칭으로 연결된다.

QA receipt·계획·이전 decision·cohort 정의 등 직접 참조는 목록화하지만 그 안을
재귀적으로 복사하지 않는다. Work 전체 문서, 소스, 로그, 다른 사례·비교군 명단,
미참조 CAS는 제외한다. 전체 Work 백업이나 독립 replay 가능한 증거 묶음이 아니다.
목록에 있다는 사실은 그 내용이 결론을 뒷받침한다는 독립 검증이 아니다.

v1은 가설·맥락의 원문도 의도적으로 제외한다. 논문 검토에는 별도로 승인·검토한
맥락 설명이 더 필요할 수 있다. 사람의 해석을 엔진 관측인 것처럼 섞으면 안 된다.

## 보장과 한계

검증은 파일 구성·크기·checksum을 확인한다. 개인정보 제거 품질·작성자 신원·원천
Work의 진위·QA 통과는 확인하지 않는다. 내용을 바꾸고 checksum도 다시 계산하면
무결성 검증만으로는 구별할 수 없으므로, 별도 보관한 manifest pin을 사용한다.
pin도 서명이나 신원 증명은 아니다. 결과의 authenticity_verified/redaction_verified는 false다.

동일 상태·정책은 결정적 결과를 낸다. export 시각은 만들지 않으며 시간 기준은
REPLAY_PREFIX_NO_WALL_CLOCK이다. MINIMAL은 head를 숨기므로 무관한 Work 변경에
출력이 같을 수 있다. LINKABLE만 전체 head를 포함한다. 현재 소스를 재검수하지 않는다.

제한: 정책 4 KiB, 연구 event 256개, 고유 inventory 객체 2,048개, 직렬화 bundle 4 MiB.
초과 시 잘라내지 않고 실패한다. CAS 검증 시간은 참조 객체 크기에 따라 증가한다.
동일 사용자에 의한 적대적인 파일 변경은 위협 모델 밖이며 경로는 비공개로 관리해야 한다.

API ownership·포맷·[논문 및 학술저서 검토 범위](bundle.md#research-basis)는 영문 계약을
참고한다. BagIt/RO-Crate 원칙을 참고했지만 해당 표준 호환 구현이라고 주장하지 않는다.
