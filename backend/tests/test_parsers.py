"""Tests for dataset_service parsers: CSV, JSON, JSONL, validation."""
import json
import pytest

from app.services.dataset_service import (
    parse_csv,
    parse_json,
    parse_jsonl,
    validate_schema,
    _extract_turn_text,
    _normalize_turn,
)


# ---------------------------------------------------------------------------
# _extract_turn_text
# ---------------------------------------------------------------------------

class TestExtractTurnText:
    def test_text_field(self):
        assert _extract_turn_text({"text": "hello"}) == "hello"

    def test_message_field(self):
        assert _extract_turn_text({"message": "hi there"}) == "hi there"

    def test_content_text_field(self):
        assert _extract_turn_text({"content_text": "content here"}) == "content here"

    def test_content_blocks_fallback(self):
        turn = {
            "content_text": None,
            "content_blocks": [
                {"type": "html", "text": "Block one", "raw": None},
                {"type": "html", "text": "Block two", "raw": None},
            ],
        }
        assert _extract_turn_text(turn) == "Block one\nBlock two"

    def test_content_blocks_raw_fallback(self):
        turn = {
            "content_blocks": [{"type": "html", "text": None, "raw": "raw content"}],
        }
        assert _extract_turn_text(turn) == "raw content"

    def test_content_blocks_string_items(self):
        turn = {"content_blocks": ["just a string"]}
        assert _extract_turn_text(turn) == "just a string"

    def test_content_plain_string(self):
        turn = {"content": "plain content"}
        assert _extract_turn_text(turn) == "plain content"

    def test_empty_returns_empty(self):
        assert _extract_turn_text({}) == ""

    def test_strips_whitespace(self):
        assert _extract_turn_text({"text": "  padded  "}) == "padded"

    def test_text_priority_over_content_text(self):
        turn = {"text": "primary", "content_text": "secondary"}
        assert _extract_turn_text(turn) == "primary"

    def test_content_text_over_blocks(self):
        turn = {
            "content_text": "ct",
            "content_blocks": [{"type": "html", "text": "block"}],
        }
        assert _extract_turn_text(turn) == "ct"


# ---------------------------------------------------------------------------
# _normalize_turn
# ---------------------------------------------------------------------------

class TestNormalizeTurn:
    def test_basic_mapping(self):
        raw = {"role": "user", "content_text": "Hello", "created_at": "2025-01-01T00:00:00Z"}
        result = _normalize_turn(raw, 0)
        assert result["speaker"] == "user"
        assert result["text"] == "Hello"
        assert result["timestamp"] == "2025-01-01T00:00:00Z"
        assert result["turn_index"] == 0

    def test_speaker_over_role(self):
        raw = {"speaker": "agent", "role": "assistant", "text": "Hi"}
        assert _normalize_turn(raw, 0)["speaker"] == "agent"

    def test_turn_index_preserved(self):
        raw = {"turn_index": 5, "text": "x", "speaker": "u"}
        assert _normalize_turn(raw, 0)["turn_index"] == 5

    def test_index_fallback(self):
        raw = {"text": "x", "speaker": "u"}
        assert _normalize_turn(raw, 3)["turn_index"] == 3

    def test_ground_truth_from_intent(self):
        raw = {"text": "x", "speaker": "u", "intent": "Billing"}
        assert _normalize_turn(raw, 0)["ground_truth_intent"] == "Billing"


# ---------------------------------------------------------------------------
# parse_csv
# ---------------------------------------------------------------------------

class TestParseCSV:
    def test_basic_csv(self):
        csv_content = (
            "conversation_id,turn_index,speaker,text\n"
            "c1,0,customer,Hello\n"
            "c1,1,agent,Hi there\n"
            "c2,0,customer,Help me\n"
        )
        result = parse_csv(csv_content)
        assert len(result) == 2
        assert result[0]["external_id"] == "c1"
        assert len(result[0]["turns"]) == 2
        assert result[1]["turns"][0]["text"] == "Help me"

    def test_csv_with_role_alias(self):
        csv_content = "conversation_id,turn_index,role,message\nc1,0,user,Hello\n"
        result = parse_csv(csv_content)
        assert result[0]["turns"][0]["speaker"] == "user"
        assert result[0]["turns"][0]["text"] == "Hello"

    def test_csv_auto_turn_index(self):
        csv_content = "conversation_id,speaker,text\nc1,user,First\nc1,agent,Second\n"
        result = parse_csv(csv_content)
        assert result[0]["turns"][0]["turn_index"] == 0
        assert result[0]["turns"][1]["turn_index"] == 1

    def test_csv_default_conversation_id(self):
        csv_content = "speaker,text\nuser,Hello\n"
        result = parse_csv(csv_content)
        assert result[0]["external_id"] == "default"


# ---------------------------------------------------------------------------
# parse_json
# ---------------------------------------------------------------------------

class TestParseJSON:
    def test_format1_conversations_with_turns(self):
        data = [
            {
                "conversation_id": "c1",
                "turns": [
                    {"turn_index": 0, "speaker": "user", "text": "Hi"},
                    {"turn_index": 1, "speaker": "agent", "text": "Hello"},
                ],
            }
        ]
        result = parse_json(json.dumps(data))
        assert len(result) == 1
        assert result[0]["external_id"] == "c1"
        assert len(result[0]["turns"]) == 2

    def test_format2_flat_turns(self):
        data = [
            {"conversation_id": "c1", "turn_index": 0, "speaker": "user", "text": "Hi"},
            {"conversation_id": "c1", "turn_index": 1, "speaker": "agent", "text": "Hello"},
            {"conversation_id": "c2", "turn_index": 0, "speaker": "user", "text": "Help"},
        ]
        result = parse_json(json.dumps(data))
        assert len(result) == 2

    def test_json_with_role_alias(self):
        data = [
            {
                "conversation_id": "c1",
                "turns": [{"role": "user", "content_text": "Hi"}],
            }
        ]
        result = parse_json(json.dumps(data))
        assert result[0]["turns"][0]["speaker"] == "user"
        assert result[0]["turns"][0]["text"] == "Hi"

    def test_invalid_json_format(self):
        with pytest.raises(ValueError, match="Unsupported JSON format"):
            parse_json(json.dumps([{"random": "data"}]))

    def test_empty_list(self):
        with pytest.raises(ValueError):
            parse_json("[]")


# ---------------------------------------------------------------------------
# parse_jsonl
# ---------------------------------------------------------------------------

class TestParseJSONL:
    def _make_conv(self, conv_id="conv-1", turns=None):
        if turns is None:
            turns = [
                {"turn_index": 0, "role": "user", "content_text": "Hello"},
                {"turn_index": 1, "role": "assistant", "content_text": "Hi there!"},
            ]
        return {"conversation_id": conv_id, "turns": turns}

    def test_single_conversation(self):
        content = json.dumps(self._make_conv())
        result = parse_jsonl(content)
        assert len(result) == 1
        assert result[0]["external_id"] == "conv-1"
        assert len(result[0]["turns"]) == 2
        assert result[0]["turns"][0]["speaker"] == "user"
        assert result[0]["turns"][0]["text"] == "Hello"

    def test_multiple_lines(self):
        lines = [
            json.dumps(self._make_conv("c1")),
            json.dumps(self._make_conv("c2")),
            json.dumps(self._make_conv("c3")),
        ]
        result = parse_jsonl("\n".join(lines))
        assert len(result) == 3
        assert [c["external_id"] for c in result] == ["c1", "c2", "c3"]

    def test_blank_lines_skipped(self):
        content = "\n" + json.dumps(self._make_conv()) + "\n\n"
        result = parse_jsonl(content)
        assert len(result) == 1

    def test_content_blocks_fallback(self):
        conv = self._make_conv(turns=[
            {
                "turn_index": 0,
                "role": "user",
                "content_text": None,
                "content_blocks": [
                    {"type": "html", "text": "Question about billing", "raw": None}
                ],
            }
        ])
        result = parse_jsonl(json.dumps(conv))
        assert result[0]["turns"][0]["text"] == "Question about billing"

    def test_created_at_mapped_to_timestamp(self):
        conv = self._make_conv(turns=[
            {"role": "user", "content_text": "Hi", "created_at": "2025-06-15T10:30:00Z"}
        ])
        result = parse_jsonl(json.dumps(conv))
        assert result[0]["turns"][0]["timestamp"] == "2025-06-15T10:30:00Z"

    def test_thread_id_preserved(self):
        conv = self._make_conv(turns=[
            {"role": "user", "content_text": "Hi", "thread_id": "thread-abc"}
        ])
        result = parse_jsonl(json.dumps(conv))
        assert result[0]["turns"][0]["thread_id"] == "thread-abc"

    def test_invalid_json_line(self):
        content = '{"conversation_id":"c1","turns":[]}\nnot json\n'
        with pytest.raises(ValueError, match="Invalid JSON on line 2"):
            parse_jsonl(content)

    def test_non_object_line(self):
        content = json.dumps([1, 2, 3])
        with pytest.raises(ValueError, match="expected a JSON object"):
            parse_jsonl(content)

    def test_turns_not_array(self):
        content = json.dumps({"conversation_id": "c1", "turns": "not-a-list"})
        with pytest.raises(ValueError, match="'turns' must be an array"):
            parse_jsonl(content)

    def test_missing_conversation_id_uses_line_number(self):
        conv = {"turns": [{"role": "user", "content_text": "Hi"}]}
        result = parse_jsonl(json.dumps(conv))
        assert result[0]["external_id"] == "1"

    def test_full_platform_format(self):
        """Test with the full platform export format."""
        conv = {
            "conversation_id": "abc-123",
            "thread_id": "thread-1",
            "title": "Billing question",
            "user_id": "user-42",
            "user_email": None,
            "user_language": "en",
            "organization_id": "org-1",
            "status": "resolved",
            "conv_type": "chat",
            "is_demo": False,
            "llm_provider": "openai",
            "model": "gpt-4o",
            "total_tokens": 1801,
            "total_price": 0.05,
            "num_turns": 2,
            "turns": [
                {
                    "turn_index": 0,
                    "role": "user",
                    "content_text": "Why was I charged twice?",
                    "content_types": ["html"],
                    "content_blocks": [{"type": "html", "text": "Why was I charged twice?", "raw": None}],
                    "llm_provider": None,
                    "model": None,
                    "feedback_valuation": None,
                    "created_at": "2025-06-15T10:30:00Z",
                },
                {
                    "turn_index": 1,
                    "role": "assistant",
                    "content_text": "Let me check your billing history.",
                    "content_types": ["html"],
                    "content_blocks": [{"type": "html", "text": "Let me check your billing history.", "raw": None}],
                    "citations": [],
                    "created_at": "2025-06-15T10:30:05Z",
                },
            ],
            "created_at": "2025-06-15T10:30:00Z",
            "updated_at": "2025-06-15T10:31:00Z",
        }
        result = parse_jsonl(json.dumps(conv))
        assert len(result) == 1
        c = result[0]
        assert c["external_id"] == "abc-123"
        assert len(c["turns"]) == 2
        assert c["turns"][0]["speaker"] == "user"
        assert c["turns"][0]["text"] == "Why was I charged twice?"
        assert c["turns"][1]["speaker"] == "assistant"
        assert c["turns"][1]["timestamp"] == "2025-06-15T10:30:05Z"


# ---------------------------------------------------------------------------
# validate_schema
# ---------------------------------------------------------------------------

class TestValidateSchema:
    def test_valid(self):
        data = [{"external_id": "c1", "turns": [{"text": "Hi", "speaker": "user", "turn_index": 0}]}]
        valid, msg = validate_schema(data)
        assert valid is True

    def test_empty(self):
        valid, msg = validate_schema([])
        assert valid is False
        assert "No conversations" in msg

    def test_no_turns_key(self):
        valid, msg = validate_schema([{"external_id": "c1"}])
        assert valid is False
        assert "missing 'turns'" in msg

    def test_empty_turns(self):
        valid, msg = validate_schema([{"turns": []}])
        assert valid is False
        assert "has no turns" in msg

    def test_empty_text(self):
        valid, msg = validate_schema([{"turns": [{"text": "", "speaker": "user"}]}])
        assert valid is False
        assert "empty text" in msg

    def test_no_speaker(self):
        valid, msg = validate_schema([{"turns": [{"text": "Hi", "speaker": ""}]}])
        assert valid is False
        assert "no speaker" in msg
