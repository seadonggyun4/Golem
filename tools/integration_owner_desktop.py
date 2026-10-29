"""Opt-in native Desktop owner review sharing the MCP service's live M2 plans.

No listener, browser, approval issuer, or policy activation. Start only as the
explicitly selected stdio launcher; this does not modify a client installation.
"""
import argparse
import asyncio
import copy
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
        return result

    def export(self,action_id,parent,*,confirmed=False,attachment_path=None,attachment_sha256=None):
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
        from tkinter import messagebox
        if self.finished and not self.busy:self.root.destroy()
        else:messagebox.showinfo('연결 유지','MCP 연결이 살아 있어 검토 창을 종료하지 않습니다. 창을 최소화하거나 client에서 이 연결을 정상 종료하세요. 진행 중 작업을 강제 종료하지 않습니다.')


def run(scoped,owner,*,approve_ui=False):
    controller=Controller(scoped,owner,approve_ui=approve_ui)
    import tkinter as tk
    root=tk.Tk();window=Window(root,controller);outcome=[]
    def transport():
        try:asyncio.run(entry.serve(scoped,owner));outcome.append(0)
        except Exception:outcome.append(1);sys.stderr.write('Golem Desktop transport stopped; no automatic restart.\n')
        finally:window.finished=True
    worker=threading.Thread(target=transport,daemon=False);worker.start()
    root.mainloop();worker.join()
    return outcome[0] if outcome else 1


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile',choices=('prepare','task','quality','parallel'),default='prepare')
    parser.add_argument('--policy',required=True);parser.add_argument('--reviewed-policy-sha256',dest='digest',required=True)
    parser.add_argument('--approve-owner',action='store_true');parser.add_argument('--approve-owner-review-ui',action='store_true')
    args=vars(parser.parse_args(argv));approved=args.pop('approve_owner_review_ui')
    try:
        c.require(approved is True,'OWNER_DESKTOP_CONSENT_REQUIRED')
        scoped,owner=entry._configure_startup(args)
        return run(scoped,owner,approve_ui=approved)
    except Exception as error:
        sys.stderr.write(c.encoded({'code':getattr(error,'code','OWNER_DESKTOP_UNAVAILABLE'),'execution_authorized':False,'automatic_retry_allowed':False}).decode()+'\n');return 1


if __name__=='__main__':sys.exit(main())
