def support_threshold(member_count):
    return member_count // 2 + 1


def valid_support(room, observation, actor_id):
    item = next((item for item in room['items'] if item['id'] == observation['item_id']), None)
    message = next((message for message in room['messages'] if message['id'] == observation['source_message_id']), None)
    return bool(item and message and observation['item_version'] == item['item_version'] and actor_id == observation['author_id'] == message['author_id'] and message['room_id'] == room['room_id'] and actor_id in {member['user_id'] for member in room['members']} and observation['stance'] != 'unclear')


def apply_support(room, observation, actor_id):
    if not valid_support(room, observation, actor_id):
        return False
    item = next(item for item in room['items'] if item['id'] == observation['item_id'])
    for key, stance in (('supporter_ids','support'), ('opponent_ids','oppose')):
        voters = set(item[key]) - {actor_id}
        if observation['stance'] == stance:
            voters.add(actor_id)
        item[key] = sorted(voters)
    item['support_threshold'] = support_threshold(len(room['members']))
    item['state'] = 'supported' if len(item['supporter_ids']) >= item['support_threshold'] else 'mentioned'
    return True
