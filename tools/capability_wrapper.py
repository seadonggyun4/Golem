"""Reviewed token models of the three supported recorder macros.

These are independent expected shapes, not learned from the source being
checked. Whitespace/comments may vary; any semantic token change needs review.
No C preprocessor or inspected code is executed.
"""
from capability_source import _tokens, ExtractionError

_START = '''int gr_errno = errno;
    golem_record *gr_scope = NULL;'''
_BODY = '''gr_errno = errno;
    gr_status = gr_api_finish(#name, gr_scope, gr_status, diagnostic);
    errno = gr_errno;
    return gr_status;'''
MODELS = {
    'GOLEM_RECORDED_API': '''#define GOLEM_RECORDED_API(name, parameters, arguments, diagnostic)
        static golem_status name##_recorded_body parameters;
        golem_status name parameters {''' + _START + '''
        golem_status gr_status = gr_api_begin(#name, &gr_scope, diagnostic);
        errno = gr_errno;
        if (gr_status != GOLEM_OK) return gr_status;
        gr_status = name##_recorded_body arguments;''' + _BODY + '''}
        static golem_status name##_recorded_body parameters''',
    'GOLEM_RECORDED_REQUIRED_API': '''#define GOLEM_RECORDED_REQUIRED_API(name, parameters, arguments)
        static golem_status name##_recorded_body parameters;
        golem_status name parameters {''' + _START + '''
        golem_status gr_started = gr_api_begin(#name, &gr_scope, NULL);
        errno = gr_errno;
        golem_status gr_status = name##_recorded_body arguments;
        gr_errno = errno;
        gr_status = gr_api_finish_required(#name, gr_scope, gr_started, gr_status);
        errno = gr_errno;
        return gr_status; }
        static golem_status name##_recorded_body parameters''',
    'GOLEM_RECORDED_RELEASE_API': '''#define GOLEM_RECORDED_RELEASE_API(name, parameters, arguments)
        static void name##_recorded_body parameters;
        void name parameters {''' + _START + '''
        golem_status gr_started = gr_api_begin(#name, &gr_scope, NULL);
        errno = gr_errno;
        name##_recorded_body arguments;
        gr_errno = errno;
        (void)gr_api_finish_required(#name, gr_scope, gr_started, GOLEM_OK);
        errno = gr_errno; }
        static void name##_recorded_body parameters''',
}


def verify_definition(raw, macro):
    if macro not in MODELS:
        raise ExtractionError('WRAPPER_UNSUPPORTED')
    # Line splicing is supported only for these named definitions. We do not
    # expand arbitrary macros or decide preprocessor conditional truth.
    source = raw.decode('utf-8')
    definitions, current = [], ''
    for line in source.splitlines():
        if current or line.lstrip().startswith('#'):
            current += line.rstrip().removesuffix('\\') + '\n'
            if not line.rstrip().endswith('\\'):
                tokens = _tokens(current)
                if tokens[:3] == ('#', 'define', macro):
                    definitions.append(tokens)
                elif macro in tokens:
                    raise ExtractionError('WRAPPER_DEFINITION_UNSUPPORTED')
                current = ''
    if current or definitions != [_tokens(MODELS[macro])]:
        raise ExtractionError('WRAPPER_DEFINITION_UNSUPPORTED')
