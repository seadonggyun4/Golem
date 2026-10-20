# AWE Concepts in Golem

`AWE — Agentic Workflow Engine` is the category name. `Golem` is the product and implementation.

`Workflow` denotes the governed stages, transitions, verification, recovery, and
completion of agentic activity. `Work` denotes an individual managed unit of
work; existing Work types, API names, schemas, and stored evidence retain their
names. This terminology clarification does not change runtime behavior.

Golem is a lightweight headless engine for agents to collaborate through work
state and verification evidence. Agents decide what to do and how; Golem checks
state, dependencies, ownership, handoffs and configured acceptance contracts.
External CLI/API clients do not require a daemon or engine-owned agent launcher.
See the [responsibility contract](agent-golem-boundary.md).

## Definition and Responsibility

The defining boundary of AWE is **what Golem is responsible for**, not whether it
owns every agent process. The agent judges what to do and how; Golem checks that
the collaboration complies with its configured contracts.

- **AI Agent:** interprets user intent, plans, edits code and uses tools to perform
  the task within the user's authority.
- **Golem:** manages work state, dependencies, ownership, handoffs and verification
  evidence, and mechanically determines which work submissions and results are
  valid under the configured contracts.

Approved QA command execution is consistent with this boundary. This definition
does not remove execution capabilities or make all execution mandatory. External
agents calling the CLI/API already form headless orchestration; a daemon and
universal direct agent execution are optional, separately qualified integrations.
An assistant or secretary is a client that uses Golem, not the engine itself.

### 한국어 정의

Golem은 **서로 다른 AI Agent가 작업 상태와 검증 증거를 이어받아 협업하게 하는
경량 헤드리스 엔진**이다. AWE의 핵심은 Golem이 책임질 영역을 명확히 하는 것이다.

- **AI Agent:** 사용자 의도를 해석하고, 계획하고, 코드를 수정하고, 도구를 사용해
  일을 수행한다.
- **Golem:** 작업 상태·의존성·소유권·인계·검증 증거를 관리하고, 어떤 작업과 결과를
  유효하게 받아들일지 설정된 계약에 따라 기계적으로 판단한다.

무슨 일을 어떻게 할지 판단하는 주체는 agent이고, 그 협업이 정해진 계약을 지켰는지
확인하는 주체는 Golem이다. Golem이 승인된 QA 명령을 실행하는 것은 이 구분과
모순되지 않는다. 모든 실행 기능을 빼거나 모든 agent를 직접 실행하자는 뜻이 아니다.
외부 agent의 CLI/API 호출만으로 headless orchestration이 성립하며, 비서는 그 위에서
Golem을 사용하는 하나의 client다. 안전·증거 검사를 줄이지 않고 AI가 처리할 절차와
입력을 줄이는 방향을 유지한다. 이 정의 자체는 토큰·비용 절감의 측정 결과가 아니다.

## Lower-Level Runtime Model

The lower-level runtime represents a `Work Capsule` and `WorkRun` containing
`StageRun` attempts. Those types do not imply that Golem launches a provider for
every stage; the current-agent session/document workflow is a separate entry path.

## Promoted Concepts

- `Work Capsule`: goal, scope, permissions, stage graph, acceptance criteria, expected artifacts, and required gates.
- `WorkRun`: one execution of a Work Capsule, with receipts for every stage.
- `StageRun`: one provider attempt at one stage, including status, attempt, lease, budget, evidence, and failure type.
- `Stage Graph`: default ordered graph of `planning -> ux -> publishing -> development -> qa -> audit`, with project override support.
- `Context Package`: stage input plus predecessor evidence digests.
- `Evidence`: content-addressed execution records, logs, artifact digests, test results, diff attestations, and reviewer output.
- `Decision`: policy outcome of `ALLOW`, `ASK`, or `DENY`.
- `Receipt`: evidence digest returned by a stage and attached to a WorkRun.

## Runtime Discipline

Golem keeps the runtime small and evidence-bound:

- status, attempt, budget, evidence, retry, and cancel shape
- lease and heartbeat checks
- stale lease rejection
- append-only evidence
- predecessor evidence digest requirements
- explicit adapter capabilities and trusted-host runner contracts where adopted;
  authenticated enrollment and signed envelopes are not universal guarantees
