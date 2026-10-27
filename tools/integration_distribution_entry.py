"""Opt-in feature package entry. Reuses D2/D4 services and owner contracts."""
import argparse
import asyncio
from contextlib import ExitStack
import os
from pathlib import Path
import sys
import time
import integration_contract as c
import integration_feature_profiles as profiles
import integration_transfer as transfer
import integration_service as reads
import integration_mutation_contract as actions
import integration_mutations as mutations
import integration_read_resources as resources
import integration_helper_contract as helpers
import integration_parallel_hosts as hosts
import integration_mcp as readonly
import integration_mutation_mcp as mutation_mcp
import integration_mcpb_entry as setup
import integration_lifecycle as lifecycle

STARTUP_WAIT_SECONDS = 5


def _startup_pause(error, deadline):
    """Only admission contention before the MCP server accepts any requests."""
    if error.code != 'REGISTRY_BUSY' or time.monotonic() >= deadline:
        raise error
    time.sleep(0.05)


def _configure_startup(args):
    deadline = time.monotonic() + STARTUP_WAIT_SECONDS
    while True:
        try:
            return configure(**args)
        except c.IntegrationError as error:
            _startup_pause(error, deadline)


def configure(profile,policy,digest,*,approve_owner=False,resource=None,resource_digest=None,approve_resources=False,
              helper=None,helper_digest=None,approve_helpers=False,host=None,host_digest=None,approve_host=False):
    spec=profiles.definition(profile)
    c.require(approve_owner is True,'OWNER_PROFILE_APPROVAL_REQUIRED')
    c._validate(digest,c.DIGEST)
    c.require(bool(resource)==bool(resource_digest)==bool(approve_resources),'READ_RESOURCE_OWNER_ARGUMENTS')
    c.require(bool(helper)==bool(helper_digest)==bool(approve_helpers),'HELPER_OWNER_ARGUMENTS')
    c.require(bool(host)==bool(host_digest)==bool(approve_host),'PARALLEL_HOST_OWNER_ARGUMENTS')
    c.require(not helper or profile=='quality','FEATURE_HELPER_SCOPE')
    c.require(not host or profile=='parallel','FEATURE_HOST_SCOPE')
    if spec['family']=='D2':
        owner=transfer.Transfer(Path(policy),digest,approve_data_transfer=True)
        selected=resources.Resources(Path(resource),resource_digest,owner,approve_resources=True) if resource else None
        service=reads.Service(owner,selected)
    else:
        owner=actions.Policy(Path(policy),digest,approve_mutations=True)
        selected=resources.Resources(Path(resource),resource_digest,owner.transfer,approve_resources=True) if resource else None
        helper_contract=helpers.Helpers(Path(helper),helper_digest,owner,approve_helpers=True) if helper else None
        host_contract=hosts.Hosts(Path(host),host_digest,owner,approve_hosts=True) if host else None
        service=mutations.Service(owner,selected,helper_contract,host_contract)
    return profiles.Scoped(service,profile),owner


def environment():
    def value(name):return os.environ.get('GOLEM_'+name,'')
    def approved(name):return value(name).lower()=='true'
    def optional(name,key):
        raw=value(name)
        # Claude retains this exact template for an unset optional field.
        # Consent and concrete paths still go through configure's triple check.
        return None if raw in ('','${user_config.'+key+'}') else raw
    return dict(profile=value('FEATURE_PROFILE'),policy=value('PROFILE_POLICY'),digest=value('PROFILE_POLICY_SHA256'),
      approve_owner=approved('APPROVE_PROFILE_OWNER'),resource=optional('RESOURCE_POLICY','resource_policy'),
      resource_digest=optional('RESOURCE_SHA256','resource_sha256'),approve_resources=approved('APPROVE_RESOURCES'),
      helper=optional('HELPER_POLICY','helper_policy'),helper_digest=optional('HELPER_SHA256','helper_sha256'),approve_helpers=approved('APPROVE_HELPERS'),
      host=optional('HOST_POLICY','host_policy'),host_digest=optional('HOST_SHA256','host_sha256'),approve_host=approved('APPROVE_HOST'))


async def serve(service,owner):
    if service.profile['family']=='D2':await readonly.run(service)
    else:
        bindings=[scope['binding'] for scope in owner.transfer.value['scopes']]
        with ExitStack() as startup:
            deadline = time.monotonic() + STARTUP_WAIT_SECONDS
            while True:
                try:
                    startup.enter_context(lifecycle.participation(owner.registry,bindings))
                    break
                except c.IntegrationError as error:
                    _startup_pause(error, deadline)
            # No request handler or native action is inside the admission loop.
            await mutation_mcp.run(service)


def main():
    try:
        if len(sys.argv)>1:
            parser=argparse.ArgumentParser(description=__doc__)
            parser.add_argument('--profile',choices=profiles.NAMES,required=True)
            parser.add_argument('--policy',required=True);parser.add_argument('--reviewed-policy-sha256',dest='digest',required=True)
            parser.add_argument('--approve-owner',action='store_true')
            for field in ('resource','helper','host'):
                parser.add_argument('--'+field+'-policy',dest=field)
                parser.add_argument('--reviewed-'+field+'-sha256',dest=field+'_digest')
            parser.add_argument('--approve-resources',action='store_true');parser.add_argument('--approve-helpers',action='store_true');parser.add_argument('--approve-host',action='store_true')
            args=vars(parser.parse_args())
        else:args=environment()
        try:service,owner=_configure_startup(args)
        except (c.IntegrationError,OSError,ValueError):
            asyncio.run(setup.run_setup(setup.setup_notice('SETUP_VALIDATION_FAILED')));return 0
        asyncio.run(serve(service,owner));return 0
    except (c.IntegrationError,OSError,ValueError) as error:
        sys.stderr.write(c.encoded({'state':'SETUP_REQUIRED','code':getattr(error,'code','INVALID_PROFILE'),
            'automatic_retry_allowed':False,'execution_authorized':False}).decode());return 1


if __name__=='__main__':sys.exit(main())
