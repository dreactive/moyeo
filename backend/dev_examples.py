"""Backend-owned synthetic examples, independent of AI imports or model weights."""
import json
from copy import deepcopy
from pathlib import Path


TOOL_ARGUMENTS = {
    'search_places': {'query': 'A식당', 'region': '여수', 'category': None},
    'get_place_details': {'place_ref': 'fixture:place-a'},
    'get_car_route': {'from_ref': 'anchor:origin', 'to_ref': 'fixture:place-a', 'departure_at': None},
    'build_itinerary': None,
    'calculate_costs': None,
}


def tool_examples(name):
    context = json.loads(Path(__file__).with_name('dev_sandbox_fixture.json').read_text(encoding='utf-8'))
    return {'fixture': {'summary': 'Synthetic fixture; use PROVIDER_MODE=fixture',
                        'value': {'context': context, 'arguments': deepcopy(TOOL_ARGUMENTS[name])}}}


def utterance_examples():
    context = tool_examples('search_places')['fixture']['value']['context']
    return {goal: {'summary': goal + ' (fake/fixture example)',
                   'value': {'context': context, 'text': '예산은 15만원이야.', 'author_id': 'u1', 'goal': goal}}
            for goal in ('extract', 'new_message', 'manual_replan')}
