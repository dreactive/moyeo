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
