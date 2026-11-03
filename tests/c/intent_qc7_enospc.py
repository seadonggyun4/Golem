"""Opt-in macOS bounded HFS+ image; real kernel ENOSPC, never host-volume fill.
Retains the image and external logs. No sudo, forced unmount or automatic retry.
"""
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile


def main():
    if sys.platform != 'darwin' or not Path('/usr/bin/hdiutil').is_file():
        print('NOT_RUN: bounded hdiutil filesystem backend unavailable')
        return 77
    if len(sys.argv) != 7 or sys.argv[6] not in ('qa', 'completion'):
        raise SystemExit('expected SCRIPT CLI SOURCE CC DRIVER qa|completion')
    base = Path(tempfile.mkdtemp(prefix='golem-qc7-enospc-')).resolve()
    os.chmod(base, 0o700)
    mount, logs, image = base/'volume', base/'logs', base/'bounded.dmg'
    mount.mkdir(mode=0o700); logs.mkdir(mode=0o700)
    print('Retained ENOSPC image/logs:',base,flush=True)
    def run(args, name):
        result=subprocess.run(args,capture_output=True,timeout=90)
        (logs/(name+'.stdout')).write_bytes(result.stdout)
        (logs/(name+'.stderr')).write_bytes(result.stderr)
        if result.returncode: raise RuntimeError(f'{name} failed; evidence retained')
        return result.stdout
    run(['/usr/bin/hdiutil','create','-size','64m','-fs','HFS+','-volname','GOLEM_QC7_DISPOSABLE',str(image)],'create')
    attached=False
    try:
        raw=run(['/usr/bin/hdiutil','attach','-nobrowse','-owners','on','-mountpoint',str(mount),'-plist',str(image)],'attach')
        attached=True
        entities=plistlib.loads(raw)['system-entities']
        matches=[e for e in entities if e.get('mount-point')==str(mount)]
        assert len(matches)==1 and matches[0]['dev-entry'].startswith('/dev/disk'), 'unexpected mount identity'
        assert mount.stat().st_dev!=base.stat().st_dev, 'refusing to fill host filesystem'
        device=mount.stat().st_dev
        # Child must prove its fresh fixture is on this exact newly mounted device.
        env=dict(os.environ, GOLEM_QC7_OUTPUT=str(mount), GOLEM_QC7_LOGS=str(logs),
                 GOLEM_QC7_VOLUME_DEVICE=str(device), GOLEM_QC7_TEST='test_real_enospc',
                 GOLEM_QC7_CASE=sys.argv[6])
        result=subprocess.run([sys.executable,*sys.argv[1:6]],env=env,capture_output=True,timeout=300)
        (logs/'fixture.stdout').write_bytes(result.stdout)
        (logs/'fixture.stderr').write_bytes(result.stderr)
        (logs/'result.json').write_text(json.dumps(dict(exit_code=result.returncode, device=device,
                                                       kernel_enospc_required=True, status='PASS' if result.returncode==0 else 'FAIL')))
        return result.returncode
    finally:
        if attached:
            # Only this task's mount, never -force. Failure preserves mounted image
            # and reports an error; do not hide it behind successful fixture output.
            run(['/usr/bin/hdiutil','detach',str(mount)],'detach')


if __name__=='__main__':
    raise SystemExit(main())
