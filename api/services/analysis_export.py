"""Read-only, bounded analysis projection of historical ESP samples."""
from datetime import datetime, timedelta, timezone
import math
from .vpd_channels import finite_number, esp_control_vpd, esp_raw_vpd

HOURS = {'1h':1, '6h':6, '12h':12, '24h':24, '48h':48}
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
            'targets_first':None,'targets_last':None,'target_changes':[], 'target_change_count':0,
            'humidifier':{'on_samples':0,'off_samples':0,'unknown_samples':0,'observed_changes':0,'transitions':[]}})
    accum=[{key:[] for key in METRICS} for _ in buckets]
    previous_time=None;previous_state=None;previous_targets=None
    sample_count=0;gaps=[];event_omissions=0
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
            previous_state=None
        values,state=sample_values(data)
        for key,value in values.items():
            if value is not None:accum[index][key].append(value)
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
    for bucket,metrics in zip(buckets,accum):
        for key,values in metrics.items():
            bucket['metrics'][key]={'avg':round(math.fsum(value/len(values) for value in values),4) if values else None,
                'min':min(values) if values else None,'max':max(values) if values else None,'n':len(values)}
    return {'schema':'growtent.analysis.v1','tentId':int(tent_id),'from':iso(start),'to':iso(end),
        'hours':hours,'bucketSeconds':seconds,'count':count,'sampleCount':sample_count,
        'units':{'temperature':'°C','humidity':'%','vpd':'kPa','temperature_raw':'°C','humidity_raw':'%','vpd_raw':'kPa','humidifier_watt':'W','alpha_temperature':'factor','alpha_humidity':'factor','leaf_offset':'°C'},
        'gapThresholdSeconds':gap_threshold,'gaps':gaps,'eventDetailsOmitted':event_omissions,
        'notes':['Empty windows and null statistics indicate missing measurements; n is the number of valid samples.',
            'Transitions and target changes are observations at backend poll times, not exact physical switching times. Pulses between polls may be missed.',
            'Unknown/stale state or sampling gaps break switch continuity; no transition is inferred across them.',
            'Event detail lists retain at most 4 target changes and 8 switch changes per window; counts include all observations.'],
        'points':buckets}
