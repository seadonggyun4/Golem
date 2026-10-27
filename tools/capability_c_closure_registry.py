"""Reviewed events dispatcher and diagnostic helper closure, no runtime refresh."""
from capability_c_closure import ScopeRule,NativeBoundary
ERROR_NOTE=ScopeRule('src/cli/error.c','f1006389b6eb215075a34c33c35163a6898263b49e7d721bb0dbab14cf7c7724','cli_error_note',None,(),('strcmp',),('strcmp',),(),())
EVENTS=ScopeRule(
'src/cli/events.c','1e9d4eeed41ac281833cdda7a15cc5a3a2600d7b7521e3dba3b008923d9496e9','golem_cli_events','argv[3]',('--jsonl','--otlp','--prov'),
('cli_error_note', 'fflush', 'fprintf', 'free', 'fwrite', 'golem_runtime_cursor_parse', 'golem_runtime_events_export', 'golem_runtime_events_snapshot', 'golem_status_string', 'malloc', 'strcmp', 'strlen'),('strcmp', 'strlen', 'malloc', 'fwrite', 'fflush', 'free', 'fprintf'), (
NativeBoundary('golem_runtime_cursor_parse','include/golem/runtime_event.h','15ef93cb0887c322d1de0b33614951830d75b9ab35ad9ab51dc61a54e8e02e85','native.golem_runtime_cursor_parse'),
NativeBoundary('golem_runtime_events_snapshot','include/golem/runtime_event.h','15ef93cb0887c322d1de0b33614951830d75b9ab35ad9ab51dc61a54e8e02e85','native.golem_runtime_events_snapshot'),
NativeBoundary('golem_runtime_events_export','include/golem/runtime_event.h','15ef93cb0887c322d1de0b33614951830d75b9ab35ad9ab51dc61a54e8e02e85','native.golem_runtime_events_export'),
NativeBoundary('golem_status_string','include/golem/error.h','98b921c0c050addbfe3b65e50e2c3dd3e85a2031939546681c50bf95eeb2e573','native.golem_status_string'),
),(ERROR_NOTE,))
