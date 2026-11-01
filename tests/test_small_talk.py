import pytest

from src.agent import _small_talk_kind
from tests.test_agent import make_agent


@pytest.mark.parametrize("text,kind", [
    ("hello", "greeting"), ("hello hello hello hello", "greeting"), ("Hi there!", "greeting"),
    ("नमस्ते", "greeting"), ("Good morning", "greeting"),
    ("how can you help me", "capability"), ("What can you do?", "capability"), ("who are you", "capability"),
    ("thanks", "thanks"), ("thank you", "thanks"), ("ok thanks", "thanks"),
])
def test_small_talk_is_detected(text, kind):
    assert _small_talk_kind(text) == kind


@pytest.mark.parametrize("text", [
    "hello my order has not arrived", "how can you help me get a refund", "can I return this",
    "thanks but where is my refund", "good", "what is the return policy",
])
def test_real_questions_are_not_small_talk(text):
    assert _small_talk_kind(text) is None


def test_greeting_gets_help_menu_without_calling_llm_or_tools(tmp_path):
    agent = make_agent(tmp_path)
    reply = agent.respond("how can you help me", "s1")
    assert "returns" in reply.response and "don't have information" not in reply.response
    assert reply.response.startswith("Hello, I’m ZentroMart’s AI support assistant.")
    assert reply.decision == "clarify"
    assert agent.llm.calls == [] and agent.tools.calls == []


def test_second_greeting_has_no_duplicate_introduction(tmp_path):
    agent = make_agent(tmp_path)
    agent.respond("hello", "s2")
    second = agent.respond("hello hello", "s2")
    assert second.response.count("AI support assistant") == 0
