"""Explicit Owner view for a pinned, optional fixed-catalog connection.

The view performs no discovery, client reload, policy write, or Work call by
itself. Every backend operation is a separate button action delegated to the
verified controller. Closing this view never cancels or repeats an operation.
"""
import json
import queue
import re
import threading

from integration_connection_ui import text


CLIENT_LABELS = {'codex': 'Codex', 'claude-desktop': 'Claude Desktop'}
REPORT_SCHEMA = 'golem.stable-owner-report.v1'
HASH = re.compile(r'[0-9a-f]{64}\Z')
INSTANCE = re.compile(r'[0-9a-f]{32}\Z')
MARKER = re.compile(r'golem-catalog-v2:([0-9a-f]{32}):([0-9a-f]{64}):([0-9a-f]{32})\Z')


def _hash(value):
    return type(value) is str and HASH.fullmatch(value) is not None


def _input_shape(path, pin):
    # UI availability only: the controller still validates the original bytes,
    # provenance, freshness, and authority after an explicit request.
    return type(path) is str and bool(path.strip()) and _hash(pin)


def _mapping(value):
    return value if type(value) is dict else {}


def _details(value):
    """Display finite controller metadata literally; never evaluate its text."""
    try:
        raw = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)
    except (TypeError, ValueError):
        return '관측 자료 형식 미확인'
    # This is display truncation only. The controller validates complete bytes.
    if len(raw) > 262144:
        raw = raw[:262144] + '\n[표시 한도 초과 — 전체 검토 기록을 별도로 확인하세요]'
    return ''.join(ch if ch.isprintable() or ch in '\n\t' else '\ufffd' for ch in raw)


def _observed_instance(client, selected, live, model, readiness, endpoints, counts):
    """Use an explicit native correlation result only for display navigation.

    This does not perform correlation, refresh a receipt, or authorize effects.
    Recheck the report's exact target so an ambiguous row is never substituted.
    """
    target = model.get('target')
    marker = model.get('marker')
    parsed = MARKER.fullmatch(marker) if type(marker) is str else None
    if not (parsed and model.get('source') == 'EXTERNAL_MODEL_DEFINITION_OBSERVATION' and
            type(target) is dict and set(target) == {'thread_id','server_name'} and
            all(type(target[key]) is str and target[key] for key in target) and
            model.get('thread_id') == target['thread_id'] and
            model.get('server_name') == target['server_name'] and
            type(model.get('turn_id')) is str and model['turn_id'] and
            readiness.get('target') == target and readiness.get('execution_authorized') is False and
            readiness.get('automatic_retry_allowed') is False and readiness.get('actual_execution') == 'HOLD'):
        return None
    correlation = (readiness.get('schema') == 'golem.stable-definition-correlation.v1' and
                   readiness.get('state') == 'EXTERNAL_CORRELATION_ONLY' and
                   readiness.get('correlated') is True and readiness.get('frontend_bound') is True and
                   readiness.get('same_chat_model_tools') == 'EXTERNALLY_CORRELATED_FIXED_DEFINITIONS')
    classified = (readiness.get('schema') == 'golem.stable-connection-readiness.v1' and
                  readiness.get('state') == 'PREPARATION_READY_NOT_AUTHORIZED' and
                  readiness.get('preparation_allowed') is True and
                  _mapping(readiness.get('stages')).get('same_chat_model_tools') ==
                  'EXTERNALLY_CORRELATED_FIXED_DEFINITIONS')
    instance = parsed.group(1)
    names = model.get('tools')
    if not ((correlation or classified) and type(names) is list and names and
            all(type(name) is str for name in names) and len(set(names)) == len(names) and
            readiness.get('observed_tools') == sorted(names) and counts.get(instance) == 1 and
            endpoints.get(instance) == 'PRESENT' and
            _mapping(selected.get('selection')).get('client') == client and
            parsed.group(2) == selected.get('catalog_sha256') and
            live.get('schema') == 'golem.stable-connection-relay.v1' and
            live.get('client') == client and live.get('instance') == instance and
            live.get('definition_marker') == marker and live.get('state') == 'READY' and
            live.get('busy') is False and live.get('failure') is None and
            type(live.get('pending')) is int and live['pending'] == 0 and
            type(live.get('server_pending')) is int and live['server_pending'] == 0):
        return None
    return instance


def presentation(value, client):
    """Render selected/live/model states separately; reject ambiguous actions."""
    if type(value) is not dict:
        raise ValueError('STABLE_OWNER_REPORT_REQUIRED')
    valid = (client in CLIENT_LABELS and value.get('schema') == REPORT_SCHEMA and
             value.get('client') == client and value.get('execution_authorized') is False and
             value.get('automatic_retry_allowed') is False and value.get('actual_execution') == 'HOLD')
    selected = _mapping(value.get('selected'))
    selection = _mapping(selected.get('selection'))
    live = _mapping(value.get('live'))
    model = _mapping(value.get('model_observation'))
    rows, endpoints, counts = [], {}, {}
    for row in value.get('connections', [])[:1024] if type(value.get('connections')) is list else []:
        row = _mapping(row)
        key = row.get('instance')
        if type(key) is str:
            counts[key] = counts.get(key, 0) + 1
        if type(key) is not str or INSTANCE.fullmatch(key) is None or key in endpoints:
            continue
        same_client = row.get('client') == client
        endpoint = row.get('endpoint_state') if same_client else 'OTHER_CLIENT'
        endpoints[key] = endpoint
        current = live.get('instance') == key and live.get('client') == client
        state = live.get('state') if current else row.get('state')
        if endpoint == 'ABSENT':
            state = '종료됨 · 기록 보존'
        elif endpoint != 'PRESENT':
            state = '연결 미확인'
        row_client=row.get('client')
        rows.append((key, (CLIENT_LABELS.get(row_client, text(row_client)), key, text(endpoint),
                           text(state), text(live.get('backend_epoch') if current else None),
                           '외부 관측 대상' if current else '대화 연결 미확인')))
    review = _mapping(value.get('review'))
    kind = review.get('kind')
    token = review.get('token')
    action_review = None
    safe_report = valid and not value.get('error') and value.get('state') not in ('BLOCKED', 'RESULT_UNKNOWN')
    if safe_report and _hash(token):
        if (kind == 'publish' and _hash(review.get('selection_sha256')) and
                _hash(review.get('expected_head_sha256')) and
                review['expected_head_sha256'] == selected.get('head_sha256') and
                review['selection_sha256'] != selected.get('selection_sha256') and
                selection.get('client') == client):
            action_review = dict(review)
        elif kind == 'refresh':
            instance, marker = review.get('instance'), review.get('marker')
            parsed = MARKER.fullmatch(marker) if type(marker) is str else None
            idle = (live.get('state') == 'READY' and live.get('busy') is False and
                    live.get('failure') is None and type(live.get('pending')) is int and
                    live.get('pending') == 0 and type(live.get('server_pending')) is int and
                    live.get('server_pending') == 0)
            if (type(instance) is str and INSTANCE.fullmatch(instance) and parsed and
                    parsed.group(1) == instance and parsed.group(2) == selected.get('catalog_sha256') and
                    endpoints.get(instance) == 'PRESENT' and live.get('client') == client and
                    live.get('instance') == instance and live.get('definition_marker') == marker and
                    model.get('marker') == marker and idle and
                    _hash(review.get('old_selection_sha256')) and
                    _hash(review.get('target_selection_sha256')) and
                    live.get('selection_sha256') == review['old_selection_sha256'] and
                    selected.get('selection_sha256') == review['target_selection_sha256'] and
                    review['old_selection_sha256'] != review['target_selection_sha256']):
                action_review = dict(review)
    readiness = _mapping(value.get('readiness'))
    ready = (safe_report and readiness.get('state') == 'PREPARATION_READY_NOT_AUTHORIZED' and
             readiness.get('preparation_allowed') is True and readiness.get('execution_authorized') is False)
    observed_instance = (_observed_instance(client, selected, live, model, readiness, endpoints, counts)
                         if safe_report and type(value.get('connections')) is list and
                         len(value['connections']) <= 1024 else None)
    selected_text = '\n'.join([
        'client: ' + text(value.get('client')),
        '선택 revision / selection SHA: ' + text(selection.get('revision')) + ' / ' + text(selected.get('selection_sha256')),
        '현재 head SHA: ' + text(selected.get('head_sha256')),
        '고정 catalog SHA: ' + text(selected.get('catalog_sha256')),
        '선택 adapter state: ' + text(selection.get('adapter_state')),
    ])
    model_text = '\n'.join([
        '외부 관측 대화 / turn: ' + text(model.get('thread_id')) + ' / ' + text(model.get('turn_id')),
        '실제 도구 정의 marker: ' + text(model.get('marker')),
        '원본 관측 시각(ns): ' + text(model.get('observed_at_ns')),
        '실제 노출 도구: ' + str(len(model['tools'])) + '개 · 전체 이름은 아래 원본 상세에서 확인'
        if type(model.get('tools')) is list else '실제 노출 도구: 미확인',
    ])
    return {'valid': valid, 'client': client, 'state': text(value.get('state')) if valid else 'STABLE_OWNER_REPORT_MISMATCH',
            'selected': selected_text, 'rows': rows, 'endpoints': endpoints,
            'observed_instance': observed_instance,
            'model': model_text, 'review': action_review, 'raw_review': review,
            'readiness': ('연결 대조 충족 · 실제 실행 HOLD' if ready else '연결 대조 미충족 · 실제 실행 HOLD'),
            'readiness_reason': text(readiness.get('reason')), 'preparation_allowed': ready,
            'error': text(value.get('error')) if value.get('error') else None,
            'details': _details(value)}


class BackgroundRequest:
    """Only explicit requests, one in flight; no Tk calls or automatic retry."""
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
                self.events.put((kind, operation(), None))
            except Exception as error:
                code = getattr(error, 'code', 'STABLE_OWNER_OPERATION_FAILED')
                if type(code) is not str or not re.fullmatch('[A-Z][A-Z0-9_]{0,99}', code):
                    code = 'STABLE_OWNER_OPERATION_FAILED'
                self.events.put((kind, None, code))
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
        # The controller retains its immutable attempt/result journal. Closing
        # a view neither kills a relay nor redispatches a pending operation.
        self.closed = True


class StableOwnerPanel:
    """Optional explicit UI. Constructing or selecting a row has no I/O effect."""
    viewport_events = ('<FocusIn>', '<Prior>', '<Next>', '<MouseWheel>', '<Button-4>', '<Button-5>')

    def __init__(self, root, controller):
        import tkinter as tk
        from tkinter import ttk
        self.root, self.controller = root, controller
        self.request = BackgroundRequest()
        self.report = None
        self.after_id = None
        self.attempted = set()
        self.input_revision = 0
        self.submitted_revision = 0
        self.submitted_client = None
        self.observation_dirty = True
        self.selected_instance = None
        self.input_widgets = []
        self.frame = ttk.Frame(root)
        self.frame.pack(fill='both', expand=True)
        self.frame.bind('<Destroy>', self._destroyed, add='+')
        canvas = tk.Canvas(self.frame, highlightthickness=0)
        scroll = ttk.Scrollbar(self.frame, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y'); canvas.pack(side='left', fill='both', expand=True)
        body = ttk.Frame(canvas, padding=12)
        item = canvas.create_window((0, 0), window=body, anchor='nw')
        body.bind('<Configure>', lambda event: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda event: canvas.itemconfigure(item, width=event.width))
        self.canvas, self.body = canvas, body
        self.status = tk.StringVar(value='미조회 · 실행 HOLD · 자동 갱신 없음')
        ttk.Label(body, text='고정 도구 정의 · 정확한 실행부 전환', font=('', 16, 'bold')).pack(anchor='w')
        ttk.Label(body, text='앱 재시작·전체 연결 갱신·Work 호출·승인 발급 없이, 검토한 한 연결만 전환합니다.',
                  wraplength=850).pack(anchor='w', pady=4)
        ttk.Label(body, textvariable=self.status, wraplength=850).pack(anchor='w')
        toolbar = ttk.Frame(body); toolbar.pack(fill='x', pady=6)
        self.clients = tuple(dict.fromkeys(client for client in controller.clients if client in CLIENT_LABELS))
        self.client = tk.StringVar(value=self.clients[0] if self.clients else '')
        ttk.Label(toolbar, text='client').pack(side='left')
        self.client_buttons = {}
        for client in self.clients:
            button = ttk.Button(toolbar, text=CLIENT_LABELS[client], takefocus=True,
                                command=lambda client=client: self.select_client(client))
            button.pack(side='left', padx=6)
            for key in ('Left', 'Right', 'Home', 'End', 'space', 'Return'):
                button.bind('<'+key+'>', lambda event, client=client: self._client_key(client, event.keysym))
            self.client_buttons[client] = button
        self.client_label = tk.StringVar()
        ttk.Label(body, textvariable=self.client_label).pack(anchor='w')
        self.inspect_button = ttk.Button(toolbar, text='선택·연결 기록 조회', command=self.inspect)
        self.inspect_button.pack(side='left')
        self.selected = tk.StringVar(value='선택 상태: 미확인')
        ttk.Label(body, textvariable=self.selected, wraplength=850).pack(anchor='w', pady=4)
        table = ttk.LabelFrame(body, text='연결 기록 — 행 선택은 표시만 변경합니다')
        table.pack(fill='x', pady=4)
        self.tree = ttk.Treeview(table, columns=('client','instance','endpoint','state','epoch','target'),
                                 show='headings', selectmode='browse', height=4)
        for key, label, width in [('client','client',110),('instance','정확한 연결 ID',250),
                ('endpoint','통신 경로',85),('state','상태',160),('epoch','실행 세대',80),('target','대화 대조',140)]:
            self.tree.heading(key, text=label); self.tree.column(key, width=width, minwidth=60)
        yscroll = ttk.Scrollbar(table, orient='vertical', command=self.tree.yview)
        xscroll = ttk.Scrollbar(table, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.tree.grid(row=0,column=0,sticky='nsew'); yscroll.grid(row=0,column=1,sticky='ns')
        xscroll.grid(row=1,column=0,sticky='ew'); table.columnconfigure(0,weight=1)
        self.tree.bind('<<TreeviewSelect>>', self._selection_changed, add='+')
        self.tree.bind('<Down>', lambda _: self.navigate(1))
        self.tree.bind('<Up>', lambda _: self.navigate(-1))
        self.select_observed_button = ttk.Button(table, text='관측된 연결 행 선택',
                                                command=self.select_observed, state='disabled')
        self.select_observed_button.grid(row=2,column=0,sticky='w',pady=4)
        self.observation_path = tk.StringVar(); self.observation_sha = tk.StringVar()
        observation = ttk.LabelFrame(body, text='같은 대화의 실제 도구 정의 관측', padding=8)
        observation.pack(fill='x', pady=5)
        ttk.Label(observation, text='실제 대화·turn·marker·도구 이름·원래 관측 시각을 담은 외부 JSON을 선택합니다.\n'
                  '이 UI는 관측값이나 시각을 생성하지 않으며 hash 일치를 진실성·권한 인증으로 해석하지 않습니다.',
                  wraplength=830).grid(row=0,column=0,columnspan=3,sticky='w')
        self._file_inputs(observation, self.observation_path, self.observation_sha, 1)
        self.observe_button = ttk.Button(observation, text='관측·현재 실행부 대조', command=self.observe)
        self.observe_button.grid(row=3,column=1,sticky='w',pady=4)
        self.model = tk.StringVar(value='대화·turn·marker·도구: 미관찰')
        ttk.Label(observation, textvariable=self.model, wraplength=830).grid(row=4,column=0,columnspan=3,sticky='w')
        self.readiness = tk.StringVar(value='연결 대조 미충족 · 실제 실행 HOLD')
        ttk.Label(observation, textvariable=self.readiness, wraplength=830).grid(row=5,column=0,columnspan=3,sticky='w',pady=4)
        selection = ttk.LabelFrame(body, text='1. 검토된 실행부 선택 공개 — 실제 연결 전환과 별도', padding=8)
        selection.pack(fill='x', pady=5)
        self.selection_path = tk.StringVar(); self.selection_sha = tk.StringVar()
        self._file_inputs(selection, self.selection_path, self.selection_sha, 0)
        self.review_selection_button = ttk.Button(selection, text='선택 후보·현재 head 대조', command=self.review_selection)
        self.review_selection_button.grid(row=2,column=1,sticky='w',pady=4)
        self.publish_consent = tk.BooleanVar(value=False)
        self.publish_check = ttk.Checkbutton(selection, text='표시된 candidate SHA·현재 head를 검토했습니다. 이 선택만 한 번 공개합니다.',
                                             variable=self.publish_consent, command=self._enable, state='disabled')
        self.publish_check.grid(row=3,column=0,columnspan=3,sticky='w')
        self.publish_button = ttk.Button(selection, text='정확한 선택 공개 1회', command=self.publish, state='disabled')
        self.publish_button.grid(row=4,column=1,sticky='w',pady=4)
        renewal = ttk.LabelFrame(body, text='2. 외부 관측으로 식별한 한 연결의 실행부 전환', padding=8)
        renewal.pack(fill='x', pady=5)
        self.review_refresh_button = ttk.Button(renewal, text='현재 대화의 old/new 전환 검토', command=self.review_refresh)
        self.review_refresh_button.pack(anchor='w')
        self.refresh_consent = tk.BooleanVar(value=False)
        self.refresh_check = ttk.Checkbutton(renewal, text='정확한 client·연결·marker·old/new 지문을 검토했습니다. 이 연결만 한 번 전환합니다.',
                                             variable=self.refresh_consent, command=self._enable, state='disabled')
        self.refresh_check.pack(anchor='w',pady=4)
        self.refresh_button = ttk.Button(renewal, text='선택한 연결 실행부 전환 1회', command=self.refresh, state='disabled')
        self.refresh_button.pack(anchor='w')
        self.recheck_button = ttk.Button(renewal, text='전환 후 원본 관측·현재 상태 재대조', command=self.observe)
        self.recheck_button.pack(anchor='w',pady=4)
        ttk.Label(renewal, text='ACK만으로 완료하지 않습니다. 새 실행 세대·현재 선택을 다시 대조해야 합니다.\n'
                  '실패·유실·불확실 결과는 보존하며 이 창을 닫아도 자동 재시도·강제 종료하지 않습니다.',
                  wraplength=830).pack(anchor='w')
        self.review_label = tk.StringVar(value='검토 후보 없음 · 선택 공개/전환 차단')
        ttk.Label(body, textvariable=self.review_label, wraplength=850).pack(anchor='w',pady=4)
        details = ttk.LabelFrame(body, text='원본 관측·정확한 지문·결과 기록')
        details.pack(fill='both',expand=True,pady=4)
        self.details = tk.Text(details, height=10, wrap='none', state='disabled')
        ds = ttk.Scrollbar(details,orient='vertical',command=self.details.yview)
        dx = ttk.Scrollbar(details,orient='horizontal',command=self.details.xview)
        self.details.configure(yscrollcommand=ds.set,xscrollcommand=dx.set)
        self.details.grid(row=0,column=0,sticky='nsew'); ds.grid(row=0,column=1,sticky='ns')
        dx.grid(row=1,column=0,sticky='ew'); details.columnconfigure(0,weight=1); details.rowconfigure(0,weight=1)
        self.client.trace_add('write', self._client_changed)
        for variable in (self.observation_path,self.observation_sha):
            variable.trace_add('write', lambda *args: self._inputs_changed('observation'))
        for variable in (self.selection_path,self.selection_sha):
            variable.trace_add('write', lambda *args: self._inputs_changed('selection'))
        self._bind_viewport()
        self._enable()

    def _bind_viewport(self):
        # A panel-local tag, not bind_all: other tabs, windows, and native
        # combobox popdowns keep their own event handling.
        self.viewport_tag = 'GolemOwnerViewport:' + str(self.frame)
        for sequence in self.viewport_events:
            callback = self._follow_focus if sequence == '<FocusIn>' else self._scroll_viewport
            self.frame.bind_class(self.viewport_tag, sequence, callback)
        pending = [self.frame]
        while pending:
            widget = pending.pop()
            tags = widget.bindtags()
            widget.bindtags((tags[0], self.viewport_tag, *tags[1:]))
            pending.extend(widget.winfo_children())

    def _viewport_target(self, widget):
        nested = False
        while widget is not None:
            if widget is self.frame:
                return 'nested' if nested else 'outer'
            if widget is not self.canvas and widget.winfo_class() in (
                    'Treeview', 'Text', 'Listbox', 'Canvas', 'TScrollbar', 'Scrollbar',
                    'TCombobox', 'Spinbox', 'TSpinbox'):
                nested = True
            widget = widget.master
        return None

    def _scroll_viewport(self, event):
        if self._viewport_target(event.widget) != 'outer':
            return None
        # Shift-wheel belongs to horizontal navigation, never this viewport.
        if getattr(event, 'state', 0) & 1:
            return None
        key = getattr(event, 'keysym', None)
        if key in ('Prior', 'Next'):
            self.canvas.yview_scroll(-1 if key == 'Prior' else 1, 'pages')
        else:
            number, delta = getattr(event, 'num', None), getattr(event, 'delta', 0)
            if number in (4, 5):
                units = -1 if number == 4 else 1
            elif type(delta) is int and delta:
                units = (-1 if delta > 0 else 1) * max(1, min(10, abs(delta) // 120))
            else:
                return None
            self.canvas.yview_scroll(units, 'units')
        return 'break'

    def _follow_focus(self, event):
        if self._viewport_target(event.widget) is None:
            return
        bounds = self.canvas.bbox('all')
        if not bounds:
            return
        height = self.canvas.winfo_height()
        extent = bounds[3] - bounds[1]
        if height <= 1 or extent <= height:
            return
        top = event.widget.winfo_rooty() - self.body.winfo_rooty()
        bottom = top + event.widget.winfo_height()
        current = self.canvas.canvasy(0)
        target = current
        if top < current + 8 or bottom - top > height - 16:
            target = top - 8
        elif bottom > current + height - 8:
            target = bottom - height + 8
        if target != current:
            self.canvas.yview_moveto(max(0.0, min(1.0, (target - bounds[1]) / extent)))

    def _file_inputs(self, parent, path, pin, row):
        from tkinter import ttk, filedialog
        def choose():
            if self.request.busy:
                return
            value = filedialog.askopenfilename(parent=self.root, title='검토한 원본 JSON 선택', filetypes=[('JSON','*.json'),('All files','*')])
            if value:
                path.set(value)
                pin.set('')  # A filename choice never silently chooses its digest.
        for offset,label,var in ((0,'원본 JSON 경로',path),(1,'검토한 SHA-256',pin)):
            ttk.Label(parent,text=label).grid(row=row+offset,column=0,sticky='w',padx=(0,6))
            entry=ttk.Entry(parent,textvariable=var);entry.grid(row=row+offset,column=1,sticky='ew')
            self.input_widgets.append(entry)
        browse=ttk.Button(parent,text='파일 선택',command=choose);browse.grid(row=row,column=2,padx=5)
        self.input_widgets.append(browse);parent.columnconfigure(1,weight=1)

    def _selected_row(self):
        selected=self.tree.selection()
        return selected[0] if len(selected)==1 else None

    def _available_review(self, kind):
        review=self.report.get('review') if self.report else None
        if (not review or review.get('kind')!=kind or self.report.get('client')!=self.client.get() or
                (kind,review['token']) in self.attempted):
            return None
        if kind=='refresh' and self._selected_row()!=review.get('instance'):
            return None
        return review

    def _available_observed_instance(self):
        if (self.request.busy or self.request.closed or self.observation_dirty or not self.report or
                self.report.get('client') != self.client.get() or not self.report.get('valid')):
            return None
        instance = self.report.get('observed_instance')
        return instance if instance in self.tree.get_children() else None

    def select_observed(self):
        # An explicit display action only. No controller call or fallback row.
        instance = self._available_observed_instance()
        if instance is None:
            return
        self.tree.selection_set(instance);self.tree.focus(instance);self.tree.see(instance)
        self.tree.focus_set()
        self._selection_changed()

    def select_client(self, client):
        # Display/input context only. A repeated choice preserves its review.
        if self.request.busy or self.request.closed or client not in self.clients:
            return
        if client != self.client.get():
            self.client.set(client)

    def _client_key(self, client, key):
        if self.request.busy or self.request.closed or client not in self.clients:
            return 'break'
        index = self.clients.index(client)
        if key == 'Left': index = max(0, index-1)
        elif key == 'Right': index = min(len(self.clients)-1, index+1)
        elif key == 'Home': index = 0
        elif key == 'End': index = len(self.clients)-1
        elif key not in ('space', 'Return'): return 'break'
        target = self.clients[index]
        self.select_client(target)
        self.client_buttons[target].focus_set()
        return 'break'

    def _can_request(self):
        return not (self.request.busy or self.request.closed) and self.client.get() in self.clients

    def _enable(self):
        busy=self.request.busy or self.request.closed
        selected=self.client.get() in self.clients
        normal='normal' if not busy and selected else 'disabled'
        for button in self.client_buttons.values():
            button.configure(state='disabled' if busy else 'normal')
        self.client_label.set('선택한 client: '+CLIENT_LABELS.get(self.client.get(), '미선택'))
        for widget in self.input_widgets:
            widget.configure(state=normal)
        self.inspect_button.configure(state=normal)
        observation=not busy and selected and _input_shape(self.observation_path.get(),self.observation_sha.get())
        selection=not busy and selected and _input_shape(self.selection_path.get(),self.selection_sha.get())
        for widget in (self.observe_button,self.review_refresh_button,self.recheck_button):
            widget.configure(state='normal' if observation else 'disabled')
        self.review_selection_button.configure(state='normal' if selection else 'disabled')
        publish=not busy and self._available_review('publish') is not None
        refresh=not busy and self._available_review('refresh') is not None
        self.publish_check.configure(state='normal' if publish else 'disabled')
        self.refresh_check.configure(state='normal' if refresh else 'disabled')
        self.publish_button.configure(state='normal' if publish and self.publish_consent.get() else 'disabled')
        self.refresh_button.configure(state='normal' if refresh and self.refresh_consent.get() else 'disabled')
        self.select_observed_button.configure(
            state='normal' if self._available_observed_instance() is not None else 'disabled')

    def _inputs_changed(self, kind):
        self.input_revision+=1
        self.publish_consent.set(False);self.refresh_consent.set(False)
        if kind=='observation':
            self.observation_dirty=True
            self.readiness.set('관측 입력 변경 · 명시적 재대조 전 연결 확인 보류 · 실행 HOLD')
        if self.report:
            self.report['review']=None
        self.review_label.set('입력 변경 · 후보/전환을 다시 검토하세요')
        self._enable()

    def _client_changed(self, *unused):
        self.input_revision+=1;self.report=None;self.observation_dirty=True;self.selected_instance=None
        self.publish_consent.set(False);self.refresh_consent.set(False)
        self.tree.delete(*self.tree.get_children())
        self.selected.set('client 변경 · 선택 상태 미확인')
        self.model.set('client 변경 · 외부 대화 관측 미확인')
        self.readiness.set('연결 대조 미충족 · 실제 실행 HOLD')
        self.review_label.set('client별 별도 관측·후보 검토 필요')
        self._enable()

    def _selection_changed(self, event=None):
        row=self._selected_row()
        if row!=self.selected_instance:
            self.refresh_consent.set(False);self.selected_instance=row
        self._enable()

    def navigate(self, direction):
        # Tk's default arrows do nothing until an item has focus. As in
        # ConnectionBrowser, only an explicit key seeds the first/last row;
        # rendering never chooses a connection or invokes the controller.
        rows=self.tree.get_children()
        if not rows:
            return 'break'
        selected=self._selected_row()
        index=rows.index(selected) if selected in rows else (-1 if direction>0 else len(rows))
        key=rows[max(0,min(len(rows)-1,index+direction))]
        self.tree.selection_set(key);self.tree.focus(key);self.tree.see(key)
        self._selection_changed()
        return 'break'

    def _render_rows(self, rows):
        selected=self._selected_row()
        self.tree.delete(*self.tree.get_children())
        for key,row in rows:
            self.tree.insert('','end',iid=key,values=row)
        if selected in self.tree.get_children():
            self.tree.selection_set(selected);self.tree.focus(selected);self.tree.see(selected)
        # An absent row invalidates its consent immediately, even before Tk
        # delivers the queued TreeviewSelect event. Never choose a replacement.
        self._selection_changed()

    def _submit(self, kind, operation):
        if not self.request.start(kind,operation):
            return
        self.submitted_revision=self.input_revision;self.submitted_client=self.client.get()
        self.publish_consent.set(False);self.refresh_consent.set(False)
        self.status.set('명시한 작업 처리 중 · 자동 재시도/Work 실행 없음')
        self._enable();self.after_id=self.root.after(40,self._drain)

    def inspect(self):
        if not self._can_request():
            return
        client=self.client.get();self._submit('inspect',lambda:self.controller.inspect(client))

    def observe(self):
        client,path,pin=self.client.get(),self.observation_path.get(),self.observation_sha.get()
        if not self._can_request() or not _input_shape(path,pin):
            return
        self._submit('observe',lambda:self.controller.observe(client,path,pin))

    def review_selection(self):
        client,path,pin=self.client.get(),self.selection_path.get(),self.selection_sha.get()
        if not self._can_request() or not _input_shape(path,pin):
            return
        self._submit('review-publish',lambda:self.controller.review_selection(client,path,pin))

    def review_refresh(self):
        client,path,pin=self.client.get(),self.observation_path.get(),self.observation_sha.get()
        if not self._can_request() or not _input_shape(path,pin):
            return
        self._submit('review-refresh',lambda:self.controller.review_refresh(client,path,pin))

    def publish(self):
        review=self._available_review('publish')
        if self.request.busy or self.request.closed or not review or not self.publish_consent.get():
            return
        client,token=self.client.get(),review['token'];self.attempted.add(('publish',token))
        self._submit('publish',lambda:self.controller.publish(client,token,approve=True))

    def refresh(self):
        review=self._available_review('refresh')
        if self.request.busy or self.request.closed or not review or not self.refresh_consent.get():
            return
        client,token=self.client.get(),review['token'];self.attempted.add(('refresh',token))
        self._submit('refresh',lambda:self.controller.refresh(client,token,approve=True))

    def _render(self, shown):
        self.report=shown
        self.status.set(shown['state']+' · '+CLIENT_LABELS.get(shown['client'],text(shown['client'])))
        self.selected.set(shown['selected']);self.model.set(shown['model'])
        if self.observation_dirty:
            self.readiness.set('외부 관측 입력 미대조 · 실제 실행 HOLD')
        else:
            self.readiness.set(shown['readiness']+'\n'+shown['readiness_reason'])
        self._render_rows(shown['rows'])
        review=shown.get('review')
        if review:
            self.review_label.set('검토 '+review['kind']+' · token '+review['token']+'\n'+
                '\n'.join(str(key)+': '+text(value) for key,value in review.items() if key not in ('kind','token')))
        else:
            self.review_label.set('실행 가능한 검토 후보 없음 · ACK는 연결/권한/완료 판정이 아닙니다.')
        self.details.configure(state='normal');self.details.delete('1.0','end')
        self.details.insert('end',shown['details']);self.details.configure(state='disabled')

    def _drain(self):
        self.after_id=None
        if self.request.closed:
            return
        event=self.request.take()
        if event is not None:
            kind,raw,error=event
            changed=(self.submitted_revision!=self.input_revision or self.submitted_client!=self.client.get())
            if changed:
                error='STABLE_OWNER_INPUT_CHANGED'
            if not error:
                try:
                    shown=presentation(raw,self.client.get())
                except (ValueError,TypeError,KeyError):
                    error='STABLE_OWNER_REPORT_INVALID'
            if error:
                self.report=None;self.publish_consent.set(False);self.refresh_consent.set(False)
                self.status.set(error+' · 결과를 재시도하지 않습니다.')
                self.readiness.set('연결 미확인 · 실제 실행 HOLD')
                self.review_label.set('후보/전환 차단 · 기존 연결·기록 보존')
                self.details.configure(state='normal');self.details.delete('1.0','end')
                self.details.insert('end',_details(raw) if raw is not None else error)
                self.details.configure(state='disabled')
            else:
                if kind in ('observe','review-refresh') and not shown['error'] and shown['valid']:
                    self.observation_dirty=False
                self._render(shown)
            self._enable()
        if self.request.busy:
            self.after_id=self.root.after(40,self._drain)

    def _destroyed(self, event):
        if event.widget is not self.frame:
            return
        self.request.close()
        if hasattr(self, 'viewport_tag'):
            for sequence in self.viewport_events:
                self.frame.unbind_class(self.viewport_tag, sequence)
        if self.after_id is not None:
            self.root.after_cancel(self.after_id);self.after_id=None
