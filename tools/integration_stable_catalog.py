"""Build explicit interface definitions and a separate, uninstalled stable broker.

No policy, launcher selection, client configuration or native operation is applied.
The fixed catalog is an interface ceiling, never an action or disclosure grant.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import stat

import integration_contract as c
import integration_feature_profiles as profiles
import integration_service as reads
import integration_mutation_contract as mutations
import integration_mcp as read_mcp
import integration_mutation_mcp as action_mcp

PROGRAMS = ('stable_entry.py', 'stable_contract.py', 'stable_relay.py',
            'launcher.py', 'connection_relay.py', 'stable_readiness.py')


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')


def digest(value):
    return hashlib.sha256(value).hexdigest()


def catalog(profile, names):
    """An explicitly enumerated subset of existing typed schemas; no service I/O."""
    ceiling = set(profiles.definition(profile)['tools'])
    c.require(type(names) is list and 0 < len(names) <= 128 and
              all(type(name) is str for name in names) and len(set(names)) == len(names),
              'STABLE_EXPLICIT_TOOL_SUBSET_REQUIRED')
    c.require(set(names) <= ceiling, 'STABLE_PROFILE_SCOPE')
    definitions = []
    for name in sorted(names):
        schema = (mutations.SCHEMAS if name in mutations.NAMES else reads.SCHEMAS).get(name)
        c.require(type(schema) is dict and schema.get('type') == 'object',
                  'STABLE_TOOL_SCHEMA_UNSUPPORTED')
        description = ('Interface definition only. This does not grant project access or authorize an action. '
                       'Every call uses current owner scope and the existing native checks; '
                       'do not retry uncertain results. ' +
                       read_mcp.COUNTER_TOOL_DESCRIPTIONS.get(name, '') +
                       read_mcp.PREPARATION_TOOL_DESCRIPTIONS.get(name, '') +
                       action_mcp.TASK_TOOL_DESCRIPTIONS.get(name, ''))
        definitions.append({'name':'golem_' + name, 'inputSchema':copy.deepcopy(schema),
                            'description':description,
                            'annotations':{'readOnlyHint':name == 'execution_read',
                                'destructiveHint':name in mutations.NAMES,
                                'idempotentHint':name == 'execution_read',
                                'openWorldHint':name in ('execution_request', 'helper_execute')}})
    return {'schema':'golem.fixed-tool-catalog.v1', 'profile':profile,
            'tools':definitions, 'tools_sha256':digest(encoded(definitions))}


def absolute(path):
    path = Path(path)
    c.require(path.is_absolute() and '..' not in path.parts and
              not any(p.is_symlink() for p in (path, *path.parents)), 'STABLE_OUTPUT_PATH')
    return path


def typed_inventory():
    """Finite source-derived interface ceiling pinned into the reviewed broker."""
    scopes, definitions = {}, {}
    for profile in profiles.NAMES:
        value = catalog(profile, list(profiles.definition(profile)['tools']))
        scopes[profile] = [tool['name'] for tool in value['tools']]
        for tool in value['tools']:
            c.require(tool['name'] not in definitions or definitions[tool['name']] == tool,
                      'STABLE_INTERFACE_PROFILE_CONFLICT')
            definitions[tool['name']] = tool
    return {'schema':'golem.typed-interface-inventory.v1', 'profiles':scopes, 'tools':definitions}


def write_new(path, raw):
    path = absolute(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as out:
        out.write(raw)
        out.flush()
        os.fsync(out.fileno())


def build_broker(output):
    """Copy only the finite repository broker payload to a NEW private directory.

    The output is not registered, enabled or launched. Initial migration and any
    broker-code upgrade require their own supported client selection. This path
    stays fixed only for subsequent compatible backend/policy selections.
    """
    output = absolute(output)
    source = Path(__file__).resolve().parents[1] / 'plugins/golem'
    payloads = {}
    for name in PROGRAMS:
        path = (Path(__file__).parent / 'integration_stable_readiness.py'
                if name == 'stable_readiness.py' else source / 'scripts' / name)
        c.require(not path.is_symlink() and stat.S_ISREG(path.stat().st_mode), 'STABLE_SOURCE_FILE')
        payloads[name] = path.read_bytes()
    payloads['LICENSE'] = (source / 'LICENSE').read_bytes()
    payloads['typed-interface.json'] = encoded(typed_inventory())
    manifest = {'schema':'golem.stable-broker-bundle.v1',
                'files':{name:digest(raw) for name,raw in sorted(payloads.items())}}
    raw = encoded(manifest)
    output.mkdir(mode=0o700)
    # On failure preserve partial output; never overwrite or automatically repair.
    for name, data in payloads.items():
        write_new(output / name, data)
    write_new(output / 'broker-manifest.json', raw)
    return {'state':'UNINSTALLED_BROKER_CANDIDATE', 'directory':str(output),
            'manifest_sha256':digest(raw), 'files':manifest['files'],
            'execution_authorized':False, 'installed':False, 'automatic_retry_allowed':False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='operation', required=True)
    export = sub.add_parser('catalog')
    export.add_argument('--profile', choices=profiles.NAMES, required=True)
    export.add_argument('--tool', action='append', required=True)
    export.add_argument('--output', type=Path, required=True)
    bundle = sub.add_parser('broker')
    bundle.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.operation == 'catalog':
            value = catalog(args.profile, args.tool)
            raw = encoded(value)
            c.require(len(raw) <= 512 * 1024, 'STABLE_CATALOG_SIZE')
            write_new(args.output, raw)
            result = {'state':'UNAPPROVED_CATALOG_CANDIDATE', 'path':str(args.output),
                      'sha256':digest(raw), 'tool_names':[row['name'] for row in value['tools']],
                      'execution_authorized':False, 'installed':False}
        else:
            result = build_broker(args.output)
        print(encoded(result).decode(), end='')
        return 0
    except (c.IntegrationError, OSError, ValueError) as error:
        print(encoded({'state':'BLOCKED', 'code':getattr(error,'code','STABLE_BUILD_FAILED'),
                       'automatic_retry_allowed':False}).decode(), end='')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
