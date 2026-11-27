"""Conservative event-time geometry. Kill messages do not contain shot trajectories."""
import bisect
import json
import math

import analysis
from map_positions import own_player_position, spectator_view

MAX_SAMPLE_AGE = 3.0


def finite(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)


def position(obj):
    return bool(obj and finite(obj.get('x')) and finite(obj.get('y'))
                and 0 <= obj['x'] <= 1 and 0 <= obj['y'] <= 1)


def same_name(name, player):
    return bool(isinstance(name,str) and player and (name.casefold()==player.casefold()
                or name.casefold().endswith(' '+player.casefold())))


def expected_type(event):
    verb=(event.get('verb') or '').casefold()
    if 'shot down' in verb or analysis.is_air_vehicle(event.get('target_vehicle') or ''):
        return 'aircraft'
    if 'sunk' in verb:
        return 'ship'
    return 'ground_model'


def build_reviews(session, events, frames):
    frames=sorted(frames,key=lambda row:row['ts'])
    times=[row['ts'] for row in frames]
    player=session.get('my_name') or session.get('provisional_my_name')
    kills=[e for e in events if analysis.is_lethal(e.get('verb')) and same_name(e.get('actor_name'),player)]
    lethal=[e for e in events if analysis.is_lethal(e.get('verb'))]
    result=[]
    for index,event in enumerate(kills):
        timestamp=event['ts']
        try:
            raw=json.loads(event.get('raw_json') or '{}')
        except (ValueError,TypeError):
            raw={}
        if not isinstance(raw,dict):
            raw={}
        review={'event_id':event['id'],'number':index+1,'t':max(0,timestamp-session['start_ts']),
                'event':event,'timestamp_basis':'game_log' if raw.get('source')=='clog' else 'feed_received',
                'origin':None,'target':None,'line':None,'vehicle_type':None,
                'sample_id':None,'sample_age_s':None,'snapshot':None,
                'origin_note':'No preceding position sample within 3 seconds of this event.',
                'target_note':'The recorded map feed does not identify this target.',
                'related_events':[e for e in events if e['id']!=event['id'] and abs(e['ts']-timestamp)<=15
                                  and e.get('actor_name')==event.get('actor_name')
                                  and e.get('target_name')==event.get('target_name')],
                'trajectory_note':'The game feed does not record the firing instant or projectile trajectory.'}
        location=bisect.bisect_right(times,timestamp)-1
        before=frames[location] if location>=0 else None
        if not before or not 0 <= timestamp-before['ts'] <= MAX_SAMPLE_AGE:
            result.append(review)
            continue
        indicators=before['indicators']
        review.update(sample_id=before['sample_id'],sample_age_s=round(timestamp-before['ts'],3),
                      vehicle_type=indicators.get('type'),snapshot={'indicators':indicators,'state':before['state']})
        valid=(before['map_info'].get('valid') is not False and indicators.get('valid') is not False
               and analysis.is_real_vehicle(indicators.get('type')))
        own=own_player_position(before['objects']) if valid else None
        if own:
            review['origin']={'x':own['x'],'y':own['y'],'sample_id':before['sample_id']}
            review['origin_note']='Recorded own position near the kill notification, not a confirmed firing position.'
        else:
            review['origin_note']=('The nearby sample shows a spectator/other vehicle; its position is not yours.'
                                   if spectator_view(before['objects']) else
                                   'The nearby sample has no valid own-vehicle map position.')
        if event.get('actor_vehicle') and analysis.normalize_vehicle_id(indicators.get('type')) != analysis.normalize_vehicle_name(event['actor_vehicle']):
            review['origin']=None
            review['origin_note']='The sampled vehicle differs from the vehicle credited with this kill; position not assigned.'
        enemy=[obj for obj in before['objects'] if position(obj) and analysis.classify_faction(obj)=='enemy'
               and obj.get('type')==expected_type(event)] if valid else []
        identified=[obj for obj in enemy if any(same_name(obj.get(key),event.get('target_name'))
                                               for key in ('player_name','player','nickname','nick','name'))]
        chosen=None
        if len(identified)==1:
            chosen=identified[0]
            review['target_note']='Target matched by a recorded player name on a compatible enemy marker.'
            method='named_marker'
        elif not identified:
            after=frames[location+1] if location+1<len(frames) else None
            after_valid=after and 0 < after['ts']-timestamp <= MAX_SAMPLE_AGE and after['map_info'].get('valid') is not False and after['map_info'].get('map_generation')==before['map_info'].get('map_generation')
            if after_valid and after['indicators'].get('type')==indicators.get('type') and own:
                new_own=own_player_position(after['objects'])
                # A respawn, missing feed or simultaneous deaths cannot identify a disappearing marker.
                continuous=new_own and math.hypot(new_own['x']-own['x'],new_own['y']-own['y']) < .05
                same_team=[o for o in after['objects'] if position(o) and analysis.classify_faction(o)=='friendly']
                overlapping=sum(abs(e['ts']-timestamp)<=MAX_SAMPLE_AGE for e in lethal)>1
                if continuous and same_team and not overlapping:
                    current=[o for o in after['objects'] if position(o) and analysis.classify_faction(o)=='enemy'
                             and o.get('type')==expected_type(event)]
                    vanished=[o for o in enemy if not any(math.hypot(o['x']-a['x'],o['y']-a['y'])<.03 for a in current)]
                    if len(vanished)==1:
                        chosen=vanished[0]
                        method='disappeared_marker_estimate'
                        review['target_note']='Possible target: one compatible enemy marker disappeared. It may have left visibility; identity is unconfirmed.'
        if chosen:
            review['target']={'x':chosen['x'],'y':chosen['y'],'method':method,
                              'confidence':'name_matched' if method=='named_marker' else 'estimated'}
        if review['origin'] and review['target']:
            info=before['map_info'];low,high=info.get('map_min'),info.get('map_max')
            distance=None
            if (isinstance(low,list) and isinstance(high,list) and len(low)>=2 and len(high)>=2
                    and all(finite(v) for v in low[:2]+high[:2])):
                distance=math.hypot((chosen['x']-own['x'])*(high[0]-low[0]),(chosen['y']-own['y'])*(high[1]-low[1]))
            review['line']={'kind':'event_time_connection','distance_m':distance,
                            'note':'Approximate 2D connection at notification time; not a ballistic trajectory or verified line of fire.'}
        result.append(review)
    return result
