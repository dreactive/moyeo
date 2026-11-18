from copy import deepcopy
from types import SimpleNamespace
import asyncio

from backend.services.rooms import get_room_snapshot


def test_item_places_are_projected_from_unique_same_region_observations(room):
    rid = room['room_id']
    room.update(current_plan=None,confirmed_plan=None)
    room['items'] = [dict(room['items'][0],kind='place',title=name,id=name)
                     for name in ('돌산공원','자산공원','오동도')]
    def search(name, region, refs):
        return dict(tool_name='search_places',arguments=dict(query=name,region=region),
                    source_refs=['search-'+name],result=dict(places=[dict(id=r,name=name) for r in refs]))
    observations = [search('돌산공원','서울',['seoul']),search('돌산공원','여수',['dolsan']),
                    search('자산공원','여수',['a','b']),search('오동도','서울',['wrong'])]
    db = SimpleNamespace(get=lambda key: deepcopy(room),observations={rid:observations})
    projected = get_room_snapshot(db,rid,room['members'][0]['user_id'])
    assert [i.get('place_ref') for i in projected['items']] == ['dolsan',None,None]
    assert projected['items'][0]['place_source_refs']==['search-돌산공원']
    assert not projected['items'][0]['included_in_plan']


def test_location_read_for_projected_ref_prefers_current_region(room):
    from backend.services.observations import fetch_place
    rid = room['room_id']
    place = dict(id='same',name='공원',latitude=34.7,longitude=127.7)
    def observation(region, data):
        return dict(tool_name='search_places',arguments=dict(query='공원',region=region),
                    result=dict(places=[data]))
    db = SimpleNamespace(observations={rid:[
        observation(room['config']['region'],place),observation('서울',dict(place,latitude=37.5))]})
    result = asyncio.run(fetch_place(db,None,room,place['id'],location_only=True))
    assert result['place']==place
