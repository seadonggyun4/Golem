"""Owner-local bridge to existing Installer/D5 plans. Never an MCP tool or repair loop."""
import argparse
from pathlib import Path
import sys
import integration_contract as c
import integration_registry as r
import integration_install as install
import integration_update as update
import integration_lifecycle as life

INSTALL_OPS=('install','remove','bootstrap')
MAINTENANCE_OPS=('freeze','stage','verify','switch','restore','thaw','ready')


def dispatch(kind,command,root,value,*,operation=None,reviewed_sha256=None,approve_owner=False):
    c.require(kind in ('installation','maintenance'),'OWNER_LIFECYCLE_KIND')
    c.require(command in ('schema','plan','apply','inspect'),'OWNER_LIFECYCLE_COMMAND')
    allowed=INSTALL_OPS if kind=='installation' else MAINTENANCE_OPS
    if command in ('schema','plan'):c.require(operation in allowed,'OWNER_LIFECYCLE_OPERATION')
    if command=='schema':return (install.SPECS if kind=='installation' else update.SPEC)[operation]
    if command=='apply':
        c.require(approve_owner is True,'OWNER_LIFECYCLE_APPROVAL_REQUIRED')
        c.require(isinstance(value,dict) and value.get('operation') in allowed,'OWNER_LIFECYCLE_OPERATION')
        c._validate(reviewed_sha256,c.DIGEST)
    manager=install.Installer(Path(root)) if kind=='installation' else update.Manager(r.Registry(Path(root)))
    if command=='plan':return manager.plan(operation,value)
    if command=='apply':
        if kind=='installation':return manager.apply(value,reviewed_sha256,approve_installation=True,repair=False)
        return manager.apply(value,reviewed_sha256,approve_maintenance=True)
    c._validate(value,install.REFERENCE if kind=='installation' else c.obj({'project_id':c.ID}))
    if kind=='installation':return manager.inspect(value['installation_id'])
    with manager.registry.locked():
        return {'lifecycle':life.current(manager.registry,value['project_id'])[0],'native_state_changed':False,
                'activation':'NOT_DETERMINED_BY_INSPECTION'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('schema','plan','apply','inspect'))
    parser.add_argument('--kind',choices=('installation','maintenance'),required=True)
    parser.add_argument('--operation');parser.add_argument('--root',type=Path);parser.add_argument('--input',type=Path)
    parser.add_argument('--reviewed-plan-sha256');parser.add_argument('--approve-owner',action='store_true');args=parser.parse_args()
    try:
        if args.command!='schema':c.require(args.root is not None and args.input is not None,'OWNER_LIFECYCLE_INPUT_REQUIRED')
        value=c.decode(r.regular(args.input,private=True)) if args.input else None
        result=dispatch(args.kind,args.command,args.root,value,operation=args.operation,
            reviewed_sha256=args.reviewed_plan_sha256,approve_owner=args.approve_owner)
        sys.stdout.buffer.write(c.encoded(result));return 0
    except (c.IntegrationError,OSError,ValueError,KeyError,TypeError) as error:
        sys.stderr.write(c.encoded({'state':'BLOCKED_OR_PARTIAL','code':getattr(error,'code','OWNER_LIFECYCLE_INVALID'),
            'automatic_retry_allowed':False,'next_operation':'REVIEW_ORIGINAL_INSTALL_OR_D5_RECORD_NO_AUTOMATIC_REPAIR'}).decode());return 1


if __name__=='__main__':sys.exit(main())
