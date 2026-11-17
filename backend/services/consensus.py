def support_threshold(member_count):
    return member_count // 2 + 1


def valid_support(room, observation, actor_id):
    item = next((item for item in room['items'] if item['id'] == observation['item_id']), None)
    message = next((message for message in room['messages'] if message['id'] == observation['source_message_id']), None)
    return bool(item and message and observation['item_version'] == item['item_version'] and actor_id == observation['author_id'] == message['author_id'] and message['room_id'] == room['room_id'] and actor_id in {member['user_id'] for member in room['members']} and observation['stance'] != 'unclear')
