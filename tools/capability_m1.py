"""Finite M1 schema/delegation/read-guard profiles, never runtime authority."""
import ast
from dataclasses import dataclass
from capability_profile import scan_sources
from capability_source import python_literal_names,_tokens
from capability_fallback import _shape
from capability_c_graph import fingerprint
from capability_c_syntax import plain_definitions

@dataclass(frozen=True)
class M1Observation:
    native_tools: tuple
    resource_tools: tuple
    checked_functions: int
    blockers: tuple
    client_delivery_verified: bool=False
    runtime_receiver_verified: bool=False
    native_execution_verified: bool=False
    policy_satisfied: bool=False


def _functions(tree):
    result={}
    def walk(nodes,prefix=''):
        for n in nodes:
            if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
                key=prefix+n.name
                if key in result:raise ValueError('M1_DUPLICATE_FUNCTION')
                result[key]=n
            elif isinstance(n,ast.ClassDef):walk(n.body,prefix+n.name+'.')
    walk(tree.body);return result


def inspect_m1(sources,model):
    scan_sources(sources,());files={f.path:f for f in sources};errors=[];trees={};checked=0
    for path,digest in model['pins']:
        f=files.get(path)
        if f is None or f.sha256!=digest:errors.append(('M1_SOURCE_MISSING_OR_DRIFT',path));continue
        if path.endswith('.py'):trees[path]=ast.parse(f.data)
    for path,name,shape in model['functions']:
        try:
            n=_functions(trees[path])[name]
            if fingerprint(_shape(n))!=shape:raise ValueError('M1_FUNCTION_STRUCTURE_CHANGED')
            checked+=1
        except (KeyError,ValueError) as e:errors.append(('M1_FUNCTION_UNVERIFIED',(path,name,str(e))))
    # Independent guard expressions, not just a source/AST re-pin.
    required=(
      ('tools/integration_reads.py','request','c.require(value.get("operation") == operation, "READ_OPERATION_REQUIRED")'),
      ('tools/integration_reads.py','read','c.require(c.encoded(before) == c.encoded(after), "OBSERVATION_STALE")'),
      ('tools/integration_read_resources.py','Resources.__init__','c.require(approve_resources is True, "OWNER_READ_RESOURCE_APPROVAL_REQUIRED")'),
      ('tools/integration_read_resources.py','Resources.current','c.require(c.sha(raw) == self.digest, "READ_RESOURCE_POLICY_CHANGED")'),
      ('tools/integration_read_resources.py','Resources.current','c.require(value["transfer_policy_sha256"] == self.transfer.digest, "READ_RESOURCE_TRANSFER_BINDING")'),
      ('tools/integration_read_resources.py','Resources.current','c.require(value["producer"] == producer(), "READ_RESOURCE_PRODUCER_CHANGED")'),
      ('tools/integration_read_resources.py','pinned_bytes','c.require(c.sha(data) == digest, "READ_RESOURCE_DIGEST")'),
      ('tools/integration_read_resources.py','read','c.require(service.resources is not None, "READ_RESOURCE_POLICY_REQUIRED")'),
    )
    for path,name,expression in required:
        n=_functions(trees[path]).get(name) if path in trees else None
        expected=_shape(ast.parse(expression).body[0].value)
        if n is None or sum(_shape(c)==expected for c in ast.walk(n) if isinstance(c,ast.Call))!=1:errors.append(('M1_MANDATORY_GUARD_CHANGED',(path,name)))
    native=resource=()
    try:
        native=python_literal_names(files['tools/integration_reads.py'].data.decode(),'NAMES',mapping=False)
        resource=python_literal_names(files['tools/integration_read_resources.py'].data.decode(),'NAMES',mapping=False)
        allnames=python_literal_names(files['tools/integration_service.py'].data.decode(),'SCHEMAS',mapping=True)
        transfer=python_literal_names(files['tools/integration_transfer.py'].data.decode(),'NAMES',mapping=False)
        if set(allnames)!=set(transfer) or set(native)&set(resource):raise ValueError('M1_TOOL_SET_MISMATCH')
        for path,names in (('tools/integration_reads.py',native),('tools/integration_read_resources.py',resource)):
            if set(python_literal_names(files[path].data.decode(),'SCHEMAS',mapping=True))!=set(names):raise ValueError('M1_LOCAL_SCHEMA_SET')
        schema=next(n.value for n in trees['tools/integration_service.py'].body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SCHEMAS' for t in n.targets))
        for module,names in (('extended_reads',native),('read_resources',resource)):
            expected_import=_shape(ast.parse('import '+('integration_reads' if module=='extended_reads' else 'integration_read_resources')+' as '+module).body[0])
            if sum(_shape(n)==expected_import for n in trees['tools/integration_service.py'].body)!=1:raise ValueError('M1_IMPORT_BINDING')
            for name in names:
                values=[v for k,v in zip(schema.keys,schema.values) if isinstance(k,ast.Constant) and k.value==name]
                if len(values)!=1 or _shape(values[0])!=_shape(ast.parse(module+'.SCHEMAS['+repr(name)+']',mode='eval').body):raise ValueError('M1_SCHEMA_REFERENCE')
        handler=_functions(trees['tools/integration_service.py'])['Service._call_locked']
        for module,names in (('extended_reads',native),('read_resources',resource)):
            branches=[n for n in ast.walk(handler) if isinstance(n,ast.If) and isinstance(n.test,ast.Compare) and _shape(n.test.left)==_shape(ast.Name(id='name',ctx=ast.Load())) and isinstance(n.test.ops[0],ast.In) and isinstance(n.test.comparators[0],ast.Tuple) and {v.value for v in n.test.comparators[0].elts}==set(names)]
            if len(branches)!=1 or _shape(branches[0].body[0])!=_shape(ast.parse('result = '+module+'.read(self, scope, name, args)').body[0]):raise ValueError('M1_HANDLER_BINDING')
        remote=python_literal_names(files['tools/integration_gateway_contract.py'].data.decode(),'REMOTE_READ_NAMES',mapping=False)
        if set(remote)&(set(native)|set(resource)):raise ValueError('M1_REMOTE_EXPANSION')
    except (KeyError,ValueError,StopIteration,AttributeError) as e:errors.append(('M1_DOMAIN_UNVERIFIED',str(e)))
    c_anchors={
      'src/cli/completion.c':('golem_cli_completion',('bool inspect=argc==5 && !strcmp(argv[2],"inspect");','golem_document_store_open(argv[3],!check && !inspect,NULL,&s,NULL)','golem_completion_report(s,(uint32_t)n,report,&out,NULL)')),
      'src/cli/reentry.c':('golem_cli_reentry',('if(st==GOLEM_OK && call && !op) st=GOLEM_ERR_INVALID_ARGUMENT;','bool readonly=inspect || (call && op && !strcmp(op,"status"));','golem_document_store_open(argv[3],!readonly,NULL,&store,NULL)','golem_reentry_report(store,(uint32_t)seq,report,&reply,NULL)')),
    }
    for path,(name,anchors) in c_anchors.items():
        try:
            body=next(d[3] for d in plain_definitions(files[path].data.decode()) if d[0]==name)
            for text in anchors:
                t=_tokens(text)
                if sum(body[i:i+len(t)]==t for i in range(len(body)-len(t)+1))!=1:raise ValueError('M1_NATIVE_READ_FLAG_CHANGED')
        except (KeyError,ValueError,StopIteration) as e:errors.append(('M1_NATIVE_READ_UNVERIFIED',(path,str(e))))
    return M1Observation(tuple(native),tuple(resource),checked,tuple(errors))
