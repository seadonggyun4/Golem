"""Real D01 writers versus authorized_root -> native Work/authority locks.
Opt-in disposable fixture only; no mocks, production paths or retries. NOT_RUN.
"""
import hashlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import selectors
import shutil
import subprocess
import sys
import tempfile

SOURCE = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(SOURCE / 'tools'))
import intent_authority as host
from integration_contract import IntegrationError


def inventory(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file() and not p.is_symlink()}


def writer(pipe, gate, operation, args):
    gate.wait(20)
    try:
        value = getattr(host, operation)(**args)
        pipe.send(('OK', value))
    except IntegrationError as exc:
        pipe.send(('BLOCKED', str(exc)))
    except BaseException as exc:
        pipe.send(('ERROR', repr(exc)))
    finally:
        pipe.close()


def race(operation, args, record):
    context = mp.get_context('spawn')
    gate = context.Event()
    children, pipes = [], []
    for _ in range(2):
        receive, send = context.Pipe(duplex=False)
        child = context.Process(target=writer, args=(send, gate, operation, args))
        child.start()
        send.close()
        children.append(child)
        pipes.append(receive)
    gate.set()
    try:
        results = []
        for pipe in pipes:
            assert pipe.poll(30), 'writer timeout (not retried)'
            results.append(pipe.recv())
        record.write_text(json.dumps(results, indent=2))
        assert [r[0] for r in results].count('OK') == 1, results
        rejected = next(r for r in results if r[0] != 'OK')
        allowed = ('AUTHORITY_REGISTRATION_BUSY', 'PLAN_STALE') if operation == 'register' else ('AUTHORITY_REGISTRATION_BUSY', 'AUTHORITY_REVOKED')
        assert rejected[0] == 'BLOCKED' and any(code in rejected[1] for code in allowed), results
        return next(r[1] for r in results if r[0] == 'OK')
    finally:
        for child in children:
            child.join(5)
            if child.is_alive():
                child.terminate()
                child.join(5)
        for pipe in pipes:
            pipe.close()


def main():
    bridge, driver, cli = [Path(x).resolve() for x in sys.argv[2:5]]
    base = Path(tempfile.mkdtemp(prefix='golem-qc7-d01-')).resolve()
    print('Retained QC7 D01 fixture:', base, flush=True)
    repo, authority, work = base/'repo', base/'authority', base/'work'
    repo.mkdir(mode=0o700)
    authority.mkdir(mode=0o700)
    git = Path(shutil.which('git')).resolve()
    env = dict(PATH='/usr/bin:/bin', HOME=str(base), GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
    def run(*args):
        return subprocess.run(list(map(str,args)), env=env, capture_output=True, check=True, timeout=30)
    run(git, 'init', '-q', repo)
    run(git, '-C', repo, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
        '-c', 'commit.gpgsign=false', 'commit', '--allow-empty', '-qm', 'fixture')
    plan = host.registration_plan(repo, authority, [bridge, driver], git=git)
    regargs = dict(root=repo, authority=authority, pins=[bridge, driver],
                   reviewed_plan_sha256=plan['plan_sha256'], git=git, bridge=bridge, approve_local_owner=True)
    registered = race('register', regargs, base/'registration-race.json')
    pin = registered['registration_sha256']
    # Valid native Work created solely to test the real lock ordering, not QA.
    run(cli, 'work', 'start', work, SOURCE/'samples/documents/work.json')
    revocation = host.revocation_plan(repo, pin, git=git)
    revargs = dict(root=repo, registration_sha256=pin,
                   reviewed_plan_sha256=revocation['plan_sha256'], git=git, approve_local_owner=True)
    fresh = host.registration_plan(repo, authority, [bridge, driver], git=git)
    regargs['reviewed_plan_sha256'] = fresh['plan_sha256']
    preserved = inventory(authority)
    work_preserved = inventory(work)
    locator = repo/'.git'/host.LOCATOR
    original_locator = locator.read_bytes()
    for lock_kind in ('hold', 'hold-authority'):
        # Actual authorized_root holds the common-dir lock while a real native
        # child holds Work, then (in second case) authority. No lock substitute.
        with host.authorized_root(repo, pin, git=git):
            read_fd, write_fd = os.pipe()
            packet = dict(op=lock_kind, work=str(work), authority=str(authority), release_fd=read_fd,
                          baseline_operation='1'*64, baseline_request='2'*64)
            child = subprocess.Popen([str(driver), ''], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, pass_fds=(read_fd,), env=env)
            os.close(read_fd)
            try:
                child.stdin.write(json.dumps(packet).encode())
                child.stdin.close()
                child.stdin = None
                with selectors.DefaultSelector() as selector:
                    selector.register(child.stdout, selectors.EVENT_READ)
                    assert selector.select(15), 'native lock acquisition timeout'
                assert child.stdout.readline() == b'READY\n'
                for operation, args in (('register', regargs), ('revoke', revargs)):
                    # A separate process invokes the actual writer entrypoint.
                    ctx=mp.get_context('spawn'); receive,send=ctx.Pipe(duplex=False); gate=ctx.Event()
                    contender=ctx.Process(target=writer,args=(send,gate,operation,args));contender.start();send.close();gate.set()
                    try:
                        assert receive.poll(20), 'writer did not fail boundedly'
                        result=receive.recv()
                        (base/f'{lock_kind}-{operation}.json').write_text(json.dumps(result))
                        assert result[0]=='BLOCKED' and 'AUTHORITY_REGISTRATION_BUSY' in result[1], result
                    finally:
                        contender.join(5)
                        if contender.is_alive(): contender.terminate(); contender.join(5)
                        receive.close()
                assert inventory(authority)==preserved
                assert locator.read_bytes()==original_locator
                child.terminate()  # read-only native lock holder, never a writer
                child.wait(10)
            finally:
                os.close(write_fd)
                if child.poll() is None: child.kill(); child.wait(5)
                stdout,stderr=child.communicate(timeout=5)
                (base/f'{lock_kind}.stderr').write_bytes(stderr)
        with host.authorized_root(repo,pin,git=git):
            pass  # Released locks remain usable; not a mutation retry.
    race('revoke',revargs,base/'revocation-race.json')
    assert inventory(authority)==preserved and locator.read_bytes()==original_locator
    assert inventory(work)==work_preserved
    try:
        with host.authorized_root(repo,pin,git=git):
            raise AssertionError('revoked registration accepted')
    except IntegrationError as exc:
        assert 'AUTHORITY_REVOKED' in str(exc)
    (base/'result.json').write_text(json.dumps(dict(status='PASS', authority_unchanged=True,
                                                  locator_unchanged=True, retries=0)))


if __name__ == '__main__':
    main()
