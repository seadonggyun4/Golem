"""Offline synthetic receipts only; no installed client, model, or Work calls."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import integration_stable_observation as observation


PREFIX = 'mcp__golem_local__'
THREAD = 'fixture-thread'
TURN = 'fixture-turn'
NAMES = ['golem_action_prepare','golem_noop']


class Receipt(unittest.TestCase):
    def setUp(self):
        definitions = [{'name':name,'description':'Fixture only.','inputSchema':{
            'type':'object','properties':{},'additionalProperties':False}} for name in NAMES]
        catalog = {'schema':observation.readiness.FRONTEND_ABI,'profile':'task',
            'tools':definitions,'tools_sha256':observation.digest(observation.encoded(definitions))}
        self.catalog = observation.encoded(catalog)
        self.catalog_pin = observation.digest(self.catalog)
        self.marker = 'golem-catalog-v2:'+('a'*32)+':'+self.catalog_pin+':'+('b'*32)
        self.metadata = {'schema':observation.METADATA_SCHEMA,'entries':[
            {'name':PREFIX+name,'description':observation.MARKER_LINE+' '+self.marker if i==0 else ''}
            for i,name in enumerate(NAMES)]}
        def row(kind,payload,second):
            return {'timestamp':f'2026-11-12T10:00:{second:02d}.123Z','type':kind,'payload':payload}
        meta = {'turn_id':TURN,'create_time':1794477601.123}
        self.rows = [
            row('session_meta',{'id':THREAD,'source':'vscode'},0),
            row('event_msg',{'type':'task_started','turn_id':TURN,'root_turn_id':'root'},1),
            row('turn_context',{'turn_id':TURN,'model':'fixture'},1),
            row('response_item',{'type':'function_call_output','name':'send_message_to_thread',
                'namespace':'codex_app','output':[],'internal_chat_message_metadata_passthrough':meta},1),
            row('response_item',{'type':'custom_tool_call','name':'exec','status':'completed',
                'call_id':'call_fixture','input':observation.metadata_script(PREFIX),
                'internal_chat_message_metadata_passthrough':meta},2),
            row('response_item',{'type':'custom_tool_call_output','call_id':'call_fixture',
                'output':[{'type':'input_text','text':'Script completed\nWall time 0.0 seconds\nOutput:\n'},
                          {'type':'input_text','text':json.dumps(self.metadata)}],
                'internal_chat_message_metadata_passthrough':meta},3),
            row('response_item',{'type':'message','role':'assistant','content':[
                {'type':'output_text','text':'MISLEADING FINAL: golem_nop, not evidence'}]},4),
            row('event_msg',{'type':'task_complete','turn_id':TURN,'root_turn_id':'root'},4)]
        self.floor = observation._utc('2026-11-12T10:00:00Z')
        self.now = observation._utc('2026-11-12T10:00:05Z')

    def raw(self, rows=None):
        return b''.join(observation.encoded(r) for r in self.rows if r) if rows is None else b''.join(
            observation.encoded(r) for r in rows if r)

    def collect(self, rows=None, raw=None, **changes):
        raw = self.raw(rows) if raw is None else raw
        args = dict(trace_sha256=observation.digest(raw),catalog_sha256=self.catalog_pin,
            thread_id=THREAD,turn_id=TURN,server_name='golem_local',prefix=PREFIX,
            started_not_before_ns=self.floor,now_ns=self.now)
        args.update(changes)
        return observation.collect(raw,self.catalog,**args)

    def blocked(self, code, rows=None, raw=None, **changes):
        with self.assertRaisesRegex(observation.ObservationError,'^'+code+'$'):
            self.collect(rows,raw,**changes)

    def update_metadata(self, value):
        rows=copy.deepcopy(self.rows);rows[5]['payload']['output'][1]['text']=json.dumps(value)
        return rows

    def exec_declaration(self):
        # Synthetic shape of a pre-context declaration, not a copied rollout.
        # Its text is deliberately unrelated to the accepted metadata receipt.
        return {'timestamp':self.rows[1]['timestamp'],'type':'response_item','payload':{
            'type':'additional_tools','id':'at_fixture','role':'developer','tools':[
                {'type':'namespace','name':'functions','description':'DECLARATION_ONLY_SENTINEL',
                 'tools':[{'type':'custom','name':'exec','description':'DECLARATION_ONLY_SENTINEL',
                           'format':{'type':'grammar','syntax':'lark','definition':'start: /fixture/'}}]}]}}

    def with_exec_declaration(self, declaration=None):
        rows=copy.deepcopy(self.rows)
        rows.insert(2,self.exec_declaration() if declaration is None else declaration)
        return rows

    def test_pre_context_exec_declaration_is_not_a_tool_call_or_receipt(self):
        expected,_=self.collect()
        result,proof=self.collect(self.with_exec_declaration())
        self.assertEqual(result,expected)
        self.assertEqual(proof['call_id'],'call_fixture')
        self.assertFalse(proof['execution_authorized'])
        self.assertEqual(proof['actual_execution'],'HOLD')
        self.assertEqual([r['kind'] for r in proof['source_records']].count('additional_tools'),1)
        self.assertNotIn(b'DECLARATION_ONLY_SENTINEL',observation.encoded(proof))

    def test_exec_declaration_cannot_replace_actual_metadata_receipt(self):
        rows=self.with_exec_declaration()
        rows=[row for row in rows if row['payload'].get('type') not in
              ('custom_tool_call','custom_tool_call_output','task_complete')]
        self.blocked('MISSING_MACHINE_RECEIPT',rows)

    def test_exec_declaration_does_not_exempt_an_actual_action_call(self):
        rows=self.with_exec_declaration()
        rows.insert(7,{'type':'response_item','timestamp':self.rows[5]['timestamp'],
                      'payload':{'type':'function_call','name':PREFIX+'golem_noop'}})
        self.blocked('NON_METADATA_TOOL_CALL',rows)

    def test_unknown_or_action_shaped_additional_tools_envelope_is_rejected(self):
        for change in ({'role':'assistant'},{'call_id':'call_disguised'},
                       {'input':'await tools.golem_noop({});'},
                       {'id':None},{'tools':[]},{'tools':'not declarations'}):
            with self.subTest(change=change):
                row=self.exec_declaration();row['payload'].update(change)
                self.blocked('NON_METADATA_TOOL_CALL',self.with_exec_declaration(row))

    def test_only_the_observed_functions_exec_declaration_shape_is_accepted(self):
        changes=[('namespace',{'name':'other'}),('namespace',{'type':'function_call'}),
                 ('namespace',{'arguments':{}}),('exec',{'type':'function_call'}),
                 ('exec',{'name':'golem_noop'}),('exec',{'call_id':'call_disguised'}),
                 ('exec',{'description':None}),('format',{'syntax':'javascript'}),
                 ('format',{'type':'text'}),('format',{'definition':None})]
        for target,change in changes:
            with self.subTest(target=target,change=change):
                row=self.exec_declaration();namespace=row['payload']['tools'][0]
                entry=namespace['tools'][0]
                {'namespace':namespace,'exec':entry,'format':entry['format']}[target].update(change)
                self.blocked('NON_METADATA_TOOL_CALL',self.with_exec_declaration(row))
        row=self.exec_declaration();row['payload']['tools'][0]['tools']*=2
        self.blocked('NON_METADATA_TOOL_CALL',self.with_exec_declaration(row))
        row=self.exec_declaration();row['payload']['tools']*=2
        self.blocked('NON_METADATA_TOOL_CALL',self.with_exec_declaration(row))

    def test_duplicate_or_late_exec_declaration_is_rejected(self):
        rows=self.with_exec_declaration();rows.insert(3,self.exec_declaration())
        self.blocked('NON_METADATA_TOOL_CALL',rows)
        for index in (3,5,6):
            with self.subTest(index=index):
                rows=copy.deepcopy(self.rows);row=self.exec_declaration()
                row['timestamp']=rows[index-1]['timestamp'];rows.insert(index,row)
                self.blocked('NON_METADATA_TOOL_CALL',rows)

    def test_exact_receipt_preserves_original_timestamp_and_no_authority(self):
        result, proof=self.collect()
        self.assertEqual(result['tools'],NAMES)
        self.assertEqual(result['marker'],self.marker)
        self.assertEqual(result['observed_at_ns'],observation._utc(self.rows[5]['timestamp']))
        self.assertNotEqual(result['observed_at_ns'],self.now)
        self.assertEqual(proof['observation_sha256'],observation.digest(observation.encoded(result)))
        self.assertEqual(proof['tool_count'],len(NAMES))
        self.assertFalse(proof['full_input_schema_delivery_verified'])
        self.assertFalse(proof['execution_authorized']);self.assertFalse(proof['agent_final_used'])
        self.assertFalse(proof['automatic_retry_allowed']);self.assertEqual(proof['actual_execution'],'HOLD')
        self.assertEqual([x['kind'] for x in proof['source_records']],
            ['task_started','turn_context','custom_tool_call','custom_tool_call_output','task_complete'])

    def test_exact_code_matches_reviewed_prompt_and_trailing_whitespace_only(self):
        code=observation.metadata_script(PREFIX)
        self.assertEqual(code,"const selected = ALL_TOOLS.filter(t => t.name.startsWith('mcp__golem_local__'));\n"
            "text({schema:'golem.external-tool-metadata.v1',entries:selected.map(t => ({name:t.name,description:t.description.split('\\n').filter(line => line.startsWith('Fixed catalog observation only; no authority:')).join('\\n')}))});")
        self.assertIn("ALL_TOOLS.filter(t => t.name.startsWith('mcp__golem_local__'))",code)
        self.assertNotIn('tools.',code)
        rows=copy.deepcopy(self.rows);rows[4]['payload']['input']='\n'+code.replace('\n','  \n')+'\n'
        self.collect(rows)

    def test_forged_text_output_with_hardcoded_script_is_rejected(self):
        for code in ('text('+json.dumps(self.metadata)+');',
                     observation.metadata_script(PREFIX)+'\nawait tools.golem_noop({});',
                     observation.metadata_script(PREFIX).replace('ALL_TOOLS','invented')):
            rows=copy.deepcopy(self.rows);rows[4]['payload']['input']=code
            self.blocked('METADATA_SCRIPT_MISMATCH',rows)

    def test_agent_final_or_read_thread_is_not_a_machine_receipt(self):
        self.blocked('MISSING_MACHINE_RECEIPT',rows=[r for i,r in enumerate(self.rows) if i not in (4,5,7)])
        raw=observation.encoded({'thread':{'id':THREAD,'turns':[{'id':TURN,'items':[
            {'type':'agentMessage','text':json.dumps(self.metadata)}]}]}})
        self.blocked('MISSING_MACHINE_RECEIPT',raw=raw,input_format='read-thread')

    def test_no_claude_or_generic_importer(self):
        self.blocked('UNSUPPORTED_TRACE_FORMAT',input_format='claude-transcript')

    def test_full_inventory_does_not_correct_nop_to_noop(self):
        value=copy.deepcopy(self.metadata);value['entries'][1]['name']=PREFIX+'golem_nop'
        self.blocked('MODEL_FULL_TOOL_INVENTORY_MISMATCH',self.update_metadata(value))

    def test_missing_extra_duplicate_and_same_count_substitutes_block(self):
        for entries in (self.metadata['entries'][:1],self.metadata['entries']*2,
                        self.metadata['entries']+[{'name':PREFIX+'golem_unknown','description':''}],
                        [self.metadata['entries'][0],{'name':PREFIX+'golem_other','description':''}]):
            value={**self.metadata,'entries':entries}
            self.blocked('MODEL_FULL_TOOL_INVENTORY_MISMATCH',self.update_metadata(value))

    def test_observed_order_can_differ_without_inventing_entries(self):
        value={**self.metadata,'entries':list(reversed(self.metadata['entries']))}
        result,_=self.collect(self.update_metadata(value));self.assertEqual(result['tools'],NAMES)

    def test_deferred_names_without_marker_do_not_qualify(self):
        value=copy.deepcopy(self.metadata);value['entries'][0]['description']=''
        self.blocked('EXACT_DEFINITION_MARKER_REQUIRED',self.update_metadata(value))

    def test_wrong_catalog_mixed_marker_and_non_marker_description_block(self):
        for description in (observation.MARKER_LINE+' '+self.marker.replace(self.catalog_pin,'c'*64),
                            observation.MARKER_LINE+' '+self.marker+'\n'+observation.MARKER_LINE+' '+self.marker):
            value=copy.deepcopy(self.metadata);value['entries'][0]['description']=description
            self.blocked('MARKER_CATALOG_MISMATCH',self.update_metadata(value))
        value=copy.deepcopy(self.metadata);value['entries'][1]['description']=observation.MARKER_LINE+' '+self.marker
        self.blocked('MARKER_TOOL_MISMATCH',self.update_metadata(value))
        value=copy.deepcopy(self.metadata);value['entries'][0]['description']='model says '+self.marker
        self.blocked('MARKER_LINE_INVALID',self.update_metadata(value))

    def test_mixed_server_or_namespace_alias_is_not_normalized(self):
        for name in ('mcp__other__golem_noop','functions.mcp__golem_local__golem_noop'):
            value=copy.deepcopy(self.metadata);value['entries'][1]['name']=name
            self.blocked('METADATA_SERVER_OR_ENTRY_MISMATCH',self.update_metadata(value))

    def test_extra_exec_and_action_calls_are_rejected(self):
        rows=copy.deepcopy(self.rows);rows.insert(6,copy.deepcopy(rows[4]))
        self.blocked('SINGLE_METADATA_EXEC_REQUIRED',rows)
        rows=copy.deepcopy(self.rows);rows.insert(6,{'type':'response_item','timestamp':rows[5]['timestamp'],
            'payload':{'type':'function_call','name':PREFIX+'golem_noop'}})
        self.blocked('NON_METADATA_TOOL_CALL',rows)

    def test_wrong_call_id_duplicate_output_and_mixed_turn_receipt_block(self):
        rows=copy.deepcopy(self.rows);rows[5]['payload']['call_id']='another'
        self.blocked('MISSING_OR_DUPLICATE_MACHINE_RECEIPT',rows)
        rows=copy.deepcopy(self.rows);rows.insert(6,copy.deepcopy(rows[5]))
        self.blocked('MISSING_OR_DUPLICATE_MACHINE_RECEIPT',rows)
        rows=copy.deepcopy(self.rows);rows[5]['payload']['internal_chat_message_metadata_passthrough']['turn_id']='other'
        self.blocked('RECEIPT_TURN_MISMATCH',rows)

    def test_injected_dispatch_result_is_not_a_general_call_exception(self):
        for change in ({'name':'golem_noop'},{'namespace':'other'},{'call_id':'paired-call'}):
            rows=copy.deepcopy(self.rows);rows[3]['payload'].update(change)
            self.blocked('NON_METADATA_TOOL_CALL',rows)

    def test_malformed_truncated_and_multiple_structured_outputs_block(self):
        rows=copy.deepcopy(self.rows);rows[5]['payload']['output'][1]['text']='{"schema":'
        self.blocked('MALFORMED_OR_TRUNCATED_JSON',rows)
        rows=copy.deepcopy(self.rows);rows[5]['payload']['output']*=2
        self.blocked('SINGLE_STRUCTURED_OUTPUT_REQUIRED',rows)
        rows=copy.deepcopy(self.rows);rows[5]['payload']['output'][0]['text']='Script failed\n'
        self.blocked('EXEC_NOT_COMPLETED',rows)
        self.blocked('TRUNCATED_ROLLOUT',raw=self.raw()[:-1])

    def test_duplicate_json_keys_and_output_unknown_fields_block(self):
        rows=copy.deepcopy(self.rows);rows[5]['payload']['output'][1]['text']='{"schema":1,"schema":2}'
        self.blocked('DUPLICATE_JSON_FIELD',rows)
        value={**self.metadata,'trusted':True}
        self.blocked('METADATA_FORMAT',self.update_metadata(value))

    def test_nonfinite_and_nonencodable_catalog_are_blocked(self):
        for raw in (b'{"not-finite":1e400}\n',b'{"bad":"\\ud800"}\n'):
            with self.assertRaisesRegex(observation.ObservationError,'CANONICAL_JSON_REQUIRED'):
                observation._catalog(raw,observation.digest(raw))

    def test_stale_future_and_before_selected_start_are_rejected(self):
        self.blocked('MODEL_OBSERVATION_STALE_OR_UNDATED',now_ns=self.now+301*10**9)
        self.blocked('TURN_TIMESTAMP_ORDER',now_ns=self.floor+2*10**9)
        self.blocked('TURN_OUTSIDE_SELECTED_WINDOW',started_not_before_ns=self.floor+2*10**9)

    def test_missing_context_completion_and_interrupted_target_block(self):
        rows=copy.deepcopy(self.rows);rows[2]=None
        self.blocked('TURN_CONTEXT_MISSING',rows)
        self.blocked('MISSING_MACHINE_RECEIPT',rows=self.rows[:-1])
        rows=copy.deepcopy(self.rows);rows[7]['payload']['type']='turn_aborted'
        self.blocked('TURN_NOT_COMPLETED',rows)
        rows=copy.deepcopy(self.rows);rows.insert(6,{'type':'event_msg','timestamp':rows[5]['timestamp'],
            'payload':{'type':'task_started','turn_id':'other'}})
        self.blocked('MIXED_OR_INCOMPLETE_TURN',rows)

    def test_other_turn_and_reasoning_content_are_not_extracted(self):
        rows=copy.deepcopy(self.rows)
        rows.insert(4,{'type':'response_item','timestamp':rows[2]['timestamp'],
            'payload':{'type':'reasoning','text':'PRIVATE_REASONING_SENTINEL'}})
        rows.extend([{'type':'event_msg','timestamp':'2026-11-12T10:00:06Z',
                      'payload':{'type':'task_started','turn_id':'another-turn'}},
                     {'type':'response_item','timestamp':'2026-11-12T10:00:07Z',
                      'payload':{'type':'function_call','name':'PRIVATE_OTHER_TURN_SENTINEL'}}])
        value,proof=self.collect(rows)
        output=observation.encoded(value)+observation.encoded(proof)
        self.assertNotIn(b'PRIVATE_',output);self.assertNotIn(b'MISLEADING',output)

    def test_trace_and_catalog_pins_are_exact(self):
        self.blocked('TRACE_PIN_OR_LIMIT',trace_sha256='0'*64)
        self.blocked('CATALOG_PIN_MISMATCH',catalog_sha256='0'*64)
        self.blocked('TRACE_THREAD_MISMATCH',thread_id='other')

    def test_only_original_receipt_time_changes_freshness(self):
        value,proof=self.collect()
        later,_=self.collect(now_ns=self.now+100*10**9)
        self.assertEqual(later,value)
        self.assertEqual(proof['original_observed_at_ns'],value['observed_at_ns'])

    def test_private_output_is_new_only_and_source_bytes_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();source=root/'rollout.jsonl';raw=self.raw();source.write_bytes(raw)
            source.chmod(0o644)
            self.assertEqual(observation.read_pinned(source,observation.digest(raw),len(raw)),raw)
            value,proof=self.collect();out=root/'output'
            observation.write_result(out,value,proof)
            self.assertEqual((out/'observation.json').read_bytes(),observation.encoded(value))
            self.assertEqual((out/'observation.json').stat().st_mode & 0o777,0o600)
            self.assertEqual(out.stat().st_mode & 0o777,0o700)
            with self.assertRaises(FileExistsError):observation.write_result(out,value,proof)
            self.assertEqual(source.read_bytes(),raw);self.assertEqual(source.stat().st_mode & 0o777,0o644)

    def test_unpinned_writable_symlink_and_partial_outputs_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();source=root/'source';source.write_bytes(b'abc');source.chmod(0o600)
            with self.assertRaisesRegex(observation.ObservationError,'PIN_MISMATCH'):
                observation.read_pinned(source,'0'*64,10)
            link=root/'link';link.symlink_to(source)
            with self.assertRaisesRegex(observation.ObservationError,'UNSAFE_INPUT_PATH'):
                observation.read_pinned(link,observation.digest(b'abc'),10)
            source.chmod(0o666)
            with self.assertRaisesRegex(observation.ObservationError,'UNSAFE_INPUT_FILE'):
                observation.read_pinned(source,observation.digest(b'abc'),10)
            value,proof=self.collect();out=root/'partial'
            with patch.object(observation.os,'fsync',side_effect=OSError('fixture full disk')):
                with self.assertRaises(OSError):observation.write_result(out,value,proof)
            self.assertTrue(out.is_dir());self.assertTrue((out/'observation.json').exists())
            with self.assertRaises(FileExistsError):observation.write_result(out,value,proof)

    def test_cli_honors_current_time_without_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();source=root/'source';source.write_bytes(self.raw());source.chmod(0o600)
            catalog=root/'catalog';catalog.write_bytes(self.catalog);catalog.chmod(0o600)
            args=['--trace',str(source),'--trace-sha256',observation.digest(self.raw()),
                  '--catalog',str(catalog),'--catalog-sha256',self.catalog_pin,
                  '--thread-id',THREAD,'--turn-id',TURN,'--server-name','golem_local',
                  '--server-prefix',PREFIX,'--started-not-before-ns',str(self.floor),
                  '--output-directory',str(root/'new')]
            with patch.object(observation.time,'time_ns',return_value=self.now),patch('builtins.print'):
                self.assertEqual(observation.main(args),0)
            self.assertEqual(json.loads((root/'new'/'observation.json').read_bytes())['observed_at_ns'],
                             observation._utc(self.rows[5]['timestamp']))
            args[-1]=str(root/'stale')
            with patch.object(observation.time,'time_ns',side_effect=[self.now,self.now+301*10**9]),patch('builtins.print'):
                self.assertEqual(observation.main(args),2)
            self.assertFalse((root/'stale').exists())


if __name__ == '__main__':
    unittest.main()
