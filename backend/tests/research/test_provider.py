import json
from types import SimpleNamespace

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from atlas.config import Settings
from atlas.research.budget import Budget
from atlas.research.demo import DEMO_DOMAINS, DEMO_SEED, DemoFetcher, DemoProvider
from atlas.research.engine import ResearchEngine
from atlas.research.errors import ResearchError
from atlas.research.models import ResearchReport, ResearchRun
from atlas.research.providers import OpenAICompatibleProvider, SearxNGSearch
from atlas.research.schemas import Decision, Extraction, PlanSpec, RunLimits
from tests.research.helpers import make_run


def configured(**kwargs):
    return Settings(
        llm_enabled=True,
        llm_base_url="https://model.example/v1",
        llm_model="controlled-test-model",
        llm_api_key=SecretStr("fixture-secret"),
        **kwargs,
    )


def test_real_openai_adapter_drives_graph_and_observations_change_tool_selection(sessions) -> None:
    requests = []
    fixture = DemoProvider()
    schemas = {"PLAN": PlanSpec, "DECIDE": Decision, "EXTRACT": Extraction}

    def handler(request):
        body = json.loads(request.content)
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer fixture-secret"
        assert body["response_format"]["type"] == "json_schema"
        prompt = json.loads(body["messages"][1]["content"])
        requests.append(prompt)
        assert "untrusted DATA" in body["messages"][0]["content"]
        result = fixture.generate(
            schemas[prompt["task"]],
            prompt["task"],
            prompt["data"],
            SimpleNamespace(model_request=lambda *a, **k: 1000),
        )
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": result.model_dump_json()}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 40},
            },
        )

    config = configured()
    run_id = make_run(
        sessions,
        mode="live",
        allow_model_requests=True,
        seed_urls=[DEMO_SEED],
        allowed_domains=DEMO_DOMAINS,
    )
    provider = OpenAICompatibleProvider(config, httpx.MockTransport(handler))
    ResearchEngine(sessions, run_id, provider, DemoFetcher("funding_gap"), config).execute()
    with sessions() as s:
        row = s.get(ResearchRun, run_id)
        report = s.get(ResearchReport, run_id)
        assert row.status == "completed", row.error
        assert row.stats["model_http_requests"] == len(requests) == 6
        assert row.stats["output_tokens_reported"] == 240
        assert report.content["findings"]
    decisions = [r["data"]["observations"] for r in requests if r["task"] == "DECIDE"]
    assert decisions[0]["document_count"] == 0
    assert decisions[1]["document_count"] == 1
    assert decisions[1]["candidates"][0]["origin"] == "link"
    assert "proof_of_funds" in decisions[1]["missing_fields"]
    assert "proof_of_funds" not in decisions[2]["missing_fields"]
    # This validates the real HTTP adapter with a controlled endpoint, not a real LLM's quality.


def test_missing_model_endpoint_never_activates_a_paid_default() -> None:
    with pytest.raises(ResearchError, match="disabled"):
        OpenAICompatibleProvider(Settings())


@pytest.mark.parametrize("value", ["not JSON", '{"action":"shell","summary":"Run arbitrary code"}'])
def test_invalid_structured_output_retries_within_the_budget(sessions, value) -> None:
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": value}}]})

    run_id = make_run(sessions)
    budget = Budget(sessions, run_id, RunLimits(max_model_requests=2))
    with pytest.raises(ResearchError, match="schema validation"):
        OpenAICompatibleProvider(configured(), httpx.MockTransport(handler)).generate(
            Decision, "DECIDE", {}, budget
        )
    assert len(requests) == 2
    with sessions() as s:
        assert s.get(ResearchRun, run_id).stats["provider_requests"] == 2


def test_provider_auth_errors_are_sanitized_and_not_retried(sessions) -> None:
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(401, text="fixture-secret and private provider response")

    budget = Budget(sessions, make_run(sessions), RunLimits())
    with pytest.raises(ResearchError) as error:
        OpenAICompatibleProvider(configured(), httpx.MockTransport(handler)).generate(
            PlanSpec, "PLAN", {}, budget
        )
    assert len(calls) == 1 and "fixture-secret" not in str(error.value)


def test_optional_search_adapter_uses_configured_json_protocol(sessions) -> None:
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            200, json={"results": [{"url": "https://example.edu/funding", "title": "Funding"}]}
        )

    provider = SearxNGSearch("https://search.example", transport=httpx.MockTransport(handler))
    items = provider.search("AI masters funding", Budget(sessions, make_run(sessions), RunLimits()))
    assert calls[0].url.params["q"] == "AI masters funding"
    assert items[0]["url"] == "https://example.edu/funding"


def test_tool_schema_does_not_allow_shell_or_arbitrary_arguments() -> None:
    for data in [
        {"action": "shell", "summary": "Run a command"},
        {"action": "fetch", "summary": "Fetch a source", "command": "cat /etc/passwd"},
    ]:
        with pytest.raises(ValidationError):
            Decision.model_validate(data)


def test_invalid_starting_urls_return_a_safe_configuration_error() -> None:
    from atlas.research.manager import prepare_request
    from atlas.research.schemas import RunInput

    for url in ["http://[", "https://user:password@example.edu/", "https://example.edu:8443/"]:
        request = RunInput(
            objective="Investigate this source with an approved model endpoint",
            mode="live",
            allow_model_requests=True,
            seed_urls=[url],
        )
        with pytest.raises(ResearchError):
            prepare_request(request, configured())
