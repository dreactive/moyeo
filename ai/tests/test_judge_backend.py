"""CPU-only boundary tests for the unchanged supplied yes/no judge."""
import json
from contextlib import contextmanager, nullcontext
from types import SimpleNamespace

import pytest


def tool(arguments=None):
    return dict(action="tool", tool_name="search_places", reason="Search the requested place",
                arguments=arguments or {"query": "엑스포", "region": "여수", "category": None},
                source_message_ids=["m1"], source_refs=[], candidate_id="candidate-1")


@pytest.fixture
def judge_backend(monkeypatch):
    import sys
    import ai.models.local_qwen as module

    class Vector(list):
        device = "cpu"
        def float(self):
            return self
        def detach(self):
            return self
        def __sub__(self, other):
            return Vector(a - b for a, b in zip(self, other))
        def __matmul__(self, other):
            return sum(a * b for a, b in zip(self, other))

    class Hidden:
        def __init__(self, value):
            self.value = value
        def __getitem__(self, position):
            return Vector([self.value, 0.])

    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(
        inference_mode=nullcontext, long="long", tensor=lambda values, **kwargs: values))

    class Tokenizer:
        prompts = None
        def __init__(self):
            self.prompts = []
        def encode(self, text, add_special_tokens=False):
            if text in ("yes", "no"):
                return [0 if text == "yes" else 1]
            self.prompts.append(text)
            return [ord(char) for char in text]

    class Model:
        disabled = False
        fail = False
        forwards = 0
        config = SimpleNamespace(max_position_embeddings=32768)
        active_adapter = "default"
        def get_base_model(self):
            return self
        def get_output_embeddings(self):
            return SimpleNamespace(weight=[Vector([1., 0.]), Vector([0., 0.])])
        def model(self, **kwargs):
            self.forwards += 1
            if self.fail:
                raise RuntimeError("judge inference failed")
            return SimpleNamespace(last_hidden_state=Hidden(-9. if self.disabled else 7.))
        @contextmanager
        def disable_adapter(self):
            self.disabled = True
            try:
                yield
            finally:
                self.disabled = False
        def generate(self, **kwargs):
            raise AssertionError("Judge must not generate")

    model, tokenizer, loads = Model(), Tokenizer(), []
    def load(*args):
        loads.append(args)
        return model, tokenizer
    monkeypatch.setattr(module, "load_components", load)
    return module.LocalQwenBackend("base", "adapter"), model, tokenizer, loads


@pytest.mark.parametrize("count", [1, 2, 3, 4])
def test_supplied_judge_uses_active_adapter_and_reuses_loaded_model(judge_backend, count):
    backend, model, tokenizer, loads = judge_backend
    assert backend.score_candidates({"current_messages": [{"text": "엑스포 검색"}]}, [tool()] * count) == [7.] * count
    assert backend.score_candidates({}, [tool()]) == [7.]
    assert loads == [("base", "adapter")]
    assert model.forwards == count + 1 and not model.disabled


def test_judge_sees_exact_tool_arguments_tools_and_evidence(judge_backend):
    backend, _, tokenizer, _ = judge_backend
    arguments = {"visits": [{"item_id": "i1", "polyline": [1, 2], "note": "필수 근거"}],
                 "anchors": {"origin": None}, "constraints": [], "route_legs": []}
    candidate = dict(tool(arguments), tool_name="build_itinerary")
    context = {"current_messages": [{"id": "m1", "text": "그대로 계산해줘"}],
               "source_messages": [{"id": "m0", "text": "여수 출발"}],
               "tools": [{"name": "build_itinerary", "parameters": {"visits": "array"}}]}
    before = json.dumps(candidate, ensure_ascii=False)
    assert backend.score_candidates(context, [candidate]) == [7.]
    prompt = tokenizer.prompts[-1]
    rendered = prompt.split("<|im_start|>assistant\n", 1)[1].split("<|im_end|>", 1)[0]
    assert json.loads(rendered) == {"name": "build_itinerary", "arguments": arguments}
    assert "여수 출발" in prompt and '"visits": "array"' in prompt
    assert json.dumps(candidate, ensure_ascii=False) == before


@pytest.mark.parametrize("action", ["ask", "unsupported", "direct"])
def test_non_tool_candidates_use_actual_response_reason(judge_backend, action):
    backend, _, tokenizer, _ = judge_backend
    candidate = dict(action=action, reason="어느 지역에서 찾을까요?", tool_name=None, arguments={})
    assert backend.score_candidates({}, [candidate]) == [7.]
    rendered = tokenizer.prompts[-1].split("<|im_start|>assistant\n", 1)[1].split("<|im_end|>", 1)[0]
    assert rendered == "어느 지역에서 찾을까요?"


@pytest.mark.parametrize("count", [0, 5])
def test_candidate_count_rejects_before_judge_forward(judge_backend, count):
    backend, model, _, _ = judge_backend
    with pytest.raises(ValueError, match="candidate"):
        backend.score_candidates({}, [tool()] * count)
    assert model.forwards == 0


@pytest.mark.parametrize("oversized", ["context", "tool", "arguments"])
def test_exact_prompt_budget_rejects_before_supplied_left_truncation(judge_backend, oversized):
    backend, model, _, _ = judge_backend
    context, candidate = {}, tool()
    if oversized == "context":
        context["source_messages"] = [{"text": "e" * 33000}]
    elif oversized == "tool":
        context["tools"] = [{"name": "search_places", "description": "t" * 33000}]
    else:
        candidate["arguments"]["query"] = "q" * 33000
    with pytest.raises(ValueError, match="budget"):
        backend.score_candidates(context, [candidate])
    assert model.forwards == 0


def test_model_position_limit_is_respected_before_forward(judge_backend):
    backend, model, _, _ = judge_backend
    model.config = SimpleNamespace(max_position_embeddings=32)
    with pytest.raises(ValueError, match="budget"):
        backend.score_candidates({}, [tool()])
    assert model.forwards == 0


def test_scoring_failure_propagates_and_adapter_remains_active(judge_backend):
    backend, model, _, _ = judge_backend
    model.fail = True
    with pytest.raises(RuntimeError, match="judge inference failed"):
        backend.score_candidates({}, [tool()])
    model.fail = False
    assert backend.score_candidates({}, [tool()]) == [7.]
    assert not model.disabled


@pytest.mark.parametrize("scores", [[float("nan")], [float("inf")], [], [1., 2.]])
def test_bad_judge_scores_are_rejected_without_fallback(judge_backend, monkeypatch, scores):
    from submission import judge
    backend, _, _, _ = judge_backend
    monkeypatch.setattr(judge, "judge_scores", lambda *args, **kwargs: scores)
    with pytest.raises(ValueError, match="score"):
        backend.score_candidates({}, [tool()])


def test_fixture_scores_are_explicit_deterministic_and_prefer_real_tools():
    from ai.models.fake import FakeModelBackend
    candidates = [dict(action="direct"), dict(action="unsupported"), dict(action="ask"), tool()]
    backend = FakeModelBackend()
    scores = backend.score_candidates({}, candidates)
    assert scores == [0., 1., 2., 3.]
    assert backend.score_candidates({"other_room": True}, candidates) == scores
    with pytest.raises(ValueError, match="candidate"):
        backend.score_candidates({}, [])


def test_service_packet_labels_verified_facts_and_keeps_native_candidate(judge_backend):
    from ai.models.qwen_judge import judge_question
    backend, _, tokenizer, _ = judge_backend
    candidate = tool()
    context = dict(current_messages=[dict(text='오동도 찾아줘')],
                   facts=dict(places={'p1':dict(id='p1',name='오동도',address='여수')}))
    backend.score_candidates(context,[candidate])
    prompt=tokenizer.prompts[-1]
    assert 'VERIFIED FACTS' in judge_question(context,'readable')
    assert 'p1' in prompt and '오동도' in prompt
    assert json.loads(prompt.split('<|im_start|>assistant\n',1)[1].split('<|im_end|>',1)[0]) == {
        'name':candidate['tool_name'],'arguments':candidate['arguments']}


def test_tool_schemas_explain_required_arguments_from_registered_contracts():
    from ai.tools.definitions import TOOL_DEFINITIONS
    from ai.tools.validation import PARAMETERS
    for definition in TOOL_DEFINITIONS:
        schema=definition['parameters']
        assert schema['type']=='object'
        assert set(schema['required'])==set(PARAMETERS[definition['name']])
        assert set(schema['properties'])==set(schema['required'])
        assert schema['additionalProperties'] is False
