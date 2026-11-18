"""Grounded choices are executable alternatives, never padding."""
from copy import deepcopy
import json


def task():
    return dict(goal="replan", run_id="r", room_id="room", base_versions={},
                recent_messages=[dict(id="m1", author_id="u1", text="엑스포 검색해줘")],
                members=[dict(user_id="u1")], config=dict(region="여수", start_date="2026-11-21",
                end_date="2026-11-21", transport="car", origin=None, destination=None, lodging=None),
                items=[], constraints=[], questions=[], observations=[], current_plan=None)


def item(ref, title):
    return dict(id=ref, kind="place", title=title, source_message_ids=["m1"],
                state="mentioned", supporter_ids=["u1"], opponent_ids=[])


def search():
    return dict(tool_name="search_places", arguments=dict(query="엑스포", region="여수", category=None),
                result=dict(places=[dict(id="place:expo", name="엑스포", latitude=34.7, longitude=127.6)]),
                source_refs=["evidence:search"])


def test_search_and_details_are_independently_ready_without_origin():
    from ai.decision_candidates import build_decision_candidates
    value = task()
    value["items"] = [item("new", "공원"), item("resolved", "엑스포")]
    value["recent_messages"][0]["text"] = "공원과 엑스포 검색해줘"
    value["observations"] = [search()]
    result = build_decision_candidates(value)
    assert result["branch"] == "valid"
    assert [(c["tool_name"], c["arguments"]) for c in result["candidates"]] == [
        ("search_places", dict(query="공원", region="여수", category=None)),
        ("get_place_details", dict(place_ref="place:expo"))]
    assert result["candidates"][1]["source_message_ids"] == ["m1"]
    assert "evidence:search" in result["candidates"][1]["source_refs"]


def test_real_calls_are_capped_deduplicated_stable_and_leave_pending_work_untouched():
    from ai.decision_candidates import build_decision_candidates
    value = task()
    value["items"] = [item(str(n), name) for n, name in enumerate(["가", "가", "나", "다", "라"])]
    before = deepcopy(value)
    result = build_decision_candidates(value)
    assert [c["arguments"]["query"] for c in result["candidates"]] == ["가", "나", "다"]
    assert len({c["candidate_id"] for c in result["candidates"]}) == 3
    assert result == build_decision_candidates(value)
    assert value == before


def test_opposed_and_inactive_places_do_not_produce_tools():
    from ai.decision_candidates import build_decision_candidates
    value = task()
    value["items"] = [item("a", "한강공원"), item("b", "엑스포"), item("c", "폐기")]
    value["items"][0].update(supporter_ids=[], opponent_ids=["u1"])
    value["items"][2]["state"] = "inactive"
    assert [c["arguments"]["query"] for c in build_decision_candidates(value)["candidates"]] == ["엑스포"]


def test_exact_observed_empty_search_is_not_repeated_or_replaced_by_fake_args():
    from ai.decision_candidates import build_decision_candidates
    value = task()
    value["items"], value["observations"] = [item("a", "엑스포")], [dict(search(), result={"places": []})]
    assert build_decision_candidates(value) == {"branch": "invalid", "candidates": []}


def test_unresolved_place_does_not_hide_independent_routes():
    from ai.decision_candidates import build_decision_candidates
    value = task()
    value["config"].update(end_date="2026-11-22", origin=dict(latitude=34, longitude=127),
                           destination=dict(latitude=34, longitude=127), lodging=dict(latitude=35, longitude=128))
    value["items"] = [item("new", "공원")]
    calls = [(c["tool_name"], c["arguments"]) for c in build_decision_candidates(value)["candidates"]]
    assert calls == [("search_places", dict(query="공원", region="여수", category=None)),
                     ("get_car_route", dict(from_ref="anchor:origin", to_ref="anchor:lodging", departure_at="2026-11-21T09:00:00+09:00")),
                     ("get_car_route", dict(from_ref="anchor:lodging", to_ref="anchor:destination", departure_at="2026-11-22T09:00:00+09:00"))]


def test_registered_calculations_keep_exact_canonical_arguments():
    from ai.decision_candidates import build_decision_candidates
    from ai.tests.test_place_route_tools import task as fixture_task
    from ai.planning import next_route, itinerary_arguments
    from ai.cost_inputs import build_cost_inputs
    from ai.tools.context import build_tool_context
    from ai.tools.validation import validate_arguments
    value = fixture_task()
    while arguments := next_route(value):
        value["observations"].append(dict(tool_name="get_car_route", arguments=arguments,
            result=dict(from_ref=arguments["from_ref"], to_ref=arguments["to_ref"], duration_seconds=600,
                        distance_m=1000, toll_krw=0, evidence_id=str(len(value["observations"])), polyline=[])))
    result = build_decision_candidates(value)
    assert [c["tool_name"] for c in result["candidates"]] == ["build_itinerary", "calculate_costs"]
    assert result["candidates"][0]["arguments"] == itinerary_arguments(value)
    assert result["candidates"][1]["arguments"] == build_cost_inputs(value)[0]
    for c in result["candidates"]:
        validate_arguments(c["tool_name"], c["arguments"], build_tool_context(value))


def test_missing_region_never_becomes_null_or_empty_tool_argument():
    from ai.decision_candidates import build_decision_candidates
    value = task()
    value["items"], value["config"]["region"] = [item("a", "엑스포")], None
    result = build_decision_candidates(value)
    assert result["branch"] == "invalid" and not any(c["action"] == "tool" for c in result["candidates"])


def test_zero_one_and_two_actual_candidates_are_supported():
    from ai.decision_candidates import build_decision_candidates
    value = task()
    assert build_decision_candidates(value) == {"branch": "invalid", "candidates": []}
    missing = dict(field="origin", target_ref="anchor:origin", text="출발지를 알려주세요.", owner_id="u1")
    one = build_decision_candidates(value, dict(missing_fields=[missing]))
    assert [c["action"] for c in one["candidates"]] == ["ask"]
    value["recent_messages"][0]["text"] = "항공권 예약해줘"
    two = build_decision_candidates(value, dict(missing_fields=[missing], unsupported=True,
        unsupported_reason="항공권 예약 기능은 제공하지 않습니다.", source_message_ids=["m1"]))
    assert [c["action"] for c in two["candidates"]] == ["ask", "unsupported"]


def test_questions_deduplicate_by_field_target_owner_and_do_not_repeat_open_questions():
    from ai.decision_candidates import build_decision_candidates
    value = task()
    missing = [dict(field="origin", target_ref="anchor:origin", text="출발지?", owner_id="u1"),
               dict(field="origin", target_ref="anchor:origin", text="어디서 출발?", owner_id="u1"),
               dict(field="destination", target_ref="anchor:destination", text="도착지?", owner_id="u1")]
    result = build_decision_candidates(value, {"missing_fields": missing})
    assert [c["question"]["field"] for c in result["candidates"]] == ["origin", "destination"]
    assert len({c["candidate_id"] for c in result["candidates"]}) == 2
    value["questions"] = [dict(result["candidates"][0]["question"], status="open")]
    assert [c["question"]["field"] for c in build_decision_candidates(value, {"missing_fields": missing})["candidates"]] == ["destination"]


def test_known_and_history_or_observation_missing_values_do_not_create_questions():
    from ai.decision_candidates import build_decision_candidates
    value = task()
    missing = dict(field="origin", target_ref="anchor:origin", text="출발지?", owner_id="u1")
    assert build_decision_candidates(value, {"missing_fields": [dict(missing, source="history")]})["candidates"] == []
    assert build_decision_candidates(value, {"missing_fields": [dict(missing, source="tool_observation")]})["candidates"] == []
    value["config"]["origin"] = {"latitude": 34, "longitude": 127}
    assert build_decision_candidates(value, {"missing_fields": [missing]})["candidates"] == []


def test_grounded_non_tool_responses_are_used_without_padding():
    from ai.decision_candidates import build_decision_candidates
    value = task()
    assert build_decision_candidates(value, dict(unsupported=True, unsupported_reason="", direct_text=""))["candidates"] == []
    result = build_decision_candidates(value, dict(direct_text="엑스포 검색해줘", source_message_ids=["m1"]))
    assert result["candidates"] == []
    assert build_decision_candidates(value, dict(unsupported=True, unsupported_reason="미지원", source_message_ids=["invented"]))["candidates"] == []


def test_valid_branch_adds_only_real_unsupported_and_no_ask_or_direct():
    from ai.decision_candidates import build_decision_candidates
    value = task()
    value["items"] = [item("a", "엑스포")]
    value["recent_messages"][0]["text"] = "엑스포 검색하고 표 예약해줘"
    result = build_decision_candidates(value, dict(unsupported=True, unsupported_reason="예약은 지원하지 않습니다.",
        direct_text="엑스포 검색해줘", missing_fields=[dict(field="origin", target_ref="anchor:origin", text="출발지?", owner_id="u1")]))
    assert [c["action"] for c in result["candidates"]] == ["tool", "unsupported"]


def test_noop_preserves_pending_work_without_candidates():
    from ai.decision_candidates import build_decision_candidates
    value = task()
    value["items"] = [item("a", "엑스포")]
    assert build_decision_candidates(value, {"noop": True}) == {"branch": "noop", "candidates": []}
    assert value["items"][0]["id"] == "a"


def test_compact_context_preserves_sources_negation_and_concrete_values_without_raw_observations():
    from ai.decision_candidates import build_decision_candidates, compact_decision_context
    value = task()
    value["recent_messages"][0]["text"] = "한강공원 말고 엑스포 검색해줘"
    value["items"], value["observations"] = [item("a", "엑스포")], [search()]
    value["observations"][0]["result"]["polyline"] = [{"latitude": 1}] * 500
    value["conversation_context"] = [dict(id="old", author_id="u2", text="과거 문맥")]
    compact = compact_decision_context(value, {"summary": "대안 검색", "missing_fields": [
        dict(field="origin", target_ref="anchor:origin", text="출발지?", owner_id="u1")]}, build_decision_candidates(value)["candidates"])
    encoded = json.dumps(compact, ensure_ascii=False)
    assert "polyline" not in encoded and "observations" not in compact and "conversation_context" not in compact
    assert "한강공원 말고 엑스포 검색해줘" in encoded and '"author_id": "u1"' in encoded
    assert "place:expo" in encoded and "evidence:search" in encoded
    assert compact["missing_fields"][0]["owner_id"] == "u1"
    assert "과거 문맥" not in encoded
    assert len(encoded) < len(json.dumps(value, ensure_ascii=False)) / 2


def test_details_readiness_does_not_require_trip_dates_or_a_plan():
    from ai.decision_candidates import build_decision_candidates
    value = task()
    value["config"].pop("start_date")
    value["items"], value["observations"] = [item("a", "엑스포")], [search()]
    result = build_decision_candidates(value)
    assert [(c["tool_name"], c["arguments"]) for c in result["candidates"]] == [
        ("get_place_details", {"place_ref": "place:expo"})]


def test_observed_item_place_reference_is_usable_without_a_matching_search_query():
    from ai.decision_candidates import build_decision_candidates
    value = task()
    value["items"], value["observations"] = [dict(item("a", "엑스포 전시관"), place_ref="place:expo")], [search()]
    result = build_decision_candidates(value)
    assert [(c["tool_name"], c["arguments"]) for c in result["candidates"]] == [
        ("get_place_details", {"place_ref": "place:expo"})]


def test_question_owner_is_part_of_identity_and_invalid_targets_are_not_questions():
    from ai.decision_candidates import build_decision_candidates
    value = task()
    value["members"].append({"user_id": "u2"})
    missing = [dict(field="origin", target_ref="anchor:origin", text="출발지?", owner_id="u1"),
               dict(field="origin", target_ref="anchor:origin", text="출발지?", owner_id="u2")]
    result = build_decision_candidates(value, {"missing_fields": missing})
    assert [c["question"]["owner_id"] for c in result["candidates"]] == ["u1", "u2"]
    assert len({c["candidate_id"] for c in result["candidates"]}) == 2
    for bad in [dict(missing[0], target_ref="invented"), dict(missing[0], owner_id="invented")]:
        assert build_decision_candidates(value, {"missing_fields": [bad]})["candidates"] == []


def test_unverified_direct_answer_and_unknown_source_refs_are_not_grounded_candidates():
    from ai.decision_candidates import build_decision_candidates
    value = task()
    assert build_decision_candidates(value, {"direct_text": "입장료는 12000원입니다.", "source_message_ids": ["m1"]})["candidates"] == []
    assert build_decision_candidates(value, {"unsupported": True, "unsupported_reason": "예약 불가", "source_refs": ["invented"]})["candidates"] == []


def test_compact_context_retains_selected_user_answers_and_all_candidate_message_quotes():
    from ai.decision_candidates import compact_decision_context
    value = task()
    value["conversation_context"] = [dict(id="old", author_id="u2", text="나는 그곳은 반대야")]
    value["questions"] = [dict(id="q", field="menu_selection", target_ref="a", owner_id="u1", status="answered",
        answer=dict(menu_id="menu", scope="shared", quantity=2), answered_by="u1", source_message_ids=["old"])]
    candidate = dict(action="tool", tool_name="calculate_costs", arguments={}, source_refs=["menu"], source_message_ids=["old"])
    compact = compact_decision_context(value, {}, [candidate])
    encoded = json.dumps(compact, ensure_ascii=False)
    assert "나는 그곳은 반대야" in encoded
    assert '"quantity": 2' in encoded and '"scope": "shared"' in encoded


def test_plan_place_reference_remains_ready_when_dates_are_missing():
    from ai.decision_candidates import build_decision_candidates
    value = task()
    value["config"].pop("start_date")
    value["items"], value["observations"] = [item("a", "엑스포 전시관")], [search()]
    value["current_plan"] = dict(item_snapshots=[dict(id="a", place_ref="place:expo")], days=[])
    result = build_decision_candidates(value)
    assert [(c["tool_name"], c["arguments"]) for c in result["candidates"]] == [
        ("get_place_details", {"place_ref": "place:expo"})]


def test_route_context_preserves_departure_time_dependencies_without_polylines():
    from ai.decision_candidates import build_decision_candidates, compact_decision_context
    value = task()
    value["config"].update(origin=dict(latitude=34, longitude=127), destination=dict(latitude=35, longitude=128))
    value["items"], value["observations"] = [item("a", "엑스포")], [search()]
    value["current_plan"] = dict(item_snapshots=[dict(id="a", place_ref="place:expo")], days=[dict(date="2026-11-21", visits=[
        dict(item_id="a", place_ref="place:expo", start_at=None, stay_minutes=60)])])
    value["observations"].append(dict(tool_name="get_car_route", arguments=dict(from_ref="anchor:origin",
        to_ref="place:expo", departure_at="2026-11-21T09:00:00+09:00"), result=dict(from_ref="anchor:origin",
        to_ref="place:expo", duration_seconds=600, evidence_id="route:incoming", polyline=[dict(latitude=34)])))
    candidates = build_decision_candidates(value)["candidates"]
    route = next(c for c in candidates if c["tool_name"] == "get_car_route")
    assert route["arguments"]["departure_at"] == "2026-11-21T10:10:00+09:00"
    assert "route:incoming" in route["source_refs"]
    compact = compact_decision_context(value, {}, candidates)
    assert compact["facts"]["route_facts"][0]["duration_seconds"] == 600
    assert compact["facts"]["visits"][0]["stay_minutes"] == 60
    assert "polyline" not in json.dumps(compact)


def test_stale_route_observation_allows_same_arguments_to_be_requested_again():
    from ai.decision_candidates import build_decision_candidates
    from ai.providers.kakao import route_evidence_id
    from ai.tools.context import build_tool_context
    value = task()
    value["config"].update(origin=dict(latitude=34, longitude=127), destination=dict(latitude=35, longitude=128))
    value["items"], value["observations"] = [item("a", "엑스포")], [search()]
    arguments = dict(from_ref="anchor:origin", to_ref="place:expo", departure_at="2026-11-21T09:00:00+09:00")
    evidence = route_evidence_id(build_tool_context(value)["places"], arguments)
    value["observations"].append(dict(tool_name="get_car_route", arguments=arguments,
        result=dict(from_ref="anchor:origin", to_ref="place:expo", duration_seconds=600, evidence_id=evidence)))
    assert not any(c["tool_name"] == "get_car_route" and c["arguments"] == arguments
                   for c in build_decision_candidates(value)["candidates"])
    value["config"]["origin"]["latitude"] = 36
    assert any(c["tool_name"] == "get_car_route" and c["arguments"] == arguments
               for c in build_decision_candidates(value)["candidates"])


def test_auxiliary_config_source_reference_is_preserved_for_grounded_response():
    from ai.decision_candidates import build_decision_candidates, compact_decision_context
    value = task()
    analysis = dict(direct_text="여수", source_message_ids=["m1"], source_refs=["config.region"])
    result = build_decision_candidates(value, analysis)
    assert [c["action"] for c in result["candidates"]] == ["direct"]
    assert result["candidates"][0]["source_refs"] == ["config.region"]
    assert compact_decision_context(value, analysis, result["candidates"])["source_refs"] == ["config.region"]


def test_unpresented_actual_calls_are_returned_with_stable_provenance_for_tracing():
    from ai.decision_candidates import build_decision_candidates
    value = task()
    value["items"] = [item(str(n), title) for n, title in enumerate(["a", "b", "c", "d", "e"])]
    result = build_decision_candidates(value)
    assert [c["arguments"]["query"] for c in result["candidates"]] == ["a", "b", "c"]
    deferred = result["deferred_candidates"]
    assert [(c["tool_name"], c["arguments"], c["source_refs"]) for c in deferred] == [
        ("search_places", dict(query="d", region="여수", category=None), ["3"]),
        ("search_places", dict(query="e", region="여수", category=None), ["4"])]
    assert all(c["source_message_ids"] == ["m1"] for c in deferred)
    assert len({c["candidate_id"] for c in result["candidates"] + deferred}) == 5
    assert build_decision_candidates(value)["deferred_candidates"] == deferred
    assert len(value["items"]) == 5


def test_support_target_question_round_trips_through_existing_backend_answer_contract():
    from ai.decision_candidates import build_decision_candidates
    from ai.questions import valid_questions
    from backend.services.questions import answer_question
    value = task()
    value["config"]["region"] = None
    value["items"] = [dict(item("a", "엑스포"), item_version=1, supporter_ids=[])]
    value["recent_messages"][0].update(text="좋아", room_id="room")
    missing = dict(field="support_target", target_ref=None, text="어느 장소에 대한 의견인가요?", owner_id="u1",
                   stance="support", source_message_ids=["m1"])
    prepared = build_decision_candidates(value, {"missing_fields": [missing]})
    assert [c["action"] for c in prepared["candidates"]] == ["ask"]
    candidate = prepared["candidates"][0]
    q = candidate["question"]
    assert q["id"] == "question:support_target:support:m1"
    assert q["target_ref"] is None and q["owner_id"] == "u1"
    assert valid_questions(value, [q]) == [q]
    room = dict(room_id="room", members=value["members"], items=value["items"],
                messages=value["recent_messages"], questions=[q])
    answered = answer_question(room, q["id"], "u1", {"item_id": "a"})
    assert answered["status"] == "answered" and answered["target_ref"] == "a"
    assert room["items"][0]["supporter_ids"] == ["u1"]


def test_support_target_question_requires_bound_stance_current_source_and_same_owner():
    from ai.decision_candidates import build_decision_candidates
    value = task()
    value["members"].append(dict(user_id="u2"))
    value["conversation_context"] = [dict(id="old", author_id="u1", text="좋아")]
    missing = dict(field="support_target", target_ref=None, text="대상?", owner_id="u1", source_message_ids=["m1"])
    for bad in [missing, dict(missing, stance="support", owner_id="u2"),
                dict(missing, stance="support", source_message_ids=["old"]),
                dict(missing, stance="support", source_message_ids=["m1", "old"])]:
        assert build_decision_candidates(value, {"missing_fields": [bad]})["candidates"] == []


def test_current_request_is_presented_before_older_pending_places():
    from ai.decision_candidates import build_decision_candidates
    value = task()
    value["recent_messages"][0]["text"] = "새장소 검색해줘"
    value["conversation_context"] = [dict(id="old", author_id="u1", text="지난 장소들 검색")]
    value["items"] = [dict(item(str(n), "old" + str(n)), source_message_ids=["old"]) for n in range(4)]
    value["items"].append(item("new", "새장소"))
    result = build_decision_candidates(value)
    assert [c["arguments"]["query"] for c in result["candidates"]] == ["새장소", "old0", "old1"]
    assert [c["arguments"]["query"] for c in result["deferred_candidates"]] == ["old2", "old3"]


def test_compound_current_targets_follow_original_text_order_instead_of_item_insertion_order():
    from ai.decision_candidates import build_decision_candidates
    value = task()
    value["recent_messages"][0]["text"] = "나, 가, 다 검색해줘"
    value["items"] = [item("a", "가"), item("c", "다"), item("b", "나")]
    result = build_decision_candidates(value)
    assert [c["arguments"]["query"] for c in result["candidates"]] == ["나", "가", "다"]


def test_non_car_transport_cannot_prepare_car_routes_or_car_dependent_calculations():
    from ai.decision_candidates import build_decision_candidates
    from ai.tests.test_place_route_tools import task as fixture_task
    value = fixture_task()
    value["config"]["transport"] = "walk"
    result = build_decision_candidates(value)
    assert not any(c["tool_name"] in ("get_car_route", "build_itinerary", "calculate_costs") for c in result["candidates"])
    value = task()
    value["config"]["transport"] = "walk"
    value["items"] = [item("a", "엑스포")]
    result = build_decision_candidates(value)
    assert [(c["tool_name"], c["arguments"]) for c in result["candidates"] if c["action"] == "tool"] == [
        ("search_places", dict(query="엑스포", region="여수", category=None))]


def test_auxiliary_cannot_claim_supported_search_is_unsupported_or_invent_service_reason():
    from ai.decision_candidates import build_decision_candidates
    value = task()
    analysis = dict(unsupported=True, unsupported_reason="장소 검색은 지원하지 않습니다.", source_message_ids=["m1"])
    assert build_decision_candidates(value, analysis)["candidates"] == []
    value["items"] = [item("a", "엑스포")]
    assert [c["action"] for c in build_decision_candidates(value, analysis)["candidates"]] == ["tool"]


def test_real_unsupported_request_uses_code_owned_response_instead_of_auxiliary_reason():
    from ai.decision_candidates import build_decision_candidates
    value = task()
    value["recent_messages"][0]["text"] = "입장권을 예약해줘"
    result = build_decision_candidates(value, dict(unsupported=False, unsupported_reason="검색이 안 됩니다."))
    assert [c["action"] for c in result["candidates"]] == ["unsupported"]
    assert result["candidates"][0]["reason"] == "예약·결제·구매·예매를 직접 처리하는 기능은 제공하지 않습니다."
    assert result["candidates"][0]["source_message_ids"] == ["m1"]


def test_standing_non_car_replan_has_actual_config_grounded_unsupported_response():
    from ai.decision_candidates import build_decision_candidates, compact_decision_context
    value = task()
    value["recent_messages"] = []
    value["config"]["transport"] = "walk"
    prepared = build_decision_candidates(value)
    assert prepared["branch"] == "invalid"
    assert [c["action"] for c in prepared["candidates"]] == ["unsupported"]
    candidate = prepared["candidates"][0]
    assert candidate["reason"] == "현재 경로 조회는 자동차 이동만 지원합니다."
    assert candidate["source_message_ids"] == [] and candidate["source_refs"] == ["config:transport"]
    context = compact_decision_context(value, {}, prepared["candidates"])
    assert context["facts"]["config"]["transport"] == "walk"
    assert context["source_refs"] == ["config:transport"]
