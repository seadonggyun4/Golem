"""Check reviewed effects against their concrete inventory facts, never infer grants."""
def inspect_effects(ledger,models):
    caps={c['id']:c for c in ledger['capabilities']};obs={o['id']:o for o in ledger['observations']};errors=[];seen=set()
    for cid,effects,routes,refs in models:
        if cid in seen:raise ValueError('DUPLICATE_EFFECT_REVIEW')
        seen.add(cid);c=caps.get(cid)
        if c is None:errors.append(('EFFECT_CAPABILITY_MISSING',cid));continue
        actual=tuple((obs[i]['source_path'],obs[i]['entrypoint'],obs[i]['selector']) for i in c['observation_ids'] if i in obs)
        if tuple(c['effects'])!=effects or tuple(c['target_routes'])!=routes or actual!=refs:
            errors.append(('EFFECT_REVIEW_MISMATCH',cid))
    for cid in caps:
        if cid.startswith(('cli.route.','cli.dispatch.','native.','operation.','surface.','m1.tool.','m2.tool.','m3.tool.','m4.tool.')) and cid not in seen:errors.append(('EFFECT_REVIEW_MISSING',cid))
    return tuple(errors)
