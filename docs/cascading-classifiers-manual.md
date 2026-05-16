# Cascading Classifiers — User Manual

## Overview

The Cascading Classifiers are two-stage LLM-powered intent classification pipelines designed for high-accuracy intent detection in conversational data. Instead of classifying a message directly into one of 84+ sub-intents (which leads to ambiguity and errors), the pipeline breaks the task into two focused stages:

- **Stage 1** — Routes the message to one of 14 top-level categories
- **Stage 2** — Classifies the specific sub-intent within the matched category

This dramatically reduces the search space at each stage, improving accuracy and consistency.

---

## Available Classifiers

IntellIntents provides two cascading classifier variants:

| Classifier | ID | Description |
| --- | --- | --- |
| **Cascading (Two-Stage LLM)** | `cascading` | Classifies each turn independently using the two-stage pipeline. No conversation context. |
| **Cascading + Context (Two-Stage LLM)** | `cascading_context` | Same two-stage pipeline, but injects surrounding conversation turns into the prompt for context-aware classification. |

---

## How the Two-Stage Pipeline Works

### Stage 1 — Category Routing

The LLM receives the user message and a system prompt listing all 14 top-level categories. It returns:

- `category` — The matched top-level category name
- `confidence` — A confidence score between 0.0 and 1.0
- `reasoning_hint` — Brief explanation of the classification decision

If the confidence is **below the Stage 1 threshold**, the turn is labeled `UNKNOWN` and Stage 2 is skipped entirely.

### Stage 2 — Sub-Intent Classification

The LLM receives the same user message but with a **category-specific prompt** that only lists the sub-intents for the matched category. It returns:

- `intent` — The specific sub-intent label
- `confidence` — A confidence score between 0.0 and 1.0
- `reasoning_hint` — Brief explanation

If the confidence is **below the Stage 2 threshold**, the turn falls back to the **category name** as its label (e.g., `ONBOARDING_KYC` instead of `open_account`).

### Final Confidence Calculation

The combined confidence is the product of both stages:

```
final_confidence = stage1_confidence x stage2_confidence
```

**Example**: Stage 1 returns 0.92, Stage 2 returns 0.87 → Final confidence = 0.92 x 0.87 = **0.8004**

---

## Top-Level Categories and Sub-Intents

The classifier recognizes the following taxonomy:

### ONBOARDING_KYC

Account opening and identity verification processes.

- `open_account`
- `verify_identity`
- `upload_document`
- `check_eligibility`
- `age_limit`
- `link_bank_account`

### INVESTOR_PROFILING

Gathering information about the investor's profile and preferences.

- `state_risk_tolerance`
- `state_investment_goal`
- `state_investment_horizon`
- `state_financial_situation`
- `state_experience_level`
- `state_esg_preference`
- `update_risk_profile`
- `refuse_to_answer_profiling`

### PRODUCT_DISCOVERY

Exploring and comparing investment products.

- `explore_product_types`
- `compare_products`
- `ask_product_features`
- `ask_product_risk`
- `ask_product_performance`
- `ask_product_eligibility`
- `filter_by_criteria`
- `ask_esg_classification`

### RECOMMENDATION_ADVISORY

Requesting, evaluating, and acting on investment recommendations.

- `request_recommendation`
- `request_portfolio_suggestion`
- `ask_why_recommended`
- `request_alternative`
- `accept_recommendation`
- `reject_recommendation`
- `request_human_advisor`
- `request_rebalance_advice`

### EXECUTION_TRANSACTIONS

Buying, selling, and managing orders and fund movements.

- `buy_investment`
- `sell_investment`
- `set_recurring_investment`
- `cancel_order`
- `check_order_status`
- `transfer_funds`
- `withdraw_funds`

### PORTFOLIO_MONITORING

Tracking portfolio value, performance, and alerts.

- `check_portfolio_value`
- `check_holdings`
- `check_performance`
- `check_gains_losses`
- `set_alert`
- `request_statement`
- `ask_dividend_info`

### FINANCIAL_EDUCATION

Explaining financial concepts, instruments, and strategies.

- `explain_concept`
- `explain_instrument`
- `explain_risk`
- `explain_strategy`
- `explain_market_event`
- `explain_regulation`
- `explain_tax_implications`

### ACCOUNT_SERVICE_MANAGEMENT

Account maintenance, support, and service inquiries.

- `change_personal_details`
- `change_password`
- `ask_about_fees`
- `file_complaint`
- `escalate_to_human`
- `terminate_account`
- `ask_service_hours`
- `ask_security`

### REGULATORY_COMPLIANCE

Regulatory disclosures, data rights, and compliance inquiries.

- `request_risk_disclaimer`
- `request_data_access`
- `request_data_deletion`
- `confirm_suitability`
- `ask_about_investor_protection`
- `ask_about_conflicts_of_interest`
- `report_suspicious_activity`

### GREETING

Conversational greetings and farewells.

- `opening`
- `closing`
- `phatic`

### SMALL_TALK

Non-task messages about the agent, user feelings, or app feedback.

- `agent_identity`
- `agent_personality`
- `user_feelings`
- `chitchat`
- `app_feedback`

### OUT_OF_SCOPE

Messages outside the system's supported domain.

- `non_financial_topic`
- `unsupported_financial_domain`
- `technical_capability_limit`
- `legal_or_policy_restricted`
- `noise_unintelligible`

### HARMFUL_UNETHICAL_COMMUNICATION

Hateful, toxic, or discriminatory messages.

- `harm_hate_lgbtiqphobia`
- `harm_hate_gender_based`
- `harm_hate_stereotypes_prejudice`
- `harm_toxic_insults_general`

### UNKNOWN

Messages that cannot be classified.

- `none`

---

## Parameters Reference

### Common Parameters (Both Classifiers)

#### provider

| | |
| --- | --- |
| **Type** | Select |
| **Options** | `openai`, `anthropic` |
| **Default** | `openai` |

The LLM provider to use. The `openai` option is compatible with any OpenAI-compatible API, including Ollama, vLLM, LiteLLM, and similar services. Use `anthropic` for Claude models.

> **Note**: Both stages always use the same provider. You cannot mix providers across stages within a single run.

---

#### model

| | |
| --- | --- |
| **Type** | Text |
| **Default** | `gpt-4o-mini` |

The default LLM model used for both Stage 1 and Stage 2. This value is overridden if `stage1_model` or `stage2_model` are specified.

**Common values for OpenAI provider:**

- `gpt-4o-mini` — Fast and cost-effective. Good baseline for both stages.
- `gpt-4o` — More capable. Recommended for Stage 2 when accuracy is critical.
- `gpt-4-turbo` — High capability, higher cost.

**Common values for Anthropic provider:**

- `claude-haiku-4-5-20251001` — Fastest, cheapest Claude model.
- `claude-sonnet-4-6` — Balanced performance and cost.
- `claude-opus-4-6` — Most capable Claude model.

**For self-hosted models** (with `base_url`):

- Any model name supported by your endpoint (e.g., `llama3`, `mistral`, `qwen2.5`).

---

#### api_key

| | |
| --- | --- |
| **Type** | Password |
| **Default** | *(empty)* |
| **Required** | No |

The API key for authenticating with the LLM provider. If left empty, the system automatically reads:

- `OPENAI_API_KEY` environment variable (for `openai` provider)
- `ANTHROPIC_API_KEY` environment variable (for `anthropic` provider)

> **Recommendation**: Use environment variables on the server instead of entering keys in the UI. This avoids exposing keys in experiment configurations.

---

#### base_url

| | |
| --- | --- |
| **Type** | Text |
| **Default** | *(empty)* |
| **Required** | No |

Custom API base URL. Leave empty to use the provider's default endpoint. Set this when using self-hosted or alternative API-compatible services.

**Examples:**

- Ollama: `http://localhost:11434/v1`
- vLLM: `http://localhost:8000/v1`
- Azure OpenAI: `https://your-resource.openai.azure.com/`

---

#### temperature

| | |
| --- | --- |
| **Type** | Range (slider) |
| **Min** | 0.0 |
| **Max** | 1.0 |
| **Step** | 0.05 |
| **Default** | 0.0 |

Controls randomness in the LLM output.

- **0.0** = Deterministic. The model always picks the most likely token. **Recommended for classification**.
- **0.1 - 0.3** = Slight variability. May help with edge cases but reduces reproducibility.
- **> 0.5** = Not recommended for classification tasks.

---

#### stage1_threshold

| | |
| --- | --- |
| **Type** | Range (slider) |
| **Min** | 0.0 |
| **Max** | 1.0 |
| **Step** | 0.05 |
| **Default** | 0.60 |

The minimum confidence score required from Stage 1 (category classification) to proceed to Stage 2.

**Behavior:**

- If Stage 1 confidence **>= threshold** → proceeds to Stage 2
- If Stage 1 confidence **< threshold** → turn is labeled `UNKNOWN`, Stage 2 is skipped

**Tuning guidance:**

- **Lower (0.40 - 0.55)**: More turns reach Stage 2. Fewer UNKNOWNs, but more potential misrouting.
- **Default (0.60)**: Balanced. Good starting point for most datasets.
- **Higher (0.70 - 0.85)**: Stricter. Only high-confidence categories proceed. More UNKNOWNs.

---

#### stage2_threshold

| | |
| --- | --- |
| **Type** | Range (slider) |
| **Min** | 0.0 |
| **Max** | 1.0 |
| **Step** | 0.05 |
| **Default** | 0.65 |

The minimum confidence score required from Stage 2 (sub-intent classification) to assign a specific sub-intent.

**Behavior:**

- If Stage 2 confidence **>= threshold** → turn is labeled with the specific sub-intent (e.g., `open_account`)
- If Stage 2 confidence **< threshold** → turn falls back to the **category name** (e.g., `ONBOARDING_KYC`)

**Tuning guidance:**

- **Lower (0.45 - 0.60)**: More specific labels assigned. May include lower-quality classifications.
- **Default (0.65)**: Balanced.
- **Higher (0.75 - 0.90)**: Only very confident sub-intents are assigned. More turns fall back to category labels.

---

#### stage1_model

| | |
| --- | --- |
| **Type** | Text |
| **Default** | *(empty — uses `model`)* |
| **Required** | No |

Override the model used specifically for Stage 1 (category routing). Leave empty to use the default `model` value.

**Use case**: Stage 1 is a simpler task (14 categories), so you can use a **faster/cheaper model** here to save cost and latency.

**Example**: Set `model` to `gpt-4o`, `stage1_model` to `gpt-4o-mini` → cheap routing, powerful sub-intent classification.

---

#### stage2_model

| | |
| --- | --- |
| **Type** | Text |
| **Default** | *(empty — uses `model`)* |
| **Required** | No |

Override the model used specifically for Stage 2 (sub-intent classification). Leave empty to use the default `model` value.

**Use case**: Stage 2 requires finer distinctions within a category, so you can use a **more capable model** here for better accuracy.

**Example**: Set `model` to `gpt-4o-mini`, `stage2_model` to `gpt-4o` → cheap routing, powerful sub-intent classification.

> **Important**: `stage1_model` and `stage2_model` are completely independent. You can set one, both, or neither. They are not mutually exclusive.

---

#### max_tokens

| | |
| --- | --- |
| **Type** | Number |
| **Default** | 200 (cascading) / 250 (cascading_context) |

Maximum number of tokens the LLM can generate per response. This applies to **each stage independently**.

The classifier expects a short JSON response (category/intent + confidence + reasoning hint), so 200 tokens is sufficient for most cases. The context variant uses 250 by default because the reasoning may reference context turns.

> **When to increase**: Only if you observe truncated JSON responses in the logs.

---

#### max_concurrency

| | |
| --- | --- |
| **Type** | Number |
| **Default** | 5 |

Number of classifications running in parallel.

- **Cascading**: Number of turns classified simultaneously.
- **Cascading + Context (Mode A)**: Number of turns classified simultaneously.
- **Cascading + Context (Mode B)**: Number of conversations classified simultaneously (turns within each conversation are sequential).

**Tuning guidance:**

| Value | Trade-off |
| --- | --- |
| 1-2 | Very slow. Safe for strict rate limits. |
| 3-5 | Good balance of speed and stability. **Recommended**. |
| 6-10 | Fast. Works well with high-tier API plans. |
| 10+ | Risk of rate limiting (HTTP 429 errors). Only for enterprise API tiers. |

> **Note**: Each turn requires **2 API calls** (Stage 1 + Stage 2), so `max_concurrency=5` means up to 10 simultaneous API calls.

---

### Context-Specific Parameters (Cascading + Context Only)

These parameters are only available in the **Cascading + Context** classifier.

#### context_backward

| | |
| --- | --- |
| **Type** | Number |
| **Default** | 2 |

Number of **preceding turns** included as context in the prompt. These turns appear before the target turn in the conversation.

**Example with `context_backward=2`:**

```
[Turn -2] agent: Welcome! How can I help you today?
[Turn -1] user: I'd like to open an investment account.

>>> TARGET TURN (classify this) <<<
[Turn 0] user: Yes, that one.
```

Without context, "Yes, that one" would be classified as UNKNOWN. With context, the LLM understands it refers to opening an account.

| Value | Behavior |
| --- | --- |
| 0 | No backward context. Same as the basic cascading classifier. |
| 1 | Only the immediately preceding turn. |
| 2 | Two preceding turns. **Recommended default**. |
| 3-5 | More context. Useful for long multi-turn dialogues. Increases token usage. |

---

#### context_forward

| | |
| --- | --- |
| **Type** | Number |
| **Default** | 1 |

Number of **following turns** included as context in the prompt. These turns appear after the target turn.

**Use case**: Sometimes the turn immediately after clarifies the intent. For example:

```
>>> TARGET TURN (classify this) <<<
[Turn 0] user: Can you help me with that?

[Turn +1] agent: Sure, I'll start the identity verification process now.
```

The forward turn reveals that the target was about `verify_identity`.

| Value | Behavior |
| --- | --- |
| 0 | No forward context. Classification is based only on past + target. |
| 1 | One following turn. **Recommended default**. |
| 2+ | More forward context. Marginal benefit for most datasets. |

---

#### context_max_chars

| | |
| --- | --- |
| **Type** | Number |
| **Default** | 500 |

Maximum characters allowed per **context turn** (preceding and following turns). Context turns exceeding this limit are truncated with `...`.

> **Important**: The target turn is **never truncated** — only context turns are subject to this limit.

**Tuning guidance:**

| Value | Behavior |
| --- | --- |
| 200 | Aggressive truncation. Saves tokens. May lose relevant detail. |
| 500 | **Recommended default**. Captures most relevant information. |
| 1000+ | Full context for long messages. Higher token cost per classification. |

---

#### use_previous_labels

| | |
| --- | --- |
| **Type** | Checkbox (boolean) |
| **Default** | `false` |

This is the most important context parameter. It controls the **classification execution mode**.

---

### Mode A — Static Context (Parallel)

**When `use_previous_labels = false` (default)**

All turns across all conversations are classified **in full parallel**. Context turns include only text and speaker information.

**Prompt example:**

```
[Turn -2] agent: Welcome! How can I help?
[Turn -1] user: I want to open an account.

>>> TARGET TURN (classify this) <<<
[Turn 0] user: What documents do I need?

[Turn +1] agent: You'll need a valid ID and proof of address.
```

**Characteristics:**

- Fast — all turns processed simultaneously up to `max_concurrency`
- Context is text-only — no awareness of how prior turns were classified
- Best for datasets where most turns are self-contained or context is mainly lexical

---

### Mode B — Chained Context (Sequential)

**When `use_previous_labels = true`**

Classification is **sequential within each conversation** but **parallel across conversations**. Each turn sees the classified intent labels of the turns before it.

**Prompt example:**

```
[Turn -2] agent -> opening: Welcome! How can I help?
[Turn -1] user -> open_account: I want to open an account.

>>> TARGET TURN (classify this) <<<
[Turn 0] user: What documents do I need?

[Turn +1] agent: You'll need a valid ID and proof of address.
```

Notice how Turn -1 shows `-> open_account` — the label classified in the previous step. This helps the LLM understand that Turn 0 is a follow-up about account opening, leading it to classify correctly as `upload_document`.

**Characteristics:**

- Slower — turns within a conversation must be processed one at a time
- `max_concurrency` controls how many **conversations** run in parallel (not turns)
- Significantly better accuracy for follow-up messages, anaphora ("Yes", "That one", "Same thing"), and ambiguous turns
- Best for conversational datasets with many multi-turn exchanges

---

## Choosing the Right Classifier and Mode

| Scenario | Recommended Classifier | Mode |
| --- | --- | --- |
| First experiment / quick test | Cascading | N/A |
| Independent, self-contained turns | Cascading | N/A |
| Conversational data, speed priority | Cascading + Context | Mode A |
| Conversational data, accuracy priority | Cascading + Context | Mode B |
| Many short conversations (< 5 turns) | Cascading + Context | Mode A |
| Long conversations with follow-ups | Cascading + Context | Mode B |

---

## Recommended Configurations

### Cost-Effective (Fast, Lower Cost)

| Parameter | Value |
| --- | --- |
| provider | `openai` |
| model | `gpt-4o-mini` |
| temperature | 0.0 |
| stage1_threshold | 0.55 |
| stage2_threshold | 0.60 |
| max_concurrency | 8 |

### Balanced (Good Accuracy, Moderate Cost)

| Parameter | Value |
| --- | --- |
| provider | `openai` |
| model | `gpt-4o-mini` |
| stage2_model | `gpt-4o` |
| temperature | 0.0 |
| stage1_threshold | 0.60 |
| stage2_threshold | 0.65 |
| max_concurrency | 5 |

### Maximum Accuracy

| Parameter | Value |
| --- | --- |
| provider | `openai` |
| model | `gpt-4o` |
| temperature | 0.0 |
| stage1_threshold | 0.65 |
| stage2_threshold | 0.70 |
| max_concurrency | 3 |
| context_backward | 3 |
| context_forward | 1 |
| use_previous_labels | `true` |

---

## Error Handling and Fallback Behavior

The classifier handles errors gracefully at each stage:

| Situation | Behavior |
| --- | --- |
| Stage 1 returns confidence below `stage1_threshold` | Turn labeled `UNKNOWN`. Stage 2 skipped. |
| Stage 1 returns `UNKNOWN` category | Turn labeled `UNKNOWN`. Stage 2 skipped. |
| Stage 2 returns confidence below `stage2_threshold` | Turn labeled with the **category name** (e.g., `ONBOARDING_KYC`). |
| Stage 2 returns an invalid sub-intent | Fuzzy matching attempted. If no match, falls back to `UNKNOWN_SUBCATEGORY`. |
| API call fails (timeout, rate limit) | Automatic retry up to 3 times with delays of 2s, 5s, 15s. |
| All first 10 turns classify as UNKNOWN | Run is **aborted** with an error (likely API key or connectivity issue). |
| LLM returns malformed JSON | Turn classified as `UNKNOWN` with confidence 0.0. |

---

## LLM Cache

All LLM API calls are cached locally to avoid redundant costs. If you re-run a classification with the same text and model, cached results are returned instantly.

**Check cache size:**

```
GET /intellintents/api/llm-cache/stats
```

**Clear the cache:**

```
DELETE /intellintents/api/llm-cache
DELETE /intellintents/api/llm-cache?provider=openai
DELETE /intellintents/api/llm-cache?model=gpt-4o-mini
```

> **When to clear**: After updating prompt files, changing model behavior expectations, or when you want fresh classifications.

---

## Prompt Customization

The classifier loads prompts from external text files in `backend/app/classifiers/prompts/`:

| File | Purpose |
| --- | --- |
| `stage1_system.txt` | Stage 1 system prompt — lists all 14 categories |
| `stage2_onboarding_kyc.txt` | Stage 2 prompt for ONBOARDING_KYC sub-intents |
| `stage2_investor_profiling.txt` | Stage 2 prompt for INVESTOR_PROFILING sub-intents |
| `stage2_product_discovery.txt` | Stage 2 prompt for PRODUCT_DISCOVERY sub-intents |
| `stage2_recommendation_advisory.txt` | Stage 2 prompt for RECOMMENDATION_ADVISORY sub-intents |
| `stage2_execution_transactions.txt` | Stage 2 prompt for EXECUTION_TRANSACTIONS sub-intents |
| `stage2_portfolio_monitoring.txt` | Stage 2 prompt for PORTFOLIO_MONITORING sub-intents |
| `stage2_financial_education.txt` | Stage 2 prompt for FINANCIAL_EDUCATION sub-intents |
| `stage2_account_service_management.txt` | Stage 2 prompt for ACCOUNT_SERVICE_MANAGEMENT sub-intents |
| `stage2_regulatory_compliance.txt` | Stage 2 prompt for REGULATORY_COMPLIANCE sub-intents |
| `stage2_greeting.txt` | Stage 2 prompt for GREETING sub-intents |
| `stage2_small_talk.txt` | Stage 2 prompt for SMALL_TALK sub-intents |
| `stage2_out_of_scope.txt` | Stage 2 prompt for OUT_OF_SCOPE sub-intents |
| `stage2_harmful_unethical_communication.txt` | Stage 2 prompt for HARMFUL sub-intents |
| `stage2_unknown.txt` | Stage 2 prompt for UNKNOWN sub-intents |

You can edit these files to adjust classification behavior without changing code. After editing, **clear the LLM cache** and restart the server.

---

## Bilingual Support

The cascading prompts support **English and Spanish** input. Messages in either language are classified using the same taxonomy. The prompt instructions guide the LLM to handle both languages transparently.

---

*IntellIntents — Cascading Classifiers Manual v1.0*
