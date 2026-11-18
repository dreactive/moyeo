from ai.tests.test_place_route_tools import task


def test_question_targets_must_match_the_contract_domain():
    from ai.questions import valid_questions, question
    value = task()
    candidates = [question("constraint_value", None, "error"),
                  question("constraint_value", "item-a", "hours missing"),
                  question("visit_duration", "item-a", "stay?"),
                  question("origin", "anchor:origin", "origin?")]
    assert [q["field"] for q in valid_questions(value, candidates)] == ["visit_duration", "origin"]


def test_lookup_question_requires_current_request_owner_and_observed_choices():
    from ai.questions import valid_questions, question
    value = task()
    value["_active_requests"] = [dict(request_id="lookup-1", intent="place_lookup", owner_id="u1",
                                      source_message_id="m1", status="needs_input", target_names=["지점"])]
    choice = dict(place_ref="fixture:place-a", name="A", address="여수 A")
    value["observations"].append(dict(tool_name="search_places", arguments={}, result=dict(places=[
        dict(id=choice["place_ref"], name=choice["name"], address=choice["address"])])))
    proper = dict(question("target_places", "lookup-1", "지점을 선택해주세요", "u1"),
                  source_message_ids=["m1"], target_name="지점", place_choices=[choice])
    assert valid_questions(value, [proper, dict(proper, owner_id="u2"),
                                   dict(proper, target_ref="item-a"),
                                   dict(proper, place_choices=[dict(choice, place_ref="unobserved")])]) == [proper]


def test_region_and_route_departure_questions_keep_their_own_targets():
    from ai.questions import valid_questions, question
    value = task()
    value["config"]["region"] = None
    value["_active_requests"] = [dict(request_id="route-1", intent="route_lookup", owner_id="u1",
                                      source_message_id="m1", status="needs_input")]
    region = question("region", "config:region", "어느 지역인가요?", "u1")
    departure = dict(question("route_departure", "route-1", "언제 출발하나요?", "u1"), source_message_ids=["m1"])
    assert valid_questions(value, [region, departure, dict(departure, target_ref="item-a"),
                                   dict(departure, owner_id="u2")]) == [region, departure]
    value["config"]["region"] = "여수"
    assert valid_questions(value, [region]) == []
