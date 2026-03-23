import json
import logging
import os
import threading
import time
from typing import List, Tuple, Dict, Any, Optional

from app.classifiers.base import BaseClassifier, ClassifierConfigError

logger = logging.getLogger(__name__)

# Retry configuration for transient API errors
_MAX_RETRIES = 3
_RETRY_DELAYS = [2, 5, 15]  # seconds


def _is_retryable(exc: Exception) -> bool:
    """Check if an exception is a transient error worth retrying."""
    exc_type = type(exc).__name__
    # OpenAI: RateLimitError, APITimeoutError, APIConnectionError, InternalServerError
    # Anthropic: RateLimitError, APITimeoutError, APIConnectionError, InternalServerError
    retryable_names = (
        "RateLimitError", "APITimeoutError", "APIConnectionError",
        "InternalServerError", "APIStatusError",
    )
    if exc_type in retryable_names:
        return True
    # Also retry on generic connection/timeout errors
    if isinstance(exc, (ConnectionError, TimeoutError)):
        return True
    # Retry on HTTP 429, 500, 502, 503, 529
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    if status and int(status) in (429, 500, 502, 503, 529):
        return True
    return False


class LLMBaseClassifier(BaseClassifier):
    """
    Base class for LLM-powered classifiers.

    Handles provider abstraction (OpenAI-compatible / Anthropic), API key
    resolution, message construction, response parsing, and batch processing.

    Subclasses override `_build_messages()` to define their prompting strategy
    (zero-shot, few-shot, chain-of-thought, etc.).
    """

    def __init__(
        self,
        provider: str = "openai",
        model: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 256,
        system_prompt: Optional[str] = None,
        batch_size: int = 1,
    ):
        self.provider = provider.lower()
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.custom_system_prompt = system_prompt
        self.batch_size = max(1, batch_size)
        self._client = None
        self._client_lock = threading.Lock()

    # ── API key ───────────────────────────────────────────────────

    def _get_api_key(self) -> str:
        if self.api_key:
            return self.api_key
        if self.provider == "anthropic":
            key = os.environ.get("ANTHROPIC_API_KEY", "")
        else:
            key = os.environ.get("OPENAI_API_KEY", "")
        if not key:
            env_var = "ANTHROPIC_API_KEY" if self.provider == "anthropic" else "OPENAI_API_KEY"
            raise ClassifierConfigError(
                f"No API key provided for {self.provider}. "
                f"Set it in config or via the {env_var} environment variable."
            )
        return key

    # ── System prompt ─────────────────────────────────────────────

    def _build_default_system_prompt(self, taxonomy_categories: List[Dict[str, Any]]) -> str:
        """Build the default system prompt. Subclasses may override."""
        categories_desc = "\n".join(
            f"- **{c['name']}**: {c.get('description') or 'No description'}"
            for c in taxonomy_categories
        )
        return (
            "You are an expert intent classifier for customer service conversations.\n\n"
            "Your task: classify the given text into exactly ONE of these intent categories:\n\n"
            f"{categories_desc}\n\n"
            "Rules:\n"
            "1. Return ONLY a valid JSON object with keys: \"label\", \"confidence\", \"explanation\"\n"
            "2. \"label\" must be EXACTLY one of the category names listed above\n"
            "3. \"confidence\" must be a float between 0.0 and 1.0\n"
            "4. \"explanation\" must be a brief reason for your choice\n"
            "5. Do not add any text outside the JSON object"
        )

    def _get_system_prompt(self, taxonomy_categories: List[Dict[str, Any]]) -> str:
        if self.custom_system_prompt:
            # Allow {categories} placeholder in custom prompts
            if "{categories}" in self.custom_system_prompt:
                categories_block = "\n".join(
                    f"- {c['name']}: {c.get('description') or 'No description'}"
                    for c in taxonomy_categories
                )
                return self.custom_system_prompt.replace("{categories}", categories_block)
            return self.custom_system_prompt
        return self._build_default_system_prompt(taxonomy_categories)

    # ── Message building (subclasses override) ────────────────────

    def _build_messages(
        self,
        texts: List[str],
        taxonomy_categories: List[Dict[str, Any]],
    ) -> List[Dict[str, str]]:
        """Build the message list for the LLM. Subclasses must override."""
        raise NotImplementedError

    # ── Provider calls ────────────────────────────────────────────

    def _call_openai(self, messages: List[Dict[str, str]], model: Optional[str] = None) -> str:
        try:
            import openai
        except ImportError:
            raise ClassifierConfigError(
                "The 'openai' package is required for LLM classifiers "
                "with OpenAI provider. Install with: pip install openai"
            )

        with self._client_lock:
            if self._client is None:
                kwargs = {"api_key": self._get_api_key()}
                if self.base_url:
                    kwargs["base_url"] = self.base_url
                self._client = openai.OpenAI(**kwargs)

        effective_model = model or self.model

        for attempt in range(_MAX_RETRIES + 1):
            try:
                kwargs = {
                    "model": effective_model,
                    "messages": messages,
                    "temperature": self.temperature,
                    "timeout": 60,
                }
                try:
                    kwargs["max_completion_tokens"] = self.max_tokens
                    response = self._client.chat.completions.create(**kwargs)
                except (openai.BadRequestError, TypeError):
                    kwargs.pop("max_completion_tokens", None)
                    kwargs["max_tokens"] = self.max_tokens
                    response = self._client.chat.completions.create(**kwargs)

                return response.choices[0].message.content.strip()
            except ClassifierConfigError:
                raise
            except Exception as e:
                if attempt < _MAX_RETRIES and _is_retryable(e):
                    delay = _RETRY_DELAYS[attempt]
                    logger.warning(
                        "OpenAI API retry %d/%d [%s/%s] after %ds: %s: %s",
                        attempt + 1, _MAX_RETRIES, self.provider, effective_model,
                        delay, type(e).__name__, str(e),
                    )
                    time.sleep(delay)
                    continue
                logger.error(
                    "OpenAI API call failed [%s/%s]: %s: %s",
                    self.provider, effective_model, type(e).__name__, str(e),
                )
                raise

    def _call_anthropic(self, messages: List[Dict[str, str]], model: Optional[str] = None) -> str:
        try:
            import anthropic
        except ImportError:
            raise ClassifierConfigError(
                "The 'anthropic' package is required for LLM classifiers "
                "with Anthropic provider. Install with: pip install anthropic"
            )

        with self._client_lock:
            if self._client is None:
                kwargs = {"api_key": self._get_api_key()}
                if self.base_url:
                    kwargs["base_url"] = self.base_url
                self._client = anthropic.Anthropic(**kwargs)

        system_content = ""
        chat_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_content = msg["content"]
            else:
                chat_messages.append(msg)

        for attempt in range(_MAX_RETRIES + 1):
            try:
                response = self._client.messages.create(
                    model=model or self.model,
                    system=system_content,
                    messages=chat_messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    timeout=60,
                )
                return response.content[0].text.strip()
            except ClassifierConfigError:
                raise
            except Exception as e:
                if attempt < _MAX_RETRIES and _is_retryable(e):
                    delay = _RETRY_DELAYS[attempt]
                    logger.warning(
                        "Anthropic API retry %d/%d [%s/%s] after %ds: %s: %s",
                        attempt + 1, _MAX_RETRIES, self.provider, model or self.model,
                        delay, type(e).__name__, str(e),
                    )
                    time.sleep(delay)
                    continue
                logger.error(
                    "Anthropic API call failed [%s/%s]: %s: %s",
                    self.provider, model or self.model, type(e).__name__, str(e),
                )
                raise

    def _call_llm(self, messages: List[Dict[str, str]], model: Optional[str] = None) -> str:
        from app.classifiers.llm_cache import get_cached, put_cached

        effective_model = model or self.model

        # Check cache first
        cached = get_cached(self.provider, effective_model, messages)
        if cached is not None:
            return cached

        # Call the API
        if self.provider == "anthropic":
            response = self._call_anthropic(messages, model=model)
        else:
            response = self._call_openai(messages, model=model)

        # Store in cache
        put_cached(self.provider, effective_model, messages, response)
        return response

    # ── Response parsing ──────────────────────────────────────────

    def _parse_response(
        self, raw: str, cat_names: List[str], count: int = 1
    ) -> List[Tuple[str, float, str]]:
        text = raw.strip()
        # Strip markdown code fences
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [line for line in lines if not line.strip().startswith("```")]
            text = "\n".join(lines).strip()

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM response as JSON: %s", text[:200])
            return [("Unknown", 0.0, f"Parse error: {text[:100]}")] * count

        if isinstance(parsed, dict):
            parsed = [parsed]

        results: List[Tuple[str, float, str]] = []
        for item in parsed[:count]:
            label = item.get("label", "Unknown")
            confidence = float(item.get("confidence", 0.5))
            explanation = item.get("explanation", "")

            # Fuzzy-match label to taxonomy
            if label not in cat_names:
                label_lower = label.lower().replace("_", " ").replace("-", " ")
                for cat in cat_names:
                    if cat.lower().replace("_", " ").replace("-", " ") == label_lower:
                        label = cat
                        break

            confidence = max(0.0, min(1.0, confidence))
            results.append((label, round(confidence, 4), explanation))

        while len(results) < count:
            results.append(("Unknown", 0.0, "No result from LLM"))

        return results

    # ── Classification interface ──────────────────────────────────

    def classify_turn(
        self,
        text: str,
        taxonomy_categories: List[Dict[str, Any]],
    ) -> Tuple[str, float, str]:
        return self.classify_batch([text], taxonomy_categories)[0]

    def classify_batch(
        self,
        turns: List[str],
        taxonomy_categories: List[Dict[str, Any]],
    ) -> List[Tuple[str, float, str]]:
        if not taxonomy_categories:
            return [("Unknown", 0.0, "No categories available")] * len(turns)

        cat_names = [c["name"] for c in taxonomy_categories]
        all_results: List[Tuple[str, float, str]] = []

        for i in range(0, len(turns), self.batch_size):
            batch = turns[i : i + self.batch_size]
            messages = self._build_messages(batch, taxonomy_categories)

            try:
                raw_response = self._call_llm(messages)
                batch_results = self._parse_response(raw_response, cat_names, len(batch))
                # Tag results with classifier info
                batch_results = [
                    (label, conf, self._tag_explanation(expl))
                    for label, conf, expl in batch_results
                ]
            except Exception as e:
                logger.error("LLM API call failed: %s", str(e))
                batch_results = [
                    ("Unknown", 0.0, f"API error: {str(e)}") for _ in batch
                ]

            all_results.extend(batch_results)

        return all_results

    def _tag_explanation(self, explanation: str) -> str:
        """Prefix explanation with classifier identity. Subclasses may override."""
        return f"LLM ({self.provider}/{self.model}). {explanation}"
