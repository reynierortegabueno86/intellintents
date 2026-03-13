import logging
import os
from typing import List, Tuple, Dict, Any, Optional

from app.classifiers.base import BaseClassifier

logger = logging.getLogger(__name__)


def _normalize(s: str) -> str:
    """Normalize a label for fuzzy matching."""
    return s.lower().strip().replace("_", " ").replace("-", " ").replace(".", " ")


def _build_label_map(
    model_labels: List[str],
    taxonomy_names: List[str],
    user_label_map: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """
    Build a mapping from model output labels → taxonomy category names.

    Priority:
    1. User-provided explicit mapping (model_label → taxonomy_label)
    2. Exact match (model label == taxonomy name)
    3. Normalized fuzzy match (case/underscore/hyphen insensitive)
    4. Unmapped labels pass through as-is
    """
    mapping: Dict[str, str] = {}
    tax_norm = {_normalize(t): t for t in taxonomy_names}

    for ml in model_labels:
        # 1. User override
        if user_label_map and ml in user_label_map:
            mapping[ml] = user_label_map[ml]
            continue

        # 2. Exact match
        if ml in taxonomy_names:
            mapping[ml] = ml
            continue

        # 3. Normalized match
        ml_norm = _normalize(ml)
        if ml_norm in tax_norm:
            mapping[ml] = tax_norm[ml_norm]
            continue

        # 4. Pass through
        mapping[ml] = ml

    return mapping


class TransformerClassifier(BaseClassifier):
    """
    Classifier based on HuggingFace Transformers.

    Supports three modes:

    - zero_shot_nli: Uses a zero-shot classification pipeline with an NLI model.
      The model receives taxonomy category names as candidate labels.
      No training required. Works with: facebook/bart-large-mnli,
      MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli, etc.

    - fine_tuned: Loads a fine-tuned text-classification model from HuggingFace Hub
      or a local directory. The model's id2label mapping is read automatically and
      mapped to taxonomy categories. Returns the top predicted label.

    - probabilities: Same as fine_tuned but returns ALL per-intent probabilities
      in the explanation, useful for analysis and debugging.

    Config:
        model_name (str): HuggingFace model name/ID or absolute local path.
                          Default: "facebook/bart-large-mnli"
        mode (str): "zero_shot_nli", "fine_tuned", or "probabilities".
                    Default: "zero_shot_nli"
        device (str): "cpu", "cuda", "mps", or "auto". Default: "cpu"
        batch_size (int): Inference batch size. Default: 16
        max_length (int): Max input tokens. Default: 512
        hypothesis_template (str): NLI hypothesis template. Default: "This text is about {}."
        multi_label (bool): Allow multi-label in zero-shot. Default: False
        label_map (dict): Explicit model_label → taxonomy_label mapping.
                          Overrides auto-detection. Default: None
        confidence_threshold (float): Min confidence to accept a prediction.
                                      Below this, label is "Unknown". Default: 0.0
    """

    def __init__(
        self,
        model_name: str = "facebook/bart-large-mnli",
        mode: str = "zero_shot_nli",
        device: str = "cpu",
        batch_size: int = 16,
        max_length: int = 512,
        hypothesis_template: str = "This text is about {}.",
        multi_label: bool = False,
        label_map: Optional[Dict[str, str]] = None,
        confidence_threshold: float = 0.0,
    ):
        self.model_name = model_name
        self.mode = mode
        self.device = device
        self.batch_size = batch_size
        self.max_length = max_length
        self.hypothesis_template = hypothesis_template
        self.multi_label = multi_label
        self.user_label_map = label_map
        self.confidence_threshold = confidence_threshold

        self._pipeline = None
        self._model_labels: Optional[List[str]] = None
        self._resolved_label_map: Optional[Dict[str, str]] = None

    # ── Model loading ─────────────────────────────────────────────

    def _resolve_device(self):
        if self.device == "auto":
            try:
                import torch
                if torch.cuda.is_available():
                    return 0
                if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                    return "mps"
            except ImportError:
                pass
            return -1
        elif self.device == "cuda":
            return 0
        elif self.device == "mps":
            return "mps"
        return -1

    def _is_local_model(self) -> bool:
        return os.path.isdir(self.model_name)

    def _load_pipeline(self):
        if self._pipeline is not None:
            return

        try:
            from transformers import pipeline as hf_pipeline, AutoConfig
        except ImportError:
            raise ImportError(
                "The 'transformers' and 'torch' packages are required for the "
                "Transformer classifier. Install with:\n"
                "  pip install transformers torch"
            )

        model_path = self.model_name
        is_local = self._is_local_model()

        if is_local:
            logger.info("Loading local model from: %s", model_path)
        else:
            logger.info("Loading model from HuggingFace Hub: %s", model_path)

        device = self._resolve_device()

        if self.mode == "zero_shot_nli":
            self._pipeline = hf_pipeline(
                "zero-shot-classification",
                model=model_path,
                device=device,
            )
        elif self.mode in ("fine_tuned", "probabilities"):
            self._pipeline = hf_pipeline(
                "text-classification",
                model=model_path,
                device=device,
                top_k=None,  # return scores for ALL labels
                truncation=True,
                max_length=self.max_length,
            )

            # Read model's id2label to discover what labels it was trained on
            try:
                config = AutoConfig.from_pretrained(model_path)
                if hasattr(config, "id2label") and config.id2label:
                    self._model_labels = list(config.id2label.values())
                    logger.info(
                        "Model id2label has %d labels: %s",
                        len(self._model_labels),
                        self._model_labels[:10],
                    )
            except Exception as e:
                logger.warning("Could not read model config for id2label: %s", e)
        else:
            raise ValueError(
                f"Unknown transformer mode: '{self.mode}'. "
                f"Use 'zero_shot_nli', 'fine_tuned', or 'probabilities'."
            )

    def _get_label_map(self, taxonomy_names: List[str]) -> Dict[str, str]:
        """Build or return cached label mapping."""
        if self._resolved_label_map is not None:
            return self._resolved_label_map

        if self._model_labels:
            self._resolved_label_map = _build_label_map(
                self._model_labels, taxonomy_names, self.user_label_map
            )
        elif self.user_label_map:
            self._resolved_label_map = dict(self.user_label_map)
        else:
            self._resolved_label_map = {}

        if self._resolved_label_map:
            mapped = {k: v for k, v in self._resolved_label_map.items() if k != v}
            if mapped:
                logger.info("Label mapping: %s", mapped)

        return self._resolved_label_map

    def _map_label(self, raw_label: str, taxonomy_names: List[str]) -> str:
        """Map a model output label to a taxonomy category name."""
        label_map = self._get_label_map(taxonomy_names)

        # Check explicit map first
        if raw_label in label_map:
            return label_map[raw_label]

        # Try direct match to taxonomy
        if raw_label in taxonomy_names:
            return raw_label

        # Try normalized match
        raw_norm = _normalize(raw_label)
        for cat in taxonomy_names:
            if _normalize(cat) == raw_norm:
                return cat

        return raw_label

    # ── Classification ────────────────────────────────────────────

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

        self._load_pipeline()

        cat_names = [c["name"] for c in taxonomy_categories]

        if self.mode == "zero_shot_nli":
            return self._classify_zero_shot(turns, cat_names)
        else:
            return self._classify_fine_tuned(turns, cat_names)

    def _classify_zero_shot(
        self, turns: List[str], cat_names: List[str]
    ) -> List[Tuple[str, float, str]]:
        pipe = self._pipeline
        results: List[Tuple[str, float, str]] = []

        for i in range(0, len(turns), self.batch_size):
            batch = [t[: self.max_length * 4] for t in turns[i : i + self.batch_size]]

            outputs = pipe(
                batch,
                candidate_labels=cat_names,
                hypothesis_template=self.hypothesis_template,
                multi_label=self.multi_label,
                batch_size=self.batch_size,
            )

            if isinstance(outputs, dict):
                outputs = [outputs]

            for out in outputs:
                label = out["labels"][0]
                score = round(float(out["scores"][0]), 4)

                if score < self.confidence_threshold:
                    label = "Unknown"

                top_n = min(5, len(out["labels"]))
                top_labels = [
                    f"{out['labels'][j]} ({out['scores'][j]:.3f})"
                    for j in range(top_n)
                ]
                explanation = (
                    f"Transformer zero-shot NLI ({self.model_name}). "
                    f"Scores: {', '.join(top_labels)}"
                )
                results.append((label, score, explanation))

        return results

    def _classify_fine_tuned(
        self, turns: List[str], cat_names: List[str]
    ) -> List[Tuple[str, float, str]]:
        pipe = self._pipeline
        results: List[Tuple[str, float, str]] = []
        return_all_probs = self.mode == "probabilities"

        for i in range(0, len(turns), self.batch_size):
            batch = [t[: self.max_length * 4] for t in turns[i : i + self.batch_size]]

            outputs = pipe(batch, batch_size=self.batch_size)

            # Normalize output shape: always list of list-of-dicts
            if not outputs:
                continue
            if isinstance(outputs[0], dict):
                # Single item returned a dict instead of list-of-dicts
                outputs = [outputs]

            for item_scores in outputs:
                if not isinstance(item_scores, list):
                    item_scores = [item_scores]

                # Sort by score descending
                item_scores = sorted(item_scores, key=lambda x: x["score"], reverse=True)

                # Map all labels
                mapped_scores = []
                for entry in item_scores:
                    raw_label = entry["label"]
                    mapped_label = self._map_label(raw_label, cat_names)
                    mapped_scores.append({
                        "raw_label": raw_label,
                        "label": mapped_label,
                        "score": round(float(entry["score"]), 4),
                    })

                best = mapped_scores[0]
                label = best["label"]
                score = best["score"]

                if score < self.confidence_threshold:
                    label = "Unknown"

                # Build explanation
                if return_all_probs:
                    # Show all probabilities
                    prob_lines = [
                        f"{s['label']}: {s['score']:.4f}"
                        + (f" (raw: {s['raw_label']})" if s['raw_label'] != s['label'] else "")
                        for s in mapped_scores
                    ]
                    explanation = (
                        f"Fine-tuned transformer ({self.model_name}), "
                        f"all probabilities:\n" + "\n".join(prob_lines)
                    )
                else:
                    top_n = min(5, len(mapped_scores))
                    top_labels = []
                    for s in mapped_scores[:top_n]:
                        entry_str = f"{s['label']} ({s['score']:.3f})"
                        if s['raw_label'] != s['label']:
                            entry_str += f" [raw: {s['raw_label']}]"
                        top_labels.append(entry_str)
                    explanation = (
                        f"Fine-tuned transformer ({self.model_name}). "
                        f"Top: {', '.join(top_labels)}"
                    )

                results.append((label, score, explanation))

        return results
