# Research Positioning

Current framing, 2026-10-20. This is reusable paper material, not an experimental
result. The [responsibility contract](agent-golem-boundary.md) is the common
definition for README, development documents and research descriptions.

## Suggested Introduction

Golem implements an Agentic Workflow Engine (AWE): a lightweight headless engine
through which different AI agents hand off work state and verification evidence.
Agents interpret user intent, plan and perform tasks. Golem manages state,
dependencies, ownership and handoffs, and mechanically checks whether submitted
results satisfy configured evidence and acceptance contracts. External agents
can use its CLI/API without a mandatory daemon or engine-owned provider launcher.
Explicitly approved development and QA execution is a supported, separate path;
it does not transfer general task judgment to the engine.

## 논문용 정의

Golem은 서로 다른 AI Agent가 작업 상태와 검증 증거를 이어받아 협업하게 하는
경량 헤드리스 엔진이다. AWE는 Agentic Workflow Engine을 뜻한다. Agent는 사용자
의도를 해석하고 계획·코드 수정·도구 사용으로 작업을 수행한다. Golem은 작업
상태·의존성·소유권·인계·검증 증거를 관리하고, 작업과 결과가 설정된 계약을
지켰는지 기계적으로 판단한다. 외부 agent의 CLI/API 호출만으로 headless
orchestration이 성립하며 daemon이나 범용 agent 직접 실행은 필수 조건이 아니다.
승인된 개발·QA 명령 실행은 이 책임 구분과 양립한다.

## Claims to Keep Separate

| Claim | Required evidence or qualification |
| --- | --- |
| Headless collaboration | Actual client CLI/API path and preserved ownership, input and receipt identities; daemon not required |
| Real direct agent execution | Non-noop provider/worker integration and observed dispatch/results; optional capability, not implied by the core |
| Contract enforcement | Reproducible rejection/acceptance tests for the exact version and configured predicate |
| Semantic correctness or independent review | Domain evidence and review provenance, not just native DONE or CAS hashes |
| Lower token/cost/procedure burden | Comparable measured inputs, calls, usage and billing boundaries; architecture alone is insufficient |

An assistant is a client using Golem, not a synonym for the engine. Research
schemas and detailed metrics are optional, not a requirement imposed on ordinary
tasks. Keep historical study versions, negative outcomes, missing observations
and frozen evidence unchanged. The current framing does not establish AWE as an
independently validated category or retrospectively qualify earlier experiments.
