"""Explicit Owner presentation for Codex connection observation and renewal.

This module imports no Tk at import time. It never launches or stops a client,
changes configuration, or calls a Work tool. An explicit refresh delegates to
the injected controller, which owns capability and target checks; a background
result is rendered only by Tk's event thread. An independent probe or reload
ACK is not a Desktop/model success.
"""
import queue
import re
import threading

from integration_client_connection import ConnectionError, validate_host_catalog


UNKNOWN = '미확인'
MAX_TEXT = 4096
CATALOG_LABELS = {
    'HOST_CATALOG_NOT_REQUESTED': '현 세대 목록 요청 없음',
    'HOST_CATALOG_NOT_RELISTED': '변경 후 목록 재조회 없음',
    'HOST_CATALOG_REQUEST_PENDING': '목록 응답 대기',
    'HOST_CATALOG_PARTIAL_RESPONSE': '목록 일부 페이지 전송',
    'HOST_CATALOG_RESPONSE_SENT': '목록 응답 전송 · 모델 미확인',
    'HOST_CATALOG_ERROR_SENT': '목록 오류 응답 전송',
    'HOST_CATALOG_UNVERIFIED_PAGE': '목록 페이지 연속성 미확인',
    'HOST_CATALOG_INVALID_RESPONSE': '목록 응답 형식 미확인',
}


def text(value):
    """Render metadata literally, with a bounded and printable display value."""
    if value is None or value == '':
        return UNKNOWN
    if not isinstance(value, (str, int, float, bool)):
        return UNKNOWN
    value = str(value)
    return ''.join(ch if ch.isprintable() or ch in '\n\t' else '\ufffd'
                   for ch in value[:MAX_TEXT])


def catalog_presentation(row):
    """Separate observed host transport from server readiness and model tools."""
    value = row.get('host_catalog')
    if value is None:
        return '미관찰', ['호스트 목록 관측: NOT_OBSERVED · 구버전/미제공 수치를 0으로 추정하지 않습니다.']
    try:
        value = validate_host_catalog(value)
    except ConnectionError:
        return '관측 형식 미확인', ['호스트 목록 관측: INVALID_METADATA · 성공 여부와 수치 미확인']
    state = value['state']
    return CATALOG_LABELS[state], [
        '호스트 목록 관측: '+state+' · '+CATALOG_LABELS[state],
        'child 세대 / 목록 세대: '+text(value['child_generation'])+' / '+text(value['catalog_generation']),
        '현 목록 세대 요청 / 전송 응답 / 오류: '+text(value['requests'])+' / '+text(value['responses'])+' / '+text(value['errors']),
        '현 목록 세대 변경 알림 전송: '+text(value['list_changed_notifications_sent']),
        '현 세대 전체 페이지 SHA-256 / 페이지 수: '+text(value['current_complete_sha256'])+' / '+text(value['current_complete_pages']),
        '마지막 전체 응답 세대 / SHA-256 / 페이지 수 (과거일 수 있음): '+
            text(value['last_complete_generation'])+' / '+text(value['last_complete_sha256'])+' / '+text(value['last_complete_pages']),
        '응답 전송은 해당 transport로 쓴 관측입니다. 호스트 cache 반영·모델 도구 전달·실행 권한을 증명하지 않습니다.',
    ]


def observation_inputs(thread_id, turn_id, marker, tools_text, required_text=''):
    """Bound literal UI input; the controller validates connection semantics."""
    values = (thread_id, turn_id, marker, tools_text, required_text)
    if any(type(value) is not str for value in values):
        raise ConnectionError('TARGET_OBSERVATION_INPUT_REQUIRED')
    if (not all(value.strip() for value in values[:4]) or len(thread_id) > 256 or
            len(turn_id) > 256 or len(marker) > 512 or len(tools_text) > 65536 or len(required_text) > 65536):
        raise ConnectionError('TARGET_OBSERVATION_INPUT_REQUIRED')
    tools = [value.strip() for value in re.split('[,\n]', tools_text) if value.strip()]
    required = [value.strip() for value in re.split('[,\n]', required_text) if value.strip()]
    if not tools or max(len(tools), len(required)) > 256 or any(len(value) > 256 for value in [*tools, *required]):
        raise ConnectionError('TARGET_OBSERVATION_INPUT_REQUIRED')
    return thread_id.strip(), turn_id.strip(), marker.strip(), tools, required


def readiness_presentation(value):
    """Render connection readiness without granting or performing an action."""
    readiness = value.get('readiness')
    readiness = readiness if isinstance(readiness, dict) else {}
    allowed = readiness.get('preparation_allowed') is True and value.get('target_bound') is True
    return {
        'state': text(readiness.get('state')),
        'preparation_allowed': allowed,
        'label': '새 실행 준비 전 연결 검증: ' + (
            '외부 관측 대조 충족 · 준비 단계로 진행 가능' if allowed else '미충족 · 새 실행 준비 보류'),
        'reason': text(readiness.get('reason')),
    }


def presentation(value):
    """Build a display model without inferring success from counts or an ACK."""
    if not isinstance(value, dict):
        raise ValueError('CONNECTION_REPORT_REQUIRED')
    selected = value.get('selected')
    selected = selected if isinstance(selected, dict) else {}
    renewal = value.get('reload')
    renewal = renewal if isinstance(renewal, dict) else {}
    mode = renewal.get('mode')
    labels = {
        'MANUAL_RESTART_REQUIRED': '호스트 정상 재시작 필요 · 아직 반영 미확인',
        'OFFICIAL_RELOAD_AVAILABLE': '현재 호스트의 공식 연결 갱신 사용 가능 · 아직 실행하지 않음',
        'GOLEM_RELAY_AVAILABLE': '현재 Golem 연결 갱신 사용 가능 · 아직 실행하지 않음',
        'REFRESH_QUEUED': '갱신 요청 접수 · 실제 연결 반영은 아직 미확인',
        'VERIFY_REQUIRED': '갱신 후 실제 연결 재확인 필요 · 완료로 판정하지 않음',
        'WAIT_FOR_IDLE': '진행 중 작업 확인 필요 · 갱신하지 않음',
        'NOT_CONFIGURED': '연결 설정 확인 필요 · 갱신하지 않음',
        'OBSERVATION_INCOMPLETE': '일부 연결 미관찰 · 재시작 필요 여부 미확인',
        'VERIFIED': '실제 연결 대조 완료 · 모델 전달 검증은 별도',
        'TARGET_NOT_IDENTIFIED': '현재 대화의 연결 미식별 · 갱신하지 않음',
    }
    selected_lines = [
        '설치 버전: ' + text(selected.get('package_version')),
        '선택 state: ' + text(selected.get('adapter_state')),
        '선택 launcher SHA-256: ' + text(selected.get('launcher_sha256')),
        '선택 policy SHA-256: ' + text(selected.get('policy_sha256')),
        '선택 runtime SHA-256: ' + text(selected.get('runtime_sha256')),
    ]
    rows = []
    relay_targets = {}
    details = [*selected_lines,
        '연결의 호스트 PID나 준비안 보유만으로 현재 대화의 transport를 확정하지 않습니다. 대화 연결 근거는 별도입니다.']
    connections = value.get('connections')
    if not isinstance(connections, list):
        connections = []
    for index, row in enumerate(connections[:128]):
        if not isinstance(row, dict):
            row = {}
        tool_count = row.get('tools_count')
        if type(tool_count) is not int or tool_count < 0:
            tool_count = None
        catalog_label, catalog_details = catalog_presentation(row)
        rows.append((str(index), (
            text(row.get('host_kind')), text(row.get('host_pid')),
            text(row.get('pid')), text(row.get('state')), text(tool_count),
            text(row.get('instance')), catalog_label,
        )))
        instance = row.get('instance')
        if (value.get('target_bound') is True and row.get('refreshable') is True and isinstance(instance, str) and
                len(instance) == 32 and all(ch in '0123456789abcdef' for ch in instance)):
            relay_targets[str(index)] = instance
        details.extend([
            '', '연결 ' + text(row.get('instance')),
            '호스트: ' + text(row.get('host_kind')) + ' / PID ' + text(row.get('host_pid')),
            '프로세스 PID: ' + text(row.get('pid')),
            '관측 상태: ' + text(row.get('state')),
            '관측 사유: ' + text(row.get('reason')),
            '실제 launcher SHA-256: ' + text(row.get('launcher_sha256')),
            '실제 policy SHA-256: ' + text(row.get('policy_sha256')),
            '실제 runtime SHA-256: ' + text(row.get('runtime_sha256')),
            '관측 도구 수: ' + text(tool_count),
            *catalog_details,
        ])
        tools = row.get('tools')
        if isinstance(tools, list):
            details.append('관측 도구: ' + ', '.join(text(t) for t in tools[:256]))
    steps = renewal.get('steps')
    steps = [text(s) for s in steps[:16]] if isinstance(steps, list) else []
    model_delivery = value.get('model_tool_delivery')
    model_delivery = ('미확인 · 현재 모델 도구 목록/실제 호출을 별도로 확인해야 합니다'
                      if model_delivery in (None, '', 'NOT_OBSERVED') else text(model_delivery))
    refresh_token = value.get('refresh_token')
    if (not isinstance(refresh_token, str) or len(refresh_token) != 64 or
            any(ch not in '0123456789abcdef' for ch in refresh_token)):
        refresh_token = None
    return {
        'state': text(value.get('state')),
        'summary': text(value.get('summary')),
        'selected': '\n'.join(selected_lines),
        'rows': rows,
        'relay_targets': relay_targets,
        'details': '\n'.join(details),
        'renewal_mode': mode,
        'renewal_label': labels.get(mode, '갱신 가능 여부 미확인 · 실행하지 않음'),
        'reason': text(renewal.get('reason')),
        'steps': steps,
        'model_delivery': model_delivery,
        'observed_at': text(value.get('observed_at')),
        'refresh_token': refresh_token,
        'readiness': readiness_presentation(value),
        'target_bound': value.get('target_bound') is True,
    }


class BackgroundRequest:
    """One outstanding, explicit read/refresh request; no retry or Tk calls."""
    def __init__(self):
        self.events = queue.Queue()
        self.busy = False
        self.closed = False
        self.thread = None

    def start(self, kind, operation):
        if self.busy or self.closed:
            return False
        self.busy = True
        def worker():
            try:
                self.events.put((kind, presentation(operation()), None))
            except Exception as error:
                # Unexpected exception messages can contain arbitrary host data.
                code = getattr(error, 'code', 'CONNECTION_OBSERVATION_FAILED')
                self.events.put((kind, None, text(code)))
        self.thread = threading.Thread(target=worker, daemon=False)
        self.thread.start()
        return True

    def take(self):
        try:
            event = self.events.get_nowait()
        except queue.Empty:
            return None
        self.busy = False
        return None if self.closed else event

    def close(self):
        # Presentation closure neither cancels an in-flight host operation nor
        # creates a replacement request. A bounded backend completes separately.
        self.closed = True


class ConnectionPanel:
    """No initial observation, automatic backend polling, or restart side effect."""
    def __init__(self, root, controller):
        import tkinter as tk
        from tkinter import ttk
        self.root, self.controller = root, controller
        self.request = BackgroundRequest()
        self.after_id = None
        self.report = None
        self.reload_attempted = False
        self.attempted_tokens = set()
        self.attempted_targets = set()
        self.selection_target = None
        self.target_revision = 0
        self.submitted_revision = 0
        self.target_dirty = False
        self.frame = ttk.LabelFrame(root, text='Codex 연결 상태 · 갱신', padding=12)
        self.frame.pack(fill='both', expand=True, padx=12, pady=8)
        self.frame.bind('<Destroy>', self._destroyed, add='+')
        self.status = tk.StringVar(value='미조회 · 아래 버튼으로 현재 연결을 확인하세요')
        ttk.Label(self.frame, textvariable=self.status, wraplength=830).pack(anchor='w')
        buttons = ttk.Frame(self.frame)
        buttons.pack(fill='x', pady=6)
        self.inspect_button = ttk.Button(buttons, text='연결 상태 확인', command=self.inspect)
        self.inspect_button.pack(side='left')
        self.refresh_button = ttk.Button(buttons, text='Codex 연결 갱신', command=self.refresh,
                                         state='disabled')
        self.refresh_button.pack(side='left', padx=8)
        self.recheck_button = ttk.Button(buttons, text='재시작 후 상태 확인', command=self.recheck,
                                        state='disabled')
        self.recheck_button.pack(side='left')
        self.selected = tk.StringVar(value='디스크의 선택 설정: 미확인')
        ttk.Label(self.frame, textvariable=self.selected, wraplength=830).pack(anchor='w', pady=4)
        target = ttk.LabelFrame(self.frame, text='현재 대화에서 확인한 도구 정의', padding=6)
        target.pack(fill='x', pady=4)
        ttk.Label(target, text='외부 관측을 대조합니다. 대화 신원 인증이나 owner 승인으로 사용하지 않습니다.',
                  wraplength=830).grid(row=0, column=0, columnspan=2, sticky='w')
        self.thread_id = tk.StringVar()
        self.turn_id = tk.StringVar()
        self.marker = tk.StringVar()
        self.target_entries = []
        for index, (label, variable) in enumerate((('대화 ID', self.thread_id),
                ('관측 turn ID', self.turn_id), ('도구 정의의 연결 marker', self.marker)), 1):
            ttk.Label(target, text=label).grid(row=index, column=0, sticky='w', padx=(0, 6))
            entry = ttk.Entry(target, textvariable=variable)
            entry.grid(row=index, column=1, sticky='ew')
            self.target_entries.append(entry)
        ttk.Label(target, text='실제로 노출된 도구 이름\n(줄바꿈 또는 쉼표 구분)').grid(row=4, column=0, sticky='nw')
        self.observed_tools = tk.Text(target, height=2, wrap='word')
        self.observed_tools.grid(row=4, column=1, sticky='ew')
        ttk.Label(target, text='다음 준비에 필요한 도구\n(비우면 준비 보류)').grid(row=5, column=0, sticky='nw')
        self.required_tools = tk.Text(target, height=1, wrap='word')
        self.required_tools.grid(row=5, column=1, sticky='ew')
        self.observation_button = ttk.Button(target, text='대화 관측 대조', command=self.observe_target)
        self.observation_button.grid(row=6, column=1, sticky='w', pady=4)
        target.columnconfigure(1, weight=1)
        self.readiness = tk.StringVar(value='새 실행 준비 전 연결 검증: 미충족 · 새 실행 준비 보류')
        ttk.Label(target, textvariable=self.readiness, wraplength=830).grid(row=7, column=0, columnspan=2, sticky='w')
        ttk.Label(target, text='이 대조는 실행·승인·QA·완료 권한을 추가하지 않으며 Work를 호출하지 않습니다.',
                  wraplength=830).grid(row=8, column=0, columnspan=2, sticky='w')
        table = ttk.Frame(self.frame)
        table.pack(fill='both', expand=True)
        self.tree = ttk.Treeview(table, columns=('host', 'host_pid', 'pid', 'state', 'tools', 'instance', 'host_catalog'),
                                 show='headings', selectmode='browse', height=4)
        for name, title, width in [('host', '호스트', 110), ('host_pid', '호스트 PID', 85),
                                   ('pid', '연결 PID', 85), ('state', '서버/연결 상태', 180),
                                   ('tools', '도구 수', 70), ('instance', '연결 ID', 200),
                                   ('host_catalog', '호스트 목록 관측', 210)]:
            self.tree.heading(name, text=title)
            self.tree.column(name, width=width, minwidth=60)
        scrollbar = ttk.Scrollbar(table, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        self.tree.pack(fill='both', expand=True)
        self.tree.bind('<<TreeviewSelect>>', self._selection_changed, add='+')
        self.guidance = tk.StringVar(value='갱신 실행 가능 여부: 미확인')
        ttk.Label(self.frame, textvariable=self.guidance, wraplength=830).pack(anchor='w', pady=5)
        self.ack = tk.BooleanVar(value=False)
        self.ack_button = ttk.Checkbutton(self.frame,
            text='다른 작업을 저장하고 진행 중인 작업을 확인했습니다. 앱을 직접 정상 재시작하겠습니다.',
            variable=self.ack, command=self.acknowledge, state='disabled')
        self.ack_button.pack(anchor='w')
        self.reload_consent = tk.BooleanVar(value=False)
        self.reload_consent_button = ttk.Checkbutton(self.frame,
            text='작업 상태를 확인했고, 표시된 Codex 호스트의 전체 MCP 연결 갱신을 1회 요청합니다.',
            variable=self.reload_consent, command=self._enable, state='disabled')
        self.reload_consent_button.pack(anchor='w')
        self.model_status = tk.StringVar(value='모델 도구 전달: 미확인 · Work 실행 없음')
        ttk.Label(self.frame, textvariable=self.model_status, wraplength=830).pack(anchor='w', pady=4)
        details = ttk.LabelFrame(self.frame, text='선택 설정과 실제 연결의 상세 대조')
        details.pack(fill='both', expand=True, pady=4)
        self.details = tk.Text(details, height=5, wrap='word', state='disabled')
        self.details.pack(fill='both', expand=True)
        for variable in (self.thread_id, self.turn_id, self.marker):
            variable.trace_add('write', self._target_changed)
        self.observed_tools.bind('<<Modified>>', self._tools_changed, add='+')
        self.required_tools.bind('<<Modified>>', self._tools_changed, add='+')

    def _destroyed(self, event):
        if event.widget is not self.frame:
            return
        self.request.close()
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None

    def _enable(self):
        busy = self.request.busy
        self.inspect_button.configure(state='disabled' if busy else 'normal')
        self.observation_button.configure(state='disabled' if busy else 'normal')
        for entry in self.target_entries:
            entry.configure(state='disabled' if busy else 'normal')
        self.observed_tools.configure(state='disabled' if busy else 'normal')
        self.required_tools.configure(state='disabled' if busy else 'normal')
        mode = self.report['renewal_mode'] if self.report else None
        manual = mode == 'MANUAL_RESTART_REQUIRED'
        relay_target = self._relay_target()
        official = (mode in ('OFFICIAL_RELOAD_AVAILABLE', 'GOLEM_RELAY_AVAILABLE') and
                    bool(self.report['refresh_token']) and
                    self.report['refresh_token'] not in self.attempted_tokens and
                    (relay_target if mode == 'GOLEM_RELAY_AVAILABLE' else 'HOST_ALL_MCP')
                    not in self.attempted_targets)
        if mode == 'GOLEM_RELAY_AVAILABLE' and not relay_target:
            official = False
        self.refresh_button.configure(text={'MANUAL_RESTART_REQUIRED':'정상 재시작 안내',
            'OFFICIAL_RELOAD_AVAILABLE':'호스트 MCP 갱신 요청',
            'GOLEM_RELAY_AVAILABLE':'Golem 연결 갱신'}.get(mode, 'Codex 연결 갱신'))
        self.reload_consent_button.configure(text=(
            '작업 상태를 확인했고, 선택한 Golem 연결 '+text(relay_target)+'만 1회 갱신합니다.' if mode == 'GOLEM_RELAY_AVAILABLE'
            else '작업 상태를 확인했고, 표시된 Codex 호스트의 전체 MCP 연결 갱신을 1회 요청합니다.'))
        self.refresh_button.configure(state='normal' if not busy and (manual or (official and self.reload_consent.get())) else 'disabled')
        self.ack_button.configure(state='normal' if manual and not busy else 'disabled')
        self.reload_consent_button.configure(state='normal' if official and not busy else 'disabled')
        verification = mode in ('REFRESH_QUEUED', 'VERIFY_REQUIRED')
        self.recheck_button.configure(text='재시작 후 상태 확인' if manual else '갱신 후 상태 확인',
            state='normal' if not busy and ((manual and self.ack.get()) or verification) else 'disabled')

    def _relay_target(self):
        selected = self.tree.selection()
        if not self.report or len(selected) != 1:
            return None
        return self.report['relay_targets'].get(selected[0])

    def _selection_changed(self, event=None):
        target = self._relay_target()
        if target != self.selection_target:
            self.reload_consent.set(False)
            self.selection_target = target
        self._enable()

    def _submit(self, kind, operation):
        if not self.request.start(kind, operation):
            return
        self.ack.set(False)
        self.reload_consent.set(False)
        self.submitted_revision = self.target_revision
        self.status.set('연결 확인 중 · 자동 재시도/앱 종료/Work 실행 없음')
        self._enable()
        self.after_id = self.root.after(50, self._drain)

    def inspect(self):
        self._submit('inspect', self.controller.inspect)

    def _target_changed(self, *unused):
        self.target_revision += 1
        self.target_dirty = True
        self.report = None
        self.reload_consent.set(False)
        if not self.request.busy:
            clear = getattr(self.controller, 'clear_target_observation', None)
            if callable(clear):
                clear()
        self.readiness.set('관측 입력 변경 · 다시 대조하기 전 새 실행 준비 보류')
        self.model_status.set('모델 도구 전달: 입력 변경 · 다시 대조 필요')
        self._enable()

    def _tools_changed(self, event=None):
        widget = self.observed_tools if event is None else event.widget
        if widget.edit_modified():
            widget.edit_modified(False)
            self._target_changed()

    def observe_target(self):
        if self.request.busy:
            return
        values = (self.thread_id.get(), self.turn_id.get(), self.marker.get(),
                  self.observed_tools.get('1.0', 'end-1c'), self.required_tools.get('1.0', 'end-1c'))
        def observe():
            arguments = observation_inputs(*values)
            self.controller.set_target_observation(*arguments)
            return self.controller.inspect()
        self._submit('target-observation', observe)

    def refresh(self):
        # request_refresh decides whether the actual host has a supported control
        # route. A manual guide must never be presented as an executed reload.
        if self.request.busy or not self.report:
            return
        mode = self.report['renewal_mode']
        instance = self._relay_target() if mode == 'GOLEM_RELAY_AVAILABLE' else None
        if mode in ('OFFICIAL_RELOAD_AVAILABLE', 'GOLEM_RELAY_AVAILABLE'):
            target = instance if mode == 'GOLEM_RELAY_AVAILABLE' else 'HOST_ALL_MCP'
            if (target in self.attempted_targets or not self.reload_consent.get() or
                    self.report['refresh_token'] in self.attempted_tokens or
                    not self.report['refresh_token'] or
                    (mode == 'GOLEM_RELAY_AVAILABLE' and not instance)):
                return
            self.reload_attempted = True
            self.attempted_targets.add(target)
            self.attempted_tokens.add(self.report['refresh_token'])
        elif mode == 'MANUAL_RESTART_REQUIRED':
            # A manual guide is strictly observational. The host capability
            # may have changed since the displayed report; never allow that
            # change to turn this button into an unconfirmed actual reload.
            self._submit('inspect', self.controller.inspect)
            return
        else:
            return
        token = self.report['refresh_token']
        self._submit('refresh', lambda: self.controller.request_refresh(
            expected_token=token, connection_instance=instance))

    def recheck(self):
        if self.report:
            mode = self.report['renewal_mode']
            if (mode == 'MANUAL_RESTART_REQUIRED' and self.ack.get()) or mode in ('REFRESH_QUEUED', 'VERIFY_REQUIRED'):
                self._submit('recheck', self.controller.inspect)

    def _drain(self):
        self.after_id = None
        if self.request.closed:
            return
        event = self.request.take()
        if event is not None:
            kind, report, error = event
            if self.submitted_revision != self.target_revision:
                error = 'TARGET_INPUT_CHANGED'
                clear = getattr(self.controller, 'clear_target_observation', None)
                if callable(clear):
                    clear()
            if kind == 'target-observation' and not error:
                self.target_dirty = False
            if error:
                self.report = None
                self.status.set('확인 실패: ' + error + ' · 자동 재시도 없음')
                self.guidance.set('반영 여부 미확인 · 기존 연결과 기록을 그대로 보존합니다.')
                self.model_status.set('모델 도구 전달: 미확인 · Work 실행 없음')
                self.readiness.set('새 실행 준비 전 연결 검증: 미충족 · 새 실행 준비 보류')
                self.tree.delete(*self.tree.get_children())
                self.selected.set('이번 관측 실패 · 이전 설정을 현재 상태로 판정하지 않습니다.')
                self.details.configure(state='normal')
                self.details.delete('1.0', 'end')
                self.details.configure(state='disabled')
            else:
                if self.target_dirty:
                    # A plain status read cannot accept edited, unsubmitted
                    # evidence or restore the prior target after an edit.
                    report['target_bound'] = False
                    report['relay_targets'] = {}
                    report['readiness'] = readiness_presentation({})
                    report['model_delivery'] = '입력 변경 · 대화 관측을 다시 대조해야 합니다'
                    if report['renewal_mode'] in ('GOLEM_RELAY_AVAILABLE', 'OFFICIAL_RELOAD_AVAILABLE'):
                        report['renewal_mode'] = 'TARGET_NOT_IDENTIFIED'
                        report['renewal_label'] = '현재 대화의 연결 미식별 · 갱신하지 않음'
                self.report = report
                self.status.set(report['state'] + ' · ' + report['summary'] + '\n관측 시각: ' + report['observed_at'])
                self.selected.set('디스크의 선택 설정\n' + report['selected'])
                self.tree.delete(*self.tree.get_children())
                for key, row in report['rows']:
                    self.tree.insert('', 'end', iid=key, values=row)
                guide = report['renewal_label'] + '\n' + report['reason']
                if report['renewal_mode'] != 'MANUAL_RESTART_REQUIRED':
                    guide += ''.join('\n'+s for s in report['steps'])
                else:
                    guide += '\n아래 확인란을 선택하면 정상 재시작 절차를 표시합니다. 자동 종료하지 않습니다.'
                if report['renewal_mode'] == 'OFFICIAL_RELOAD_AVAILABLE':
                    guide += '\n연결 갱신은 이 Codex 호스트의 다른 연결에 영향을 줄 수 있습니다. 작업 상태를 확인한 뒤 1회 요청하세요.'
                if report['renewal_mode'] == 'GOLEM_RELAY_AVAILABLE':
                    guide += '\n목록에서 갱신할 연결 한 행을 선택하고 해당 연결의 작업 상태를 확인하세요. 다른 연결은 갱신하지 않습니다.'
                if self.reload_attempted:
                    guide += '\n이미 시도한 연결은 이 창에서 다시 갱신하지 않습니다. 다른 연결은 새 상태 확인과 해당 행 선택·동의가 필요합니다.'
                self.guidance.set(guide)
                self.model_status.set('모델 도구 전달: ' + report['model_delivery'] + '\n연결 확인은 Work 실행·QA·완료 검증이 아닙니다.')
                self.readiness.set(report['readiness']['label'] + '\n' +
                                   report['readiness']['state'] + ' · ' + report['readiness']['reason'])
                self.details.configure(state='normal')
                self.details.delete('1.0', 'end')
                self.details.insert('end', report['details'])
                self.details.configure(state='disabled')
            self._enable()
        if self.request.busy:
            self.after_id = self.root.after(50, self._drain)

    def acknowledge(self):
        if self.report and self.report['renewal_mode'] == 'MANUAL_RESTART_REQUIRED':
            guide = self.report['renewal_label'] + '\n' + self.report['reason']
            if self.ack.get():
                guide += ''.join('\n'+s for s in self.report['steps'])
                guide += '\n재시작을 마친 뒤 “재시작 후 상태 확인”을 누르세요. 확인란은 재시작 성공 증거가 아닙니다.'
            else:
                guide += '\n먼저 다른 작업의 저장·진행 상태를 확인하세요. 앱을 자동 종료하지 않습니다.'
            self.guidance.set(guide)
        self._enable()
