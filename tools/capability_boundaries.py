"""Content pins for reviewed build/package exclusions that can redirect entrypoints."""
from capability_c_graph import fingerprint
from capability_profile import scan_sources

def inspect_boundaries(sources,models):
    scan_sources(sources,());files={f.path:f for f in sources};errors=[];reviewed=[]
    for path,digest,structure in models:
        f=files.get(path)
        if f is None or f.sha256!=digest or fingerprint(f.data.decode('utf-8'))!=structure:
            errors.append(('BOUNDARY_CONTRACT_MISSING_OR_DRIFT',path))
        else:reviewed.append(path)
    return tuple(errors),tuple(reviewed)
