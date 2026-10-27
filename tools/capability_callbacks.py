"""Approved public callback declaration boundary; never receiver/authority proof."""
from dataclasses import dataclass
from capability_c_syntax import declaration_tokens
from capability_profile import _close,scan_sources,Scan,Observation
from capability_ledger import observation_identity

@dataclass(frozen=True)
class CallbackRule:
    path: str
    sha256: str
    structure: str
    field: str
    parameters: tuple
    returns: tuple=()

def declarations(raw):
    tokens=declaration_tokens(raw.decode('utf-8')); found=[];i=0
    while i<len(tokens)-3:
        if tokens[i:i+2]==('typedef','struct') and tokens[i+3:i+4]==('{',):
            end=_close(tokens,i+3);structure=tokens[i+2];body=tokens[i+4:end]
            for j in range(len(body)-4):
                if body[j:j+2]==('(','*') and body[j+3:j+5]==(')','('):
                    finish=_close(body,j+4)
                    start=j-1
                    while start>=0 and body[start]!=';':start-=1
                    returns=body[start+1:j]
                    if not returns:raise ValueError('CALLBACK_RETURN_TYPE_MISSING')
                    found.append((structure,body[j+2],returns,body[j+5:finish]))
            i=end
        i+=1
    if len(found)!=len(set((s,f) for s,f,r,p in found)):raise ValueError('CALLBACK_DECLARATION_DUPLICATE')
    return tuple(found)

def scan_callbacks(sources,rules):
    scan_sources(sources,()); files={s.path:s for s in sources};observed=[];problems=[]
    for path in sorted({r.path for r in rules}):
        if path not in files:continue
        expected=[r for r in rules if r.path==path];source=files[path]
        try:
            if any(source.sha256!=r.sha256 for r in expected):raise ValueError('CALLBACK_SOURCE_DRIFT')
            actual=declarations(source.data)
            if actual!=tuple((r.structure,r.field,r.returns,r.parameters) for r in expected):raise ValueError('CALLBACK_SET_OR_SIGNATURE_CHANGED')
            for structure,field,returns,parameters in actual:
                fields=dict(kind='C_PUBLIC_DECLARATION',source_path=path,entrypoint=structure+'.'+field,selector=None)
                observed.append(Observation(observation_identity(**fields),**fields))
        except (ValueError,UnicodeError) as error:problems.append((path,None,str(error)))
    return Scan(tuple(observed),tuple(problems))
