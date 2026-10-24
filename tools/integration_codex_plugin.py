"""Build a private local marketplace from an explicitly supplied launcher."""
import argparse
import json
from pathlib import Path
import re

from integration_registry import regular
import integration_mcp as branding


def pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('Duplicate launcher field')
        result[key] = value
    return result


def build(output, launcher, marketplace='golem-local', server='golem-local'):
    for name in (marketplace, server):
        if not re.fullmatch(r'[a-z][a-z0-9-]{0,63}', name):
            raise ValueError('Invalid local identifier')
    raw = regular(launcher)
    if len(raw) > 256 * 1024:
        raise ValueError('Launcher exceeds 256 KiB')
    command = json.loads(raw, object_pairs_hook=pairs)
    if (not isinstance(command, dict) or set(command) != {'command', 'args'}
            or not isinstance(command['command'], str)
            or not Path(command['command']).is_absolute()
            or not isinstance(command['args'], list)
            or any(not isinstance(v, str) for v in command['args'])):
        raise ValueError('Expected absolute command and string args only')
    for value in [command['command'], *command['args']]:
        if '\x00' in value or '${' in value:
            raise ValueError('NUL and client variable expansion are forbidden')
    root = Path(__file__).resolve().parents[1]
    manifest = {'name': 'golem', 'version': '0.1.3',
        'description': 'Owner-approved local workflow context and evidence.',
        'author': {'name': 'Donggyun Seo'}, 'mcpServers': './.mcp.json',
        'requires_local_executor': True, 'license': 'PolyForm-Noncommercial-1.0.0',
        'interface': {'displayName': 'Golem', 'developerName': 'Donggyun Seo',
            'shortDescription': 'Read approved workflow context and evidence',
            'category': 'Developer Tools', 'composerIcon': './assets/icon.png',
            'logo': './assets/icon.png'}}
    def encoded(value):
        return (json.dumps(value, indent=2) + '\n').encode()
    files = {
        '.agents/plugins/marketplace.json': encoded({'name': marketplace,
            'plugins': [{'name': 'golem', 'source': {'source': 'local', 'path': './plugins/golem'},
                'policy': {'installation': 'AVAILABLE', 'authentication': 'ON_INSTALL'},
                'category': 'Developer Tools'}]}),
        'plugins/golem/.codex-plugin/plugin.json': encoded(manifest),
        'plugins/golem/.mcp.json': encoded({'mcpServers': {server: {'type': 'stdio', **command}}}),
        'plugins/golem/assets/icon.png': branding.icon_bytes(),
        'plugins/golem/LICENSE': regular(root / 'LICENSE')}
    output.mkdir(mode=0o700)
    for name, data in files.items():
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with path.open('xb') as stream:
            stream.write(data)
        path.chmod(0o600)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--launcher', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--marketplace', default='golem-local')
    parser.add_argument('--server', default='golem-local')
    args = parser.parse_args()
    build(args.output, args.launcher, args.marketplace, args.server)
    print('Local marketplace created; review before installing. No settings or approvals changed.')


if __name__ == '__main__':
    main()
