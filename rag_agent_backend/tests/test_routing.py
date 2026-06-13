"""
tests/test_routing.py — Unit tests for the intent router's regex heuristics.

These tests run without a live database or Ollama — they only exercise the
pure-Python classification logic (product-lookup heuristic, multistep heuristic,
keyword patterns).
"""

import pytest

from rag_agent.retrieval.router import (
    _extract_product_name,
    _multistep_classify,
    _product_lookup_classify,
    _keyword_classify,
)


# ---------------------------------------------------------------------------
# Product-lookup heuristic
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("question,expected_intent,expected_name_substr", [
    ("how many Organic Baby Spinach are in stock", "product_lookup", "Organic Baby Spinach"),
    ("price of Fresh Milk", "product_lookup", "Fresh Milk"),
    ("how much does CloudSync Pro cost", "product_lookup", "CloudSync Pro"),
    ("stock of DataPulse Analytics Platform", "product_lookup", "DataPulse Analytics Platform"),
    ("what is the price of Artisan Sourdough Loaf?", "product_lookup", "Artisan Sourdough Loaf"),
])
def test_product_lookup_classify(question, expected_intent, expected_name_substr):
    assert _product_lookup_classify(question) == expected_intent
    name = _extract_product_name(question)
    assert name is not None
    assert expected_name_substr.lower() in name.lower()


@pytest.mark.parametrize("question", [
    "show me your newest products",
    "what do you sell",
    "compare the two cheapest laptops",
])
def test_product_lookup_does_not_fire_on_non_lookup(question):
    assert _product_lookup_classify(question) is None


# ---------------------------------------------------------------------------
# Multi-step heuristic
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("question", [
    "compare product 12 and product 30",
    "of the newest products which is cheapest",
    "find a laptop and tell me its discount",
])
def test_multistep_classify_fires(question):
    assert _multistep_classify(question) == "agent"


@pytest.mark.parametrize("question", [
    "how many Spinach are in stock",
    "what is your return policy",
    "show me most popular products",
])
def test_multistep_does_not_fire_on_simple_questions(question):
    assert _multistep_classify(question) is None


# ---------------------------------------------------------------------------
# Keyword fast-path
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("question,expected_label", [
    ("what are your newest products", "analytics_newest"),
    ("show me the most discounted items", "analytics_discount"),
    ("which products are most popular", "analytics_demand"),
])
def test_keyword_classify(question, expected_label):
    assert _keyword_classify(question) == expected_label
