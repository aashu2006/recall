import json

import httpx
import pytest
from pydantic import BaseModel

from app import llm
from app.config import Settings


class Answer(BaseModel):
    item: str
    quantity: int


def settings(**kw):
    base = dict(groq_api_key="g", groq_model="groq-m", gemini_api_key="k", gemini_model="gem-m")
    return Settings(_env_file=None, **{**base, **kw})


def groq_ok(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def gemini_ok(content: str) -> httpx.Response:
    return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": content}]}}]})


def mock_client(responses):
    requests = []

    def handler(request):
        requests.append(request)
        result = responses[len(requests) - 1]
        if isinstance(result, Exception):
            raise result
        return result

    return httpx.Client(transport=httpx.MockTransport(handler)), requests


def test_groq_json_mode_and_validation():
    client, requests = mock_client([groq_ok('{"item": "bracket", "quantity": 300}')])

    out = llm.complete_json("sys", "bracket 300 kar do", Answer, settings=settings(), client=client)

    assert out == Answer(item="bracket", quantity=300)
    body = json.loads(requests[0].content)
    assert requests[0].url == "https://api.groq.com/openai/v1/chat/completions"
    assert requests[0].headers["Authorization"] == "Bearer g"
    assert body["model"] == "groq-m"
    assert body["response_format"] == {"type": "json_object"}
    assert body["messages"][0]["role"] == "system"
    assert '"quantity"' in body["messages"][0]["content"]  # schema is in the prompt
    assert body["messages"][1] == {"role": "user", "content": "bracket 300 kar do"}


def test_falls_back_to_gemini_on_rate_limit():
    client, requests = mock_client(
        [httpx.Response(429, json={"error": "rate"}), gemini_ok('{"item": "angle", "quantity": 40}')]
    )

    out = llm.complete_json("sys", "u", Answer, settings=settings(), client=client)

    assert out.item == "angle"
    assert "gem-m:generateContent" in str(requests[1].url)
    assert requests[1].headers["x-goog-api-key"] == "k"
    body = json.loads(requests[1].content)
    assert body["generationConfig"]["responseMimeType"] == "application/json"


def test_falls_back_on_connection_error():
    client, _ = mock_client([httpx.ConnectError("down"), gemini_ok('{"item": "a", "quantity": 1}')])

    assert llm.complete_json("s", "u", Answer, settings=settings(), client=client).quantity == 1


def test_retries_once_with_validation_error():
    client, requests = mock_client(
        [groq_ok('{"item": "bracket"}'), groq_ok('{"item": "bracket", "quantity": 300}')]
    )

    out = llm.complete_json("s", "u", Answer, settings=settings(), client=client)

    assert out.quantity == 300
    retry = json.loads(requests[1].content)["messages"]
    assert retry[2] == {"role": "assistant", "content": '{"item": "bracket"}'}
    assert "quantity" in retry[3]["content"]


def test_two_invalid_answers_move_to_fallback():
    client, requests = mock_client(
        [groq_ok("not json"), groq_ok("{}"), gemini_ok('```json\n{"item": "x", "quantity": 2}\n```')]
    )

    assert llm.complete_json("s", "u", Answer, settings=settings(), client=client).quantity == 2
    assert len(requests) == 3


def test_all_fail_raises():
    client, _ = mock_client([httpx.Response(500), httpx.Response(503)])

    with pytest.raises(llm.LlmError, match="groq.*gemini"):
        llm.complete_json("s", "u", Answer, settings=settings(), client=client)


def test_skips_unconfigured_groq():
    client, requests = mock_client([gemini_ok('{"item": "x", "quantity": 2}')])

    llm.complete_json("s", "u", Answer, settings=settings(groq_model=""), client=client)

    assert len(requests) == 1 and "generateContent" in str(requests[0].url)


def test_nothing_configured_raises():
    with pytest.raises(llm.LlmError, match="No LLM configured"):
        llm.complete_json("s", "u", Answer, settings=Settings(_env_file=None))
