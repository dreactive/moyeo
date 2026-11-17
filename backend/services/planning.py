import hashlib
import json
from copy import deepcopy
from fastapi import HTTPException


HASH_FIELDS = ('selected_item_ids','item_snapshots','days','cost','evidence')
IGNORED_TIMES = {'retrieved_at','observed_at','provider_updated_at'}


def substantive(value):
    if isinstance(value, dict):
        return {key:substantive(item) for key,item in value.items() if key not in IGNORED_TIMES}
    if isinstance(value, list):
        return [substantive(item) for item in value]
    return value


def semantic_plan_hash(snapshot):
    content = substantive({key:snapshot.get(key) for key in HASH_FIELDS})
    return hashlib.sha256(json.dumps(content, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
