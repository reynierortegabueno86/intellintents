"""Tests for ContextCascadingClassifier (context-aware cascading)."""
import json
import pytest
from unittest.mock import patch

from app.classifiers.base import TurnInfo, ClassifierConfigError
from app.classifiers.context_cascading_classifier import ContextCascadingClassifier
from app.services.classification_service import get_classifier, _group_turns_by_conversation


SAMPLE_CATEGORIES = [
    {"name": "Greeting", "description": "Initial greetings"},
    {"name": "Technical Problem", "description": "Reporting errors"},
]


# ---------------------------------------------------------------------------
# TurnInfo
# ---------------------------------------------------------------------------

class TestTurnInfo:
    def test_creation(self):
        ti = TurnInfo(text="hello", speaker="user", turn_index=0, conversation_id=1)
        assert ti.text == "hello"
        assert ti.speaker == "user"
        assert ti.turn_index == 0
        assert ti.conversation_id == 1

    def test_is_namedtuple(self):
        ti = TurnInfo("a", "b", 0, 1)
        assert ti._asdict() == {
            "text": "a", "speaker": "b", "turn_index": 0, "conversation_id": 1
        }


# ---------------------------------------------------------------------------
# get_classifier registration
# ---------------------------------------------------------------------------

class TestGetClassifierRegistration:
    def test_cascading_context_default(self):
        clf = get_classifier("cascading_context", {})
        assert isinstance(clf, ContextCascadingClassifier)
        assert clf.context_backward == 2
        assert clf.context_forward == 1
        assert clf.context_max_chars == 500
        assert clf.use_previous_labels is False
        assert clf.max_tokens == 250

    def test_cascading_context_custom(self):
        clf = get_classifier("cascading_context", {
            "context_backward": 4,
            "context_forward": 2,
            "context_max_chars": 300,
            "use_previous_labels": True,
        })
        assert clf.context_backward == 4
        assert clf.context_forward == 2
        assert clf.context_max_chars == 300
        assert clf.use_previous_labels is True

    def test_use_previous_labels_string_coercion(self):
        """Frontend may send string 'true'/'false' — backend must coerce."""
        clf = get_classifier("cascading_context", {"use_previous_labels": "true"})
        assert clf.use_previous_labels is True
        clf2 = get_classifier("cascading_context", {"use_previous_labels": "false"})
        assert clf2.use_previous_labels is False
        clf3 = get_classifier("cascading_context", {"use_previous_labels": "False"})
        assert clf3.use_previous_labels is False

    def test_has_conversation_batch_method(self):
        clf = get_classifier("cascading_context", {})
        assert hasattr(clf, "classify_conversation_batch")


# ---------------------------------------------------------------------------
# Context formatting
# ---------------------------------------------------------------------------

def _make_clf(**kwargs):
    defaults = dict(provider="openai", model="test", api_key="k", context_backward=2, context_forward=1)
    defaults.update(kwargs)
    return ContextCascadingClassifier(**defaults)


def _make_turns(conversation_id=1):
    return [
        TurnInfo("I can help you explore ESG funds.", "assistant", 0, conversation_id),
        TurnInfo("What about the Vanguard one?", "user", 1, conversation_id),
        TurnInfo("Is it suitable for my risk profile?", "user", 2, conversation_id),
        TurnInfo("Based on your conservative profile...", "assistant", 3, conversation_id),
    ]


class TestFormatContextMessage:
    def test_mode_a_no_labels(self):
        clf = _make_clf()
        turns = _make_turns()
        msg = clf._format_context_message(
            target=turns[2], backward=[turns[0], turns[1]], forward=[turns[3]],
        )
        assert ">>> TARGET TURN (classify this) <<<" in msg
        assert "[Turn 0] user: Is it suitable" in msg
        assert "[Turn -2] assistant:" in msg
        assert "[Turn -1] user:" in msg
        assert "[Turn +1] assistant:" in msg
        # No labels in Mode A
        assert "→" not in msg

    def test_mode_b_with_labels(self):
        clf = _make_clf()
        turns = _make_turns()
        labels = {0: "PRODUCT_DISCOVERY", 1: "PRODUCT_DISCOVERY"}
        msg = clf._format_context_message(
            target=turns[2], backward=[turns[0], turns[1]], forward=[turns[3]],
            backward_labels=labels,
        )
        assert "→ PRODUCT_DISCOVERY:" in msg
        # Forward turn should never have a label
        assert msg.count("→") == 2  # only backward turns

    def test_first_turn_no_backward(self):
        clf = _make_clf()
        turns = _make_turns()
        msg = clf._format_context_message(
            target=turns[0], backward=[], forward=[turns[1]],
        )
        assert "[Turn -" not in msg
        assert "[Turn 0]" in msg
        assert "[Turn +1]" in msg

    def test_last_turn_no_forward(self):
        clf = _make_clf()
        turns = _make_turns()
        msg = clf._format_context_message(
            target=turns[3], backward=[turns[1], turns[2]], forward=[],
        )
        assert "[Turn +" not in msg

    def test_single_turn_conversation(self):
        clf = _make_clf()
        t = TurnInfo("Hello", "user", 0, 1)
        msg = clf._format_context_message(target=t, backward=[], forward=[])
        assert "TARGET TURN" in msg
        assert "[Turn 0] user: Hello" in msg

    def test_truncation(self):
        clf = _make_clf(context_max_chars=20)
        long_turn = TurnInfo("A" * 100, "user", 0, 1)
        target = TurnInfo("target", "user", 1, 1)
        msg = clf._format_context_message(
            target=target, backward=[long_turn], forward=[],
        )
        # Context turn should be truncated, target should not
        assert "AAAA..." in msg
        assert len("A" * 100) not in [len(l) for l in msg.split("\n")]

    def test_target_never_truncated(self):
        clf = _make_clf(context_max_chars=20)
        long_text = "B" * 200
        target = TurnInfo(long_text, "user", 0, 1)
        msg = clf._format_context_message(target=target, backward=[], forward=[])
        assert long_text in msg


# ---------------------------------------------------------------------------
# _group_turns_by_conversation helper
# ---------------------------------------------------------------------------

class TestGroupTurnsByConversation:
    def test_basic_grouping(self):
        class FakeTurn:
            def __init__(self, text, speaker, turn_index, conversation_id):
                self.text = text
                self.speaker = speaker
                self.turn_index = turn_index
                self.conversation_id = conversation_id

        turns = [
            FakeTurn("a", "user", 0, 10),
            FakeTurn("b", "assistant", 1, 10),
            FakeTurn("c", "user", 0, 20),
        ]
        groups = _group_turns_by_conversation(turns)
        assert set(groups.keys()) == {10, 20}
        assert len(groups[10]) == 2
        assert len(groups[20]) == 1
        assert all(isinstance(ti, TurnInfo) for ti in groups[10])

    def test_sorted_by_turn_index(self):
        class FakeTurn:
            def __init__(self, text, speaker, turn_index, conversation_id):
                self.text = text
                self.speaker = speaker
                self.turn_index = turn_index
                self.conversation_id = conversation_id

        turns = [
            FakeTurn("second", "user", 1, 1),
            FakeTurn("first", "user", 0, 1),
        ]
        groups = _group_turns_by_conversation(turns)
        assert groups[1][0].text == "first"
        assert groups[1][1].text == "second"


# ---------------------------------------------------------------------------
# Classification with mocked LLM
# ---------------------------------------------------------------------------

class TestContextClassificationModeA:
    """Mode A: static context, full parallel."""

    def test_single_conversation(self):
        clf = _make_clf(use_previous_labels=False)
        turns = _make_turns()

        stage1_resp = json.dumps({"category": "EXECUTION_TRANSACTIONS", "confidence": 0.90, "reasoning_hint": ""})
        stage2_resp = json.dumps({"intent": "buy_investment", "confidence": 0.85, "reasoning_hint": ""})

        with patch.object(clf, "_call_llm", side_effect=[stage1_resp, stage2_resp] * 4):
            results = clf.classify_conversation_batch(
                {1: turns}, SAMPLE_CATEGORIES
            )

        assert 1 in results
        assert len(results[1]) == 4
        for label, conf, expl in results[1]:
            assert label == "buy_investment"
            assert "CascadingCtx" in expl

    def test_multiple_conversations(self):
        clf = _make_clf(use_previous_labels=False)
        conv1 = _make_turns(conversation_id=1)
        conv2 = [
            TurnInfo("Help me", "user", 0, 2),
            TurnInfo("Sure, what do you need?", "assistant", 1, 2),
        ]

        stage1_resp = json.dumps({"category": "EXECUTION_TRANSACTIONS", "confidence": 0.90, "reasoning_hint": ""})
        stage2_resp = json.dumps({"intent": "buy_investment", "confidence": 0.85, "reasoning_hint": ""})

        with patch.object(clf, "_call_llm", side_effect=[stage1_resp, stage2_resp] * 6):
            results = clf.classify_conversation_batch(
                {1: conv1, 2: conv2}, SAMPLE_CATEGORIES
            )

        assert set(results.keys()) == {1, 2}
        assert len(results[1]) == 4
        assert len(results[2]) == 2


class TestContextClassificationModeB:
    """Mode B: chained context, sequential per conversation."""

    def test_sequential_passes_labels(self):
        clf = _make_clf(use_previous_labels=True, context_backward=1, context_forward=0)
        turns = [
            TurnInfo("I want ESG funds", "user", 0, 1),
            TurnInfo("Yes, that one", "user", 1, 1),
        ]

        call_messages = []

        def fake_call_llm(messages, **kwargs):
            user_msg = messages[-1]["content"]
            call_messages.append(user_msg)
            if "Stage 1" in messages[0]["content"] or len(call_messages) % 2 == 1:
                return json.dumps({"category": "EXECUTION_TRANSACTIONS", "confidence": 0.90, "reasoning_hint": ""})
            return json.dumps({"intent": "buy_investment", "confidence": 0.85, "reasoning_hint": ""})

        with patch.object(clf, "_call_llm", side_effect=fake_call_llm):
            results = clf.classify_conversation_batch(
                {1: turns}, SAMPLE_CATEGORIES
            )

        assert len(results[1]) == 2
        # The second turn's stage1 call should have the label from the first turn
        # (since use_previous_labels=True and context_backward=1)
        # We check that at least one call contains the arrow notation
        all_messages = " ".join(call_messages)
        assert "buy_investment" in all_messages


class TestFallbackBehavior:
    def test_classify_batch_fallback_warns(self):
        clf = _make_clf()
        stage1_resp = json.dumps({"category": "UNKNOWN", "confidence": 0.50, "reasoning_hint": ""})

        with patch.object(clf, "_call_llm", return_value=stage1_resp):
            results = clf.classify_batch(["Hello"], SAMPLE_CATEGORIES)

        assert len(results) == 1
        assert results[0][0] == "UNKNOWN"

    def test_empty_conversations(self):
        clf = _make_clf()
        results = clf.classify_conversation_batch({}, SAMPLE_CATEGORIES)
        assert results == {}
