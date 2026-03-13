"""
Context-Aware Cascading Intent Classifier

Extends the two-stage CascadingClassifier with conversational context.
Surrounding turns (backward/forward) are injected into the prompt so the LLM
can resolve anaphora, follow-ups, and ambiguous messages.

Two modes:
  - Mode A (static):  text + speaker only → all turns in full parallel.
  - Mode B (chained): backward turns include already-classified labels →
                       sequential within each conversation, parallel across.
"""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import List, Tuple, Dict, Any, Optional

from app.classifiers.base import ClassifierConfigError, TurnInfo
from app.classifiers.cascading_classifier import CascadingClassifier

logger = logging.getLogger(__name__)


class ContextCascadingClassifier(CascadingClassifier):
    """
    Two-stage cascading classifier with conversational context window.

    Extra config (beyond CascadingClassifier):
        context_backward  (int):  Preceding turns to include.  Default 2.
        context_forward   (int):  Following turns to include.  Default 1.
        context_max_chars (int):  Max chars per context turn.   Default 500.
        use_previous_labels (bool): Include classified labels in backward
            context (Mode B — sequential per conversation). Default False.
    """

    def __init__(
        self,
        provider: str = "openai",
        model: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 250,
        stage1_threshold: float = 0.60,
        stage2_threshold: float = 0.65,
        stage1_model: Optional[str] = None,
        stage2_model: Optional[str] = None,
        stage1_prompt: Optional[str] = None,
        stage2_prompts: Optional[Dict[str, str]] = None,
        max_concurrency: int = 5,
        context_backward: int = 2,
        context_forward: int = 1,
        context_max_chars: int = 500,
        use_previous_labels: bool = False,
        **kwargs,
    ):
        super().__init__(
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            stage1_threshold=stage1_threshold,
            stage2_threshold=stage2_threshold,
            stage1_model=stage1_model,
            stage2_model=stage2_model,
            stage1_prompt=stage1_prompt,
            stage2_prompts=stage2_prompts,
            max_concurrency=max_concurrency,
        )
        self.context_backward = max(0, context_backward)
        self.context_forward = max(0, context_forward)
        self.context_max_chars = max(50, context_max_chars)
        self.use_previous_labels = use_previous_labels

    # ── Context formatting ────────────────────────────────────────

    def _truncate(self, text: str) -> str:
        if len(text) <= self.context_max_chars:
            return text
        return text[: self.context_max_chars - 3] + "..."

    def _format_context_message(
        self,
        target: TurnInfo,
        backward: List[TurnInfo],
        forward: List[TurnInfo],
        backward_labels: Optional[Dict[int, str]] = None,
    ) -> str:
        """Build the user message with conversation context wrapping the target."""
        lines: List[str] = []
        lines.append("=== CONVERSATION CONTEXT ===")

        if backward_labels:
            lines.append(
                "Classify ONLY the TARGET TURN. "
                "Context turns (with their classified intents) are for reference only."
            )
        else:
            lines.append(
                "Classify ONLY the TARGET TURN. "
                "Context turns are for reference only."
            )

        lines.append("")

        # Backward turns
        for turn in backward:
            offset = turn.turn_index - target.turn_index
            truncated = self._truncate(turn.text)
            if backward_labels and turn.turn_index in backward_labels:
                label = backward_labels[turn.turn_index]
                lines.append(
                    f"[Turn {offset:+d}] {turn.speaker} \u2192 {label}: {truncated}"
                )
            else:
                lines.append(f"[Turn {offset:+d}] {turn.speaker}: {truncated}")

        # Target turn
        lines.append("")
        lines.append(">>> TARGET TURN (classify this) <<<")
        lines.append(f"[Turn 0] {target.speaker}: {target.text}")
        lines.append("")

        # Forward turns
        for turn in forward:
            offset = turn.turn_index - target.turn_index
            truncated = self._truncate(turn.text)
            lines.append(f"[Turn {offset:+d}] {turn.speaker}: {truncated}")

        lines.append("=== END CONTEXT ===")
        return "\n".join(lines)

    # ── Single-turn classification with context ───────────────────

    def _classify_single_with_context(
        self,
        target: TurnInfo,
        backward: List[TurnInfo],
        forward: List[TurnInfo],
        backward_labels: Optional[Dict[int, str]] = None,
    ) -> Tuple[str, float, str]:
        """Run the two-stage cascade using a context-wrapped user message."""
        user_message = self._format_context_message(
            target, backward, forward, backward_labels
        )

        snippet = target.text[:80].replace("\n", " ")
        logger.info(
            '── Classifying (ctx): "%s%s"',
            snippet,
            "..." if len(target.text) > 80 else "",
        )

        # Stage 1
        s1 = self._classify_stage1(user_message)
        category = s1["category"]
        s1_conf = s1["confidence"]
        logger.info(
            "  Stage 1 → category=%s  conf=%.2f", category, s1_conf
        )

        if category == "UNKNOWN" or s1_conf < self.stage1_threshold:
            return (
                "UNKNOWN",
                round(s1_conf, 4),
                f"CascadingCtx ({self.provider}/{self.stage1_model}). "
                f"Stage 1: UNKNOWN (conf={s1_conf:.2f}). {s1['reasoning_hint']}",
            )

        # Stage 2
        s2 = self._classify_stage2(user_message, category)
        intent = s2["intent"]
        s2_conf = s2["confidence"]
        logger.info("  Stage 2 → intent=%s  conf=%.2f", intent, s2_conf)

        if intent == "UNKNOWN_SUBCATEGORY" or s2_conf < self.stage2_threshold:
            return (
                category,
                round(s1_conf, 4),
                f"CascadingCtx ({self.provider}/{self.stage2_model}). "
                f"Stage 1: {category} (conf={s1_conf:.2f}). "
                f"Stage 2: no sub-intent (conf={s2_conf:.2f}). {s2['reasoning_hint']}",
            )

        combined = round(s1_conf * s2_conf, 4)
        return (
            intent,
            combined,
            f"CascadingCtx ({self.provider}/{self.stage1_model}|{self.stage2_model}). "
            f"Stage 1: {category} (conf={s1_conf:.2f}). "
            f"Stage 2: {intent} (conf={s2_conf:.2f}). {s2['reasoning_hint']}",
        )

    # ── Sequential conversation handler (Mode B) ─────────────────

    def _classify_conversation_sequential(
        self,
        conv_turns: List[TurnInfo],
        taxonomy_categories: List[Dict[str, Any]],
    ) -> List[Tuple[str, float, str]]:
        """Classify turns sequentially, passing labels from prior turns."""
        results: List[Tuple[str, float, str]] = []
        labels: Dict[int, str] = {}

        for i, target in enumerate(conv_turns):
            backward = conv_turns[max(0, i - self.context_backward): i]
            forward = conv_turns[i + 1: i + 1 + self.context_forward]
            result = self._classify_single_with_context(
                target, backward, forward, labels
            )
            results.append(result)
            labels[target.turn_index] = result[0]

        return results

    # ── Conversation batch entry point ────────────────────────────

    def classify_conversation_batch(
        self,
        conversations: Dict[int, List[TurnInfo]],
        taxonomy_categories: List[Dict[str, Any]],
    ) -> Dict[int, List[Tuple[str, float, str]]]:
        """Classify all turns across multiple conversations with context.

        Args:
            conversations: {conversation_id: [TurnInfo, ...]} sorted by turn_index.
            taxonomy_categories: taxonomy categories (for interface compat; unused
                by cascading prompts).

        Returns:
            {conversation_id: [(label, confidence, explanation), ...]}
        """
        results: Dict[int, List[Tuple[str, float, str]]] = {}

        if self.use_previous_labels:
            # Mode B: sequential within conversation, parallel across
            return self._classify_mode_b(conversations, taxonomy_categories)
        else:
            # Mode A: full parallel across all turns
            return self._classify_mode_a(conversations, taxonomy_categories)

    def _classify_mode_a(
        self,
        conversations: Dict[int, List[TurnInfo]],
        taxonomy_categories: List[Dict[str, Any]],
    ) -> Dict[int, List[Tuple[str, float, str]]]:
        """Mode A: pre-build all context windows, classify everything in parallel."""
        # Build tasks: (conv_id, position_in_conv, target, backward, forward)
        tasks: List[tuple] = []
        for conv_id, conv_turns in conversations.items():
            for i, target in enumerate(conv_turns):
                backward = conv_turns[max(0, i - self.context_backward): i]
                forward = conv_turns[i + 1: i + 1 + self.context_forward]
                tasks.append((conv_id, i, target, backward, forward))

        total = len(tasks)
        if total == 0:
            return {}

        logger.info(
            "Context-cascading (Mode A): %d turns across %d conversations, concurrency=%d",
            total, len(conversations), self.max_concurrency,
        )

        # Pre-allocate result storage
        task_results: list = [None] * total
        completed = [0]
        lock = threading.Lock()

        def _run(idx: int, conv_id: int, pos: int, target, backward, forward):
            try:
                result = self._classify_single_with_context(
                    target, backward, forward, backward_labels=None
                )
            except ClassifierConfigError:
                raise
            except Exception as e:
                logger.error("Turn %d (conv %d) failed: %s", pos, conv_id, e)
                result = ("UNKNOWN", 0.0, f"Classification error: {e}")
            task_results[idx] = (conv_id, pos, result)
            with lock:
                completed[0] += 1
                if completed[0] % 20 == 0 or completed[0] == total:
                    logger.info("  Progress: %d/%d", completed[0], total)

        with ThreadPoolExecutor(max_workers=self.max_concurrency) as pool:
            futures = [
                pool.submit(_run, idx, conv_id, pos, target, bw, fw)
                for idx, (conv_id, pos, target, bw, fw) in enumerate(tasks)
            ]
            for f in futures:
                try:
                    f.result(timeout=300)
                except ClassifierConfigError:
                    for remaining in futures:
                        remaining.cancel()
                    raise
                except Exception as e:
                    logger.error("Future failed: %s", e)

        # Reconstruct per-conversation results in order
        results: Dict[int, List[Tuple[str, float, str]]] = {
            cid: [None] * len(turns) for cid, turns in conversations.items()
        }
        for item in task_results:
            if item is not None:
                conv_id, pos, result = item
                results[conv_id][pos] = result

        return results

    def _classify_mode_b(
        self,
        conversations: Dict[int, List[TurnInfo]],
        taxonomy_categories: List[Dict[str, Any]],
    ) -> Dict[int, List[Tuple[str, float, str]]]:
        """Mode B: sequential per conversation, parallel across conversations."""
        total_turns = sum(len(t) for t in conversations.values())
        logger.info(
            "Context-cascading (Mode B): %d turns across %d conversations, concurrency=%d",
            total_turns, len(conversations), self.max_concurrency,
        )

        results: Dict[int, List[Tuple[str, float, str]]] = {}
        lock = threading.Lock()
        completed_turns = [0]

        def _run_conversation(conv_id: int, conv_turns: List[TurnInfo]):
            try:
                conv_results = self._classify_conversation_sequential(
                    conv_turns, taxonomy_categories
                )
            except ClassifierConfigError:
                raise
            except Exception as e:
                logger.error("Conversation %d failed: %s", conv_id, e)
                conv_results = [
                    ("UNKNOWN", 0.0, f"Classification error: {e}")
                    for _ in conv_turns
                ]
            with lock:
                results[conv_id] = conv_results
                completed_turns[0] += len(conv_turns)
                logger.info(
                    "  Conversation %d done (%d turns). Total: %d/%d",
                    conv_id, len(conv_turns), completed_turns[0], total_turns,
                )

        with ThreadPoolExecutor(max_workers=self.max_concurrency) as pool:
            futures = [
                pool.submit(_run_conversation, conv_id, conv_turns)
                for conv_id, conv_turns in conversations.items()
            ]
            for f in futures:
                try:
                    f.result(timeout=600)
                except ClassifierConfigError:
                    for remaining in futures:
                        remaining.cancel()
                    raise
                except Exception as e:
                    logger.error("Future failed: %s", e)

        return results

    # ── Fallback: plain classify_batch logs warning ───────────────

    def classify_batch(
        self,
        turns: List[str],
        taxonomy_categories: List[Dict[str, Any]],
    ) -> List[Tuple[str, float, str]]:
        """Fallback: classify without context (same as parent CascadingClassifier).

        This is called when the service layer passes plain text instead of
        grouped conversations. Logs a warning since context is lost.
        """
        logger.warning(
            "ContextCascadingClassifier.classify_batch called with plain text — "
            "no conversation context available. Falling back to isolated classification."
        )
        return super().classify_batch(turns, taxonomy_categories)
