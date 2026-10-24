<div align="center">
  <img width="650" alt="Golem Banner" src="assets/Golem.png" />
</div>

<h1 align="center">Golem — Agentic Workflow Engine</h1>

<p align="center">
  <strong>서로 다른 AI Agent가 작업 상태와 검증 증거를 이어받아 협업하게 하는 경량 헤드리스 엔진</strong>
</p>

<p align="center"><em>Awaken the worker.</em></p>

[![CI](https://github.com/seadonggyun4/Golem/actions/workflows/c.yml/badge.svg)](https://github.com/seadonggyun4/Golem/actions/workflows/c.yml)
[![C17](https://img.shields.io/badge/core-C17-blue)](CMakeLists.txt)
[![Alpha](https://img.shields.io/badge/status-alpha-orange)](docs/conformance.md)
[![Agents](https://img.shields.io/badge/agents-Codex%20%7C%20Claude-327866)](docs/agent-session.md)
[![License](https://img.shields.io/badge/license-PolyForm%20Noncommercial-blue)](LICENSE)

**한국어** · [English](README.md) · [설치 안내](docs/runtime-reference.md#conan-package) · [작업 프로토콜](docs/agent-session.md)

## Golem이 하는 일

**지원 agent 연동: Codex · Claude.** 외부 agent가 Golem CLI/API를 호출하고 작업 상태와 검증 증거를 인계하는 것만으로 headless orchestration이 성립합니다. Golem이 모든 agent를 직접 실행하거나 daemon을 구동할 필요는 없습니다.

Agent는 사용자 의도를 해석하고 계획하며 코드 수정과 도구 사용으로 작업을 수행합니다. Golem은 작업 상태·의존성·소유권·인계·검증 증거를 관리하고, 제출과 완료 주장이 설정된 계약을 지켰는지 기계적으로 판단합니다. **AWE는 Agentic Workflow Engine이라는 분류명이며, 제품명은 Golem입니다.** C17 엔진과 CLI·JSON·Markdown을 제공하며 UI는 만들지 않습니다.

| 책임 | 담당 |
| --- | --- |
| 사용자 권한 안에서 무엇을 어떻게 할지 판단하고 수행 | AI Agent |
| 상태 전이·소유권·입력 최신성·수락 계약 검사 | Golem |
| 명시적으로 승인된 개발·QA 명령 실행과 관측 기록 | Golem의 선택적 실행 경로 |
| 비서·UI·provider별 launcher 제공 | 엔진의 필수 서비스가 아닌 client/host 연동 |

목표는 오케스트레이션 코어를 유지하면서 AI가 처리할 절차와 입력을 줄이는 것입니다. 증거·안전 검사를 줄인다는 뜻이 아닙니다. '경량'은 역할 경계를 뜻하며 토큰·청구액·성능 절감의 실측 결과가 아닙니다. [역할 및 실행 경계](docs/agent-golem-boundary.md)를 참고하세요.

## MCP

Golem은 **Codex와 Claude용 로컬 설치 MCP**를 제공합니다.
프로젝트 접근 범위와 맥락 전달은 소유자의 명시적 승인이 필요합니다.
Codex는 GitHub 기반 marketplace에서 설치하며 **Golem Setup** 스킬을 포함합니다.
Claude는 MCPB 확장으로 설치합니다.

![Donggyun Seo가 개발한 Golem 로컬 Codex 플러그인](assets/Golem-codex-plugin.png)

[Codex 플러그인 설치·설정](docs/integration-codex-plugin.md) ·
[Claude Desktop 설치·설정](docs/integration-mcpb.md#install-and-configure)

이미지는 검증한 합성 전용 설치 사례이며 공개 marketplace 등록을 뜻하지 않습니다.
설치만으로 프로젝트 접근이나 실행 권한을 부여하지 않습니다.

## 아키텍처

```mermaid
flowchart TD
    A["외부 Agent: 판단·코드 수정·도구 사용"] -->|"직접 CLI / C API"| C["Native C17 core: 상태·소유권·의존성·증거 검사"]
    A --> L["로컬 Codex 플러그인 / Claude MCPB"]
    L -->|"stdio MCP: 승인된 조회·맥락"| I["Python integration layer: D1-D6"]
    A -->|"별도로 opt-in한 지원 hook"| I
    O["소유자가 검토한 client·프로젝트·전달·변경 정책"] --> I
    I -->|"고정된 CLI / JSON 요청"| C
    C --> E["승인된 실행·QA·현재 완료 판정"]
    C --> S["명시적으로 선택한 Work 저장소: 통상 .golem 아래"]
    E --> S
    S --> J["영속 이벤트·receipt / 내용 해시 기반 원본"]
    S --> M["파생 Markdown·보고서"]
```

Integration layer는 client를 연결하며 native 수락 판정을 대체하지 않습니다.
D1은 승인·관리형 설치, D2는 제한된 조회·맥락·인계, D3는 읽기 전용 startup/resume 안내,
D4는 별도 승인된 typed 변경, D5는 소유자 주도 업데이트·reload·복구,
D6는 선택적 인증 TLS gateway를 담당합니다. 여섯 엔진이나 필수 상주 서비스가 아닙니다.
Work 경로는 명시적으로 선택하며, `.golem` 디렉토리의 존재만으로 권한이 생기지 않습니다.
client 이름은 인증된 신원이 아니며, 맥락 전달은 모델이 실제 입력을 소비했다는 증거가 아닙니다.

로컬 패키지는 D1/D2를 재사용하며 자동 hook·Work 재개·쓰기 권한을 추가하지 않습니다.
`AVAILABLE`은 데이터 전달 상태이지 native `DONE`이 아닙니다.
실제 데스크톱 호출 결과와 client별 표시 한계는 설치 문서에 구분해 기록했습니다.

전체 흐름과 저장 권위·코드/회귀 대응표는 [구현 아키텍처](docs/architecture.md),
client별 지원·승인·배포 경계는 [통합 계약](docs/integration-layer-design.md)을 참고하세요.

## 작업 흐름

명시적으로 생성·등록된 Work의 대표적인 **개발 작업** 경로입니다.

```mermaid
flowchart TD
    S["status / next 조회·preflight 확인"] --> G{"현재 진행 가능한가?"}
    G -->|"불가 / 효과 불명확"| B["대기·명시적 복구 판단<br/>임의 재실행 금지"]
    G -->|"가능"| P["산출물별 claim / context / begin<br/>현재 계획·승인된 prepare"]
    P --> A["Agent가 소스 수정"]
    A --> D["finish 관측·개발 결과 등록·session 제출"]
    D --> Q["QA 계획·별도 QA claim<br/>승인된 검사·결과 등록 및 제출"]
    Q --> R{"QA 결과"}
    R -->|"FAIL / ERROR"| F["Agent가 원인 판단·영향받은 입력 개정"]
    F --> S
    R -->|"PASS"| V["현재 소스·문서·증거 재검증"]
    V --> C["명시적 finalize<br/>필수 보고서 게시"]
    C --> N["현재 조건 충족 시에만 native DONE"]
```

한 claim은 전체 흐름이 아니라 하나의 요구 산출물에 대응합니다. 표준 stage-selection
workflow의 기획·개발·QA·완료 검증은 필수이며 UX·퍼블리싱은 범위에 따라 결정됩니다.
문서 전용 모드와 등록된 역할 계약은 별도 조건을 따르며 코드·테스트 성공을 꾸며내지 않습니다.
하위 입력은 정확한 상위 revision을 참조합니다. 소스나 상위 문서가 바뀌면 과거 증거가
유효하지 않을 수 있으며, 등록 성공·QA PASS·현재 DONE은 서로 다른 상태입니다.
startup hook과 preflight는 자동 재개·실행·인수를 하지 않습니다.
인계 대상은 명시된 상태·증거이며 client의 전체 대화를 자동 공유하지 않습니다.

| 핵심 | 동작 | 상세 |
| --- | --- | --- |
| Markdown 산출물 | 본문 저장, 불변 revision, 상위 문서 연결 | [문서 계약](docs/document-registry.md) |
| 탐색·범위 선정 | 조사 근거와 개선 범위를 기록 | [탐색·조사](docs/discovery.md) |
| 현재 agent 연동 | 작업 수령·제출·heartbeat·재개 | [세션](docs/agent-session.md) |
| 문서 기반 개발·QA | 개발 변경과 승인된 실제 테스트를 증거로 연결 | [실행](docs/execution.md) |
| 실패 재진입 | 원인에 따라 영향 문서 개정, 반복 예산 적용 | [재진입](docs/reentry.md) |
| 완료·복구 | 최신 문서·QA·소스 검증과 완료 보고서 복원 | [완료](docs/completion.md) |
| 연구 기록 | 작업·시도의 가설, 개입, 관측과 다음 판단을 불변 기록 | [ResearchCase·AttemptDecision](docs/research.ko.md) |
| 결과 의미 판정 | 필수 검증의 누락·SKIPPED·실패·낡은 판정으로 완료 차단 | [OutcomeAdjudication](docs/outcome.ko.md) |
| 연구 지표 | replay 기반 기록·최신 판정·복구 흐름 집계와 미측정 구분 | [ResearchMetrics](docs/metrics.ko.md) |
| 비교군 | 비사용·부분사용·전체사용의 불변 배정, 관측 개정과 replay 비교 | [ComparisonCohort](docs/cohort.ko.md) |
| 연구 bundle | 구조적 redaction·범위가 명확한 증거 목록·checksum 검증을 갖춘 비공개 export | [CaseStudyBundle](docs/bundle.ko.md) |
| 파생 observability | 원본 CAS/journal과 분리된 읽기 전용 OTLP snapshot 로그·PROV-JSON | [OTel / PROV](docs/observability.ko.md) |

## 빠른 시작

### 기본 실행과 선택 기능

기본 경로는 현재 client가 구동하는 native CLI·JSON 세션과 문서 workflow입니다.
[실행 계약](docs/execution.md)은 명시한 로컬 개발·QA 명령을 실제로 실행하며,
[worker executor](docs/worker-executor.md)는 신뢰된 host용 C API입니다.
client가 바뀌어도 Work·source·sequence·owner/binding·입력 참조·receipt를 유지해야
하며, 인수·재실행 권한이 자동으로 생기지 않습니다.
[context 재개](docs/context-resume.md)의 진단·복구 계약을 따릅니다.
[기본 current context](docs/current-context-selection.md)는 활성 의존성과 명시적
archive 참조를 유지하며, 이력·효과 판단이 불확실하면 full metadata로 돌아갑니다.
저장 원본과 native 전체 replay 검증은 줄이지 않습니다.

[lifecycle wrapper](docs/agent-lifecycle.md)는 검토한 준비·실행·종료를 한 호출로
묶는 선택 기능입니다. 원자적 실행이나 native DONE 판정은 아닙니다.
연구 schema·cohort·상세 지표·observability·provider 사용량 adapter는 일반 작업마다
작성할 필수 문서가 아닙니다. 설정된 native QA·증거·완료 조건은 유지됩니다.

로컬 daemon은 선택 기능이며 agent 협업의 전제조건이 아닙니다.
`run --noop`와 CLI daemon의 `local.noop` worker는 시뮬레이션이며 실제 에이전트
작업 완료가 아닙니다. 과거 Python `golem-prototype`도 native `golem`과 구별합니다.
인증된 원격 runner·임의 provider 실행·Windows runtime 지원을 이 예제가 보장하지
않습니다. 개별 지원 범위는 [기술 문서](docs/runtime-reference.md)를 참고하세요.

assessment·status·journal은 [통합 Work 기록](docs/work-records.md)에서
원본의 권한과 이력을 유지하며 함께 조회할 수 있습니다.

Python 검증·벤치마크 실행 도구에는 [기계적 실행 기록](docs/execution-recording.md)이
자동 적용됩니다. 적용 경로와 예외를 구분하며, 기록 자체가 제품 승인이나 QA 통과를 뜻하지는 않습니다.

네이티브 CLI는 큰 운영 JSON 응답을 기본적으로 간결하게 표시합니다.
프로토콜 필드를 읽는 스크립트는 `golem --output-mode full COMMAND ...`을 사용하세요.
간결 응답의 근거 ID로 명령 재실행 없이 원문을 검증·조회할 수 있습니다.
[출력 모드와 호환성 안내](docs/cli-output.md)를 참고하세요.

macOS 또는 Linux에서 C17 컴파일러, CMake 3.21+, Ninja, Python 3.11+, OpenSSL 3, pkg-config, json-c 0.15+, MD4C 0.4.8+가 필요합니다. [OS별 의존성](docs/runtime-reference.md#build-and-run) 또는 [Conan 설치](docs/runtime-reference.md#conan-package)를 참고하세요.

json-c는 구성 시 strict Unicode 파싱 검사를 통과해야 합니다. 수정되지 않은 0.18은 지원하지 않습니다. CI와 Conan은 0.17로 고정하며, upstream 0.19 Release 빌드의 별도 누수 문제는 의존성 문서를 참고하세요.

```sh
git clone https://github.com/seadonggyun4/Golem.git
cd Golem
cmake --preset release
cmake --build --preset release
ctest --preset release
build/release/golem --version
```

새 작업을 만들고 예제 Markdown을 등록합니다. 저장 위치는 직접 지정합니다.

```sh
mkdir -p .golem/workspace
WORK="$(cd .golem/workspace && pwd -P)/first-work"
build/release/golem work start "$WORK" samples/documents/work.json
build/release/golem document validate samples/documents/planning.json samples/documents/planning.md
build/release/golem document submit "$WORK" samples/documents/planning.json samples/documents/planning.md planning-first
build/release/golem document inspect "$WORK" planning 1
```

생성 문서: `.golem/workspace/first-work/documents/planning/r0001.md`.
예제는 **등록 확인용**이며 자동 개발 실행이나 QA 통과를 의미하지 않습니다. 기존 Work를 덮어쓰지 말고 새 경로를 사용하세요. 대상 프로젝트에서도 `.golem/`을 Git에서 제외하세요.

실제 작업에는 프로젝트 범위·QA 명령·권한을 설정하고, Codex 또는 Claude가 [작업 지침 예제](samples/agent-session/AGENTS.fragment.md)와 [세션 프로토콜](docs/agent-session.md)을 따르도록 연결합니다.

## Agent 진입점 설정

프로젝트의 기존 **`AGENTS.md`**에 [공통 규칙 템플릿](samples/agent-session/AGENTS.quickstart.ko.md)을 덧붙이고, **`CLAUDE.md`**에는 이를 참조하는 [Claude 템플릿](samples/agent-session/CLAUDE.quickstart.ko.md)을 추가하세요. 기존 지침을 덮어쓰지 않습니다.

템플릿의 실행 파일·Work 저장 루트·프로토콜 문서·대상 저장소 경로를 실제 값으로 바꾼 뒤, 현재 Codex·Claude에게 해당 진입점을 읽고 작업하도록 요청하세요. 프로젝트별 QA와 권한은 작업 범위에 맞춰 설정합니다.

**[설정 절차·경로 예시·요청 예시](docs/agent-setup.ko.md)** · [English](docs/agent-setup.md)

## 설치와 문서

| 목적 | 안내 |
| --- | --- |
| GitHub 소스로 Conan 패키지·CLI 설치 | [Conan 설치](docs/runtime-reference.md#conan-package) |
| C/C++ 라이브러리 연동 | [Golem::golem 빌드·설치](docs/runtime-reference.md#development) |
| 다중 client·MCP 설계와 읽기 연동 | [통합 설계](docs/integration-layer-design.md) · [D1 승인/읽기](docs/integration-d1.md) · [owner 설정 설치·bootstrap](docs/integration-install.md) · [D2 MCP](docs/integration-d2.md) · [D3 opt-in hook](docs/integration-d3.md) |
| 명시적 typed 변경·소유자 승인 QA | [D4 local MCP·승인 host](docs/integration-d4.md) (별도 opt-in, hook은 읽기 전용 유지) |
| 소유자 승인 업데이트·재로딩·불확실 결과 복구 | [D5 유지보수](docs/integration-d5.md) (staged pin, 자동 native 재개·효과 재시도 없음) |
| Opt-in 원격 TLS gateway | [D6 인증·전달 동의](docs/integration-d6.md) (외부 AS·명시적 권한, Hosted 자동 설정 없음) |
| Python·TypeScript 연동 | [언어 바인딩](docs/runtime-reference.md#language-bindings) |
| 단계 선택·문서 참조·최신성 | [워크플로우](docs/workflow.md) |
| 역할별 산출물·실제 증거·완료 조건 | [역할 계약](docs/role-contracts.md) |
| 검증 절차와 보장 범위 | [통합 검증](docs/conformance.md) |
| 런타임·성능·운영 상세 | [기술 레퍼런스](docs/runtime-reference.md) |
| 저널 검사·비파괴 복구·호환성 | [무결성과 복구](docs/runtime-integrity.md) |

현재 배포 방식은 **GitHub + Conan 레시피**입니다. ConanCenter 등록이나 공개 Golem 패키지 서버를 전제로 하지 않습니다.

## 현재 상태

**Public Alpha.** Codex와 Claude를 통한 소규모 로컬 사례에서 Markdown → QA FAIL → 개정·수정 → PASS → 완료 흐름을 확인했습니다. 프로젝트별 QA와 권한 설정이 필요하며, 선언된 테스트의 통과가 문서 내용 전체의 타당성을 보증하지는 않습니다. [검증 범위와 절차](docs/conformance.md)를 참고하세요.

## 라이선스

Copyright 2026 Donggyun Seo. Golem은 [PolyForm Noncommercial 1.0.0](LICENSE)을 따르는 **source-available** 소프트웨어이며 OSI 승인 오픈소스 라이선스가 아닙니다. 허용되는 비상업적 이용·수정·재배포의 정확한 범위는 라이선스 원문을 따릅니다.

허용 범위 밖의 이용에는 Donggyun Seo의 별도 서면 라이선스가 필요합니다. [상용 이용 안내](COMMERCIAL-LICENSE.md) · [필수 고지 및 제3자 범위](NOTICE) · [seadonggyun@gmail.com](mailto:seadonggyun@gmail.com). 문의만으로 추가 권한이 부여되지 않으며, 의존성의 라이선스와 소유권은 각각 유지됩니다.
