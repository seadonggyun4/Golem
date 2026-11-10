"""Owner-only exact bootstrap changes; MCP reuses PACKET for pinned inspection.

The MCP Intent adapter may import this schema and dispatch enrollment-inspect,
never this local plan/apply entry or review/enroll operations. Baseline object
storage continues to use intent_authority.store_objects. This adapter never
constructs review evidence, chooses a verdict, or adopts sources.
"""
from pathlib import Path
import os
import select

import integration_contract as c
import integration_registry as r
import intent_authority as authority
import execution_record as records

TEXT = {'type': 'string', 'maxLength': c.LIMIT}
PACKET = c.obj({
    'schema': {'const': 'golem.intent-bootstrap-host.v1'},
    'operation': c.enum('review', 'enrollment-inspect', 'enrollment-digest', 'enroll'),
    'work': {'type': 'string', 'maxLength': 4096},
    **{key: TEXT for key in ('policy', 'bundle', 'control', 'baseline', 'enrollment')},
    **{key: c.DIGEST for key in ('policy_sha256', 'bundle_sha256', 'baseline_operation',
        'baseline_request', 'publication_operation', 'authority_head', 'work_head', 'approval')},
    'policy_name': {'type': 'string', 'minLength': 1, 'maxLength': 64},
    'bundle_name': {'type': 'string', 'minLength': 1, 'maxLength': 64},
    'sources': c.array(c.obj({'control': TEXT, 'text': TEXT}), 64),
    'definitions': c.array(TEXT, 256), 'authority_sequence': c.INTEGER, 'work_sequence': c.INTEGER})


def _selected(repository, registration, git, bridge, packet, review_root, action_id, audit):
    c._validate(action_id, c.ID)
    c._validate(registration, c.DIGEST)
    raw = r.regular(packet, c.LIMIT, private=True)
    value = c.decode(raw)
    c._validate(value, PACKET)
    keys = {'schema', 'operation', 'work', 'policy', 'bundle', 'control',
            'policy_sha256', 'bundle_sha256', 'policy_name', 'bundle_name',
            'baseline', 'sources', 'definitions', 'baseline_operation',
            'baseline_request', 'publication_operation', 'authority_sequence',
            'authority_head', 'work_sequence', 'work_head', 'enrollment', 'approval'}
    c.require(isinstance(value, dict) and set(value) == keys and
              value['schema'] == 'golem.intent-bootstrap-host.v1' and
              value['operation'] in ('review', 'enrollment-inspect', 'enrollment-digest', 'enroll'), 'BOOTSTRAP_PACKET')
    for field in ('policy', 'bundle'):
        name = value[field + '_name']
        c.require(isinstance(name, str) and name not in ('', '.', '..') and '/' not in name,
                  'BOOTSTRAP_REVIEW_NAME')
        selected = r.regular(review_root / name, c.LIMIT, private=True)
        c.require(isinstance(value[field], str) and selected == value[field].encode() and
                  c.sha(selected) == value[field + '_sha256'], 'BOOTSTRAP_REVIEW_PIN')
    for directory in (review_root, audit):
        info = directory.stat()
        c.require(directory.is_dir() and info.st_uid == os.getuid() and not info.st_mode & 0o077,
                  'BOOTSTRAP_PRIVATE_ROOT')
    with authority.authorized_root(repository, registration, git=git) as (_, record):
        c.require(r.file_pin(bridge) in record['authority']['pins'], 'NATIVE_BRIDGE_PIN_REQUIRED')
        c.require(not audit.is_relative_to(Path(repository)) and
                  not audit.is_relative_to(Path(record['authority']['path'])), 'BOOTSTRAP_AUDIT_SCOPE')
        work = value['work']
        if value['operation'] == 'review':
            c.require(work == '' and value['enrollment'] == '', 'BOOTSTRAP_REVIEW_SCOPE')
            work_identity = None
        else:
            target = r.real_path(work)
            c.require(target.is_relative_to(Path(repository)) and target != Path(repository),
                      'BOOTSTRAP_WORK_SCOPE')
            work_identity = r.identity(target)
        return {'schema': 'golem.intent-bootstrap-plan.v1', 'action_id': action_id,
                'adapter_sha256': c.sha(r.regular(Path(__file__))),
                'repository': str(repository), 'registration_sha256': registration,
                'registration_record': record, 'git': r.file_pin(git), 'bridge': r.file_pin(bridge),
                'packet': r.file_pin(packet), 'operation': value['operation'],
                'work': work, 'work_identity': work_identity,
                'review_root': {'path': str(review_root), 'identity': r.identity(review_root)},
                'audit_root': {'path': str(audit), 'identity': r.identity(audit)},
                'execution_authorized': False}, raw


def plan(repository, registration, *, git, bridge, packet, review_root, action_id, audit_root):
    paths = [r.real_path(str(p)) for p in (repository, git, bridge, packet, review_root, audit_root)]
    value, _ = _selected(paths[0], registration, *paths[1:5], action_id, paths[5])
    return {'plan': value, 'plan_sha256': c.sha(c.encoded(value))}


def apply(repository, registration, reviewed_plan_sha256, *, git, bridge, packet,
          review_root, action_id, audit_root, approve_local_owner=False):
    c.require(approve_local_owner is True, 'OWNER_APPROVAL_REQUIRED')
    c._validate(reviewed_plan_sha256, c.DIGEST)
    paths = [r.real_path(str(p)) for p in (repository, git, bridge, packet, review_root, audit_root)]
    repository, git, bridge, packet, review_root, audit_root = paths
    selected, raw = _selected(repository, registration, git, bridge, packet, review_root, action_id, audit_root)
    c.require(c.sha(c.encoded(selected)) == reviewed_plan_sha256, 'PLAN_STALE')
    # One fixed action directory, created before dispatch. Never remove on error.
    output = audit_root / action_id
    output.mkdir(mode=0o700)
    records.save(output / 'dispatch-intent.json', c.encoded(selected))
    result = {'status': 'COMMIT_UNKNOWN', 'automatic_retry_allowed': False,
              'execution_authorized': False}
    try:
        with authority.authorized_root(repository, registration, git=git) as (fd, _):
            current, current_raw = _selected(repository, registration, git, bridge, packet,
                                             review_root, action_id, audit_root)
            c.require(current == selected and current_raw == raw, 'PLAN_STALE')
            reviewfd = os.open(review_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                info = os.fstat(reviewfd)
                c.require({'device': info.st_dev, 'inode': info.st_ino} == selected['review_root']['identity'],
                          'BOOTSTRAP_REVIEW_ROOT_CHANGED')
                def exchange(process, deadline):
                    import time
                    streams = {process.stdout.fileno(): bytearray(), process.stderr.fileno(): bytearray()}
                    outputs = dict(streams)
                    pending = memoryview(raw)
                    for pipe in (*streams, process.stdin.fileno()): os.set_blocking(pipe, False)
                    try:
                        while streams or pending:
                            remaining = deadline - time.monotonic()
                            c.require(remaining > 0, 'BOOTSTRAP_TIMEOUT')
                            ready, writable, _ = select.select(list(streams), [process.stdin.fileno()] if pending else [], [], remaining)
                            if writable:
                                pending = pending[os.write(process.stdin.fileno(), pending[:65536]):]
                                if not pending: process.stdin.close()
                            for pipe in ready:
                                chunk = os.read(pipe, 65536)
                                if not chunk: del streams[pipe]; continue
                                c.require(len(streams[pipe]) + len(chunk) <= c.LIMIT, 'BOOTSTRAP_OUTPUT_LIMIT')
                                streams[pipe].extend(chunk)
                        process.wait(timeout=max(.01, deadline - time.monotonic()))
                        c.require(process.returncode == 0, 'BOOTSTRAP_NATIVE_FAILURE')
                    finally:
                        for name, data in zip(('stdout', 'stderr'), outputs.values()):
                            records.save(output / (name + '.log'), bytes(data))
                records.run_private([str(bridge), '--bootstrap-fd', str(fd), registration,
                    str(reviewfd), c.sha(raw)], destination=output / 'process', timeout=30,
                    env={'PATH': '/usr/bin:/bin', 'LANG': 'C', 'LC_ALL': 'C'}, source=repository,
                    protocol=exchange, protocol_stderr=True, pass_fds=(fd, reviewfd))
            finally:
                os.close(reviewfd)
            current, current_raw = _selected(repository, registration, git, bridge, packet,
                                             review_root, action_id, audit_root)
            c.require(current == selected and current_raw == raw, 'BOOTSTRAP_POSTCHECK_CHANGED')
        result['native'] = c.decode(r.regular(output / 'stdout.log', c.LIMIT, private=True))
        result['status'] = 'NATIVE_RETURNED'
        return result
    finally:
        records.save(output / 'result.json', c.encoded(result))


def main(argv=None):
    """Local operator entry; no network listener or model-facing registration."""
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('plan', 'apply', 'schema'))
    parser.add_argument('--config', type=Path)
    parser.add_argument('--reviewed-plan-sha256')
    parser.add_argument('--approve-local-owner', action='store_true')
    args = parser.parse_args(argv)
    if args.operation == 'schema':
        print(c.encoded(PACKET).decode()); return 0
    if args.config is None: parser.error('--config is required')
    cfg = c.decode(r.regular(args.config, c.LIMIT, private=True))
    c._validate(cfg, c.obj({'repository': c.PATH, 'registration': c.DIGEST,
        **{k: c.PATH for k in ('git', 'bridge', 'packet', 'review_root', 'audit_root')}, 'action_id': c.ID}))
    if args.operation == 'apply':
        result = apply(**cfg, reviewed_plan_sha256=args.reviewed_plan_sha256,
                       approve_local_owner=args.approve_local_owner)
    else:
        result = plan(**cfg)
    print(c.encoded(result).decode())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
