"""PostgreSQL journal, cached controller state and transactional notification outbox."""
from contextlib import contextmanager
import hashlib
import json
@contextmanager
def get_conn():
    from db.database import get_conn as connect
    conn=connect()
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def create_tables(cur):
    cur.execute('''CREATE TABLE IF NOT EXISTS irrigation_controller_state (
        tent_id INTEGER PRIMARY KEY REFERENCES tents(id) ON DELETE CASCADE,
        controller_url TEXT NOT NULL, state JSONB, legacy_plan JSONB NOT NULL,
        checked_at TIMESTAMPTZ, error_code TEXT, polled_at TIMESTAMPTZ, attempted_at TIMESTAMPTZ);
      CREATE TABLE IF NOT EXISTS irrigation_events (
        event_key TEXT PRIMARY KEY, tent_id INTEGER NOT NULL REFERENCES tents(id) ON DELETE CASCADE,
        controller_url TEXT NOT NULL, stream_id TEXT NOT NULL, seq BIGINT NOT NULL,
        event JSONB NOT NULL, received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(controller_url,stream_id,seq));
      CREATE TABLE IF NOT EXISTS irrigation_notifications (
        notification_key TEXT PRIMARY KEY, tent_id INTEGER NOT NULL REFERENCES tents(id) ON DELETE CASCADE,
        payload JSONB NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
        next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), sent_at TIMESTAMPTZ);
      CREATE TABLE IF NOT EXISTS irrigation_commands (
        tent_id INTEGER NOT NULL REFERENCES tents(id) ON DELETE CASCADE, command_id TEXT NOT NULL,
        controller_url TEXT NOT NULL, expires_at BIGINT NOT NULL, status TEXT NOT NULL,
        PRIMARY KEY(tent_id,command_id));''')

class IrrigationStore:
    @contextmanager
    def lock(self, tent_id, url=None):
        lock_key=int.from_bytes(hashlib.sha256(url.encode()).digest()[:4],'big',signed=True) if url else tent_id
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT pg_try_advisory_lock(119670, %s)',(lock_key,))
                held=cur.fetchone()[0]
                try: yield held
                finally:
                    if held: cur.execute('SELECT pg_advisory_unlock(119670, %s)',(lock_key,))

    def snapshot(self,tent_id,url):
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT irrigation_plan_json,irrigation_last_run_date FROM tents WHERE id=%s',(tent_id,))
                row=cur.fetchone()
                if not row: raise ValueError('tent_not_found')
                legacy={'plan':json.loads(row[0] or '{}'),'last_run_date':row[1].isoformat() if row[1] else None}
                cur.execute('''INSERT INTO irrigation_controller_state(tent_id,controller_url,legacy_plan)
                    VALUES(%s,%s,%s::jsonb) ON CONFLICT(tent_id) DO NOTHING''',(tent_id,url,json.dumps(legacy)))
                cur.execute('SELECT controller_url,state,legacy_plan,checked_at,error_code,attempted_at FROM irrigation_controller_state WHERE tent_id=%s',(tent_id,))
                current=cur.fetchone()
                if current[0]!=url:
                    # Never use a previous physical controller's state/commands for a new host.
                    cur.execute('UPDATE irrigation_controller_state SET controller_url=%s,state=NULL,checked_at=NULL,polled_at=NULL,error_code=NULL,legacy_plan=%s::jsonb WHERE tent_id=%s',(url,json.dumps(legacy),tent_id))
                    return {'state':None,'legacy':legacy,'checked_at':None,'error':None}
                return {'state':current[1],'legacy':current[2],'checked_at':current[3],'error':current[4],'attempted_at':current[5]}

    def cache(self,tent_id,state=None,error=None):
        with get_conn() as conn:
            with conn.cursor() as cur:
                if state is None:
                    cur.execute('UPDATE irrigation_controller_state SET error_code=%s,attempted_at=NOW() WHERE tent_id=%s',(error,tent_id))
                else:
                    cur.execute('UPDATE irrigation_controller_state SET state=%s::jsonb,checked_at=NOW(),attempted_at=NOW(),error_code=NULL WHERE tent_id=%s',(json.dumps(state),tent_id))
                    plan={k:state[k] for k in ('enabled','every_n_days','offset_after_light_on_min')}
                    cur.execute('UPDATE tents SET irrigation_plan_json=%s,irrigation_last_run_date=%s WHERE id=%s',(json.dumps(plan),state.get('last_run_date'),tent_id))

    def command(self,tent_id,url,command_id,expires):
        with get_conn() as conn:
            with conn.cursor() as cur:
                # An uncertain earlier command must be resolved, never replaced by a new ID.
                cur.execute("SELECT command_id FROM irrigation_commands WHERE tent_id=%s AND controller_url=%s AND status IN ('prepared','uncertain') AND command_id<>%s LIMIT 1",(tent_id,url,command_id))
                old=cur.fetchone()
                if old: return {'blocked_by':old[0]}
                cur.execute("INSERT INTO irrigation_commands VALUES(%s,%s,%s,%s,'prepared') ON CONFLICT DO NOTHING",(tent_id,command_id,url,expires))
                cur.execute('SELECT controller_url,expires_at,status FROM irrigation_commands WHERE tent_id=%s AND command_id=%s',(tent_id,command_id))
                row=cur.fetchone()
                return {'url':row[0],'expires':row[1],'status':row[2]}

    def command_status(self,tent_id,command_id,status):
        with get_conn() as conn:
            with conn.cursor() as cur: cur.execute('UPDATE irrigation_commands SET status=%s WHERE tent_id=%s AND command_id=%s',(status,tent_id,command_id))

    @staticmethod
    def event_key(tent_id,url,stream,seq):
        return hashlib.sha256(json.dumps([url,stream,seq]).encode()).hexdigest()

    def ingest(self,tent_id,url,stream,events,notify):
        # Commit both the event and notification intent before returning a safe ACK cursor.
        with get_conn() as conn:
            with conn.cursor() as cur:
                for event in events:
                    key=self.event_key(tent_id,url,stream,event['seq'])
                    cur.execute('''INSERT INTO irrigation_events(event_key,tent_id,controller_url,stream_id,seq,event)
                        VALUES(%s,%s,%s,%s,%s,%s::jsonb) ON CONFLICT DO NOTHING RETURNING event_key''',
                        (key,tent_id,url,stream,event['seq'],json.dumps(event)))
                    if cur.fetchone():
                        cur.execute('''INSERT INTO irrigation_notifications(notification_key,tent_id,payload)
                            VALUES(%s,%s,%s::jsonb) ON CONFLICT DO NOTHING''',(key,tent_id,json.dumps(notify(event))))
                    if event.get('run_id') and event['type'] in ('started','completed','aborted'):
                        cur.execute("UPDATE irrigation_commands SET status=%s WHERE tent_id=%s AND command_id=%s AND controller_url=%s",("aborted" if event["type"]=="aborted" else "accepted",tent_id,event["run_id"],url))
        return events[-1]['seq'] if events else None

    def warning(self,tent_id,key,payload):
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute('INSERT INTO irrigation_notifications(notification_key,tent_id,payload) VALUES(%s,%s,%s::jsonb) ON CONFLICT DO NOTHING',(key,tent_id,json.dumps(payload)))

    def deliver(self,send,limit=8):
        for _ in range(limit):
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute('''SELECT notification_key,payload FROM irrigation_notifications
                        WHERE sent_at IS NULL AND next_attempt_at<=NOW() ORDER BY next_attempt_at
                        FOR UPDATE SKIP LOCKED LIMIT 1''')
                    row=cur.fetchone()
                    if not row: return
                    try: ok=bool(send(**row[1]))
                    except Exception: ok=False
                    if ok: cur.execute('UPDATE irrigation_notifications SET sent_at=NOW() WHERE notification_key=%s',(row[0],))
                    else: cur.execute("UPDATE irrigation_notifications SET attempts=attempts+1,next_attempt_at=NOW()+LEAST(3600,15*POWER(2,LEAST(attempts,8))) * INTERVAL '1 second' WHERE notification_key=%s",(row[0],))

    def claim_poll(self,tent_id):
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE irrigation_controller_state SET polled_at=NOW() WHERE tent_id=%s AND (polled_at IS NULL OR polled_at<NOW()-INTERVAL '30 seconds') RETURNING tent_id",(tent_id,))
                return cur.fetchone() is not None

    def resolve_commands(self,tent_id,url,state,now):
        known={c['command_id']:c.get('status') for c in state.get('manual_commands',[])}
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT command_id,expires_at FROM irrigation_commands WHERE tent_id=%s AND controller_url=%s AND status IN ('prepared','uncertain')",(tent_id,url))
                for command_id,expires in cur.fetchall():
                    status=('aborted' if known[command_id]=='aborted' else 'accepted') if command_id in known else 'expired' if expires<=now else None
                    if status: cur.execute('UPDATE irrigation_commands SET status=%s WHERE tent_id=%s AND command_id=%s',(status,tent_id,command_id))
