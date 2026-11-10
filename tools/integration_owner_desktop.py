"""Headless MCP plus an explicitly launched, separate local owner presentation.

Default stdio startup never imports Tk or opens a window. Optional private Unix
IPC retains live-instance validation; it grants no native action or approval.
Same-user IPC is not proof of human identity. No TCP, shell, or policy activation.
"""
import argparse
import asyncio
import copy
from contextlib import nullcontext
from pathlib import Path
import queue
import sys
import threading
import uuid
import integration_contract as c
import integration_registry as r
import integration_mutation_contract as actions
import integration_owner_review as review
import integration_distribution_entry as entry
import integration_preparations as preparations
import integration_lifecycle as lifecycle


class Controller:
    def __init__(self, scoped, owner, *, approve_ui=False):
        c.require(approve_ui is True,'OWNER_DESKTOP_CONSENT_REQUIRED')
        c.require(scoped.profile['profile'] in ('prepare','task','quality','parallel'),'OWNER_DESKTOP_PREPARATION_REQUIRED')
        self.scoped=scoped
        self.owner=review.FirstActionDraft(owner) if scoped.profile['family']=='D2' else owner
        self.reads=scoped.service if scoped.profile['family']=='D2' else scoped.service.reads
        c.require(self.reads.transfer.digest==self.owner.transfer.digest,'PREPARATION_POLICY_BINDING')
        self.selection=None;self.attempted=False

    def drafts(self):
        """List live local references only; native freshness is checked on inspect.

        No spool discovery across instances, new MCP endpoint, or approval.
        Use the existing service and registry locks without waiting/retrying.
        """
        c.require('plan_read' in self.scoped.profile['tools'],'FEATURE_PROFILE_SCOPE')
        c.require(self.reads._lock.acquire(blocking=False),'SERVICE_BUSY')
        try:
            with self.reads.registry.locked():
                self.reads.transfer.current()
                result=[]
                for plan_id,digest in self.reads.preparation_plans.copy().items():
                    raw=r.regular(self.reads.registry.root/('read-m2-plan-'+plan_id)/'plan.json',preparations.MAX_PLAN_BYTES,private=True)
                    c.require(c.sha(raw)==digest,'PREPARATION_CHANGED')
                    value=c.decode(raw,preparations.MAX_PLAN_BYTES)
                    args={key:value[key] for key in ('project_id','work_id','plan_id')}
                    args['plan_sha256']=digest
                    scope=self.reads.transfer.scope(args['project_id'],args['work_id'],'plan_read')
                    self.reads._authorize(scope,args['work_id'],'record')
                    try:plan=preparations.load(self.reads,scope,args)
                    except c.IntegrationError as error:
                        if error.code=='PREPARATION_EXPIRED':continue
                        raise
                    if plan['payload']['kind']=='DRAFT_ACTION':result.append(args)
                return result
        finally:self.reads._lock.release()

    def inspect(self,args):
        self.selection=None;self.attempted=False
        result=self.scoped.call('plan_read',args)
        payload=result['plan']['payload']
        c.require(payload['kind']=='DRAFT_ACTION','OWNER_REVIEW_DRAFT_REQUIRED')
        self.selection=copy.deepcopy(args)
        if payload.get('entry_review',{}).get('tool') in ('intent_qa_accept','intent_completion_finalize'):
            result['owner_display']={'state':'UNAPPROVED_DRAFT','native_contract':'QC4_CURRENT_QA_AND_QC5_LOCAL_NO_MERGE','effect':'CANDIDATE_FILE_ONLY_NOT_POLICY_APPLICATION','required':'SEPARATE_EXACT_INTENT_HOST_AND_D4','native_assurance_label':'LOCAL_COOPERATIVE_REVIEWED_NOT_PROVEN','automatic_execution':False}
        return result

    def export(self,action_id,parent,*,confirmed=False,attachment_path=None,attachment_sha256=None):
        # Share MCP admission through the complete candidate publication. A
        # transport close cannot release D5 while an Owner export is in flight.
        with (self.scoped.admission.operation() if isinstance(self.scoped,lifecycle.AdmittedService) else nullcontext()):
            c.require(confirmed is True,'OWNER_REVIEW_REQUIRED')
            c.require(self.selection is not None and not self.attempted,'OWNER_DESKTOP_REVIEW_REQUIRED')
            # Reserve before any effect, including a failed attachment read. Manual
            # reinspection is possible, but never an automatic repeat of publication.
            self.attempted=True
            attachment=None
            c.require(bool(attachment_path)==bool(attachment_sha256),'OWNER_ATTACHMENT_SELECTION')
            if attachment_path:
                c._validate(attachment_sha256,c.DIGEST)
                raw=r.regular(r.real_path(str(attachment_path)),private=True)
                c.require(c.sha(raw)==attachment_sha256,'OWNER_ATTACHMENT_CHANGED')
                attachment=c.decode(raw);c._validate(attachment,actions.QA)
            parent=r.real_path(str(parent));self.reads.registry._private(parent)
            destination=parent/('owner-review-'+uuid.uuid4().hex)
            try:
                result=review.export_candidate(self.reads,self.selection,self.owner,action_id,destination,
                    approve_review=True,native_attachment=attachment)
            except (c.IntegrationError,OSError,ValueError) as error:
                error.evidence_path=str(destination)
                raise
            return {'candidate_directory':str(destination),**result}


class Window:
    """Tk widgets render untrusted text literally; no HTML, links, or evaluation."""
    def __init__(self,root,controller):
        import tkinter as tk
        from tkinter import ttk
        self.root,self.controller=root,controller
        self.events=queue.Queue();self.busy=False;self.finished=False
        self.reviewed=False;self.attachment=None
        root.title('Golem · Owner 검토');root.geometry('980x780')
        box=ttk.Frame(root,padding=16);box.pack(fill='both',expand=True)
        ttk.Label(box,text='검토 후보 생성 — 실행 승인·정책 적용 아님',font=('',17,'bold')).pack(anchor='w')
        ttk.Label(box,text='같은 연결의 준비안 목록에서 선택하세요. 조회 후 검토·확인해야 후보를 저장할 수 있습니다.').pack(anchor='w',pady=8)
        self.draft_rows=[]
        catalog=ttk.Frame(box);catalog.pack(fill='x',pady=4)
        self.draft_choice=ttk.Combobox(catalog,state='readonly',width=65)
        self.draft_choice.pack(side='left',fill='x',expand=True)
        self.draft_choice.bind('<<ComboboxSelected>>',self.choose_draft)
        self.refresh_button=ttk.Button(catalog,text='준비안 목록 새로고침',command=self.refresh)
        self.refresh_button.pack(side='left',padx=8)
        self.fields={};self.inputs=[]
        for key,label in (('project_id','프로젝트'),('work_id','Work'),('plan_id','Plan ID'),('plan_sha256','Plan SHA-256'),('action_id','새 action ID')):
            row=ttk.Frame(box);row.pack(fill='x',pady=2)
            ttk.Label(row,text=label,width=18).pack(side='left')
            var=tk.StringVar();self.fields[key]=var
            widget=ttk.Entry(row,textvariable=var);widget.pack(side='left',fill='x',expand=True);self.inputs.append(widget)
            var.trace_add('write',self.invalidate)
        buttons=ttk.Frame(box);buttons.pack(fill='x',pady=8)
        self.inspect_button=ttk.Button(buttons,text='현재 초안 조회',command=self.inspect);self.inspect_button.pack(side='left')
        self.attachment_button=ttk.Button(buttons,text='기존 native 첨부 선택 (실행 요청만)',command=self.choose_attachment);self.attachment_button.pack(side='left',padx=8)
        self.text=tk.Text(box,wrap='word',height=22,state='disabled');self.text.pack(fill='both',expand=True)
        self.consent=tk.BooleanVar(value=False)
        ttk.Checkbutton(box,text='표시한 정확한 초안·첨부를 검토했습니다. 후보 파일만 생성합니다.',variable=self.consent).pack(anchor='w',pady=8)
        self.export_button=ttk.Button(box,text='새 private 폴더에 검토 후보 생성',command=self.export,state='disabled');self.export_button.pack(anchor='w')
        self.status=tk.StringVar(value='미조회 · 정책 적용/실행 없음')
        ttk.Label(box,textvariable=self.status,wraplength=900).pack(anchor='w',pady=8)
        root.protocol('WM_DELETE_WINDOW',self.close)
        root.after(100,self.poll)

    def invalidate(self,*unused):
        self.reviewed=False
        if hasattr(self,'consent'):self.consent.set(False)
        if hasattr(self,'export_button'):self.export_button.configure(state='disabled')

    def show(self,value):
        self.text.configure(state='normal');self.text.delete('1.0','end')
        import json
        self.text.insert('end',json.dumps(value,ensure_ascii=True,indent=2));self.text.configure(state='disabled')

    def submit(self,kind,operation):
        if self.busy:return
        self.busy=True
        for widget in self.inputs:widget.configure(state='disabled')
        self.inspect_button.configure(state='disabled');self.export_button.configure(state='disabled');self.attachment_button.configure(state='disabled')
        self.refresh_button.configure(state='disabled');self.draft_choice.configure(state='disabled')
        self.status.set('검사 중 · 자동 재시도 없음')
        def worker():
            try:self.events.put((kind,operation(),None))
            except Exception as error:self.events.put((kind,None,{'code':getattr(error,'code','LOCAL_REVIEW_FAILED'),'candidate_directory':getattr(error,'evidence_path',None),'automatic_retry_allowed':False}))
        threading.Thread(target=worker,daemon=False).start()

    def refresh(self):
        self.invalidate()
        self.draft_rows=[];self.draft_choice.configure(values=());self.draft_choice.set('')
        self.submit('catalog',self.controller.drafts)

    def choose_draft(self,event=None):
        if self.busy:return
        index=self.draft_choice.current()
        if index<0 or index>=len(self.draft_rows):return
        for key,value in self.draft_rows[index].items():self.fields[key].set(value)
        self.fields['action_id'].set('')
        self.invalidate();self.attachment=None
        self.status.set('준비안 선택됨 · 새 action ID 입력 후 현재 초안 조회 필요')

    def inspect(self):
        args={k:self.fields[k].get() for k in ('project_id','work_id','plan_id','plan_sha256')}
        self.invalidate();self.attachment=None
        self.submit('inspect',lambda:self.controller.inspect(args))

    def choose_attachment(self):
        from tkinter import filedialog
        if self.busy or not self.reviewed:return
        path=filedialog.askopenfilename(title='owner가 검토한 기존 native 승인 첨부 JSON')
        if not path:return
        try:
            raw=r.regular(r.real_path(path),private=True);value=c.decode(raw);c._validate(value,actions.QA)
            self.attachment=(path,c.sha(raw));self.consent.set(False)
            self.show({'draft':self.displayed,'owner_selected_attachment':value,'attachment_sha256':c.sha(raw)})
        except (c.IntegrationError,OSError,ValueError) as error:
            self.attachment=None;self.consent.set(False)
            self.show({'draft':self.displayed,'attachment_error':getattr(error,'code','ATTACHMENT_READ_FAILED'),'selected_attachment':None})
            self.status.set('첨부 선택 실패 · 첨부 없음')

    def export(self):
        from tkinter import filedialog,messagebox
        if self.busy or not self.reviewed or not self.consent.get():return
        parent=filedialog.askdirectory(title='Work·registry 밖 owner-private 출력 폴더')
        if not parent:return
        action_id=self.fields['action_id'].get()
        if not messagebox.askokcancel('정확한 후보 생성',f'action: {action_id}\n출력 부모: {parent}\n기존 정책을 변경하지 않고 새 후보만 생성합니다.'):return
        attachment=self.attachment
        self.reviewed=False;self.consent.set(False)
        self.submit('export',lambda:self.controller.export(action_id,parent,confirmed=True,
            attachment_path=attachment[0] if attachment else None,attachment_sha256=attachment[1] if attachment else None))

    def poll(self):
        try:
            while True:
                kind,result,error=self.events.get_nowait()
                self.busy=False
                for widget in self.inputs:widget.configure(state='normal')
                self.inspect_button.configure(state='normal');self.attachment_button.configure(state='normal')
                self.refresh_button.configure(state='normal');self.draft_choice.configure(state='readonly')
                if error:
                    self.reviewed=False;self.show(error);self.status.set('차단/실패 · 부분 파일 보존 · 자동 재시도 없음')
                else:
                    self.show(result)
                    if kind=='catalog':
                        self.draft_rows=result
                        self.draft_choice.configure(values=[row['project_id']+' / '+row['work_id']+' / '+row['plan_id'] for row in result])
                        self.status.set(f'현재 연결의 유효한 초안 {len(result)}개 · 목록에서 선택하세요 · 최신성 검사는 조회 시 수행')
                    elif kind=='inspect':
                        self.displayed=result;self.reviewed=True;self.export_button.configure(state='normal');self.status.set('현재 초안 확인 · native admission 미실행')
                    else:self.status.set('후보 생성됨 · 미적용 · 실행/QA/완료를 의미하지 않음')
        except queue.Empty:pass
        if self.finished and not self.busy:self.root.destroy();return
        self.root.after(100,self.poll)

    def close(self):
        # Closing presentation never closes the service. An in-flight export
        # finishes in its worker; losing the view is not permission to retry.
        self.finished=True
        if not self.busy:self.root.destroy()
        else:
            self.root.withdraw()


def run(scoped,owner,*,approve_ui=False,review_directory=None,review_label="Golem"):
    """Legacy launcher-compatible headless entry; IPC is separately opt-in."""
    with entry.connection(scoped,owner) as scoped:
        endpoint=None
        if review_directory is not None:
            controller=Controller(scoped,owner,approve_ui=approve_ui)
            try:
                endpoint=ReviewEndpoint(review_directory,controller,label=review_label)
                endpoint.start()
            except Exception:
                # An optional presentation failure must not take down MCP. Do not
                # retry, repair directories, or expose endpoint tokens in stderr.
                if endpoint is not None:endpoint.close()
                endpoint=None
                sys.stderr.write('OWNER_REVIEW_UNAVAILABLE; MCP remains headless.\n')
        try:
            asyncio.run(entry.serve(scoped,owner))
            return 0
        except Exception:
            sys.stderr.write('Golem transport stopped; no automatic restart.\n')
            return 1
        finally:
            if endpoint is not None:endpoint.close()



def main(argv=None):
    argv=list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0]=='owner-app':return owner_app(argv[1:])
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile',choices=('prepare','task','quality','parallel'),default='prepare')
    parser.add_argument('--policy',required=True);parser.add_argument('--reviewed-policy-sha256',dest='digest',required=True)
    parser.add_argument('--approve-owner',action='store_true');parser.add_argument('--approve-owner-review-ui',action='store_true')
    parser.add_argument('--review-directory',help='Existing owner-private Unix IPC directory; explicit opt-in only')
    parser.add_argument('--review-label',default='Golem',help='Display label only; never authenticated client identity')
    args=vars(parser.parse_args(argv));approved=args.pop('approve_owner_review_ui');directory=args.pop('review_directory');label=args.pop('review_label')
    try:
        c.require(approved is True,'OWNER_DESKTOP_CONSENT_REQUIRED')
        scoped,owner=entry._configure_startup(args)
        return run(scoped,owner,approve_ui=approved,review_directory=directory,review_label=label)
    except Exception as error:
        sys.stderr.write(c.encoded({'code':getattr(error,'code','OWNER_DESKTOP_UNAVAILABLE'),'execution_authorized':False,'automatic_retry_allowed':False}).decode()+'\n');return 1



# IPC is owner-host presentation only, never registered as an MCP tool. File
# ownership/private modes and a per-instance random capability exclude other OS
# users, not malicious code already running as this owner. Human intent remains
# an explicit UI review, not an identity attestation by this protocol.
IPC_LIMIT=1048576
IPC_TIMEOUT=30
IPC_REQUEST_LIMIT=1024


def private_directory(value):
    import os,stat
    path=Path(value)
    c.require(path.is_absolute() and path.resolve()==path,'OWNER_IPC_DIRECTORY')
    info=path.lstat()
    c.require(stat.S_ISDIR(info.st_mode) and info.st_uid==os.getuid() and
              stat.S_IMODE(info.st_mode)==0o700,'OWNER_IPC_DIRECTORY')
    return path


def identity(value):
    import re
    c.require(isinstance(value,str) and re.fullmatch('[0-9a-f]{32}',value) is not None,'OWNER_IPC_ID')
    return value


def receive_frame(conn):
    import time
    deadline=time.monotonic()+IPC_TIMEOUT
    def exact(count):
        result=bytearray()
        while len(result)<count:
            left=deadline-time.monotonic()
            if left<=0:raise TimeoutError('OWNER_IPC_TIMEOUT')
            conn.settimeout(left)
            part=conn.recv(count-len(result))
            if not part:raise EOFError('OWNER_IPC_CLOSED')
            result.extend(part)
        return bytes(result)
    size=int.from_bytes(exact(4),'big')
    c.require(0<size<=IPC_LIMIT,'OWNER_IPC_SIZE')
    return c.decode(exact(size),IPC_LIMIT)


def send_frame(conn,value):
    raw=c.encoded(value);c.require(len(raw)<=IPC_LIMIT,'OWNER_IPC_SIZE')
    conn.settimeout(IPC_TIMEOUT);conn.sendall(len(raw).to_bytes(4,'big')+raw)


def descriptor(directory,instance):
    import os,stat
    directory=private_directory(directory);identity(instance)
    path=directory/(instance+'.json')
    info=path.lstat()
    c.require(stat.S_ISREG(info.st_mode) and info.st_uid==os.getuid() and stat.S_IMODE(info.st_mode)==0o600,'OWNER_IPC_DESCRIPTOR')
    value=c.decode(r.regular(path,4096,private=True),4096)
    c.require(set(value)=={'instance','token','kind','label'} and value['instance']==instance and
              value['kind'] in ('review','activation'),'OWNER_IPC_DESCRIPTOR')
    c.require(isinstance(value['label'],str) and 0<len(value['label'])<=80 and all(ch.isprintable() for ch in value['label']),'OWNER_IPC_LABEL')
    c._validate(value['token'],c.DIGEST)
    return value


class LocalEndpoint:
    """Single bounded request worker; no retry or takeover of existing paths."""
    def __init__(self,directory,handler,kind='review',label='Golem'):
        import secrets
        self.directory=private_directory(directory);self.handler=handler
        c.require(isinstance(label,str) and 0<len(label)<=80 and all(ch.isprintable() for ch in label),'OWNER_IPC_LABEL')
        self.instance=uuid.uuid4().hex;self.token=secrets.token_hex(32);self.kind=kind;self.label=label
        self.path=self.directory/(self.instance+'.sock')
        c.require(len(str(self.path).encode())<100,'OWNER_IPC_PATH_LENGTH')
        self.record=self.directory/(self.instance+'.json')
        self.stop=threading.Event();self.worker=None;self.socket=None;self.seen=set()
        self.created_socket=False;self.created_record=False

    def start(self):
        import os,socket
        c.require(self.socket is None,'OWNER_IPC_ALREADY_STARTED')
        private_directory(self.directory)
        self.socket=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        try:
            self.socket.bind(str(self.path));self.created_socket=True;os.chmod(self.path,0o600)
            self.socket.listen(4);self.socket.settimeout(.2)
            from execution_record import save
            save(self.record,c.encoded({'instance':self.instance,'token':self.token,'kind':self.kind,'label':self.label}));self.created_record=True
            self.worker=threading.Thread(target=self.serve,daemon=False);self.worker.start()
        except Exception:
            self.close();raise
        return self

    def dispatch(self,message):
        import hmac
        c.require(isinstance(message,dict) and set(message)=={'instance','token','request_id','operation','arguments'},'OWNER_IPC_ENVELOPE')
        c.require(message['instance']==self.instance and isinstance(message['token'],str) and
                  hmac.compare_digest(message['token'],self.token),'OWNER_IPC_AUTH')
        request=identity(message['request_id'])
        c.require(request not in self.seen,'OWNER_IPC_REPLAY')
        c.require(len(self.seen)<IPC_REQUEST_LIMIT,'OWNER_IPC_QUOTA')
        c.require(type(message['operation']) is str and type(message['arguments']) is dict,'OWNER_IPC_ENVELOPE')
        self.seen.add(request)
        return self.handler(message['operation'],message['arguments'])

    def serve(self):
        import socket
        while not self.stop.is_set():
            try:conn,_=self.socket.accept()
            except socket.timeout:continue
            except OSError:break
            with conn:
                try:
                    message=receive_frame(conn)
                    c.require(not self.stop.is_set(),'OWNER_IPC_CLOSED')
                    value=self.dispatch(message)
                    send_frame(conn,{'ok':True,'value':value})
                except Exception as error:
                    try:send_frame(conn,{'ok':False,'code':getattr(error,'code','OWNER_IPC_FAILED'),
                        'candidate_directory':getattr(error,'evidence_path',None),'automatic_retry_allowed':False})
                    except (OSError,EOFError):pass

    def close(self):
        self.stop.set()
        if self.socket is not None:self.socket.close()
        if self.worker is not None:
            # Never kill an in-flight candidate export. It uses bounded native
            # calls; preserve partial evidence if the OS terminates the process.
            self.worker.join()
        for path,created in ((self.record,self.created_record),(self.path,self.created_socket)):
            if created:
                try:path.unlink()
                except FileNotFoundError:pass
        self.created_record=False;self.created_socket=False


class ReviewEndpoint(LocalEndpoint):
    def __init__(self,directory,controller,*,label='Golem'):
        self.controller=controller;self.exports=set()
        super().__init__(directory,self.handle,label=label+' / '+controller.scoped.profile['profile'])

    def handle(self,operation,args):
        if operation=='catalog':
            c.require(not args,'OWNER_IPC_ARGUMENTS')
            return self.controller.drafts()
        if operation=='inspect':
            return self.controller.inspect(args)
        if operation=='export':
            c.require(set(args)=={'plan','action_id','parent','confirmed','attachment_path','attachment_sha256'},'OWNER_IPC_ARGUMENTS')
            c.require(args['confirmed'] is True,'OWNER_REVIEW_REQUIRED')
            c._validate(args['plan'],preparations.SCHEMAS['plan_read'])
            # One export attempt per exact plan per service, even when a second
            # owner client reconnects or a reply is lost. Reinspection cannot
            # clear this publication fence. No policy/action is executed here.
            key=(args['plan']['plan_id'],args['plan']['plan_sha256'])
            c.require(key not in self.exports,'OWNER_EXPORT_ALREADY_ATTEMPTED')
            self.exports.add(key)
            self.controller.inspect(args['plan'])
            return self.controller.export(args['action_id'],args['parent'],confirmed=True,
                attachment_path=args['attachment_path'],attachment_sha256=args['attachment_sha256'])
        raise c.IntegrationError('OWNER_IPC_OPERATION')


class RemoteController:
    def __init__(self,directory,instance):
        self.directory=private_directory(directory);self.instance=identity(instance)
        self.pinned=descriptor(self.directory,instance)
        c.require(self.pinned['kind']=='review','OWNER_IPC_KIND')
        self.selection=None;self.attempted=False

    def call(self,operation,args):
        import socket
        c.require(descriptor(self.directory,self.instance)==self.pinned,'OWNER_IPC_CHANGED')
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as conn:
            conn.settimeout(IPC_TIMEOUT)
            try:
                conn.connect(str(self.directory/(self.instance+'.sock')))
                send_frame(conn,{'instance':self.instance,'token':self.pinned['token'],
                    'request_id':uuid.uuid4().hex,'operation':operation,'arguments':args})
                reply=receive_frame(conn)
            except (OSError,EOFError,ValueError):
                raise c.IntegrationError('OWNER_EXPORT_UNKNOWN' if operation=='export' else 'OWNER_CONNECTION_UNAVAILABLE') from None
        c.require(isinstance(reply,dict) and type(reply.get('ok')) is bool,'OWNER_IPC_RESPONSE')
        if not reply['ok']:
            error=c.IntegrationError(reply.get('code','OWNER_IPC_FAILED'))
            error.evidence_path=reply.get('candidate_directory')
            raise error
        return reply['value']

    def drafts(self):return self.call('catalog',{})

    def inspect(self,args):
        self.selection=None;self.attempted=False
        value=self.call('inspect',args);self.selection=copy.deepcopy(args);return value

    def export(self,action_id,parent,*,confirmed=False,attachment_path=None,attachment_sha256=None):
        c.require(confirmed is True and self.selection is not None and not self.attempted,'OWNER_DESKTOP_REVIEW_REQUIRED')
        self.attempted=True
        return self.call('export',{'plan':self.selection,'action_id':action_id,'parent':str(parent),
            'confirmed':True,'attachment_path':attachment_path,'attachment_sha256':attachment_sha256})


def connections(directory):
    directory=private_directory(directory)
    names=list(directory.glob('*.json'))
    c.require(len(names)<=128,'OWNER_IPC_CATALOG_LIMIT')
    rows=[]
    for path in sorted(names):
        if path.stem=='owner-app':continue
        value=descriptor(directory,path.stem)
        if value['kind']=='review':rows.append(value['instance'])
    return rows


CONNECTION_STATES = {'record': '연결 기록 · 생존 미확인', 'closed': '종료/사용 불가',
                     'invalid': '검증 불가'}


class ConnectionCatalog:
    """Presentation-only cache. Never probe Work, delete records or infer authority."""
    def __init__(self,directory):
        self.directory=private_directory(directory);self.rows={}

    def refresh(self):
        import os,stat
        names=list(self.directory.glob('*.json'))
        c.require(len(names)<=128,'OWNER_IPC_CATALOG_LIMIT')
        current={}
        for path in sorted(names):
            if path.stem=='owner-app':continue
            key=path.stem;label=self.rows.get(key,{}).get('label',key)
            try:
                value=descriptor(self.directory,key)
                if value['kind']!='review':continue
                label=value['label']
                info=(self.directory/(key+'.sock')).lstat()
                valid=stat.S_ISSOCK(info.st_mode) and info.st_uid==os.getuid() and stat.S_IMODE(info.st_mode)==0o600
                state='record' if valid else 'invalid'
                label=value['label']
            except FileNotFoundError:
                state='closed'
            except (OSError,c.IntegrationError):
                state='invalid'
            current[key]={'instance':key,'label':label,'state':state}
        # Retain only bounded in-memory history, not a second persistent registry.
        for key,row in self.rows.items():
            if key not in current and len(current)<128:
                current[key]={**row,'state':'closed'}
        self.rows=current

    def visible(self,query='',show_closed=False,order='name'):
        words=query.casefold().split()
        rows=[row for row in self.rows.values()
              if (show_closed or row['state']!='closed') and
              all(word in (row['label']+' '+row['instance']).casefold() for word in words)]
        key=(lambda row:row['instance']) if order=='id' else (lambda row:(row['label'].casefold(),row['instance']))
        return sorted(rows,key=key,reverse=order=='name_desc')


class ConnectionBrowser:
    """Search/sort preserves exact instance selection; no automatic first-row pick."""
    def __init__(self,root,directory,open_callback):
        import tkinter as tk
        from tkinter import ttk
        self.catalog=ConnectionCatalog(directory);self.open_callback=open_callback
        pane=ttk.Frame(root,padding=16);pane.pack(fill='both',expand=True)
        ttk.Label(pane,text='Owner 연결 선택 — 실행 승인·정책 적용 없음').pack(anchor='w')
        controls=ttk.Frame(pane);controls.pack(fill='x',pady=8)
        ttk.Label(controls,text='이름 / 연결 ID 검색').pack(side='left')
        self.query=tk.StringVar();self.search=ttk.Entry(controls,textvariable=self.query,width=30)
        self.search.pack(side='left',fill='x',expand=True,padx=8)
        self.order=tk.StringVar(value='이름순');sort=ttk.Combobox(controls,textvariable=self.order,
            values=['이름순','이름 역순','연결 ID순'],state='readonly',width=12);sort.pack(side='left')
        self.show_closed=tk.BooleanVar(value=False)
        ttk.Checkbutton(pane,text='종료/사용 불가 연결 표시 (기록 삭제 없음)',variable=self.show_closed,command=self.render).pack(anchor='w')
        table=ttk.Frame(pane);table.pack(fill='both',expand=True,pady=8)
        self.tree=ttk.Treeview(table,columns=('name','state','id'),show='headings',selectmode='browse',height=10)
        for column,title,width in [('name','연결 이름',280),('state','상태',190),('id','정확한 연결 ID',280)]:
            self.tree.heading(column,text=title);self.tree.column(column,width=width,minwidth=100)
        scrollbar=ttk.Scrollbar(table,orient='vertical',command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set);scrollbar.pack(side='right',fill='y');self.tree.pack(fill='both',expand=True)
        self.status=tk.StringVar();ttk.Label(pane,textvariable=self.status,wraplength=800).pack(anchor='w')
        buttons=ttk.Frame(pane);buttons.pack(fill='x',pady=8)
        ttk.Button(buttons,text='연결 목록 새로고침',command=self.refresh).pack(side='left')
        self.open_button=ttk.Button(buttons,text='선택한 연결 검토',command=self.open_selected,state='disabled')
        self.open_button.pack(side='left',padx=12)
        ttk.Label(pane,text='소켓 기록은 생존·권한 보증이 아닙니다. 실제 조회 시 원래 연결을 다시 검사합니다.').pack(anchor='w')
        self.query.trace_add('write',lambda *_:self.render());sort.bind('<<ComboboxSelected>>',lambda _:self.render())
        self.tree.bind('<<TreeviewSelect>>',lambda _:self.selection_changed())
        self.tree.bind('<Return>',lambda _:self.open_selected())
        self.tree.bind('<Down>',lambda _:self.navigate(1))
        self.tree.bind('<Up>',lambda _:self.navigate(-1))
        self.refresh()

    def navigate(self,direction):
        # An explicit arrow key selects; refresh/filter alone never does.
        rows=self.tree.get_children()
        if not rows:return 'break'
        selected=self.tree.selection()
        index=rows.index(selected[0]) if selected and selected[0] in rows else (-1 if direction>0 else len(rows))
        key=rows[max(0,min(len(rows)-1,index+direction))]
        self.tree.selection_set(key);self.tree.focus(key);self.tree.see(key)
        self.selection_changed()
        return 'break'

    def selection_changed(self):
        selected=self.tree.selection();row=self.catalog.rows.get(selected[0]) if selected else None
        self.open_button.configure(state='normal' if row and row['state']=='record' else 'disabled')

    def render(self):
        selected=self.tree.selection()
        rows=self.catalog.visible(self.query.get(),self.show_closed.get(),
            {'이름순':'name','이름 역순':'name_desc','연결 ID순':'id'}[self.order.get()])
        self.tree.delete(*self.tree.get_children())
        for row in rows:self.tree.insert('', 'end',iid=row['instance'],values=(row['label'],CONNECTION_STATES[row['state']],row['instance']))
        if selected and self.tree.exists(selected[0]):self.tree.selection_set(selected[0]);self.tree.focus(selected[0]);self.tree.see(selected[0])
        self.selection_changed()
        closed=sum(row['state']=='closed' for row in self.catalog.rows.values())
        self.status.set(f'표시 {len(rows)} / 전체 {len(self.catalog.rows)} · 종료/사용 불가 {closed} · 자동 선택 없음')

    def refresh(self):
        try:self.catalog.refresh();self.render()
        except Exception as error:
            self.tree.delete(*self.tree.get_children());self.selection_changed()
            self.status.set(getattr(error,'code','OWNER_CONNECTION_UNAVAILABLE'))

    def open_selected(self):
        selected=self.tree.selection()
        if not selected:return
        key=selected[0];row=self.catalog.rows.get(key)
        if not row or row['state']!='record':return
        try:self.open_callback(key)
        except Exception as error:
            state='closed' if isinstance(error,FileNotFoundError) or getattr(error,'code','')=='OWNER_CONNECTION_UNAVAILABLE' else 'invalid'
            self.catalog.rows[key]={**row,'state':state};self.render()
            self.status.set(getattr(error,'code','OWNER_CONNECTION_UNAVAILABLE')+' · 재실행 없음')


class OwnerInstance:
    """OS lock, not PID guessing. Stale files never authorize a new service."""
    def __init__(self,directory):
        import os,stat,fcntl
        self.directory=private_directory(directory);self.endpoint=None;self.primary=False
        path=self.directory/'owner-app.lock'
        self.fd=os.open(path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
        info=os.fstat(self.fd)
        if not (stat.S_ISREG(info.st_mode) and info.st_uid==os.getuid() and stat.S_IMODE(info.st_mode)==0o600):
            os.close(self.fd);raise c.IntegrationError('OWNER_APP_LOCK')
        try:fcntl.flock(self.fd,fcntl.LOCK_EX|fcntl.LOCK_NB);self.primary=True
        except BlockingIOError:pass
        self.events=queue.Queue()

    def activate(self):
        import socket
        raw=r.regular(self.directory/'owner-app.json',4096,private=True)
        instance=c.decode(raw,4096)['instance'];value=descriptor(self.directory,instance)
        c.require(value['kind']=='activation','OWNER_IPC_KIND')
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as conn:
            conn.settimeout(IPC_TIMEOUT);conn.connect(str(self.directory/(instance+'.sock')))
            send_frame(conn,{**{k:value[k] for k in ('instance','token')},'request_id':uuid.uuid4().hex,'operation':'activate','arguments':{}})
            c.require(receive_frame(conn)=={'ok':True,'value':True},'OWNER_APP_ACTIVATION')

    def start(self):
        import os
        c.require(self.primary,'OWNER_APP_ALREADY_RUNNING')
        def handle(operation,args):
            c.require(operation=='activate' and not args,'OWNER_IPC_OPERATION')
            self.events.put(True);return True
        self.endpoint=LocalEndpoint(self.directory,handle,'activation').start()
        from execution_record import save
        temporary=self.directory/(uuid.uuid4().hex+'.tmp')
        save(temporary,c.encoded({'instance':self.endpoint.instance}))
        os.replace(temporary,self.directory/'owner-app.json')

    def close(self):
        import os
        if self.endpoint is not None:
            self.endpoint.close()
            try:(self.directory/'owner-app.json').unlink()
            except FileNotFoundError:pass
        os.close(self.fd)


def owner_app(argv):
    parser=argparse.ArgumentParser(description='Explicit local Owner app; no MCP or native execution')
    parser.add_argument('--review-directory',required=True)
    args=parser.parse_args(argv);instance=OwnerInstance(args.review_directory)
    try:
        if not instance.primary:
            instance.activate();return 0
        instance.start()
        import tkinter as tk
        from tkinter import ttk
        root=tk.Tk();root.title('Golem · Owner 연결 선택');root.geometry('900x480')
        windows={}
        def open_review(key):
            # Recheck descriptor even when a previous child window exists.
            controller=RemoteController(instance.directory,key)
            old=windows.get(key)
            if old is not None and old.winfo_exists():old.deiconify();old.lift();return
            child=tk.Toplevel(root);windows[key]=child
            Window(child,controller);child.title('Golem · Owner 검토 · '+key[:12])
        browser=ConnectionBrowser(root,instance.directory,open_review)
        def poll():
            try:
                while True:instance.events.get_nowait();root.deiconify();root.lift()
            except queue.Empty:pass
            root.after(100,poll)
        root.after(100,poll);root.mainloop()
        return 0
    finally:instance.close()


if __name__=='__main__':sys.exit(main())
