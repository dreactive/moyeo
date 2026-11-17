def valid_sources(room, source_ids, owner_id=None):
    messages = {message['id']:message for message in room['messages']}
    members = {member['user_id'] for member in room['members']}
    return bool(source_ids) and all(
        source_id in messages
        and messages[source_id]['room_id'] == room['room_id']
        and messages[source_id]['author_id'] in members
        and (owner_id is None or messages[source_id]['author_id'] == owner_id)
        for source_id in source_ids
    )

from uuid import uuid4


def add_item_proposal(room, proposal):
    if not valid_sources(room, proposal['source_message_ids']):
        raise ValueError('Invalid proposal sources')
    if proposal['kind'] not in ('place','itinerary_change','shared_condition'):
        raise ValueError('Unknown item kind')
    item = {key:proposal[key] for key in ('kind','title','source_message_ids')}
    item.update(id=uuid4().hex, item_version=1, included_in_plan=False, supporter_ids=[], opponent_ids=[], support_threshold=len(room['members'])//2+1, state='mentioned', conflict_ids=[])
    room['items'].append(item)
    return item


def update_item_proposal(room, proposal):
    item = next(item for item in room['items'] if item['id'] == proposal['existing_item_id'])
    if (item['title'], item['kind']) != (proposal['title'], proposal['kind']):
        item.update(title=proposal['title'], kind=proposal['kind'], item_version=item['item_version']+1, supporter_ids=[], opponent_ids=[], state='mentioned')
    item['source_message_ids'] = sorted(set(item['source_message_ids'] + proposal['source_message_ids']))
    return item


def apply_item_proposals(room, proposals):
    refs = {}
    for proposal in proposals:
        if not valid_sources(room, proposal['source_message_ids']):
            raise ValueError('Invalid proposal source')
        update = update_item_proposal if proposal.get('existing_item_id') else add_item_proposal
        refs[proposal['client_ref']] = update(room, proposal)['id']
    return refs


REF_FIELDS = {'item_id','target_ref','selected_item_ids','related_item_ids','affected_item_ids','ordered_item_ids'}


def resolve_refs(value, refs, field=None):
    if isinstance(value, dict):
        return {key:resolve_refs(item, refs, key) for key,item in value.items()}
    if isinstance(value, list):
        return [resolve_refs(item, refs, field) for item in value]
    return refs.get(value, value) if isinstance(value, str) and field in REF_FIELDS else value


def add_constraint_proposal(room, proposal):
    if not valid_sources(room, proposal['source_message_ids'], proposal['owner_id']):
        raise ValueError('Condition owner does not match evidence')
    for existing in room['constraints']:
        same_key = existing['owner_id'] == proposal['owner_id'] and existing['key'] == proposal['key']
        if existing['id'] == proposal.get('replaces_constraint_id') and not same_key:
            raise ValueError('Cannot replace another owner condition')
        if same_key and existing['value'] == proposal['value'] and existing['kind'] == proposal['kind'] and existing['status'] != 'superseded':
            return None
    condition = {key:proposal[key] for key in ('owner_id','key','value','kind','source_message_ids')}
    condition.update(id=uuid4().hex, status='needs_owner_confirmation')
    room['constraints'].append(condition)
    return condition



def project_items(room):
    current = room['current_plan']
    confirmed = room['confirmed_plan']
    selected = set(current['selected_item_ids']) if current else set()
    same_plan = bool(current and confirmed and current['confirmation_target'] == confirmed['confirmation_target'])
    snapshots = {item['id']:item for item in confirmed['item_snapshots']} if same_plan else {}
    for item in room['items']:
        item['support_threshold'] = len(room['members']) // 2 + 1
        item['included_in_plan'] = item['id'] in selected
        item['state'] = 'supported' if len(set(item['supporter_ids'])) >= item['support_threshold'] else 'mentioned'
        if item['id'] in snapshots and snapshots[item['id']]['item_version'] == item['item_version']:
            item['state'] = 'confirmed'
        item['conflict_ids'] = [conflict['id'] for conflict in room['conflicts'] if item['id'] in conflict['affected_item_ids'] and conflict['status'] == 'open']
    return room
