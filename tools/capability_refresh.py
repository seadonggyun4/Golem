"""Regenerate fixed M0 review artifacts; never refresh the reviewed ledger/models.

Explicit repository root only. Reuses the bounded reader and checker. Outputs
are development documentation, never producer, policy, approval or Work files.
"""
import argparse
from dataclasses import asdict
import json
import os
import stat
from capability_check import reconcile
from capability_ledger import decode_identified_ledger,SCHEMA
from capability_files import read_inventory,read_sources,_open_root
from capability_sample_registry import SOURCES,REVIEWED_NEW_SOURCES
from capability_audit import Audit,render_markdown
from capability_connections import ConnectionAudit,render_connections
from capability_handler import inspect_handler
from capability_handler_registry import HANDLERS
from capability_fallback import inspect_fallback,PINS as D2_PINS
from capability_delegation import inspect_delegation,PINS as D4_PINS
from capability_mutation_graph import inspect_mutation_graph


def artifacts(root):
    report,markdown=reconcile(root,repository_sources=True)
    inventory=read_inventory(root)
    if inventory.sha256!=report['inventory_sha256']:raise ValueError('INVENTORY_CHANGED_DURING_RENDER')
    ledger=decode_identified_ledger(inventory.data)
    audit=Audit(tuple(report['selected_blockers']),tuple(report['delivery_backlog']))
    public=[o for o in ledger['observations'] if o['kind']=='C_PUBLIC_DECLARATION' and o['source_path'].startswith('include/golem/')]
    ids={o['id'] for o in public}
    caps=[c for c in ledger['capabilities'] if set(c['observation_ids']) & ids]
    selected={o['source_path'] for o in public}|{r['path'] for c in caps for field in ('test_refs','doc_refs') for r in c[field]}
    projection=dict(schema=SCHEMA,sources=[s for s in ledger['sources'] if s['path'] in selected],observations=public,capabilities=caps)
    decode_identified_ledger(json.dumps(projection,ensure_ascii=False).encode())
    files=read_sources(root,list(SOURCES),reviewed_new=list(REVIEWED_NEW_SOURCES))
    if {f.path:f.sha256 for f in files}!={s['path']:s['sha256'] for s in report['inspected_sources']}:raise ValueError('SOURCE_CHANGED_DURING_RENDER')
    handlers=[]
    for rule in HANDLERS:
        result=inspect_handler(files,rule)
        handlers.append(dict(handler=rule.handler_path+':'+rule.method,**asdict(result),linked=result.linked))
    values={
        'mcp-m0-reconciliation.json':report,
        'mcp-m0-integrated-connections.json':report['static_connections'],
        'mcp-m0-public-observations.json':projection,
        'mcp-m0-handler-observations.json':handlers,
        'mcp-m0-connection-observations.json':dict(d2_fallback=dict(source_pins=D2_PINS,observation=asdict(inspect_fallback(files))),d4_delegation=dict(source_pins=D4_PINS,observation=asdict(inspect_delegation(files)))),
        'mcp-m0-mutation-graph.json':dict(source_pins=D4_PINS,observation=asdict(inspect_mutation_graph(files)))}
    out={name:json.dumps(value,ensure_ascii=False,indent=2)+'\n' for name,value in values.items()}
    out['mcp-m0-repository-scope.md']=markdown.rstrip('\n')+'\n'
    out['mcp-m0-observations.md']=render_markdown(ledger,audit)+render_connections(ConnectionAudit(audit,report['static_connections']))
    return report,out


def write_artifacts(root,outputs):
    """Fixed docs basenames, no symlink/hardlink redirection or arbitrary output path."""
    allowed={'mcp-m0-reconciliation.json','mcp-m0-integrated-connections.json','mcp-m0-public-observations.json','mcp-m0-handler-observations.json','mcp-m0-connection-observations.json','mcp-m0-mutation-graph.json','mcp-m0-repository-scope.md','mcp-m0-observations.md'}
    if set(outputs)-allowed:raise ValueError('ARTIFACT_OUTPUT_NOT_ALLOWED')
    root_fd=_open_root(root)
    try:
        docs=os.open('docs',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=root_fd)
        try:
            for name,text in outputs.items():
                raw=text.encode('utf-8')
                if len(raw)>16*1024*1024:raise ValueError('ARTIFACT_BYTES_LIMIT')
                fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW|os.O_NONBLOCK,0o644,dir_fd=docs)
                try:
                    info=os.fstat(fd)
                    if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1:raise ValueError('ARTIFACT_UNSAFE_TARGET')
                    os.ftruncate(fd,0)
                    while raw:
                        n=os.write(fd,raw)
                        if n<=0:raise OSError('ARTIFACT_NO_PROGRESS')
                        raw=raw[n:]
                finally:os.close(fd)
        finally:os.close(docs)
    finally:os.close(root_fd)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',required=True);args=parser.parse_args(argv)
    report,outputs=artifacts(args.root);write_artifacts(args.root,outputs)
    print(json.dumps(dict(selected_complete=report['selected_inventory_complete'],repository_complete=not report['repository']['blockers'],client_e2e='NOT_RUN')))
    return 0 if report['selected_inventory_complete'] and not report['repository']['blockers'] else 2

if __name__=='__main__':raise SystemExit(main())
