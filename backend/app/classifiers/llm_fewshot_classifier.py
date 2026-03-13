import json
from typing import List, Dict, Any, Optional

from app.classifiers.llm_base import LLMBaseClassifier


class LLMFewShotClassifier(LLMBaseClassifier):
    """
    Few-shot intent classifier using an LLM API.

    Extends zero-shot by injecting example user/assistant exchanges before
    the actual classification request. Examples can be provided manually or
    are auto-generated from category names and descriptions.

    Config options (in addition to LLMBaseClassifier):
        num_examples (int): Number of synthetic examples per category. Default: 2
        examples (list): Custom few-shot examples as [{"text": ..., "label": ...}].
                         If not provided, synthetic examples are generated.
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
        num_examples: int = 2,
        examples: Optional[List[Dict[str, str]]] = None,
        batch_size: int = 1,
    ):
        super().__init__(
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
            batch_size=batch_size,
        )
        self.num_examples = num_examples
        self.custom_examples = examples

    def _build_few_shot_examples(
        self, taxonomy_categories: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        if self.custom_examples:
            return self.custom_examples[: self.num_examples * len(taxonomy_categories)]

        examples = []
        for cat in taxonomy_categories:
            name = cat["name"]
            desc = cat.get("description") or name
            examples.append({
                "text": f"I need help with {desc.lower().rstrip('.')}",
                "label": name,
            })
            if self.num_examples >= 2:
                examples.append({
                    "text": f"My question is about {name.lower().replace('_', ' ')}",
                    "label": name,
                })
        return examples

    def _build_messages(
        self,
        texts: List[str],
        taxonomy_categories: List[Dict[str, Any]],
    ) -> List[Dict[str, str]]:
        system_prompt = self._get_system_prompt(taxonomy_categories)
        examples = self._build_few_shot_examples(taxonomy_categories)

        messages = [{"role": "system", "content": system_prompt}]

        # Few-shot examples as user/assistant pairs
        for ex in examples:
            messages.append({"role": "user", "content": f"Classify: \"{ex['text']}\""})
            messages.append({
                "role": "assistant",
                "content": json.dumps({
                    "label": ex["label"],
                    "confidence": 0.95,
                    "explanation": f"The text relates to {ex['label']}."
                }),
            })

        # Actual text(s) to classify
        if len(texts) == 1:
            messages.append({"role": "user", "content": f"Classify: \"{texts[0]}\""})
        else:
            numbered = "\n".join(f"{i+1}. \"{t}\"" for i, t in enumerate(texts))
            messages.append({
                "role": "user",
                "content": (
                    f"Classify each of these {len(texts)} texts. "
                    f"Return a JSON array of objects:\n\n{numbered}"
                ),
            })

        return messages

    def _tag_explanation(self, explanation: str) -> str:
        return f"Few-shot LLM ({self.provider}/{self.model}). {explanation}"
