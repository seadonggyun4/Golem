"""Isolated Work Pack read-only CLI conformance; no client or Work calls."""
import hashlib,json,os,pathlib,subprocess,sys,tempfile,fcntl
binary=pathlib.Path(sys.argv[1]).resolve(); source=pathlib.Path(sys.argv[2]).resolve()
manifest=json.loads(source.read_bytes())
env={k:v for k,v in os.environ.items() if not k.startswith('GOLEM_')}
def call(*args):
    return subprocess.run([str(binary),*map(str,args)],capture_output=True,env=env,timeout=5)
def failure(*args):
    p=call(*args);assert p.returncode!=0 and not p.stdout,(args,p.stdout,p.stderr)
    assert json.loads(p.stderr.splitlines()[-1])['execution_authorized'] is False
with tempfile.TemporaryDirectory(prefix='golem-pack-') as directory:
    root=pathlib.Path(directory).resolve();p=root/'pack.json';p.write_bytes(source.read_bytes())
    baseline=p.read_bytes(); digest=hashlib.sha256(baseline).hexdigest()
    for command in ('validate','inspect','compatibility'):
        r=call('pack',command,p);assert r.returncode==0,r.stderr
        value=json.loads(r.stdout);assert value['exact_digest']==digest and value['size']==len(baseline)
        assert not any(value[k] for k in ('authorized','bound','work_done'))
        assert r.stdout==call('pack',command,p).stdout
        if command=='inspect':assert value['manifest']==manifest
        if command=='compatibility':assert value['declared_compatible'] and value['runtime_availability']=='NOT_EVALUATED'
    r=call('pack','compatibility',p,'--core-version','65535.65535.65535');assert r.returncode==1 and not json.loads(r.stdout)['declared_compatible']
    for v in ('latest','1.2','01.0.0','1.0.0-beta','1.0.65536','1.0.0"x'):
        failure('pack','compatibility',p,'--core-version',v)
    interval=dict(manifest,core_min='2.0.0',core_max='10.0.0')
    p.write_text(json.dumps(interval))
    for version,expected in [('2.0.0',True),('9.0.0',True),('10.0.0',True),('1.65535.65535',False),('10.0.1',False)]:
        r=call('pack','compatibility',p,'--core-version',version)
        assert json.loads(r.stdout)['declared_compatible'] is expected
        assert r.returncode==(0 if expected else 1)
    p.write_bytes(baseline)
    for args in [('pack',),('pack','bogus',p),('pack','validate',p,'extra'),('pack','compatibility',p,'--unknown','1.0.0')]:
        assert call(*args).returncode==2
    failure('pack','validate',root/'missing');failure('pack','inspect',root)
    link=root/'alias';link.symlink_to(p);failure('pack','validate',link)
    parent=root/'parent';parent.symlink_to(root,target_is_directory=True);failure('pack','inspect',parent/'pack.json')
    failure('pack','validate',root/'..'/root.name/'pack.json')
    hard=root/'hard';os.link(p,hard);failure('pack','validate',p);hard.unlink()
    fifo=root/'fifo';os.mkfifo(fifo);failure('pack','validate',fifo)
    with p.open('rb') as f:
        fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);failure('pack','validate',p)
    for data in (b'',b'{}',b'[]',baseline+b'{}',b'x'*65537,b'{"x":1,"x":2}',b'{"x":"\xff"}',baseline.replace(b'"experimental"',b'"approved"')):
        p.write_bytes(data);failure('pack','inspect',p)
    p.write_bytes(baseline+b' '*(65536-len(baseline)));assert call('pack','validate',p).returncode==0
    p.write_bytes(baseline)
    output=root/'not-created'
    r=call('--output-mode','compact','--output-store',output,'pack','inspect',p)
    assert r.returncode==0 and json.loads(r.stdout)['manifest']==manifest and not output.exists()
    assert p.read_bytes()==baseline
print('Work Pack CLI valid/negative/path/lock/determinism/no-output-store PASS')
