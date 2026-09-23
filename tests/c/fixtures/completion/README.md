# Historical Completion Fixture

`v1-store.json` was captured from the already-built native CLI for commit
`51849798f370b93fb2a9ed8c3c877a694163bf75`, before the renderer/checkpoint changes.
It contains a synthetic development/QA completion with current-agent sessions.
The original temporary source project has been deleted; replay must not need it.

Normal CI decodes the fixed file inventory, opens/replays the old store, restores
the report and compares its original SHA-256. It also checks allocator failures
while loading the historical session events. It never regenerates the fixture.
The encoded content is test data, not private user evidence.

Do not refresh this fixture merely to make a compatibility failure disappear.
Add a separate versioned fixture when introducing a new evaluator or renderer.
The explicit maintainer capture command is:

```sh
TMPDIR=/private/tmp python3 tests/c/completion_history.py --capture OLD_CLI . /usr/bin/clang
```

Use an appropriate temporary directory/compiler on other systems. Audit decoded
contents and update producer provenance when deliberately capturing a new version.
