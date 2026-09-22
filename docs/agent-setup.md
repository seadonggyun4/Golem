# 프로젝트 agent 진입점 설정

Golem은 현재 Codex·Claude가 사용하는 문서 기반 작업 프로토콜이다.
설치만으로 프로젝트 지침이 자동 주입되거나 개발이 시작되지는 않는다.
이 안내는 소유자가 Golem 사용을 승인한 프로젝트에 적용한다.

## 빠른 적용

1. [설치 안내](runtime-reference.md#conan-package)로 최신 CLI를 준비한다.
   `golem --version`과 설치 소스 revision을 확인한다. 버전 문자열만 같아도
   실제 기능은 다를 수 있다. 같은 revision의 `docs/`와 `samples/`를 사용한다.
2. 프로젝트 루트의 기존 `AGENTS.md`에
   [공통 규칙 블록](../samples/agent-session/AGENTS.quickstart.md)을 덧붙인다.
   기존 파일을 템플릿으로 덮어쓰지 않는다. `AGENT.md`를 별도로 운영한다면
   사용하는 도구가 실제 읽는 진입점과 연결되어 있는지 확인한다.
3. 기존 `CLAUDE.md`에는 [Claude 진입 블록](../samples/agent-session/CLAUDE.quickstart.md)을
   덧붙인다. 공통 규칙을 중복 관리하지 않고 같은 루트의 `AGENTS.md`를 참조한다.
   파일명 대소문자를 유지한다.
4. 아래 placeholder를 실제 경로로 치환한다. Work 루트를 생성하고 Git에서 제외한다.
5. 현재 agent에게 진입점 파일을 읽게 하고, 아래 요청 예시처럼 작업 범위와
   Golem 사용을 명시한다. 자동 파일 탐색에만 의존하지 않는다.

| Placeholder | 설정 예시 |
| --- | --- |
| `<GOLEM_EXECUTABLE>` | `/absolute/install/bin/golem` 또는 프로젝트의 `.golem/bin/golem` |
| `<GOLEM_WORK_ROOT>` | `.golem/workspace/works` |
| `<GOLEM_DOCS_DIR>` | `/absolute/Golem/docs` 또는 복사한 `.golem/sdk/<revision>/docs` |
| `<TARGET_REPOSITORIES>` | 현재 저장소 `.` 또는 실제 하위 저장소 이름 목록 |

예시 경로는 설치를 생성하지 않는다. 실제 존재하는 실행 파일과 문서를 지정한다.
프로젝트별 `.golem/project.json`·`.golem/work.py`는 선택적 로컬 도구이며
Golem이 자동 검색하거나 기본 제공하는 설정 계약은 아니다.

프로젝트 루트에서:

```sh
mkdir -p .golem/workspace/works
```

기존 `.gitignore`에 중복 없이 `.golem/`을 추가한다. 진입점 자체도 비공개라면
`AGENTS.md`, `CLAUDE.md`를 제외한다. 이미 추적 중인 파일은 ignore로 숨겨지지
않으므로 인덱스 상태를 별도 검토한다. 기존 추적 파일을 자동 삭제하지 않는다.
Ignore 규칙은 암호화나 업로드 접근 통제가 아니다.

## 요청 예시

```text
AGENTS.md의 Golem 설정과 작업 규칙을 먼저 읽어줘.
현재 프로젝트의 [대상 기능]을 탐색하고 개선 범위를 선정해줘.
필요한 단계의 Markdown을 등록하고 그 문서에 따라 개발해줘.
실제 QA 결과를 기록하고, 실패하면 영향 문서를 개정해 재검수해줘.
완료 조건을 확인한 뒤 완료 보고서를 남겨줘.
기존 변경은 보존하고 커밋·푸시·배포는 하지 마.
```

## 적용 확인

- 지정한 CLI가 `work`, `document`, `session`, `execution`, `reentry`,
  `completion` 기능을 포함하는 설치인지 확인한다.
- [README 등록 예제](../README.md#빠른-시작)를 새 테스트 Work에서 실행하고
  실제 `.md` 파일이 선택한 경로에 생성되는지 확인한다.
- 실제 작업의 acceptance·필요 단계·QA argv·보호 테스트·권한은 탐색 후
  선정한다. 합성 샘플의 테스트 결과를 프로젝트 QA로 재사용하지 않는다.
- 재개 시 기존 session/Work부터 조회한다. 완료는 최신 문서·소스·QA와
  보고서가 유효한 현재 DONE이어야 한다.

상세 계약: [문서](document-registry.md) · [단계](workflow.md) ·
[세션](agent-session.md) · [실행](execution.md) · [재진입](reentry.md) ·
[완료](completion.md). 템플릿은 협력 지침이지 강제 sandbox가 아니다.

## English Summary

Install Golem and keep protocol docs pinned to the same source revision. Append
the linked common template to the project's existing `AGENTS.md`, and the Claude
entry block to `CLAUDE.md`; never overwrite existing instructions. The templates
are Korean and can be used by either supported agent. Replace all four placeholders
with real executable, Work root, protocol directory and repository paths.

Create the Work root and exclude runtime data from Git and published artifacts.
Ask the current agent explicitly to read the entrypoints. This does not install
an agent plugin, authorize arbitrary QA commands, or launch development on its
own. Select and approve project-specific gates within each task. Preserve existing
Work history and require current DONE before reporting completion.
