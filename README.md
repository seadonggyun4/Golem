<div align="center">
  <img width="500" alt="Golem Banner" src="assets/Golem.png" />
</div>

<h1 align="center">Golem — Agentic Work Engine</h1>

<p align="center">
  <strong>문서와 검증 결과를 이어받아 일을 끝까지 수행하는 headless work runtime</strong>
</p>

<p align="center"><em>Awaken the worker.</em></p>

[![CI](https://github.com/seadonggyun4/Golem/actions/workflows/c.yml/badge.svg)](https://github.com/seadonggyun4/Golem/actions/workflows/c.yml)
[![C17](https://img.shields.io/badge/core-C17-blue)](CMakeLists.txt)
[![Alpha](https://img.shields.io/badge/status-alpha-orange)](docs/conformance.md)
[![Agents](https://img.shields.io/badge/agents-Codex%20%7C%20Claude-327866)](docs/agent-session.md)
[![License](https://img.shields.io/badge/license-PolyForm%20Noncommercial-blue)](LICENSE)

**한국어** · [English](README.en.md) · [설치 안내](docs/runtime-reference.md#conan-package) · [작업 프로토콜](docs/agent-session.md)

## Golem이 하는 일

**지원 에이전트: Codex · Claude.** 핵심은 별도 agent를 새로 띄우는 것보다, 지금 작업 중인 agent가 Markdown 문서와 검증 결과를 이어받아 완료까지 진행하도록 만드는 데 있습니다.

에이전트가 조사·문서 작성·코드 수정을 수행하고, Golem은 문서의 관계와 최신성, 실행 증거, 권한 및 완료 조건을 관리합니다. **AWE는 Agentic Work Engine이라는 분류명이며, 제품명은 Golem입니다.** C17 엔진과 CLI·JSON·Markdown을 제공하며 UI는 만들지 않습니다.

## 작업 흐름

```text
사용자 요청
→ 현재 agent가 Golem에서 작업 시작/복원
→ 프로젝트 탐색·관련 자료 조사·개선 범위 선정
→ 필요한 단계의 Markdown 작성 및 등록
→ 검증된 문서를 입력으로 개발
→ 실제 QA 실행 및 결과 Markdown 작성
→ 실패 원인 분류
→ 영향받은 문서 개정 → 개발/검수 반복
→ 완료 조건 검증 및 완료 보고서
```

기획 → UX → 퍼블리싱 → 개발 → QA → 검수 중 **필요한 단계만 선택**합니다. 하위 문서는 정확한 상위 revision을 참조하고, 상위 문서가 바뀌면 영향을 받는 문서와 검증 결과의 최신성을 다시 확인합니다.

| 핵심 | 동작 | 상세 |
| --- | --- | --- |
| Markdown 산출물 | 본문 저장, 불변 revision, 상위 문서 연결 | [문서 계약](docs/document-registry.md) |
| 탐색·범위 선정 | 조사 근거와 개선 범위를 기록 | [탐색·조사](docs/discovery.md) |
| 현재 agent 연동 | 작업 수령·제출·heartbeat·재개 | [세션](docs/agent-session.md) |
| 문서 기반 개발·QA | 개발 변경과 승인된 실제 테스트를 증거로 연결 | [실행](docs/execution.md) |
| 실패 재진입 | 원인에 따라 영향 문서 개정, 반복 예산 적용 | [재진입](docs/reentry.md) |
| 완료·복구 | 최신 문서·QA·소스 검증과 완료 보고서 복원 | [완료](docs/completion.md) |

## 빠른 시작

macOS 또는 Linux에서 C17 컴파일러, CMake 3.21+, Ninja, Python 3.11+, OpenSSL 3, pkg-config, json-c 0.15+, MD4C 0.4.8+가 필요합니다. [OS별 의존성](docs/runtime-reference.md#build-and-run) 또는 [Conan 설치](docs/runtime-reference.md#conan-package)를 참고하세요.

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

## 설치와 문서

| 목적 | 안내 |
| --- | --- |
| GitHub 소스로 Conan 패키지·CLI 설치 | [Conan 설치](docs/runtime-reference.md#conan-package) |
| C/C++ 라이브러리 연동 | [Golem::golem 빌드·설치](docs/runtime-reference.md#development) |
| Python·TypeScript 연동 | [언어 바인딩](docs/runtime-reference.md#language-bindings) |
| 단계 선택·문서 참조·최신성 | [워크플로우](docs/workflow.md) |
| 검증 절차와 보장 범위 | [통합 검증](docs/conformance.md) |
| 런타임·성능·운영 상세 | [기술 레퍼런스](docs/runtime-reference.md) |

현재 배포 방식은 **GitHub + Conan 레시피**입니다. ConanCenter 등록이나 공개 Golem 패키지 서버를 전제로 하지 않습니다.

## 현재 상태

**Public Alpha.** Codex와 Claude를 통한 소규모 로컬 사례에서 Markdown → QA FAIL → 개정·수정 → PASS → 완료 흐름을 확인했습니다. 프로젝트별 QA와 권한 설정이 필요하며, 선언된 테스트의 통과가 문서 내용 전체의 타당성을 보증하지는 않습니다. [검증 범위와 절차](docs/conformance.md)를 참고하세요.

## 라이선스

Copyright 2026 Donggyun Seo. Golem은 [PolyForm Noncommercial 1.0.0](LICENSE)을 따르는 **source-available** 소프트웨어이며 OSI 승인 오픈소스 라이선스가 아닙니다. 허용되는 비상업적 이용·수정·재배포의 정확한 범위는 라이선스 원문을 따릅니다.

허용 범위 밖의 이용에는 Donggyun Seo의 별도 서면 라이선스가 필요합니다. [상용 이용 안내](COMMERCIAL-LICENSE.md) · [필수 고지 및 제3자 범위](NOTICE) · [seadonggyun@gmail.com](mailto:seadonggyun@gmail.com). 문의만으로 추가 권한이 부여되지 않으며, 의존성의 라이선스와 소유권은 각각 유지됩니다.
