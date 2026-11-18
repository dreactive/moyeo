"""Explicit deterministic auxiliary for tests and fixture runtimes, never a live fallback."""
import re
from ai.auxiliary_schema import AuxiliaryBatch
from ai.auxiliary_grounding import short_budget_value, title_in, reply_stance
from ai.condition_grounding import condition_value

PLACES = re.compile(r'오동도|엑스포|아쿠아플라넷|[가-힣A-Za-z0-9]+(?:해상케이블카|케이블카|공원|박물관|식당|카페|전망대|해수욕장|대학교)')
CUES = re.compile(r'(?P<title>[가-힣A-Za-z0-9 ]+?)\s*(?P<cue>말고|가자|좋아|찬성|반대|싫어|철회|찾아줘|검색해줘)')


class FixtureAuxiliary:
    backend = 'fixture'

    def extract(self, task: dict, stage: int = 1) -> dict:
        analysis = dict(summary='', needs_context=False, context_queries=[], missing_fields=[], unsupported=False,
                        unsupported_reason='', direct_text='', noop=False)
        output = dict(item_proposals=[], constraint_proposals=[], support_observations=[], analysis=analysis)
        items = list(task.get('items', []))
        requests, prior = [], []
        for message in task.get('recent_messages', []):
            text = message['text']
            evidence = lambda quote: dict(message_id=message['id'], quote=quote)
            requests.append(text)
            for key in ('budget_krw', 'return_by'):
                value = condition_value(key, text)
                if value is None:
                    value = short_budget_value(key, text, message['author_id'], task)
                if value is not None:
                    output['constraint_proposals'].append(dict(key=key, value=value, evidence=evidence(text)))
            for clause in re.split(r'[.!?;\n]', text):
                for match in CUES.finditer(clause):
                    title = re.sub(r'^(?:나는|난|우리|저는)\s+', '', match['title']).strip()
                    found = PLACES.search(title)
                    known = next((i for i in items if title_in(title, i)), None)
                    if known:
                        ref, version = known['id'], known['item_version']
                    elif found:
                        title = title if found.end() == len(title) else found[0]
                        ref, version = 'fixture:' + message['id'] + ':' + title, 1
                        output['item_proposals'].append(dict(client_ref=ref, title=title, mention_text=title,
                                                             evidence=evidence(match[0])))
                        items.append(dict(id=ref, item_version=version, title=title))
                    else:
                        continue
                    cue = match['cue']
                    stance = 'withdraw' if cue == '철회' else 'oppose' if cue in ('말고', '반대', '싫어') else 'support'
                    if cue not in ('찾아줘', '검색해줘'):
                        output['support_observations'].append(dict(item_id=ref, item_version=version, stance=stance,
                                                                   evidence=evidence(match[0])))
            if not CUES.search(text):
                mention = re.sub(r'^(?:나는|난|우리|저는)\s+', '', text.strip().rstrip('.!?')).strip()
                named = PLACES.search(mention)
                if named and named.end() == len(mention) and not any(title_in(mention, i) for i in items):
                    ref = 'fixture:' + message['id'] + ':' + mention
                    output['item_proposals'].append(dict(client_ref=ref, title=mention, mention_text=mention, evidence=evidence(text)))
                    items.append(dict(id=ref, item_version=1, title=mention))
            if re.fullmatch(r'\s*(?:응|네|예|좋아|아니|거기는\s*빼자)[.!?\s]*', text):
                records = (task.get('conversation_context', []) if stage == 2 else []) + prior
                questions = [q for q in task.get('questions', []) if q.get('field') == 'support_target'
                             and q.get('status') == 'open' and q.get('owner_id') in (None, message['author_id'])
                             and any(i['id'] == q.get('target_ref') and title_in(q.get('text', ''), i) for i in items)]
                targets = [i for i in items if any(title_in(m['text'], i) for m in records)]
                question = questions[0] if len(questions) == 1 else None
                if question:
                    item = next(i for i in items if i['id'] == question['target_ref'])
                    stance = reply_stance(text, [question['text']])
                    if stance:
                        output['support_observations'].append(dict(item_id=item['id'], item_version=item['item_version'],
                            stance=stance, evidence=evidence(text), question_id=question['id']))
                elif len(targets) == 1:
                    item = targets[0]
                    relevant = [m for m in records if title_in(m['text'], item)]
                    stance = 'oppose' if '빼자' in text else reply_stance(text, [m['text'] for m in relevant])
                    if stance:
                        output['support_observations'].append(dict(item_id=item['id'], item_version=item['item_version'],
                            stance=stance, evidence=evidence(text), context_message_ids=[m['id'] for m in relevant]))
                else:
                    analysis.update(needs_context=True, context_queries=[i['title'] for i in items[:8]])
                    analysis['missing_fields'].append(dict(field='support_target', target_ref=None, text='어느 장소에 대한 의견인가요?',
                        owner_id=message['author_id'], source='history', source_message_ids=[message['id']],
                        stance='oppose' if '빼자' in text or text.strip() == '아니' else 'support'))
            prior.append(message)
            if re.search(r'결제|표\s*구매|예약해', text):
                analysis.update(unsupported=True, unsupported_reason='결제와 예약 기능은 제공하지 않습니다.')
        analysis['summary'] = ' / '.join(requests)[:2000]
        analysis['noop'] = bool(requests) and all(re.fullmatch(r'\s*(?:안녕|안녕하세요|좋은\s*아침|ㅋㅋ+|ㅎㅎ+|고마워|감사합니다)[.!?\s]*', text) for text in requests)
        return AuxiliaryBatch.model_validate(output).model_dump()
