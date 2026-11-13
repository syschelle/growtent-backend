import copy
import hashlib
import hmac
import json
from contextlib import contextmanager
from datetime import datetime,timezone

import httpx
import pytest
from services.irrigation_client import IrrigationClient,IrrigationError,PLAN,EVENTS,ACK,START
from services.irrigation_service import IrrigationService,notification,validate_events

KEY='0123456789abcdef'*4
NOW=1794560400
COMMAND='a'*32

def state(**overrides):
    return dict(ok=True,api_version=2,manual_start_supported=True,enabled=True,revision=3,
        every_n_days=2,offset_after_light_on_min=60,last_run_date='2026-11-12',stream_id='stream1',
        manual_commands=[],pending_request=0,last_applied_request=0,last_failed_request=0,**overrides)

def response(request,body,status=200,*,modify=None):
    nonce=request.headers['X-GrowTent-Nonce']
    raw=json.dumps(body,separators=(',',':')).encode()
    timestamp=str(NOW)
    canonical=f'RESPONSE\n{request.method}\n{request.url.path}\n{status}\n{timestamp}\n{nonce}\n{hashlib.sha256(raw).hexdigest()}'
    sig=hmac.new(bytes.fromhex(KEY),canonical.encode(),hashlib.sha256).hexdigest()
    headers={'X-GrowTent-Nonce':nonce,'X-GrowTent-Timestamp':timestamp,'X-GrowTent-Signature':sig}
    if modify: raw,status,headers=modify(raw,status,headers)
    return httpx.Response(status,content=raw,headers=headers)

def client_for(handler):
    def checked(request):
        ts=request.headers['X-GrowTent-Timestamp'];nonce=request.headers['X-GrowTent-Nonce']
        canonical=f'{request.method}\n{request.url.path}\n{ts}\n{nonce}\n{hashlib.sha256(request.content).hexdigest()}'
        assert request.headers['X-GrowTent-Signature']==hmac.new(bytes.fromhex(KEY),canonical.encode(),hashlib.sha256).hexdigest()
        assert not request.url.query
        return handler(request)
    return IrrigationClient('http://esp:8080',KEY,client_factory=lambda:httpx.Client(transport=httpx.MockTransport(checked)),now=lambda:NOW,sleep=lambda n:None)

@pytest.mark.parametrize('path,method,payload',[(PLAN,'GET',None),(PLAN,'POST',{'revision':4}),(EVENTS,'GET',None),(ACK,'POST',{'stream_id':'x','through_seq':8}),(START,'POST',{'command_id':COMMAND,'expires_at':NOW+240})])
def test_each_path_and_method_sign_exact_bytes(path,method,payload):
    client=client_for(lambda request:response(request,{'ok':True}))
    assert client.request(method,path,payload)['ok']

@pytest.mark.parametrize('tamper', ['body','nonce','timestamp','signature','status'])
def test_tampered_signed_response_never_accepted(tamper):
    def mutate(raw,status,headers):
        if tamper=='body': raw=raw+b' '
        if tamper=='nonce': headers['X-GrowTent-Nonce']='b'*32
        if tamper=='timestamp': headers['X-GrowTent-Timestamp']=str(NOW-61)
        if tamper=='signature': headers['X-GrowTent-Signature']='0'*64
        if tamper=='status': status=202
        return raw,status,headers
    client=client_for(lambda request:response(request,{'ok':True},modify=mutate))
    with pytest.raises(IrrigationError):client.request('GET',PLAN)

def test_unsigned_success_is_rejected():
    client=client_for(lambda r:httpx.Response(200,json={'ok':True}))
    with pytest.raises(IrrigationError,match='authentication'):client.request('GET',PLAN)

def test_wrong_key_signed_response_rejected():
    def handler(request):
        result=response(request,{'ok':True})
        result.headers['X-GrowTent-Signature']=hmac.new(b'wrong',b'response',hashlib.sha256).hexdigest()
        return result
    with pytest.raises(IrrigationError,match='signature'):client_for(handler).request('GET',PLAN)

@pytest.mark.parametrize('code',['drying_phase','watering_running','event_queue_full','nonce_cache_full','invalid_last_run_date'])
def test_signed_controller_rejections_do_not_fallback(code):
    paths=[]
    def handler(req):paths.append(req.url.path);return response(req,{'ok':False,'error':code},409)
    client=client_for(handler)
    with pytest.raises(IrrigationError,match=code):client.manual_start(COMMAND,NOW+240)
    assert paths==[START]

def test_plan_edit_waits_for_durable_revision_and_allows_real_history_to_advance():
    current=state();posts=[]
    def handler(req):
        if req.method=='GET':return response(req,current)
        data=json.loads(req.content);posts.append(data)
        current.update(data,last_run_date='2026-11-13',last_applied_request=17)
        return response(req,{'ok':True,'requestId':17},202)
    client=client_for(handler)
    result=client.apply_plan(3,{'enabled':True,'every_n_days':3,'offset_after_light_on_min':10,'last_run_date':'2026-11-12'})
    assert result['revision']==4 and result['last_run_date']=='2026-11-13'
    assert posts[0]['last_run_date']=='2026-11-12' # No fabricated today baseline.

def test_stale_plan_revision_never_posts():
    posts=[]
    client=client_for(lambda req:(posts.append(req.method) or response(req,state())))
    with pytest.raises(IrrigationError,match='revision_conflict'):client.apply_plan(2,{'enabled':True})
    assert posts==['GET']

def test_old_firmware_is_not_used_as_legacy_start_fallback():
    client=client_for(lambda req:response(req,{**state(),'api_version':1,'manual_start_supported':False}))
    with pytest.raises(IrrigationError,match='upgrade_required'):client.read_plan()

def event(seq=1,kind='started',**kw):
    return {'seq':seq,'type':kind,'occurred_at':NOW-10,'run_id':COMMAND,'reason':'test','count':1,**kw}

def test_event_validation_rejects_gaps_and_invalid_times():
    for events in ([event(1),event(3)],[event(1,occurred_at=True)],[event(1,kind='unknown')]):
        with pytest.raises(IrrigationError):validate_events({'stream_id':'s','events':events})

def test_delayed_push_uses_original_time_and_aborted_is_not_success():
    delayed=notification('Tent',event(kind='aborted',occurred_at=NOW-3600),NOW)
    assert 'Nachträglich' in delayed['message'] and 'abgebrochen' in delayed['title']
    assert 'erfolgreich' not in delayed['title']
    assert 'Nachträglich' not in notification('Tent',event(),NOW)['message']

class MemoryStore:
    def __init__(self):
        self.snapshot_value={'state':None,'legacy':{'plan':{'enabled':True,'every_n_days':7},'last_run_date':'2026-11-01'},'checked_at':None,'error':None}
        self.events={};self.outbox={};self.commands={};self.order=[];self.fail_ingest=False
    @contextmanager
    def lock(self,tent,*args):yield True
    def snapshot(self,*args):return copy.deepcopy(self.snapshot_value)
    def cache(self,tent,state=None,error=None):
        if state is not None:self.snapshot_value.update(state=copy.deepcopy(state),checked_at=datetime.fromtimestamp(NOW,timezone.utc),error=None)
        else:self.snapshot_value['error']=error
    def event_error(self,tent,error=None):self.snapshot_value['event_error']=error
    def claim_poll(self,tent):return True
    def resolve_commands(self,*args):pass
    def ingest(self,tent,url,stream,events,notify):
        if self.fail_ingest:raise RuntimeError('database failure')
        for e in events:
            key=(tent,url,stream,e['seq'])
            if key not in self.events:self.events[key]=e;self.outbox[key]=notify(e)
        self.order.append('durable_ingest')
        return events[-1]['seq'] if events else None
    def warning(self,*args):pass
    def command(self,tent,url,command,expires):
        for key,row in self.commands.items():
            if key!=command and row['status']=='uncertain':return {'blocked_by':key}
        return self.commands.setdefault(command,{'url':url,'expires':expires,'status':'prepared'})
    def command_status(self,tent,command,status):self.commands[command]['status']=status

class FakeClient:
    url='http://esp:8080'
    def __init__(self,store):self.store=store;self.state=state();self.failure=None;self.starts=[];self.acks=[]
    def read_plan(self):
        if self.failure:raise self.failure
        return copy.deepcopy(self.state)
    def request(self,method,path):return {'ok':True,'stream_id':'stream1','events':[event()]}
    def ack(self,stream,seq):self.store.order.append('ack');self.acks.append(seq)
    def manual_start(self,command,expires):
        self.starts.append((command,expires))
        if self.failure:raise self.failure
        return self.state
    def apply_plan(self,revision,payload):
        assert revision==self.state['revision']
        self.state.update(payload,revision=revision+1)
        return self.state

def service_fixture():
    store=MemoryStore();client=FakeClient(store)
    config=lambda tent:{'backend_write_enabled':True,'backend_controller_url':client.url,'_backend_hmac_secret':KEY,'name':'Tent'}
    service=IrrigationService(store,config,lambda *args:client,now=lambda:NOW)
    return service,store,client

def test_ingest_is_idempotent_and_commits_before_ack():
    service,store,client=service_fixture();service.sync(1);service.sync(1)
    assert len(store.events)==len(store.outbox)==1
    assert store.order==['durable_ingest','ack','durable_ingest','ack']

def test_database_failure_never_acknowledges_events():
    service,store,client=service_fixture();store.fail_ingest=True
    with pytest.raises(RuntimeError):service.sync(1)
    assert client.acks==[]

def test_offline_read_returns_stale_confirmed_state_and_never_writes_controller():
    service,store,client=service_fixture();service.get(1)
    store.snapshot_value['checked_at']=datetime.fromtimestamp(NOW-100,timezone.utc)
    client.failure=IrrigationError('controller_unreachable')
    result=service.get(1)
    assert result['stale'] and result['plan']['every_n_days']==2 and not client.starts

def test_legacy_plan_is_suggested_only_for_explicit_first_transfer():
    service,store,client=service_fixture();client.state['revision']=0
    result=service.get(1)
    assert result['legacy_plan']['plan']['every_n_days']==7
    assert result['plan']['every_n_days']==2 # GET never overwrites the ESP.

def test_manual_repeat_uses_existing_command_and_no_second_start():
    service,store,client=service_fixture()
    assert service.start(1,COMMAND)['ok']
    assert service.start(1,COMMAND)['unchanged']
    assert len(client.starts)==1

def test_unresolved_manual_identity_blocks_new_command():
    service,store,client=service_fixture()
    store.commands[COMMAND]={'url':client.url,'expires':NOW+240,'status':'uncertain'}
    with pytest.raises(IrrigationError) as error:service.start(1,'b'*32)
    assert error.value.command_id==COMMAND and error.value.uncertain
    assert not client.starts

def test_backend_routes_retire_legacy_automatic_and_manual_post():
    from pathlib import Path
    source=(Path(__file__).parents[1]/'api/app.py').read_text()
    scheduler=source.split('def _try_run_irrigation_schedule(',1)[1].split('\ndef ',1)[0]
    assert 'client.post' not in scheduler and 'return None' in scheduler
    start=source.split('def start_watering(',1)[1].split('\n\n',1)[0]
    assert "_irrigation_call('start'" in start and 'proxy_post' not in start

def test_manual_poll_failure_after_acceptance_remains_uncertain():
    def handler(request):
        if request.method=='POST':return response(request,{'ok':True,'requestId':99},202)
        raise httpx.ConnectError('offline',request=request)
    with pytest.raises(IrrigationError) as error:client_for(handler).manual_start(COMMAND,NOW+240)
    assert error.value.uncertain, 'A failed status GET cannot justify a new physical command identity'

def test_manual_post_timeout_keeps_command_for_reconciliation():
    service,store,client=service_fixture()
    def ambiguous(command,expires):
        raise IrrigationError('controller_unreachable',uncertain=True)
    client.manual_start=ambiguous
    with pytest.raises(IrrigationError):service.start(1,COMMAND)
    assert store.commands[COMMAND]['status']=='uncertain'


def test_mutation_models_require_revision_and_explicit_manual_identity():
    from models.schemas import IrrigationPlanPayload,ManualIrrigationPayload
    from pydantic import ValidationError
    with pytest.raises(ValidationError):IrrigationPlanPayload(enabled=True)
    with pytest.raises(ValidationError):IrrigationPlanPayload(expected_revision=1,every_n_days=2.5)
    with pytest.raises(ValidationError):ManualIrrigationPayload(command_id='bad')
    assert IrrigationPlanPayload(expected_revision=0,enabled=True,every_n_days=366,offset_after_light_on_min=0).every_n_days==366

def test_event_failure_does_not_make_confirmed_plan_stale_or_uneditable():
    service,store,client=service_fixture()
    def fail_events(*args):raise IrrigationError('event_sequence_gap')
    client.request=fail_events
    assert service.sync(1)=='event_sequence_gap'
    summary=service.get(1)
    assert summary['stale'] is False and summary['error'] is None
    assert summary['event_sync_error']=='event_sequence_gap'
    assert service.update(1,{'expected_revision':3,'enabled':True,'every_n_days':3,'offset_after_light_on_min':60,'last_run_date':'2026-11-12'})['verified']


def test_busy_refresh_uses_recent_confirmed_revision_but_not_old_or_failed_cache():
    service,store,client=service_fixture();service.get(1)
    from contextlib import contextmanager
    @contextmanager
    def busy(*args):yield False
    store.lock=busy
    store.snapshot_value['checked_at']=datetime.fromtimestamp(NOW-40,timezone.utc)
    summary=service.get(1)
    assert not summary['stale'] and summary['refresh_pending']
    store.snapshot_value['checked_at']=datetime.fromtimestamp(NOW-120,timezone.utc)
    assert service.get(1)['stale']
    store.snapshot_value['checked_at']=datetime.fromtimestamp(NOW-40,timezone.utc)
    store.snapshot_value['error']='controller_unreachable'
    assert service.get(1)['stale']


@pytest.mark.parametrize('method',['GET','POST'])
def test_unsigned_auth_diagnostic_never_becomes_authenticated_success(method):
    client=client_for(lambda request:httpx.Response(403,json={'ok':False,'error':'source_ip_not_allowed'}))
    with pytest.raises(IrrigationError,match='unverified_source_ip_not_allowed') as error:client.request(method,PLAN,{} if method=='POST' else None)
    assert error.value.uncertain==(method=='POST')
