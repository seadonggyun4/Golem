# Workflow selection templates

For integration, recovery and benchmark checks, see
[orchestration validation](orchestration-validation.md).

Templates are bounded, declarative starting configurations for the existing
document workflow. They do not spawn agents, grant permissions, execute commands,
register documents or claim that acceptance passed.

| Template | Mode | Required evidence |
| --- | --- | --- |
| feature | development | Planning, actual development result, passing QA, review |
| bugfix | development | Same, with declared `reproduction` and `regression` QA cases |
| review | documents | Planning, development recommendations, QA documents, review |
| research | documents | Planning/research findings, recommendations, QA documents, review |

The existing planning -> UX -> publishing -> development -> QA -> audit order
remains fixed. UX and publishing depend on validated scope findings. Omitted
stages retain explicit reasons and scope evidence. Documents mode retains the
development-plan and QA-plan/result documents, but cannot mint an actual
development-result or executable QA PASS through the template.

## CLI

```sh
golem workflow template list
golem workflow template show bugfix > bugfix-template.json
golem workflow template validate bugfix-template.json
golem workflow template instantiate "$WORK" scope 1 bugfix-template.json > selection.json
```

`validate` prints the definition digest. `instantiate` prints a selection proposal
for the specified existing, current scope revision. Register it using the normal
stage-selection document submission path: document metadata schema 3, with this
proposal as `selection`. The nested selection schema is 2; older schema-1
selections remain supported. See [document workflow](workflow.md).

Before requesting downstream inputs, explicitly enroll the embedded
`template_instance.definition.role_contract` using the existing role API and
its exact-contract approval. Template creation is not role enrollment or human
execution approval. Existing permission, freshness, execution and completion
checks still apply. See [role contracts](role-contracts.md).

## Customization and pinning

Use `show` as a complete editable schema example. Definition schema 1 accepts
only the documented fields emitted there. Unknown keys, unsupported versions,
cycles, arbitrary expressions and weakened evidence floors fail closed. Each
stage has a reason and its immediate predecessor; applicability is `ALWAYS`,
`SCOPE_UX` or `SCOPE_PUBLISHING`. Conditional applicability cannot skip a stage
required by the scope. Templates may require additional UX/publishing work.

The full definition and digest are embedded in each immutable selection
revision. Editing the local template file has no effect on registered work.
New revisions cannot switch selection identity or template kind, remove the
template, change its role contract, relax an ALWAYS stage, or increase budgets.
Use a new Work for a different contract. Digests use the engine's versioned JSON
serialization, not a cross-language canonical-JSON standard.

Default context cap is 1 MiB and reentry cap is four recorded reentries per Work.
Custom bounds are enforced at context/execution and reentry admission, in
addition to existing limits. They are not CPU, token-price or wall-clock limits.
Exceeding the context cap fails; it does not silently truncate required inputs.

Bugfix case IDs establish a minimum executable contract, not proof that the
test reproduces the original defect or sufficiently covers regressions. The
actual QA executor must supply valid results. Review evidence remains mandatory;
independent reviewer identity is optional unless explicitly required by the role
contract. Template wording alone does not validate research conclusions.

## C API and compatibility

`golem/workflow_template.h` exposes validate, builtin, pure expand, and
store-aware instantiate. Inputs are borrowed. Owned replies use
`golem_execution_reply_free`; outputs are unchanged on failure. The pure expander
does not establish scope freshness: registration and runtime validators do.
There is no new dependency or generic scripting engine. Existing selection-v1
workflows and historical completion evaluator dispatch remain unchanged.

## Design references

- [Workflow Patterns, van der Aalst et al. (2003)](https://pure.tue.nl/ws/files/2053121/613310.pdf):
  separates control-flow patterns from other workflow concerns. Here the template
  selects an existing sequence; authority and evidence remain separate validators.
- [Specifying Systems, Lamport (2002)](https://lamport.azurewebsites.net/tla/book-21-07-04.pdf):
  invariants must hold across transitions. Applied here as non-weakening revision
  rules and execution-time checks, not a claim of formal verification.
- [NIST SP 800-218 v1.1 (2022), PW.8](https://nvlpubs.nist.gov/nistpubs/specialpublications/nist.sp.800-218.pdf):
  executable testing and recorded results complement review. Development
  templates retain real QA evidence; document-only outcomes are not test passes.
