"""Build a public launcher-only Claude Desktop MCPB; never configure or install it."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'plugins/golem'
FILES = ('LICENSE', 'assets/icon.png', 'scripts/launcher.py')


def manifest():
    version = json.loads((PACKAGE / '.codex-plugin/plugin.json').read_text())['version']
    return {
        'manifest_version': '0.4',
        # Preserve the installed extension identity; this name grants no profile rights.
        'name': 'golem-prepare',
        'display_name': 'Golem',
        'version': version,
        'description': 'Connect a separately reviewed local Golem launcher. Installation grants no Work access.',
        'author': {'name': 'Golem contributors'},
        'repository': {'type': 'git', 'url': 'https://github.com/seadonggyun4/Golem'},
        'icon': 'assets/icon.png',
        'license': 'PolyForm-Noncommercial-1.0.0',
        'server': {
            'type': 'python',
            'entry_point': 'scripts/launcher.py',
            'mcp_config': {
                'command': 'python3',
                'args': ['-I', '-B', '${__dirname}/scripts/launcher.py', 'serve',
                         '--client', 'claude-desktop', '--state', '${user_config.state}'],
            },
        },
        'compatibility': {'platforms': ['darwin', 'linux'], 'runtimes': {'python': '>=3.11'}},
        'tools_generated': True,
        'user_config': {
            'state': {
                'type': 'directory',
                'title': 'Reviewed Claude Desktop launcher state',
                'description': 'Select the owner-private state directory prepared with explicit claude-desktop launcher approval. This selection does not configure or approve a launcher.',
                'required': True,
            },
        },
    }


def build():
    payload = {name: (PACKAGE / name).read_bytes() for name in FILES}
    payload['manifest.json'] = (json.dumps(manifest(), indent=2, sort_keys=True) + '\n').encode()
    result = io.BytesIO()
    with zipfile.ZipFile(result, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(payload.items()):
            entry = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, data)
    return result.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    data = build()
    with args.output.open('xb') as output:
        output.write(data)
    print(json.dumps({'artifact': str(args.output), 'sha256': hashlib.sha256(data).hexdigest()}))


if __name__ == '__main__':
    main()
