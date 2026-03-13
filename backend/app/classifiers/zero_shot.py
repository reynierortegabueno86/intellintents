from typing import List, Dict, Any, Optional

from app.classifiers.llm_base import LLMBaseClassifier

# Default zero-shot prompt template. {categories} is replaced with the taxonomy list.
DEFAULT_PROMPT = """You are an expert intent classifier for customer service conversations.

Classify the given text into exactly ONE of these intent categories:

{categories}

Analyze the text carefully. Consider:
- The primary action or need expressed
- The emotional tone and urgency
- Key phrases that signal specific intents
- The conversational context implied by the text

Rules:
1. Return ONLY a valid JSON object with keys: "label", "confidence", "explanation"
2. "label" must be EXACTLY one of the category names listed above
3. "confidence" must be a float between 0.0 and 1.0
4. "explanation" must be a brief reason for your choice (1-2 sentences)
5. Do not add any text outside the JSON object"""


class ZeroShotClassifier(LLMBaseClassifier):
    """
    Zero-shot intent classifier using an LLM API.

    Sends only the taxonomy categories and the text to classify — no examples.
    The LLM must infer the correct intent purely from category names/descriptions
    and its pre-trained knowledge.

    Config options:
        provider (str): "openai" or "anthropic". Default: "openai"
        model (str): Model identifier. Default: "gpt-4o-mini"
        api_key (str): API key. Falls back to OPENAI_API_KEY or ANTHROPIC_API_KEY env vars.
        base_url (str): Custom API base URL (for Ollama, vLLM, etc.). Default: None
        temperature (float): Sampling temperature. Default: 0.0
        max_tokens (int): Max response tokens. Default: 256
        system_prompt (str): Custom system prompt. Use {categories} placeholder for the
                             taxonomy list. Default: built-in analytical prompt.
        batch_size (int): Texts per API call. Default: 1
    """

    def __init__(
        self,
        provider: str = "openai",
        model: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 256,
        system_prompt: Optional[str] = None,
        batch_size: int = 1,
    ):
        super().__init__(
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=system_prompt or DEFAULT_PROMPT,
            batch_size=batch_size,
        )

    def _build_messages(
        self,
        texts: List[str],
        taxonomy_categories: List[Dict[str, Any]],
    ) -> List[Dict[str, str]]:
        system_prompt = self._get_system_prompt(taxonomy_categories)
        messages = [{"role": "system", "content": system_prompt}]

        if len(texts) == 1:
            messages.append({
                "role": "user",
                "content": f"Classify this text:\n\n\"{texts[0]}\""
            })
        else:
            numbered = "\n".join(f"{i+1}. \"{t}\"" for i, t in enumerate(texts))
            messages.append({
                "role": "user",
                "content": (
                    f"Classify each of these {len(texts)} texts. "
                    f"Return a JSON array of {len(texts)} objects:\n\n{numbered}"
                ),
            })

        return messages

    def _tag_explanation(self, explanation: str) -> str:
        return f"Zero-shot LLM ({self.provider}/{self.model}). {explanation}"
