# 제품 명칭 및 이름 변경 기록

확정일: 2026-09-21.

| 분류 | 확정 이름 | 역할 | 이름의 의미 |
|---|---|---|---|
| AWE | Golem, 골램 | agent·도구·정책·단계를 조립하고 실행·검증·복구를 관리하는 work engine | 구성요소를 조립해 작동하는 골램을 만든다는 이미지 |
| AWO | Hatchling, 헤츨링 | 품질·안전 제약을 지키면서 서비스 실행 비용을 절감하는 optimizer | 《호빗》의 금화 더미를 지키는 용에서 착안한, 비용을 아끼는 어린 용 이미지 |

이는 명칭의 비유이며 특정 캐릭터의 공식 제휴나 그림 사용 권한을 뜻하지 않는다.

## 개발 목적과 경계

Golem은 작업 실행 품질과 안정성을, Hatchling은 품질·안전 제약 안에서의 비용 절감을 담당한다.

Golem은 실행·승인·완료 판정의 정책 경계를 유지한다. Hatchling은 비용 최적화 제안을 제공하며 Golem이나 다른 runtime의 승인 권한을 대체하지 않는다. 두 제품은 독립적이고 통합은 선택적이다.

## 로컬 경로와 인터페이스 변경

- 기존 AWE 소스 `Hatchling-project/Hatchling`은 `golem-project/Golem`으로 이동했다.
- 기존 AWE 계획서 `project-docs/hatchling`은 `golem-project/project-docs/golem`으로 이동했다.
- 기존 AWO의 `golem-project` 자료는 `hatchling-project`로 이동했다.
- AWE CLI와 Python import는 `golem`, Python distribution은 `golem-awe`다.
- C 헤더는 `golem/*.h`, 공개 함수는 `golem_*`, 상수는 `GOLEM_*`다.
- CMake package는 `Golem`, library target은 `Golem::golem`이다.
- AWE의 기본 로컬 상태 디렉터리는 `.golem`이다. 이 작업에서 기존 `.hatchling` 디렉터리를 이동했으며 내부 증거 bytes는 수정하지 않았다.
- 기존 journal v1의 `HWJR` wire magic과 binary fixture는 호환성을 위해 그대로 유지한다. 제품 이름 변경은 저장 형식 변경이 아니다.

기존 C/Python 호출자는 새 이름으로 import·include·link하고 다시 빌드해야 한다. 옛 `hatchling` runtime alias는 제공하지 않는다. 해당 이름은 이제 optimizer를 의미하기 때문이다. 다른 위치의 실행 상태를 자동 검색하거나 이전하지 않는다.

## 보존 범위

Git 이력과 기존 작업은 보존한다. AWE의 원격 저장소와 origin은 `https://github.com/seadonggyun4/Golem.git`이다. 패키지 registry 배포는 별도 작업이다.

이동 전 build는 `Golem/tmp/build-before-brand-rename`에 보존했다. 그 안의 절대 경로·옛 바이너리는 역사적 산출물이며 새 빌드에 사용하지 않는다. 새 소스에서는 `cmake --preset dev`, `cmake --build --preset dev`, `ctest --preset dev`로 다시 구성한다.

내용의 의미를 보존하기 위해 외부 학술논문 제목·URL·Git 이력·content-addressed 증거·binary journal을 새 제품 이름으로 다시 쓰지 않는다. 현재 코드·문서의 제품 참조는 새 역할에 맞게 변경한다.
