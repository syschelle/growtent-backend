"""ESP is authoritative. The backend edits plans and consumes durable events only."""
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from services.irrigation_client import IrrigationClient, IrrigationError, EVENTS
from services.irrigation_store import IrrigationStore

PLAN_FIELDS=('enabled','every_n_days','offset_after_light_on_min')

def notification(label,event,now=None):
    now=time.time() if now is None else now
    original=event.get('occurred_at')
    delayed=original is None or now-original>60
    when=datetime.fromtimestamp(original,timezone.utc).astimezone(ZoneInfo('Europe/Berlin')).strftime('%d.%m.%Y %H:%M:%S %Z') if original else 'Zeitpunkt unbekannt'
    words={'started':'Bewässerung gestartet','completed':'Bewässerung erfolgreich beendet','aborted':'Bewässerung abgebrochen','missed':'Bewässerung verpasst'}
    title='CanopyOps: '+words[event['type']]
    message=f'{label}: {words[event["type"]]}. {when}.'
    if delayed: message+=' Nachträglich gemeldet.'
    if event['type'] in ('aborted','missed'): message+=f' Grund: {event.get("reason","unknown")}. Anzahl: {event.get("count",1)}.'
    return {'title':title,'message':message,'priority':1 if event['type'] in ('aborted','missed') else 0,'_occurred_at':original,'_delayed':delayed}


def validate_events(batch):
    stream=batch.get('stream_id')
    events=batch.get('events')
    if not isinstance(stream,str) or not 1<=len(stream)<=64 or not isinstance(events,list) or len(events)>8:
        raise IrrigationError('invalid_event_batch')
    previous=None
    for event in events:
        if not isinstance(event,dict) or type(event.get('seq')) is not int or event['seq']<1 or event.get('type') not in ('started','completed','aborted','missed'):
            raise IrrigationError('invalid_event_batch')
        if previous is not None and event['seq']!=previous+1: raise IrrigationError('event_sequence_gap')
        at=event.get('occurred_at')
        if at is not None and (type(at) is not int or not 1609459200<=at<=4102444800): raise IrrigationError('invalid_event_time')
        if not isinstance(event.get('run_id',''),str) or len(event.get('run_id',''))>100: raise IrrigationError('invalid_event_batch')
        if not isinstance(event.get('reason',''),str) or len(event.get('reason',''))>160: raise IrrigationError('invalid_event_batch')
        previous=event['seq']
    return stream,events

class IrrigationService:
    def __init__(self,store=None,config=None,client_factory=None,now=time.time):
        self.store=store or IrrigationStore()
        if config is None:
            from db.crud import get_tent_write_config_raw
            config=get_tent_write_config_raw
        self.config=config
        self.client_factory=client_factory or IrrigationClient
        self.now=now

    def context(self,tent_id):
        cfg=self.config(tent_id)
        if not cfg.get('backend_write_enabled'): raise IrrigationError('backend_write_not_enabled',409)
        if not cfg.get('backend_controller_url') or not cfg.get('_backend_hmac_secret'): raise IrrigationError('backend_hmac_not_configured',409)
        try: client=self.client_factory(cfg['backend_controller_url'],cfg['_backend_hmac_secret'])
        except ValueError as exc: raise IrrigationError('backend_hmac_configuration_invalid',409) from exc
        return cfg,client

    def view(self,tent_id,snapshot,stale=False,error=None):
        state=snapshot.get('state') or {}
        checked=snapshot.get('checked_at')
        return {'tent_id':tent_id,'owner':'esp','plan':{k:state[k] for k in PLAN_FIELDS} if state else None,
                'last_run_date':state.get('last_run_date'),'revision':state.get('revision'),
                'stale':stale,'error':error or snapshot.get('error'),
                'last_success_at':checked.isoformat() if checked else None,
                'legacy_plan':snapshot.get('legacy') if state and state.get('revision')==0 else None,
                'status':{k:state.get(k) for k in ('active','drying_blocked','clock_valid','schedule_stale','last_schedule_sync','queued_events')}}

    def get(self,tent_id):
        try: cfg,client=self.context(tent_id)
        except IrrigationError as exc:
            return {'tent_id':tent_id,'owner':'esp','plan':None,'revision':None,'stale':True,'error':exc.code,'last_run_date':None}
        with self.store.lock(tent_id,client.url) as held:
            snapshot=self.store.snapshot(tent_id,client.url)
            checked=snapshot.get('checked_at')
            attempted=snapshot.get('attempted_at') or checked
            if attempted and self.now()-attempted.timestamp()<30:
                return self.view(tent_id,snapshot,bool(snapshot.get('error')))
            if not held: return self.view(tent_id,snapshot,True,'irrigation_busy')
            try:
                state=client.read_plan();self.store.cache(tent_id,state)
                return self.view(tent_id,self.store.snapshot(tent_id,client.url))
            except IrrigationError as exc:
                self.store.cache(tent_id,error=exc.code)
                return self.view(tent_id,snapshot,True,exc.code)

    def update(self,tent_id,payload):
        cfg,client=self.context(tent_id)
        with self.store.lock(tent_id,client.url) as held:
            if not held: raise IrrigationError('irrigation_busy',409)
            self.store.snapshot(tent_id,client.url)
            values=dict(payload)
            expected=values.pop('expected_revision')
            if values.get('last_run_date') is not None: values['last_run_date']=values['last_run_date'].isoformat() if hasattr(values['last_run_date'],'isoformat') else values['last_run_date']
            try: state=client.apply_plan(expected,values)
            except IrrigationError as exc:
                self.store.cache(tent_id,error=exc.code);raise
            self.store.cache(tent_id,state)
            return {'ok':True,'verified':True,**self.view(tent_id,self.store.snapshot(tent_id,client.url))}

    def start(self,tent_id,command_id):
        cfg,client=self.context(tent_id)
        with self.store.lock(tent_id,client.url) as held:
            if not held: raise IrrigationError('irrigation_busy',409,uncertain=True)
            self.store.snapshot(tent_id,client.url)
            state=client.read_plan()  # Require explicit firmware capability; never fall back to legacy start.
            self.store.resolve_commands(tent_id,client.url,state,int(self.now()))
            command=self.store.command(tent_id,client.url,command_id,int(self.now())+240)
            if command.get('blocked_by'):
                error=IrrigationError('previous_manual_command_unresolved',409,uncertain=True);error.command_id=command['blocked_by'];raise error
            if command['url']!=client.url: raise IrrigationError('manual_controller_changed',409)
            if command['status']=='accepted': return {'ok':True,'verified':True,'command_id':command_id,'unchanged':True}
            if command['status'] in ('rejected','expired','aborted'): raise IrrigationError('manual_command_'+command['status'],409)
            try:
                state=client.manual_start(command_id,command['expires'])
            except IrrigationError as exc:
                self.store.command_status(tent_id,command_id,'uncertain' if exc.uncertain else 'rejected')
                raise
            self.store.command_status(tent_id,command_id,'accepted');self.store.cache(tent_id,state)
            return {'ok':True,'verified':True,'command_id':command_id,'last_run_date':state.get('last_run_date')}

    def sync(self,tent_id):
        cfg,client=self.context(tent_id)
        with self.store.lock(tent_id,client.url) as held:
            if not held: return
            snapshot=self.store.snapshot(tent_id,client.url)
            checked=snapshot.get('checked_at')
            # Event polls have their own durable throttle; UI reads must not starve ingestion.
            if not self.store.claim_poll(tent_id): return
            try:
                state=client.read_plan();self.store.cache(tent_id,state)
                self.store.resolve_commands(tent_id,client.url,state,int(self.now()))
                batch=client.request('GET',EVENTS);stream,events=validate_events(batch)
                if stream!=state['stream_id']: raise IrrigationError('event_stream_changed')
                through=self.store.ingest(tent_id,client.url,stream,events,lambda e:notification(cfg.get('name') or f'Tent {tent_id}',e,self.now()))
                if through is not None: client.ack(stream,through)
                if (state.get('queued_events') or 0)>=48:
                    key=f'irrigation-queue:{tent_id}:{stream}:{int(self.now())//3600}'
                    self.store.warning(tent_id,key,{'title':'CanopyOps: Bewässerungspuffer fast voll','message':f'{cfg.get("name")}: {state["queued_events"]}/64 Ereignisse im ESP-Puffer.','priority':1})
            except IrrigationError as exc:
                self.store.cache(tent_id,error=exc.code)
                # Poller logs safe codes only; failures never trigger watering or erase intent.
                return exc.code
