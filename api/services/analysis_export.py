"""Read-only, bounded analysis projection of historical ESP samples."""
from datetime import datetime, timedelta, timezone
import math
from .vpd_channels import finite_number, esp_control_vpd, esp_raw_vpd

HOURS = {'1h':1, '6h':6, '12h':12, '24h':24, '48h':48}
SHELLY_ROLES = ('main','light','humidifier','heater','heatmat','fan','exhaust')
CONTEXT_DETAIL_LIMIT = 128
METRICS = ('temperature','humidity','vpd','temperature_raw','humidity_raw','vpd_raw','humidifier_watt','alpha_temperature','alpha_humidity')

def iso(ts):
    return ts.astimezone(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')

def targets(data):
    t=finite_number(data.get('settings.grow.targetTemperature'))
    v=finite_number(data.get('settings.grow.targetVPD'))
    return {'temperature':t,'vpd':v if v is not None and v>=0 else None,
        'leaf_offset':finite_number(data.get('settings.grow.offsetLeafTemperature'))}

def sample_values(data):
    available=(data.get('sensors.climate.fresh',True) is True and data.get('sensors.climate.status','ok')=='ok')
    def number(*keys):
        for key in keys:
            if key in data: return finite_number(data[key])
        return None
    values={
        'temperature':number('sensors.smoothed.temperatureC','sensors.cur.temperatureC'),
        'humidity':number('sensors.smoothed.humidityPct','sensors.cur.humidityPct'),
        'vpd':esp_control_vpd(data),
        'temperature_raw':number('sensors.cur.temperatureRawC','sensors.raw.temperatureC'),
        'humidity_raw':number('sensors.cur.humidityRawPct','sensors.raw.humidityPct'),
        'vpd_raw':esp_raw_vpd(data),
    }
    if not available: values={key:None for key in values}
    # Missing is not OFF; stale Shelly cache must not produce inferred transitions.
    fresh=data.get('cur.shelly.humidifier.fresh',True) is True
    state=data.get('cur.shelly.humidifier.isOn') if fresh else None
    state=state if isinstance(state,bool) else None
    values['alpha_temperature']=number('sensors.cur.effectiveAlfaTempC') if available else None
    values['alpha_humidity']=number('sensors.cur.effectiveAlfaHumPct') if available else None
    values['humidifier_watt']=number('cur.shelly.humidifier.Watt','cur.shelly.hum.Watt') if fresh else None
    return values,state

def _stats(values):
    return {'avg':round(math.fsum(v/len(values) for v in values),4) if values else None,
        'min':min(values) if values else None,'max':max(values) if values else None,'n':len(values)}


def _clock(value):
    # Only export the ESP's stored schedule times, never the IP-bearing line.
    if not isinstance(value,str) or len(value)>5:return None
    parts=value.split(':')
    if len(parts)!=2 or not all(p.isdigit() for p in parts):return None
    hour,minute=map(int,parts)
    return f'{hour:02}:{minute:02}' if 0<=hour<24 and 0<=minute<60 else None


def analysis_context(data):
    def integer(key):
        value=finite_number(data.get(key))
        return int(value) if value is not None and value>=0 and value.is_integer() else None
    return {'phase':integer('settings.grow.currentPhase'),
        'phase_week':integer('settings.grow.currentPhaseWeek'),
        'phase_day':integer('settings.grow.currentPhaseDay'),
        'grow_week':integer('settings.grow.currentGrowWeek'),
        'grow_day':integer('settings.grow.currentGrowDay'),
        'light_schedule':{'on':_clock(data.get('settings.shelly.light.on')),
            'off':_clock(data.get('settings.shelly.light.off'))}}


def shelly_samples(data):
    result={}
    for role in SHELLY_ROLES:
        prefix=f'cur.shelly.{role}.'
        if not data.get(f'settings.shelly.{role}.ip') and not any(key.startswith(prefix) for key in data if isinstance(key,str)):
            continue
        freshness=data.get(prefix+'fresh')
        fresh=freshness if isinstance(freshness,bool) else None
        # Legacy missing freshness is unknown, not an explicit failed sample.
        available=fresh is True or prefix+'fresh' not in data
        state=data.get(prefix+'isOn') if available else None
        state=state if isinstance(state,bool) else None
        power=finite_number(data.get(prefix+'Watt')) if available else None
        if role=='humidifier' and prefix+'Watt' not in data and available:
            power=finite_number(data.get('cur.shelly.hum.Watt'))
        energy=finite_number(data.get(prefix+'Wh')) if available else None
        age=finite_number(data.get(prefix+'ageMs'))
        result[role]={'state':state,'fresh':fresh,'power':power,
            'energy':energy if energy is not None and energy>=0 else None,
            'age':age if age is not None and age>=0 else None}
    return result


def build_analysis_export(tent_id,rows,end,hours=24,poll_seconds=10,max_points=720):
    if hours not in HOURS.values(): raise ValueError('unsupported range')
    end=end.astimezone(timezone.utc)
    start=end-timedelta(hours=hours)
    seconds=max(120,math.ceil(hours*3600/max_points/120)*120)
    gap_threshold=max(60,3*poll_seconds)
    count=math.ceil(hours*3600/seconds)
    buckets=[]
    for i in range(count):
        t=start+timedelta(seconds=i*seconds)
        buckets.append({'timestamp':iso(t),'samples':0,'metrics':{},
            'targets_first':None,'targets_last':None,'target_changes':[], 'target_change_count':0,'shelly':{},
            'humidifier':{'on_samples':0,'off_samples':0,'unknown_samples':0,'observed_changes':0,'transitions':[]}})
    accum=[{key:[] for key in METRICS} for _ in buckets]
    previous_time=None;previous_state=None;previous_targets=None
    sample_count=0;gaps=[];event_omissions=0
    previous_devices={};device_accum=[{} for _ in buckets]
    context_first=None;context_last=None;context_timeline=[];context_changes=0;context_omissions=0
    # No filling from current/latest settings, preceding DB rows or future samples.
    for ts,data in sorted(rows,key=lambda row:row[0]):
        ts=ts.astimezone(timezone.utc)
        if not (start<=ts<end): continue
        data=data if isinstance(data,dict) else {}
        index=min(count-1,int((ts-start).total_seconds())//seconds)
        bucket=buckets[index];bucket['samples']+=1;sample_count+=1
        delta=(ts-(previous_time or start)).total_seconds()
        if delta>gap_threshold:
            gaps.append({'from':iso(previous_time or start),'to':iso(ts),'seconds':round(delta,1)})
            previous_state=None;previous_devices={}
        values,state=sample_values(data)
        for key,value in values.items():
            if value is not None:accum[index][key].append(value)
        context=analysis_context(data)
        if context_first is None:context_first={'at':iso(ts),**context}
        if context_last is None or context!={k:v for k,v in context_last.items() if k!='at'}:
            if context_last is not None:context_changes+=1
            entry={'at':iso(ts),**context}
            if len(context_timeline)<CONTEXT_DETAIL_LIMIT:context_timeline.append(entry)
            else:context_omissions+=1
        context_last={'at':iso(ts),**context}
        devices=shelly_samples(data)
        for role,sample in devices.items():
            if role not in bucket['shelly']:
                bucket['shelly'][role]={'samples':0,'on_samples':0,'off_samples':0,'unknown_samples':0,
                    'fresh_samples':0,'stale_samples':0,'freshness_unknown_samples':0,
                    'state_first':sample['state'],'state_last':None,
                    'observed_changes':0,'transitions':[]}
                device_accum[index][role]={'power':[],'energy':[],'age':[]}
            device=bucket['shelly'][role];device['samples']+=1
            st=sample['state'];device['state_last']=st
            device['unknown_samples' if st is None else 'on_samples' if st else 'off_samples']+=1
            device['freshness_unknown_samples' if sample['fresh'] is None else 'fresh_samples' if sample['fresh'] else 'stale_samples']+=1
            for metric in ['power','energy','age']:
                if sample[metric] is not None:device_accum[index][role][metric].append(sample[metric])
            prev=previous_devices.get(role)
            if prev is not None and st is not None and st!=prev:
                device['observed_changes']+=1
                if len(device['transitions'])<8:device['transitions'].append({'at':iso(ts),'on':st})
                elif role!='humidifier':event_omissions+=1
        # A missing role or invalid sample breaks continuity, just like a gap.
        previous_devices={role:sample['state'] for role,sample in devices.items()}
        target=targets(data)
        if bucket['targets_first'] is None:bucket['targets_first']=target
        bucket['targets_last']=target
        if previous_targets is not None and target!=previous_targets:
            bucket['target_change_count']+=1
            if len(bucket['target_changes'])<4:bucket['target_changes'].append({'at':iso(ts),**target})
            else:event_omissions+=1
        previous_targets=target
        hf=bucket['humidifier'];hf['unknown_samples' if state is None else ('on_samples' if state else 'off_samples')]+=1
        if state is not None and previous_state is not None and state!=previous_state:
            hf['observed_changes']+=1
            if len(hf['transitions'])<8:hf['transitions'].append({'at':iso(ts),'on':state})
            else:event_omissions+=1
        previous_state=state;previous_time=ts
    tail=(end-(previous_time or start)).total_seconds()
    if tail>gap_threshold:gaps.append({'from':iso(previous_time or start),'to':iso(end),'seconds':round(tail,1)})
    for bucket,devices in zip(buckets,device_accum):
        for role,metrics in devices.items():
            device=bucket['shelly'][role]
            device['power_w']=_stats(metrics['power']);device['age_ms']=_stats(metrics['age'])
            energy=metrics['energy']
            device['energy_wh']={'first':energy[0] if energy else None,'last':energy[-1] if energy else None,
                'min':min(energy) if energy else None,'max':max(energy) if energy else None,'n':len(energy)}
    for bucket,metrics in zip(buckets,accum):
        for key,values in metrics.items():
            bucket['metrics'][key]={'avg':round(math.fsum(value/len(values) for value in values),4) if values else None,
                'min':min(values) if values else None,'max':max(values) if values else None,'n':len(values)}
    return {'schema':'growtent.analysis.v1','tentId':int(tent_id),'from':iso(start),'to':iso(end),
        'hours':hours,'bucketSeconds':seconds,'count':count,'sampleCount':sample_count,
        'units':{'temperature':'°C','humidity':'%','vpd':'kPa','temperature_raw':'°C','humidity_raw':'%','vpd_raw':'kPa','humidifier_watt':'W','alpha_temperature':'factor','alpha_humidity':'factor','leaf_offset':'°C'},
        'shellyRoles':list(SHELLY_ROLES),'context_first':context_first,'context_last':context_last,
        'context_timeline':context_timeline,'context_change_count':context_changes,'context_details_omitted':context_omissions,
        'deviceUnits':{'power_w':'W','energy_wh':'Wh','age_ms':'ms'},
        'gapThresholdSeconds':gap_threshold,'gaps':gaps,'eventDetailsOmitted':event_omissions,
        'notes':['Shelly metrics and context come only from stored ESP payloads; live dashboard-only direct reads are not backfilled.',
            'Shelly fresh/stale/unknown counters preserve reported freshness. State and power are not inferred from each other; PM1 ON may mean permanently connected.',
            'The light schedule is the ESP stored day-0 on/off schedule, not a reconstructed full Shelly weekly schedule. Context times are observations, not exact switch times.',
            'Context timeline retains at most 128 entries; first/last context and total changes remain available. No current settings or inferred day/night are substituted.',
            'Empty windows and null statistics indicate missing measurements; n is the number of valid samples.',
            'Transitions and target changes are observations at backend poll times, not exact physical switching times. Pulses between polls may be missed.',
            'Unknown/stale state or sampling gaps break switch continuity; no transition is inferred across them.',
            'Event detail lists retain at most 4 target changes per window and 8 switch changes per device/window; counts include all observations.'],
        'points':buckets}
