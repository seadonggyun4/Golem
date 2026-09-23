# Product Naming and Rename Record

[한국어](product-naming.ko.md) · **English**

Decision date: 2026-09-21.

| Category | Final name | Role | Meaning |
| --- | --- | --- | --- |
| AWE | Golem | Work engine that assembles agents, tools, policies, and stages, then manages execution, verification, and recovery | The image of assembling parts into a working golem |
| AWO | Hatchling | Optimizer that reduces service execution cost while preserving quality and safety constraints | Inspired by a young dragon guarding a pile of gold in *The Hobbit* |

These names are metaphors. They do not imply official affiliation with, or rights
to use art from, any specific character or franchise.

## Purpose and Boundary

Golem is responsible for work execution quality and stability. Hatchling is
responsible for cost reduction inside quality and safety constraints.

Golem keeps the policy boundary for execution, approval, and completion
decisions. Hatchling provides cost-optimization proposals and does not replace
Golem's, or any other runtime's, approval authority. The products are independent;
integration is optional.

## Local Path and Interface Changes

- Former AWE source `Hatchling-project/Hatchling` moved to `golem-project/Golem`.
- Former AWE plans `project-docs/hatchling` moved to `golem-project/project-docs/golem`.
- Former AWO material in `golem-project` moved to `hatchling-project`.
- The AWE CLI and Python import are `golem`; the Python distribution is
  `golem-awe`.
- C headers are `golem/*.h`; public functions use `golem_*`; constants use
  `GOLEM_*`.
- The CMake package is `Golem`; the library target is `Golem::golem`.
- AWE's default local state directory is `.golem`. During the rename, the former
  `.hatchling` directory was moved without modifying internal evidence bytes.
- Existing journal v1 `HWJR` wire magic and binary fixtures remain unchanged for
  compatibility. The product rename is not a storage-format change.

Existing C/Python callers must import, include, link, and rebuild with the new
names. No legacy `hatchling` runtime alias is provided because that name now
refers to the optimizer. Golem does not automatically discover or migrate runtime
state from other locations.

## Preserved Scope

Git history and existing work are preserved. The AWE remote repository and origin
are `https://github.com/seadonggyun4/Golem.git`. Package-registry publication is
a separate task.

The pre-rename build is preserved under `Golem/tmp/build-before-brand-rename`.
Absolute paths and old binaries there are historical artifacts and must not be
used for new builds. Reconfigure from current source with `cmake --preset dev`,
`cmake --build --preset dev`, and `ctest --preset dev`.

To preserve meaning, external paper titles, URLs, Git history, content-addressed
evidence, and binary journals are not rewritten with the new product name. Current
code and documentation should use product references that match the new roles.
