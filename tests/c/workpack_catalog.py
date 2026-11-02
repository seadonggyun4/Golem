"""Owner-selected local catalog fixtures, no installed clients or Work operations."""
import copy,fcntl,hashlib,json,os,pathlib,subprocess,sys,tempfile
binary=pathlib.Path(sys.argv[1]).resolve();sample=json.loads(pathlib.Path(sys.argv[2]).read_bytes())
env={k:v for k,v in os.environ.items() if not k.startswith('GOLEM_')}
with tempfile.TemporaryDirectory(prefix='golem-catalog-') as d:
    root=pathlib.Path(d).resolve();catalog=root/'catalog.json'
    def entry(name,version='0.1.0'):
        m=dict(sample,id=name,version=version);p=root/(name+version+'.json');p.write_text(json.dumps(m,ensure_ascii=False))
        return {**{k:m[k] for k in ('id','version','schema','status','intent','negative_intent','capabilities')},'digest':hashlib.sha256(p.read_bytes()).hexdigest(),'manifest':p.name,'aliases':['dataset check','데이터 검증'],'category':'data quality'}
    entries=[entry('test.z','10.0.0'),entry('test.a'),entry('test.z','2.0.0')]
    def save(items=entries):catalog.write_text(json.dumps({'schema':'golem.workpack.catalog.v0','entries':items},ensure_ascii=False))
    def call(query=None,path=catalog):
        args=['list','--catalog',str(path)] if query is None else ['search',query,'--catalog',str(path)]
        return subprocess.run([str(binary),'pack',*args],capture_output=True,env=env,timeout=10)
    def ok(query=None,path=catalog):
        p=call(query,path);assert p.returncode==0,p.stderr
        v=json.loads(p.stdout);assert not v['authorized'] and not v['bound'];assert v['runtime_availability']=='NOT_EVALUATED';return v
    def bad(query=None,path=catalog):
        p=call(query,path);assert p.returncode==1 and not p.stdout,(p.stdout,p.stderr)
    save();v=ok();assert [(e['id'],e['version']) for e in v['entries']]==[('test.a','0.1.0'),('test.z','2.0.0'),('test.z','10.0.0')]
    assert call().stdout==call().stdout
    for query in ('DATASET','데이터 검증','quality quality','truthound.check-file'):
        v=ok(query);assert v['result']=='AMBIGUOUS' and len(v['entries'])==3
    assert ok('quality quality')['entries'][0]['score']==1
    for query in ('dataset edit dataset rows','데이터 직접 수정','notfound','datasets'):
        assert ok(query)['result']=='NO_MATCH'
    for query in ('',' '*5,'x'*257,'a\x01') :bad(query)
    subset=copy.deepcopy(entries);subset[0]['aliases']=['unique'];save(subset);assert ok('unique')['result']=='MATCH'
    save();ordered=call().stdout;save(list(reversed(entries)));assert call().stdout==ordered
    save([]);assert ok()['entries']==[] and ok('dataset')['result']=='NO_MATCH'
    raw=catalog.read_bytes();catalog.write_bytes(raw+b' '*(1048576-len(raw)));assert ok()['entries']==[]
    assert ok('x'*256)['result']=='NO_MATCH'
    many=[entry('test.limit',f'0.0.{i}') for i in range(256)];save(many);assert len(ok()['entries'])==256
    save(many+[entry('test.limit','0.1.0')]);bad()
    for key,value in [('digest','0'*64),('id','test.wrong'),('intent',['forged']),('manifest','../escape'),('manifest','/etc/passwd'),('manifest','https://example.com'),('version','latest'),('category',''),('aliases',['x']*17),('unknown',True)]:
        altered=copy.deepcopy(entries);altered[0][key]=value;save(altered);bad('notfound')
    save(entries+[entries[0]]);bad()
    save(entries*86);bad()
    save();original=catalog.read_bytes();catalog.write_bytes(original+b' '*1048576);bad()
    catalog.write_bytes(b'{"schema":"golem.workpack.catalog.v0","entries":[],"entries":[]}');bad()
    catalog.write_bytes(b'{"bad":"\xff"}');bad()
    save();link=root/'link';link.symlink_to(catalog);bad(path=link)
    p=root/entries[0]['manifest'];raw=p.read_bytes();p.unlink();p.symlink_to(root/entries[1]['manifest']);bad();p.unlink();p.write_bytes(raw)
    with catalog.open('rb') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);bad()
    p.write_bytes(raw+b' ');bad();p.write_bytes(raw);save();assert ok()['result']=='LISTED'
    store=root/'output';p=subprocess.run([str(binary),'--output-mode','compact','--output-store',str(store),'pack','list','--catalog',str(catalog)],capture_output=True,env=env,timeout=10)
    assert p.returncode==0 and not store.exists(),p.stderr
print('catalog/search fixtures PASS')
