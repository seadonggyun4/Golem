"""M6 bounded native private publication; no client or production Work access."""
import sys,pathlib,json,hashlib,subprocess,copy,shutil,os,fcntl
HELPER=pathlib.Path(sys.argv.pop(3)).resolve()
from workpack_binding import Binding,ENV
class Receipts(Binding):
    def cli(self,*args,ok=True,env=None):
        result=super().cli(*args,ok=ok,env=env)
        if not ok:
            self.assertEqual(result.returncode,1,result.stderr.decode())
            self.assertNotIn(b'Sanitizer',result.stderr)
            self.assertNotIn(b'runtime error:',result.stderr)
        return result
    def bound(self):
        req=self.prepare();digest=self.cli('pack','resolve',self.work,req)['binding_digest'];receipt=self.cli('pack','bind',self.work,req,'--approve-binding',digest)
        d=self.docs['selection'];self.request_export=dict(schema='golem.workpack.receipt-request.v0',expected_generation=self.generation,binding_receipt=receipt['receipt_digest'],documents=[dict(document_id='selection',revision=d['revision'],digest=d['manifest_digest'])]);self.req=self.write('export.json',self.request_export);self.parent=self.root/'exports';self.parent.mkdir(mode=0o700)
        return self.req
    def plan(self,fmt='json',parent=None,req=None,ok=True):return self.cli('receipt','manifest',self.work,req or self.req,parent or self.parent,'--format',fmt,ok=ok)
    def export(self,plan,fmt='json',parent=None,ok=True):return self.cli('receipt','export',self.work,self.req,parent or self.parent,'--approve-export',plan['approval_digest'],'--format',fmt,ok=ok)
    def verify(self,path,digest,ok=True):return self.cli('receipt','verify',path,'--expect-manifest',digest,ok=ok)
    def published(self,fmt='json'):
        self.bound();p=self.plan(fmt);self.export(p,fmt);return p,self.parent/p['manifest_digest']
    def tree(self,path):return {str(p.relative_to(path)):hashlib.sha256(p.read_bytes()).hexdigest() for p in path.rglob('*') if p.is_file()}
    def reanchor(self,path,manifest):
        data=json.dumps(manifest,separators=(',',':')).encode();digest=hashlib.sha256(data).hexdigest()
        for n in ['manifest.json','COMMIT.json']:(path/n).chmod(0o600)
        (path/'manifest.json').write_bytes(data);(path/'COMMIT.json').write_text(json.dumps(dict(schema='golem.workpack.receipt-commit.v0',manifest=digest)))
        return digest
    def test_roundtrip_and_gate(self):
        self.bound();before=self.snapshot();plan=self.plan();self.assertFalse(plan['authorized']);self.assertEqual(before,self.snapshot());self.assertEqual(list(self.parent.iterdir()),[])
        self.cli('receipt','export',self.work,self.req,self.parent,ok=False)
        bad=copy.deepcopy(plan);bad['approval_digest']='0'*64;self.export(bad,ok=False);self.assertEqual(list(self.parent.iterdir()),[])
        result=self.export(plan);self.assertEqual(result['manifest_digest'],plan['manifest_digest']);path=self.parent/plan['manifest_digest'];r=self.verify(path,plan['manifest_digest']);self.assertEqual(r['integrity'],'VERIFIED');self.assertEqual(r['origin'],'UNAUTHENTICATED');self.assertFalse(r['completion_verified']);self.assertFalse(r['semantic_truth_verified']);self.assertFalse(r['authorized']);self.assertEqual(before,self.snapshot())
        saved=self.tree(path);self.export(plan,ok=False);self.assertEqual(saved,self.tree(path));self.assertEqual(before,self.snapshot())
        self.assertTrue(all((p.stat().st_mode&0o777)==0o400 for p in path.iterdir() if p.is_file()))
    def test_markdown_is_projection(self):
        p,path=self.published('markdown');self.verify(path,p['manifest_digest']);self.assertIn('not a native receipt',(path/'summary.md').read_text())
        f=path/'summary.md';f.chmod(0o600);f.write_text('APPROVED\n');self.verify(path,p['manifest_digest'],ok=False)
        self.verify(f,p['manifest_digest'],ok=False)
    def test_missing_truncated_extra_symlink_hardlink(self):
        p,path=self.published();manifest=json.loads((path/'manifest.json').read_text());obj=manifest['inventory'][0]['digest']
        for mode in ['missing','truncated','extra','symlink','hardlink','marker']:
            dest=self.root/mode;shutil.copytree(path,dest)
            if mode=='missing':(dest/obj).unlink()
            elif mode=='truncated':(dest/obj).chmod(0o600);(dest/obj).write_bytes(b'{}')
            elif mode=='extra':(dest/'secret.txt').write_text('not inventoried')
            elif mode=='symlink':(dest/obj).unlink();(dest/obj).symlink_to(path/obj)
            elif mode=='hardlink':(dest/obj).unlink();os.link(path/obj,dest/obj)
            else:(dest/'COMMIT.json').unlink()
            self.verify(dest,p['manifest_digest'],ok=False)
            if mode=='hardlink':(dest/obj).unlink()
        (path/('.pending-'+'a'*24)).write_text('untrusted partial');self.verify(path,p['manifest_digest'])
    def test_schema_references_and_unsigned_origin(self):
        p,path=self.published();base=json.loads((path/'manifest.json').read_text())
        for name,mutate in [('oversized',lambda m:m.update(padding='x'*65536)),('schema',lambda m:m.update(schema='unknown')),('type',lambda m:m['inventory'][0].update(type='executable')),('ref',lambda m:m['documents'][0].update(body='f'*64)),('work',lambda m:m['work'].update(identity='foreign')),('size',lambda m:m['inventory'][0].update(size=1048577)),('count',lambda m:m.update(inventory=m['inventory']*30)),('signature',lambda m:m.update(signature='trusted'))]:
            dest=self.root/("mutant-"+name);shutil.copytree(path,dest);m=copy.deepcopy(base);mutate(m);h=self.reanchor(dest,m);self.verify(dest,h,ok=False)
        dest=self.root/'unsigned';shutil.copytree(path,dest);m=copy.deepcopy(base);m['work']['head']='f'*64;h=self.reanchor(dest,m)
        self.verify(dest,p['manifest_digest'],ok=False);r=self.verify(dest,h);self.assertEqual(r['origin'],'UNAUTHENTICATED');self.assertFalse(r['authorized'])
    def test_stale_parent_format_and_paths(self):
        self.bound();plan=self.plan();before=self.snapshot();self.export(plan,'markdown',ok=False);self.assertEqual(list(self.parent.iterdir()),[])
        old=self.root/'old-parent';self.parent.rename(old);self.parent.mkdir(mode=0o700);self.export(plan,ok=False)
        self.plan(parent=self.work,ok=False);nested=self.work/'no-export';nested.mkdir(mode=0o700);self.plan(parent=nested,ok=False);nested.rmdir();self.plan(parent=self.root,ok=False)
        link=self.root/'link';link.symlink_to(self.parent,target_is_directory=True);self.plan(parent=link,ok=False)
        self.parent.chmod(0o755);self.plan(ok=False);self.parent.chmod(0o700)
        for update in [dict(expected_generation=99),dict(binding_receipt='f'*64),dict(documents=[]),dict(documents=self.request_export['documents']*2),dict(extra=True)]:
            self.plan(req=self.write('bad.json',dict(self.request_export,**update)),ok=False)
        self.assertEqual(before,self.snapshot());self.managed('planning');self.export(plan,ok=False)
    def test_locks(self):
        self.bound();plan=self.plan();fd=os.open(self.work,os.O_RDONLY)
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);self.plan(ok=False)
        finally:os.close(fd)
        fd=os.open(self.parent,os.O_RDONLY)
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);self.export(plan,ok=False)
        finally:os.close(fd)
        self.assertEqual(list(self.parent.iterdir()),[])
    def test_interruption_before_payload(self):self.fault('0')
    def test_interruption_after_commit(self):self.fault('1')
    def fault(self,mode):
        self.bound();before=self.snapshot();p=subprocess.run([str(HELPER),str(self.work),str(self.req),str(self.parent),mode],capture_output=True,env=ENV,timeout=30);self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(before,self.snapshot());self.assertEqual(len(list(self.parent.iterdir())),1)
if __name__=='__main__':
    import unittest
    unittest.main(defaultTest=[f'Receipts.{n}' for n in ('test_roundtrip_and_gate','test_markdown_is_projection','test_missing_truncated_extra_symlink_hardlink','test_schema_references_and_unsigned_origin','test_stale_parent_format_and_paths','test_locks','test_interruption_before_payload','test_interruption_after_commit')])
