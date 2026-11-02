# Work Pack common MCP delivery contract

Status: selected contract, implemented in the common MCP layer. This document is the
retained design decision, not an installation or permission grant. See [usage and
current verification](mcp.md) for subsequent client results.

- D2 `workpack_read` accepts bounded caller-supplied JSON for validate, inspect,
  compatibility, resolve, explain, proposal validation, assess and reference
  observation. Native CLI/API remains the only semantic validator.
- Catalog/search and receipt verify consume explicitly owner-selected resource
  snapshots. No model-supplied host path or directory discovery. Existing
  resource bounds remain in force; native's larger bounds do not expand them.
- D4 `workpack_bind`, `workpack_receipt_manifest`, and
  `workpack_receipt_export` select an exact immutable owner action. The model
  sends project/Work/action/request IDs only. Manifest is classified as an owner
  action because it examines an explicitly chosen output parent outside Work.
- Binding action contains exact native request bytes and the separate native
  binding approval digest. Manifest/export actions contain exact request bytes,
  canonical output parent and format; export additionally contains its separate
  native approval digest. An execution approval receipt is never substituted.
- Native parser, locks, generation/selection checks, CAS, parent identity and
  publication checks remain authoritative. Existing D4 durable intent, fence,
  stale/pending/unknown handling and no automatic redispatch apply unchanged.
- Output parents must remain outside the source Work, registry and policy files;
  owner chooses them explicitly in the pinned action. No network/credential,
  external Truthound invocation or automatic release/QA/completion authority.
- Common MCP schemas/profiles/package closure serve both clients. Implementation
  and fixture verification do not modify TopSolar policies, install bytes or
  producer pins and do not prove Desktop E2E.
