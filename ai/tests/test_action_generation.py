from ai.tests.test_place_route_tools import task


def test_observation_changes_fixture_next_action():
    from ai.models.fake_actions import propose_actions
    value = task()
    value["observations"] = []
    action = propose_actions(value)[0]
    assert action["tool_name"] == "get_place_details"
    value["observations"] = task()["observations"]
    assert propose_actions(value)[0]["tool_name"] == "get_car_route"
    changed = task()
    changed["current_plan"]["item_snapshots"][0]["place_ref"] = "fixture:other"
    changed["observations"] = []
    assert propose_actions(changed)[0]["arguments"]["place_ref"] == "fixture:other"
