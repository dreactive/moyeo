from copy import deepcopy
import re


PRIVATE = re.compile(r'key|token|password|secret|authorization|reasoning|thought|raw_response', re.I)
URL_SECRET = re.compile(r'([?&](?:api_?key|token|servicekey)=)[^&\s]+', re.I)


def sanitize(value):
    if isinstance(value, dict):
        condition = (isinstance(value.get('owner_id'), str) and value.get('kind') in ('hard','preference')
                     and 'value' in value)
        return {key:sanitize(item) for key,item in value.items()
                if not PRIVATE.search(key) or (key=='key' and condition and isinstance(item,str)
                                               and not PRIVATE.search(item))}
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, str):
        return URL_SECRET.sub(r'\1[redacted]', value)
    return value



def store_trace(db, event):
    if not getattr(db, 'trace_enabled', True):
        return False
    run = db.get('run:' + event['run_id'])
    if not run or event['event'] not in ('decision','tool_call','tool_result','state_applied'):
        return False
    trace = db.traces.setdefault(event['run_id'], dict(run_id=event['run_id'], room_id=run['room_id'], started_at=event['created_at'], events=[]))
    trace['events'].append(sanitize({key:event[key] for key in ('run_id','step','event','call_id','created_at','payload')}))
    return True


def get_run_traces(db, room_id, run_id=None):
    return deepcopy([trace for trace in db.traces.values() if trace['room_id'] == room_id and (run_id is None or trace['run_id'] == run_id)])
