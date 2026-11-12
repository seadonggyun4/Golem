"""Real pinned SDK stdio initialization over disposable pipes, never a Work.

Both public run(service) entrypoints execute with SDK2.3.0. The service has no
projects/actions and never executes a tool; this verifies ABI wire delivery,
not a real client installation, owner approval or native execution.
"""
import importlib.metadata
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import time
import unittest

import integration_stable_catalog as builder


ROOT=Path(__file__).resolve().parents[1]
ABI='golem.fixed-tool-catalog.v1'
try:
    SDK_AVAILABLE=(importlib.metadata.version('mcp')=='2.3.0' and
                   importlib.metadata.version('mcp-types')=='2.3.0')
except importlib.metadata.PackageNotFoundError:
    SDK_AVAILABLE=False

CHILD=r'''
import asyncio,json,sys
sys.path.insert(0,sys.argv[1])
import integration_mcp as read
import integration_mutation_mcp as mutation
mode,scope,tamper=sys.argv[2:]
module=read if mode=='read' else mutation
class EmptyService:
    tools_count=0
    call_count=0
    def __init__(self):
        if scope!='none':self.profile={'tools':json.loads(scope)}
    def tools(self):
        self.tools_count+=1
        return []
    def call(self,*args):
        self.call_count+=1
        raise AssertionError('No Work call permitted in SDK fixture')
service=EmptyService()
if tamper=='schema':
    read.SCHEMAS={**read.SCHEMAS,'projects_list':{'type':'object','properties':{'unreviewed':{'type':'string'}}}}
try:
    asyncio.run(module.run(service))
finally:
    sys.stderr.write('\nFIXTURE_COUNTS='+json.dumps({'tools':service.tools_count,'calls':service.call_count})+'\n')
'''


@unittest.skipUnless(SDK_AVAILABLE,'exact mcp==2.3.0/mcp-types==2.3.0 SDK fixture dependencies required')
class SDKInitialization(unittest.TestCase):
    def wire(self,mode,environment=None,scope=None,tamper='none',listed=False):
        with tempfile.TemporaryDirectory(prefix='stable-sdk-',dir='/private/tmp' if Path('/private/tmp').exists() else None) as directory:
            environment={**{'PATH':os.environ.get('PATH','/usr/bin:/bin'),'HOME':directory,
                'TMPDIR':directory,'PYTHONDONTWRITEBYTECODE':'1'},**(environment or {})}
            with tempfile.TemporaryFile(dir=directory) as errors:
                child=subprocess.Popen([sys.executable,'-I','-B','-c',CHILD,str(ROOT/'tools'),mode,
                    json.dumps(scope) if scope is not None else 'none',tamper],
                    stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=errors,env=environment,bufsize=0)
                buffer=bytearray()
                def send(value):
                    child.stdin.write((json.dumps(value,separators=(',',':'))+'\n').encode());child.stdin.flush()
                def receive():
                    deadline=time.monotonic()+10
                    while b'\n' not in buffer:
                        remaining=deadline-time.monotonic()
                        if remaining<=0 or not select.select([child.stdout],[],[],remaining)[0]:
                            self.fail('isolated SDK response timeout')
                        part=os.read(child.stdout.fileno(),65536)
                        if not part:return None
                        buffer.extend(part)
                        self.assertLessEqual(len(buffer),1024*1024)
                    raw,_,rest=buffer.partition(b'\n');buffer[:]=rest
                    return json.loads(raw)
                try:
                    send({'jsonrpc':'2.0','id':1,'method':'initialize','params':{
                        'protocolVersion':'2025-06-18','capabilities':{},
                        'clientInfo':{'name':'isolated-stable-ABI-test','version':'1'}}})
                    initialized=receive()
                    tools=None
                    if initialized is not None and 'result' in initialized:
                        send({'jsonrpc':'2.0','method':'notifications/initialized'})
                        if listed:
                            send({'jsonrpc':'2.0','id':2,'method':'tools/list','params':{}})
                            tools=receive()
                    child.stdin.close();child.wait(timeout=10)
                    errors.seek(0);stderr=errors.read(2*1024*1024).decode(errors='replace')
                    counts=[line.removeprefix('FIXTURE_COUNTS=') for line in stderr.splitlines()
                            if line.startswith('FIXTURE_COUNTS=')]
                    self.assertEqual(len(counts),1,stderr)
                    counters=json.loads(counts[0]);self.assertEqual(counters['calls'],0)
                    return initialized,tools,child.returncode,stderr,counters
                finally:
                    if child.poll() is None:
                        # Only this disposable test child may be stopped after
                        # a failed assertion; no client or existing host PID.
                        child.terminate();child.wait(timeout=5)
                    for stream in (child.stdin,child.stdout):
                        if stream is not None and not stream.closed:stream.close()

    def environment(self,profile,names):
        return {'GOLEM_STABLE_FRONTEND_ABI':ABI,'GOLEM_STABLE_FRONTEND_PROFILE':profile,
                'GOLEM_STABLE_FRONTEND_TOOLS':json.dumps(names)}

    def assert_abi(self,response,profile,names):
        self.assertEqual(response['id'],1)
        result=response['result']
        self.assertEqual(result['capabilities']['experimental'][ABI],{
            'catalog_sha256':builder.digest(builder.encoded(builder.catalog(profile,names)))})
        self.assertIn('tools',result['capabilities'])
        self.assertNotIn('execution_authorized',result['capabilities']['experimental'][ABI])

    def test_read_run_delivers_exact_ABI_in_real_initialize_response(self):
        names=['projects_list','work_inspect']
        value,_,exit_code,stderr,counts=self.wire('read',self.environment('read',names))
        self.assertEqual(exit_code,0,stderr);self.assert_abi(value,'read',names)
        self.assertEqual(counts,{'tools':0,'calls':0})

    def test_mutation_run_delivers_exact_ABI_without_executing_an_action(self):
        names=['document_submit','projects_list']
        value,_,exit_code,stderr,counts=self.wire('mutation',self.environment('task',names),scope=names)
        self.assertEqual(exit_code,0,stderr);self.assert_abi(value,'task',names)
        self.assertEqual(counts,{'tools':0,'calls':0})

    def test_default_read_and_mutation_run_do_not_enable_stable_ABI(self):
        for mode in ('read','mutation'):
            with self.subTest(mode=mode):
                value,_,exit_code,stderr,counts=self.wire(mode)
                self.assertEqual(exit_code,0,stderr)
                self.assertNotIn(ABI,value['result']['capabilities'].get('experimental',{}))
                self.assertEqual(counts,{'tools':0,'calls':0})

    def test_ABI_visibility_leaves_actual_backend_tools_empty(self):
        names=['document_submit','projects_list']
        value,listed,exit_code,stderr,counts=self.wire('mutation',self.environment('task',names),scope=names,listed=True)
        self.assertEqual(exit_code,0,stderr);self.assert_abi(value,'task',names)
        self.assertEqual(listed['id'],2)
        self.assertEqual(listed['result']['tools'],[])
        self.assertEqual(counts,{'tools':1,'calls':0})

    def test_partial_opt_in_or_unsupported_read_schema_blocks_before_initialize(self):
        cases=[({'GOLEM_STABLE_FRONTEND_ABI':ABI},'STABLE_ABI_ARGUMENTS'),
               (self.environment('task',['document_submit']),'STABLE_BACKEND_TOOL_UNSUPPORTED')]
        for environment,reason in cases:
            with self.subTest(reason=reason):
                value,_,exit_code,stderr,counts=self.wire('read',environment)
                self.assertIsNone(value);self.assertNotEqual(exit_code,0)
                self.assertIn(reason,stderr);self.assertEqual(counts,{'tools':0,'calls':0})

    def test_loaded_schema_or_service_profile_mismatch_never_advertises_ABI(self):
        for mode,environment,scope,tamper,reason in (
            ('read',self.environment('read',['projects_list']),None,'schema','STABLE_BACKEND_SCHEMA_CHANGED'),
            ('mutation',self.environment('task',['document_submit']),['projects_list'],'none','STABLE_BACKEND_PROFILE')):
            with self.subTest(reason=reason):
                value,_,exit_code,stderr,counts=self.wire(mode,environment,scope,tamper)
                self.assertIsNone(value);self.assertNotEqual(exit_code,0)
                self.assertIn(reason,stderr);self.assertEqual(counts,{'tools':0,'calls':0})


if __name__=='__main__':
    unittest.main()
