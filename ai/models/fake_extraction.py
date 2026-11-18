"""Schema-preserving adapter for deterministic fake-model fixtures only."""
from ai.assistance import assist_extraction


def fixture_batch(raw, task):
    facts = assist_extraction(raw, task)
    messages = {m['id']: m for m in task['recent_messages']}
    batch = dict(message_assessments=[dict(message_id=m['id'], intents=['chitchat']) for m in messages.values()],
                 item_proposals=[], constraint_proposals=[], support_observations=[])
    for key in ('constraint_proposals', 'item_proposals', 'support_observations'):
        for original in facts[key]:
            proposal = dict(original)
            source = proposal.pop('source_message_id', None) or proposal.pop('source_message_ids', [None])[0]
            proposal['evidence'] = dict(message_id=source, quote=messages[source]['text'])
            if key == 'item_proposals':
                proposal['mention_text'] = proposal['title']
                for field in ('client_ref', 'kind'):
                    proposal.pop(field, None)
            batch[key].append(proposal)
    return batch
