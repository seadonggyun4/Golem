"""Reviewed renderer boundaries: architecture tripwire, not arbitrary-code proof.

C references include definitions; runtime tests enforce the conditional paths.
Python uses its AST so comments/docstrings do not affect call inventory.
"""
import ast
from collections import Counter
from pathlib import Path
import re
import sys

ROOT = Path(sys.argv[1])
EXPECTED = {
    'reentry/store.c': {'re_markdown': 3, 'golem_reentry_report': 1},
    'completion/evaluator.c': {'co_markdown': 1, 'rc_markdown': 1, 'co_markdown_v1': 1},
    'completion/predicate_roles.c': {'rc_markdown': 1},
    'completion/renderer_v1.c': {'co_markdown_v1': 1},
    'completion/store.c': {'co_markdown': 2},
    'completion/report.c': {'golem_completion_report': 1},
    'research/report.c': {'rs_markdown': 1},
    'research/store.c': {'golem_research_report': 1, 'rs_markdown': 1},
    'research/metrics_report.c': {'golem_research_metrics_report': 1},
    'execution/report.c': {'golem_execution_render': 1},
    'execution/proof_pack.c': {'golem_proof_render': 2},
    'discovery/report.c': {'golem_discovery_report': 1},
    'workflow/context_projection.c': {'golem_context_render': 1},
    'cli/completion.c': {'golem_completion_report': 1},
    'cli/reentry.c': {'golem_reentry_report': 1},
    'cli/research.c': {'golem_research_report': 1, 'golem_research_metrics_report': 1},
    'cli/execution.c': {'golem_execution_render': 1},
    'cli/proof.c': {'golem_proof_render': 1},
    'cli/discovery.c': {'golem_discovery_report': 2},
    'cli/context.c': {'golem_context_render': 1},
}
names = {name for references in EXPECTED.values() for name in references}
pattern = re.compile(r'\b(' + '|'.join(sorted(names)) + r')\s*\(')
observed = {}
for path in (ROOT / 'src').rglob('*.c'):
    found = dict(Counter(pattern.findall(path.read_text())))
    if found:
        observed[path.relative_to(ROOT / 'src').as_posix()] = found
if observed != EXPECTED:
    raise AssertionError(f'Renderer boundaries changed; review timing policy: {observed!r}')

expected_python = {'agent_io.py': {'report': 1},
                   'verify_agent.py': {'render_report': 2, 'write_report': 1}}
observed_python = {}
for path in (ROOT / 'tools').glob('*.py'):
    if path.name.startswith('test_'):
        continue
    found = Counter(node.func.id for node in ast.walk(ast.parse(path.read_text()))
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id in ('report', 'render_report', 'write_report'))
    if found:
        observed_python[path.name] = dict(found)
if observed_python != expected_python:
    raise AssertionError(f'Python report boundaries changed: {observed_python!r}')
print('Reviewed reporting boundaries match; gate evidence remains mandatory')
