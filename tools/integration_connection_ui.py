"""Explicit Owner presentation for Codex connection observation and renewal.

This module imports no Tk at import time. It never launches or stops a client,
changes configuration, or calls a Work tool. An explicit refresh delegates to
the injected controller, which owns capability and target checks; a background
result is rendered only by Tk's event thread. An independent probe or reload
ACK is not a Desktop/model success.
"""
import queue
import threading


UNKNOWN = '미확인'
MAX_TEXT = 4096


def text(value):
    """Render metadata literally, with a bounded and printable display value."""
    if value is None or value == '':
        return UNKNOWN
    if not isinstance(value, (str, int, float, bool)):
        return UNKNOWN
    value = str(value)
    return ''.join(ch if ch.isprintable() or ch in '\n\t' else '\ufffd'
                   for ch in value[:MAX_TEXT])


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
    details = list(selected_lines)
    connections = value.get('connections')
    if not isinstance(connections, list):
        connections = []
    for index, row in enumerate(connections[:128]):
        if not isinstance(row, dict):
            row = {}
        tool_count = row.get('tools_count')
        if type(tool_count) is not int or tool_count < 0:
            tool_count = None
        rows.append((str(index), (
            text(row.get('host_kind')), text(row.get('host_pid')),
            text(row.get('pid')), text(row.get('state')), text(tool_count),
            text(row.get('instance')),
        )))
        instance = row.get('instance')
        if (row.get('refreshable') is True and isinstance(instance, str) and
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
        table = ttk.Frame(self.frame)
        table.pack(fill='both', expand=True)
        self.tree = ttk.Treeview(table, columns=('host', 'host_pid', 'pid', 'state', 'tools', 'instance'),
                                 show='headings', selectmode='browse', height=4)
        for name, title, width in [('host', '호스트', 110), ('host_pid', '호스트 PID', 85),
                                   ('pid', '연결 PID', 85), ('state', '관측 상태', 220),
                                   ('tools', '도구 수', 70), ('instance', '연결 ID', 200)]:
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
        self.status.set('연결 확인 중 · 자동 재시도/앱 종료/Work 실행 없음')
        self._enable()
        self.after_id = self.root.after(50, self._drain)

    def inspect(self):
        self._submit('inspect', self.controller.inspect)

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
            _, report, error = event
            if error:
                self.report = None
                self.status.set('확인 실패: ' + error + ' · 자동 재시도 없음')
                self.guidance.set('반영 여부 미확인 · 기존 연결과 기록을 그대로 보존합니다.')
                self.model_status.set('모델 도구 전달: 미확인 · Work 실행 없음')
                self.tree.delete(*self.tree.get_children())
                self.selected.set('이번 관측 실패 · 이전 설정을 현재 상태로 판정하지 않습니다.')
                self.details.configure(state='normal')
                self.details.delete('1.0', 'end')
                self.details.configure(state='disabled')
            else:
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
