"""Signed ESP irrigation protocol. Never retry a physical start with a new identity."""
from __future__ import annotations
import hashlib
import hmac
import json
import secrets
import time
from datetime import date
import httpx
from services.grow_write_service import normalize_controller_url, validate_secret_hex, serialize_request_body

PLAN = '/api/backend/irrigation-plan'
EVENTS = '/api/backend/irrigation-events'
ACK = '/api/backend/irrigation-events/ack'
START = '/api/backend/irrigation-start'

class IrrigationError(Exception):
    def __init__(self, code, status=502, *, uncertain=False):
        self.code, self.status, self.uncertain = code, status, uncertain
        self.command_id = None
        super().__init__(code)

class IrrigationClient:
    def __init__(self, url, secret, *, client_factory=None, now=time.time, sleep=time.sleep):
        self.url = normalize_controller_url(url)
        self.key = bytes.fromhex(validate_secret_hex(secret))
        self.factory = client_factory or (lambda: httpx.Client(timeout=5, follow_redirects=False))
        self.now, self.sleep = now, sleep

    def request(self, method, path, payload=None):
        body = b'' if payload is None else serialize_request_body(payload)
        nonce, stamp = secrets.token_hex(16), str(int(self.now()))
        canonical = f'{method}\n{path}\n{stamp}\n{nonce}\n{hashlib.sha256(body).hexdigest()}'
        signature = hmac.new(self.key, canonical.encode(), hashlib.sha256).hexdigest()
        headers = {'Content-Type':'application/json', 'X-GrowTent-Timestamp':stamp,
                   'X-GrowTent-Nonce':nonce, 'X-GrowTent-Signature':signature}
        try:
            with self.factory() as client:
                response = client.request(method, self.url + path, content=body, headers=headers)
        except httpx.RequestError as exc:
            raise IrrigationError('controller_unreachable', uncertain=method=='POST') from exc
        raw = response.content
        if len(raw) > 32768:
            raise IrrigationError('controller_response_too_large', uncertain=method=='POST')
        ts = response.headers.get('X-GrowTent-Timestamp', '')
        rn = response.headers.get('X-GrowTent-Nonce', '')
        sig = response.headers.get('X-GrowTent-Signature', '')
        if not ts.isdigit() or abs(int(ts)-int(self.now())) > 60 or rn != nonce or len(sig)!=64 or any(c not in '0123456789abcdef' for c in sig):
            raise IrrigationError('invalid_response_authentication', uncertain=method=='POST')
        canonical = f'RESPONSE\n{method}\n{path}\n{response.status_code}\n{ts}\n{nonce}\n{hashlib.sha256(raw).hexdigest()}'
        expected = hmac.new(self.key, canonical.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            raise IrrigationError('invalid_response_signature', uncertain=method=='POST')
        try:
            data = json.loads(raw)
        except (ValueError, UnicodeError) as exc:
            raise IrrigationError('invalid_controller_json', uncertain=method=='POST') from exc
        if not isinstance(data, dict):
            raise IrrigationError('invalid_controller_json', uncertain=method=='POST')
        if response.status_code >= 400 or data.get('ok') is not True:
            code = str(data.get('error') or 'controller_error')
            # Only a fixed safe code is exposed; arbitrary controller messages are not logged.
            if not code.replace('_','').isalnum() or len(code)>80: code='controller_error'
            raise IrrigationError(code, response.status_code if 400 <= response.status_code < 500 else 502)
        return data

    def read_plan(self):
        state = self.request('GET', PLAN)
        if type(state.get('api_version')) is not int or state['api_version'] < 2 or state.get('manual_start_supported') is not True:
            raise IrrigationError('firmware_upgrade_required', 409)
        for key, low, high in [('revision',0,4294967295),('every_n_days',1,366),('offset_after_light_on_min',0,1440)]:
            if type(state.get(key)) is not int or not low <= state[key] <= high:
                raise IrrigationError('invalid_controller_state')
        if type(state.get('enabled')) is not bool or not isinstance(state.get('stream_id'),str):
            raise IrrigationError('invalid_controller_state')
        last=state.get('last_run_date')
        if last is not None:
            try:
                if date.fromisoformat(last).isoformat()!=last: raise ValueError()
            except (ValueError,TypeError): raise IrrigationError('invalid_controller_state')
        commands=state.get('manual_commands')
        if not isinstance(commands,list) or len(commands)>16 or any(not isinstance(c,dict) or not isinstance(c.get('command_id'),str) or c.get('status') not in ('accepted','completed','aborted') for c in commands):
            raise IrrigationError('invalid_controller_state')
        return state

    def wait(self, request_id, *, revision=None, values=None, command_id=None):
        for attempt in range(6):
            self.sleep(1)
            state = self.read_plan()
            if command_id:
                command = next((c for c in state.get('manual_commands',[]) if c.get('command_id')==command_id),None)
                if command:
                    if command.get('status')=='aborted': raise IrrigationError('manual_start_aborted',409)
                    return state
            elif revision is not None:
                if state['revision']==revision and all((state.get(k)==v if k!='last_run_date' else v is None or state.get(k) is not None and state[k]>=v) for k,v in values.items()): return state
                if state['revision']>revision: raise IrrigationError('revision_conflict',409,uncertain=True)
            elif state.get('last_applied_request')==request_id: return state
            if state.get('last_failed_request')==request_id:
                raise IrrigationError('controller_apply_failed',409)
        raise IrrigationError('controller_apply_timeout',504,uncertain=True)

    def apply_plan(self, expected_revision, payload):
        current=self.read_plan()
        if current['revision']!=expected_revision or expected_revision>=4294967295:
            raise IrrigationError('revision_conflict',409)
        last=payload.get('last_run_date',current.get('last_run_date'))
        stored=current.get('last_run_date')
        if stored and (not last or last < stored): raise IrrigationError('invalid_last_run_date',400)
        values={k:payload[k] for k in ('enabled','every_n_days','offset_after_light_on_min')}
        values['last_run_date']=last
        result=self.request('POST',PLAN,{'revision':expected_revision+1,**values})
        return self.wait(result.get('requestId'),revision=expected_revision+1,values=values)

    def manual_start(self, command_id, expires_at):
        result=self.request('POST',START,{'command_id':command_id,'expires_at':expires_at})
        try:
            if result.get('unchanged'):
                if result.get('command_status')=='aborted': raise IrrigationError('manual_start_aborted',409)
                return self.read_plan()
            return self.wait(result.get('requestId'),command_id=command_id)
        except IrrigationError as exc:
            # Acceptance was authenticated. A failed subsequent GET cannot prove
            # that a physical start did not occur. Keep the same command identity.
            if exc.code not in ('manual_start_aborted','controller_apply_failed'):
                exc.uncertain=True
            raise

    def ack(self, stream, seq):
        result=self.request('POST',ACK,{'stream_id':stream,'through_seq':seq})
        return self.wait(result.get('requestId'))
