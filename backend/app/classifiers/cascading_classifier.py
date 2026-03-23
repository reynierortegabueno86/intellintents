"""
Cascading Intent Classifier — Two-Stage Pipeline

Stage 1: Classifies user message into one of 14 top-level categories (or UNKNOWN).
Stage 2: Classifies into a specific sub-intent within the matched category.

Each stage uses a specialized prompt scoped to its task, dramatically reducing
ambiguity and improving accuracy over flat classification across all 84 intents.
"""

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import List, Tuple, Dict, Any, Optional

from app.classifiers.base import ClassifierConfigError
from app.classifiers.llm_base import LLMBaseClassifier
from app.classifiers.cascading_prompts import (
    STAGE1_SYSTEM_PROMPT,
    STAGE2_PROMPTS,
    CATEGORY_INTENTS,
)

logger = logging.getLogger(__name__)


class CascadingClassifier(LLMBaseClassifier):
    """
    Two-stage cascading intent classifier.

    Stage 1 routes to a top-level category using a broad classifier.
    Stage 2 narrows down to a specific sub-intent using a category-scoped classifier.

    Config options (in addition to LLMBaseClassifier):
        stage1_threshold (float): Min confidence for Stage 1. Default: 0.60
        stage2_threshold (float): Min confidence for Stage 2. Default: 0.65
        stage1_model (str): Optional separate model for Stage 1 (e.g. faster/cheaper).
        stage2_model (str): Optional separate model for Stage 2 (e.g. more capable).
        stage1_prompt (str): Override Stage 1 system prompt.
        stage2_prompts (dict): Override Stage 2 prompts per category.
    """

    def __init__(
        self,
        provider: str = "openai",
        model: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 200,
        stage1_threshold: float = 0.60,
        stage2_threshold: float = 0.65,
        stage1_model: Optional[str] = None,
        stage2_model: Optional[str] = None,
        stage1_prompt: Optional[str] = None,
        stage2_prompts: Optional[Dict[str, str]] = None,
        max_concurrency: int = 5,
        **kwargs,
    ):
        super().__init__(
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            batch_size=1,
        )
        self.stage1_threshold = stage1_threshold
        self.stage2_threshold = stage2_threshold
        self.stage1_model = stage1_model or model
        self.stage2_model = stage2_model or model
        self.stage1_prompt = stage1_prompt or STAGE1_SYSTEM_PROMPT
        self.stage2_prompts = stage2_prompts or STAGE2_PROMPTS
        self.max_concurrency = max(1, max_concurrency)

    # ── LLM call helpers ───────────────────────────────────────────

    def _call_stage(self, system_prompt: str, user_message: str, model: str) -> str:
        """Make a single LLM call for a classification stage (thread-safe)."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        return self._call_llm(messages, model=model)

    def _parse_stage_response(self, raw: str) -> Dict[str, Any]:
        """Parse a JSON response from a classification stage."""
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [line for line in lines if not line.strip().startswith("```")]
            text = "\n".join(lines).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning("Failed to parse stage response: %s", text[:200])
            return {}

    # ── Stage 1: Top-Level Category ─────────────────────────────────

    def _classify_stage1(self, text: str) -> Dict[str, Any]:
        """Classify into top-level category."""
        try:
            raw = self._call_stage(self.stage1_prompt, text, self.stage1_model)
            result = self._parse_stage_response(raw)
            return {
                "category": result.get("category", "UNKNOWN"),
                "confidence": float(result.get("confidence", 0.0)),
                "reasoning_hint": result.get("reasoning_hint", ""),
            }
        except ClassifierConfigError:
            raise  # Missing API key / package — must fail immediately
        except Exception as e:
            logger.error("Stage 1 classification failed: %s", str(e))
            return {
                "category": "UNKNOWN",
                "confidence": 0.0,
                "reasoning_hint": f"Stage 1 error: {str(e)}",
            }

    # ── Stage 2: Sub-Intent ─────────────────────────────────────────

    def _classify_stage2(self, text: str, category: str) -> Dict[str, Any]:
        """Classify into sub-intent within the given category."""
        stage2_prompt = self.stage2_prompts.get(category)
        if not stage2_prompt:
            logger.warning("No Stage 2 prompt for category: %s", category)
            return {
                "intent": "UNKNOWN_SUBCATEGORY",
                "confidence": 0.0,
                "reasoning_hint": f"No sub-classifier for {category}",
            }

        try:
            raw = self._call_stage(stage2_prompt, text, self.stage2_model)
            result = self._parse_stage_response(raw)
            intent = result.get("intent", "UNKNOWN_SUBCATEGORY")
            confidence = float(result.get("confidence", 0.0))

            # Validate intent belongs to the category
            valid_intents = CATEGORY_INTENTS.get(category, [])
            if intent not in valid_intents and intent != "UNKNOWN_SUBCATEGORY":
                logger.warning(
                    "Intent '%s' not valid for category '%s'. Falling back.",
                    intent, category,
                )
                # Try fuzzy match
                intent_lower = intent.lower().replace("-", "_").replace(" ", "_")
                matched = False
                for valid in valid_intents:
                    if valid.lower() == intent_lower:
                        intent = valid
                        matched = True
                        break
                if not matched:
                    intent = "UNKNOWN_SUBCATEGORY"
                    confidence = min(confidence, 0.50)

            return {
                "intent": intent,
                "confidence": confidence,
                "reasoning_hint": result.get("reasoning_hint", ""),
            }
        except ClassifierConfigError:
            raise  # Missing API key / package — must fail immediately
        except Exception as e:
            logger.error("Stage 2 classification failed: %s", str(e))
            return {
                "intent": "UNKNOWN_SUBCATEGORY",
                "confidence": 0.0,
                "reasoning_hint": f"Stage 2 error: {str(e)}",
            }

    # ── Full Pipeline ───────────────────────────────────────────────

    def _classify_single(self, text: str) -> Tuple[str, float, str]:
        """Run the full two-stage pipeline on a single message."""
        snippet = text[:80].replace("\n", " ")
        logger.info("── Classifying: \"%s%s\"", snippet, "..." if len(text) > 80 else "")

        # Stage 1
        s1 = self._classify_stage1(text)
        category = s1["category"]
        s1_conf = s1["confidence"]
        logger.info("  Stage 1 → category=%s  conf=%.2f  hint=%s", category, s1_conf, s1["reasoning_hint"][:100])

        if category == "UNKNOWN" or s1_conf < self.stage1_threshold:
            logger.info("  Result: UNKNOWN (Stage 1 below threshold %.2f)", self.stage1_threshold)
            return (
                "UNKNOWN",
                round(s1_conf, 4),
                f"Cascading ({self.provider}/{self.stage1_model}). "
                f"Stage 1: UNKNOWN (conf={s1_conf:.2f}). {s1['reasoning_hint']}",
            )

        # Stage 2
        s2 = self._classify_stage2(text, category)
        intent = s2["intent"]
        s2_conf = s2["confidence"]
        logger.info("  Stage 2 → intent=%s  conf=%.2f  hint=%s", intent, s2_conf, s2["reasoning_hint"][:100])

        if intent == "UNKNOWN_SUBCATEGORY" or s2_conf < self.stage2_threshold:
            # Sub-intent unresolved — fall back to the category label itself
            logger.info("  Result: %s (fallback to category, Stage 2 below threshold %.2f)", category, self.stage2_threshold)
            return (
                category,
                round(s1_conf, 4),
                f"Cascading ({self.provider}/{self.stage2_model}). "
                f"Stage 1: {category} (conf={s1_conf:.2f}). "
                f"Stage 2: no sub-intent matched (conf={s2_conf:.2f}), "
                f"using category label. {s2['reasoning_hint']}",
            )

        # Fully classified
        combined_confidence = round(s1_conf * s2_conf, 4)
        logger.info("  Result: %s  combined_conf=%.4f", intent, combined_confidence)
        return (
            intent,
            combined_confidence,
            f"Cascading ({self.provider}/{self.stage1_model}|{self.stage2_model}). "
            f"Stage 1: {category} (conf={s1_conf:.2f}). "
            f"Stage 2: {intent} (conf={s2_conf:.2f}). {s2['reasoning_hint']}",
        )

    # ── BaseClassifier interface ────────────────────────────────────

    def classify_turn(
        self,
        text: str,
        taxonomy_categories: List[Dict[str, Any]],
    ) -> Tuple[str, float, str]:
        """Classify a single turn using the two-stage cascading pipeline.

        Note: taxonomy_categories from the DB are accepted for interface
        compatibility but the cascading classifier uses its own built-in
        prompt taxonomy. The taxonomy_categories param is not used.
        """
        return self._classify_single(text)

    def classify_batch(
        self,
        turns: List[str],
        taxonomy_categories: List[Dict[str, Any]],
    ) -> List[Tuple[str, float, str]]:
        """Classify a batch of turns concurrently through the pipeline.

        Uses a thread pool to run up to ``max_concurrency`` classifications
        in parallel, dramatically reducing total wall-clock time.
        For 300 turns at concurrency=5: ~2 min instead of ~15 min.
        """
        if len(turns) <= 1:
            return [self._classify_single(text) for text in turns]

        import threading

        total = len(turns)
        logger.info(
            "Classifying %d turns with concurrency=%d (2 API calls each)",
            total, self.max_concurrency,
        )

        results: list = [None] * total
        completed = [0]
        lock = threading.Lock()

        def _classify_indexed(idx: int, text: str):
            try:
                result = self._classify_single(text)
            except ClassifierConfigError:
                raise  # API key / package missing — abort everything
            except Exception as e:
                logger.error("Turn %d failed: %s", idx, str(e))
                result = ("UNKNOWN", 0.0, f"Classification error: {str(e)}")
            results[idx] = result
            with lock:
                completed[0] += 1
                done = completed[0]
            if done % 20 == 0 or done == total:
                logger.info("  Progress: %d/%d turns classified", done, total)

        with ThreadPoolExecutor(max_workers=self.max_concurrency) as pool:
            futures = [
                pool.submit(_classify_indexed, i, text)
                for i, text in enumerate(turns)
            ]
            for f in futures:
                try:
                    f.result(timeout=300)  # 5 min max per turn
                except ClassifierConfigError:
                    # Cancel remaining futures and re-raise
                    for remaining in futures:
                        remaining.cancel()
                    raise
                except Exception as e:
                    logger.error("Future failed: %s", str(e))

        # Fill any None results from incomplete futures
        for i, r in enumerate(results):
            if r is None:
                results[i] = ("UNKNOWN", 0.0, "Classification did not complete")

        # Early abort: if first N results all failed, raise instead of silent all-UNKNOWN
        check_count = min(10, total)
        unknown_count = sum(1 for r in results[:check_count] if r[0] == "UNKNOWN")
        if check_count > 0 and unknown_count == check_count:
            errors = [r[2] for r in results[:check_count] if r[0] == "UNKNOWN" and r[2]]
            last_err = errors[-1] if errors else "Unknown error"
            raise ValueError(
                f"All first {check_count} turns classified as UNKNOWN — aborting run. "
                f"Last error: {last_err}. "
                f"Check API key, model name, and network connectivity."
            )

        logger.info("Batch classification complete: %d turns", total)
        return results

    def _build_messages(
        self,
        texts: List[str],
        taxonomy_categories: List[Dict[str, Any]],
    ) -> List[Dict[str, str]]:
        """Not used directly — the cascading classifier manages its own messages."""
        raise NotImplementedError("CascadingClassifier uses _classify_single instead.")

    def _tag_explanation(self, explanation: str) -> str:
        return explanation
