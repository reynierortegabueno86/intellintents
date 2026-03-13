"""Tests for classifier implementations (rule_based, embedding, hybrid, cascading)."""
import json
import pytest
from unittest.mock import patch, MagicMock

from app.classifiers.rule_based import RuleBasedClassifier
from app.classifiers.embedding_classifier import EmbeddingSimilarityClassifier
from app.classifiers.hybrid import HybridClassifier
from app.classifiers.cascading_classifier import CascadingClassifier
from app.classifiers.cascading_prompts import (
    STAGE1_SYSTEM_PROMPT,
    STAGE2_PROMPTS,
    CATEGORY_INTENTS,
)
from app.classifiers.base import ClassifierConfigError
from app.services.classification_service import get_classifier, is_fallback_label


SAMPLE_CATEGORIES = [
    {"name": "Greeting", "description": "Initial greetings and salutations"},
    {"name": "Technical Problem", "description": "Reporting errors, crashes, or technical difficulties"},
    {"name": "Purchase Intent", "description": "Interest in buying, upgrading, or pricing"},
    {"name": "Complaint", "description": "Expressing dissatisfaction or negative feedback"},
    {"name": "Cancellation", "description": "Requesting to cancel subscription or account"},
]


class TestRuleBasedClassifier:
    def setup_method(self):
        self.clf = RuleBasedClassifier()

    def test_classify_single(self):
        label, confidence, explanation = self.clf.classify_turn("Hello!", SAMPLE_CATEGORIES)
        assert isinstance(label, str)
        assert 0.0 <= confidence <= 1.0
        assert isinstance(explanation, str)

    def test_classify_batch(self):
        texts = ["Hello!", "The app keeps crashing", "I want to cancel"]
        results = self.clf.classify_batch(texts, SAMPLE_CATEGORIES)
        assert len(results) == 3
        for label, confidence, explanation in results:
            assert isinstance(label, str)
            assert 0.0 <= confidence <= 1.0

    def test_empty_categories(self):
        results = self.clf.classify_batch(["Hello"], [])
        assert len(results) == 1
        assert results[0][0] == "Unknown"

    def test_empty_texts(self):
        results = self.clf.classify_batch([], SAMPLE_CATEGORIES)
        assert results == []

    def test_custom_keyword_map(self):
        clf = RuleBasedClassifier(keyword_map={"Purchase Intent": ["buy", "purchase", "pricing"]})
        label, _, _ = clf.classify_turn("I want to buy your product", SAMPLE_CATEGORIES)
        assert label == "Purchase Intent"


class TestEmbeddingClassifier:
    def setup_method(self):
        self.clf = EmbeddingSimilarityClassifier()

    def test_classify_single(self):
        label, confidence, explanation = self.clf.classify_turn(
            "My application crashes every time", SAMPLE_CATEGORIES
        )
        assert isinstance(label, str)
        assert 0.0 <= confidence <= 1.0

    def test_classify_batch(self):
        texts = ["Hello there", "I want to cancel my account", "How much does it cost?"]
        results = self.clf.classify_batch(texts, SAMPLE_CATEGORIES)
        assert len(results) == 3

    def test_empty_categories(self):
        results = self.clf.classify_batch(["Hello"], [])
        assert results[0][0] == "Unknown"


class TestHybridClassifier:
    def test_default_weights(self):
        clf = HybridClassifier()
        results = clf.classify_batch(["I want to cancel"], SAMPLE_CATEGORIES)
        assert len(results) == 1
        assert isinstance(results[0][0], str)

    def test_custom_weights(self):
        clf = HybridClassifier(rule_weight=0.8, embedding_weight=0.2)
        results = clf.classify_batch(["Hello!"], SAMPLE_CATEGORIES)
        assert len(results) == 1


class TestGetClassifier:
    def test_rule_based(self):
        clf = get_classifier("rule_based")
        assert isinstance(clf, RuleBasedClassifier)

    def test_embedding(self):
        clf = get_classifier("embedding")
        assert isinstance(clf, EmbeddingSimilarityClassifier)

    def test_hybrid(self):
        clf = get_classifier("hybrid")
        assert isinstance(clf, HybridClassifier)

    def test_unknown_method(self):
        with pytest.raises(ValueError, match="Unknown classification method"):
            get_classifier("nonexistent")

    def test_rule_based_with_config(self):
        clf = get_classifier("rule_based", {"keyword_map": {"Greeting": ["hi"]}})
        assert isinstance(clf, RuleBasedClassifier)

    def test_cascading(self):
        clf = get_classifier("cascading", {"provider": "openai", "model": "gpt-4o-mini"})
        assert isinstance(clf, CascadingClassifier)


# ---------------------------------------------------------------------------
# Cascading Classifier Tests
# ---------------------------------------------------------------------------

class TestCascadingPromptsLoading:
    """Verify that prompts are loaded from .txt files correctly."""

    def test_stage1_prompt_loaded(self):
        assert len(STAGE1_SYSTEM_PROMPT) > 100
        assert "ONBOARDING_KYC" in STAGE1_SYSTEM_PROMPT
        assert "UNKNOWN" in STAGE1_SYSTEM_PROMPT

    def test_all_stage2_prompts_loaded(self):
        assert len(STAGE2_PROMPTS) == 14
        for category, prompt in STAGE2_PROMPTS.items():
            assert len(prompt) > 100, f"Stage 2 prompt for {category} is too short"
            assert "UNKNOWN_SUBCATEGORY" in prompt

    def test_stage2_prompts_match_categories(self):
        assert set(STAGE2_PROMPTS.keys()) == set(CATEGORY_INTENTS.keys())

    def test_category_intents_total(self):
        total = sum(len(intents) for intents in CATEGORY_INTENTS.values())
        assert total == 84


class TestCascadingClassifierUnit:
    """Unit tests for CascadingClassifier with mocked LLM calls."""

    def setup_method(self):
        self.clf = CascadingClassifier(
            provider="openai", model="gpt-4o-mini", api_key="test-key"
        )

    def _mock_llm_response(self, response_dict):
        """Create a mock that returns a JSON string."""
        return json.dumps(response_dict)

    def test_full_pipeline_english(self):
        """Test successful two-stage classification with English input."""
        stage1_resp = json.dumps({
            "category": "EXECUTION_TRANSACTIONS",
            "confidence": 0.95,
            "reasoning_hint": "User wants to buy.",
        })
        stage2_resp = json.dumps({
            "intent": "buy_investment",
            "confidence": 0.93,
            "reasoning_hint": "Direct purchase order.",
        })

        with patch.object(self.clf, "_call_llm", side_effect=[stage1_resp, stage2_resp]):
            label, conf, explanation = self.clf.classify_turn(
                "Buy 100 shares of AAPL", []
            )

        assert label == "buy_investment"
        assert conf == round(0.95 * 0.93, 4)
        assert "Stage 1: EXECUTION_TRANSACTIONS" in explanation
        assert "Stage 2: buy_investment" in explanation

    def test_full_pipeline_spanish(self):
        """Test successful two-stage classification with Spanish input."""
        stage1_resp = json.dumps({
            "category": "ONBOARDING_KYC",
            "confidence": 0.97,
            "reasoning_hint": "User wants to open an account.",
        })
        stage2_resp = json.dumps({
            "intent": "open_account",
            "confidence": 0.96,
            "reasoning_hint": "Direct request.",
        })

        with patch.object(self.clf, "_call_llm", side_effect=[stage1_resp, stage2_resp]):
            label, conf, explanation = self.clf.classify_turn(
                "Me gustaria abrir una nueva cuenta de inversion", []
            )

        assert label == "open_account"
        assert conf == round(0.97 * 0.96, 4)

    def test_unknown_category(self):
        """Stage 1 returns UNKNOWN -> pipeline stops."""
        stage1_resp = json.dumps({
            "category": "UNKNOWN",
            "confidence": 0.90,
            "reasoning_hint": "Not related to finance.",
        })

        with patch.object(self.clf, "_call_llm", return_value=stage1_resp):
            label, conf, explanation = self.clf.classify_turn("What's the weather?", [])

        assert label == "UNKNOWN"
        assert "Stage 1: UNKNOWN" in explanation

    def test_low_stage1_confidence(self):
        """Stage 1 confidence below threshold -> UNKNOWN."""
        stage1_resp = json.dumps({
            "category": "FINANCIAL_EDUCATION",
            "confidence": 0.45,
            "reasoning_hint": "Ambiguous.",
        })

        with patch.object(self.clf, "_call_llm", return_value=stage1_resp):
            label, conf, explanation = self.clf.classify_turn("Help me", [])

        assert label == "UNKNOWN"

    def test_low_stage2_confidence(self):
        """Stage 2 confidence below threshold -> falls back to category label."""
        stage1_resp = json.dumps({
            "category": "PORTFOLIO_MONITORING",
            "confidence": 0.88,
            "reasoning_hint": "Portfolio related.",
        })
        stage2_resp = json.dumps({
            "intent": "check_performance",
            "confidence": 0.50,
            "reasoning_hint": "Ambiguous within category.",
        })

        with patch.object(self.clf, "_call_llm", side_effect=[stage1_resp, stage2_resp]):
            label, conf, explanation = self.clf.classify_turn("Tell me about my stuff", [])

        assert label == "PORTFOLIO_MONITORING"
        assert conf == 0.88

    def test_invalid_intent_fuzzy_match(self):
        """Stage 2 returns misformatted intent -> fuzzy match corrects it."""
        stage1_resp = json.dumps({
            "category": "FINANCIAL_EDUCATION",
            "confidence": 0.92,
            "reasoning_hint": "Educational question.",
        })
        stage2_resp = json.dumps({
            "intent": "Explain-Concept",  # wrong format
            "confidence": 0.90,
            "reasoning_hint": "Financial concept.",
        })

        with patch.object(self.clf, "_call_llm", side_effect=[stage1_resp, stage2_resp]):
            label, conf, explanation = self.clf.classify_turn("What is diversification?", [])

        assert label == "explain_concept"

    def test_invalid_intent_no_match(self):
        """Stage 2 returns wrong-category intent -> falls back to category label."""
        stage1_resp = json.dumps({
            "category": "FINANCIAL_EDUCATION",
            "confidence": 0.92,
            "reasoning_hint": "Educational.",
        })
        stage2_resp = json.dumps({
            "intent": "buy_investment",  # wrong category
            "confidence": 0.90,
            "reasoning_hint": "Misclassified.",
        })

        with patch.object(self.clf, "_call_llm", side_effect=[stage1_resp, stage2_resp]):
            label, conf, explanation = self.clf.classify_turn("Teach me", [])

        assert label == "FINANCIAL_EDUCATION"

    def test_stage1_api_error(self):
        """Stage 1 LLM call fails -> graceful fallback to UNKNOWN."""
        with patch.object(self.clf, "_call_llm", side_effect=Exception("API timeout")):
            label, conf, explanation = self.clf.classify_turn("Buy shares", [])

        assert label == "UNKNOWN"
        assert conf == 0.0

    def test_stage2_api_error(self):
        """Stage 2 LLM call fails -> falls back to category label."""
        stage1_resp = json.dumps({
            "category": "EXECUTION_TRANSACTIONS",
            "confidence": 0.95,
            "reasoning_hint": "Transaction.",
        })

        call_count = 0

        def side_effect(messages, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return stage1_resp
            raise Exception("API timeout")

        with patch.object(self.clf, "_call_llm", side_effect=side_effect):
            label, conf, explanation = self.clf.classify_turn("Buy shares", [])

        assert label == "EXECUTION_TRANSACTIONS"

    def test_malformed_json_stage1(self):
        """Stage 1 returns non-JSON -> UNKNOWN."""
        with patch.object(self.clf, "_call_llm", return_value="not json at all"):
            label, conf, explanation = self.clf.classify_turn("Buy shares", [])

        assert label == "UNKNOWN"

    def test_config_error_propagates(self):
        """ClassifierConfigError (missing API key) must NOT be caught silently."""
        with patch.object(
            self.clf, "_call_llm",
            side_effect=ClassifierConfigError("No API key provided"),
        ):
            with pytest.raises(ClassifierConfigError, match="No API key"):
                self.clf.classify_turn("Buy shares", [])

    def test_classify_batch(self):
        """Batch classification processes each message independently."""
        responses = [
            json.dumps({"category": "ONBOARDING_KYC", "confidence": 0.95, "reasoning_hint": "Open account."}),
            json.dumps({"intent": "open_account", "confidence": 0.90, "reasoning_hint": "New account."}),
            json.dumps({"category": "UNKNOWN", "confidence": 0.85, "reasoning_hint": "Greeting."}),
        ]

        with patch.object(self.clf, "_call_llm", side_effect=responses):
            results = self.clf.classify_batch(
                ["Open account", "Hi there"], []
            )

        assert len(results) == 2
        assert results[0][0] == "open_account"
        assert results[1][0] == "UNKNOWN"

    def test_custom_thresholds(self):
        """Verify custom thresholds are respected."""
        clf = CascadingClassifier(
            provider="openai", model="test", api_key="test",
            stage1_threshold=0.80, stage2_threshold=0.85,
        )
        stage1_resp = json.dumps({
            "category": "FINANCIAL_EDUCATION",
            "confidence": 0.75,  # below custom 0.80 threshold
            "reasoning_hint": "Maybe educational.",
        })

        with patch.object(clf, "_call_llm", return_value=stage1_resp):
            label, _, _ = clf.classify_turn("Something", [])

        assert label == "UNKNOWN"

    def test_separate_stage_models(self):
        """Verify different models can be used for each stage."""
        clf = CascadingClassifier(
            provider="openai", model="default",
            api_key="test",
            stage1_model="fast-model",
            stage2_model="smart-model",
        )
        assert clf.stage1_model == "fast-model"
        assert clf.stage2_model == "smart-model"


class TestFallbackLabels:
    """Verify that UNKNOWN/null/None/empty are recognized as fallback labels."""

    def test_unknown_variants(self):
        assert is_fallback_label("UNKNOWN") is True
        assert is_fallback_label("Unknown") is True
        assert is_fallback_label("unknown") is True

    def test_none_null_empty(self):
        assert is_fallback_label("None") is True
        assert is_fallback_label("null") is True
        assert is_fallback_label("NULL") is True
        assert is_fallback_label("empty") is True
        assert is_fallback_label("EMPTY") is True
        assert is_fallback_label("") is True

    def test_unknown_subcategory_patterns(self):
        assert is_fallback_label("UNKNOWN_SUBCATEGORY") is True
        # Category labels used as fallback are NOT fallback labels themselves
        assert is_fallback_label("EXECUTION_TRANSACTIONS") is False
        assert is_fallback_label("PORTFOLIO_MONITORING") is False

    def test_real_intents_are_not_fallback(self):
        assert is_fallback_label("buy_investment") is False
        assert is_fallback_label("open_account") is False
        assert is_fallback_label("ONBOARDING_KYC") is False
        assert is_fallback_label("explain_concept") is False
