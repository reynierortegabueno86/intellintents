# Intent Distribution — Statistical Analysis

**Subject:** Distributional characterisation of intents in the GPTAdvisor conversational corpus
**Dataset analysed:** `GPTAdvisorProcessedConv` (id 4) classified by run 4 against taxonomy `(FII)-Financial Investment Intents` v1
**Volume:** 146,127 conversations · 514,814 turns · 246,537 user turns · 268,277 assistant turns
**Taxonomy:** 11 top-level categories · 87 leaf intents
**Language:** Spanish (Spain)
**Date:** April 2026

---

## 0. Executive summary

The corpus shows an extremely concentrated, heavy-headed intent distribution with a long sparse tail (HHI 54,830; Gini 0.7235; top-20 intents = 76.21% of all turns). Conversations are short and mono-topic: 63.25% are exactly two turns, 85% involve at most two distinct intents, and self-transition probabilities for the dominant intents range 60%–84%. The assistant operates dominantly as a customer-service / operational agent (ACCOUNT_SERVICE_MANAGEMENT + PRODUCT_DISCOVERY + EXECUTION_TRANSACTIONS = 73.5% of turns), with investment advisory and investor profiling together below 2% of activity. The classifier is bimodal in reliability: parent-category labels and high-volume operational leaves are confidently classified, while several compliance-load-bearing leaves (`buy_investment`, `transfer_funds`, `ask_about_fees`, `file_complaint`, `change_personal_details`) carry 47%–71% of rows below 0.7 confidence.

Seventeen findings are stated below, each tagged with a strength-of-evidence label (Bedrock / Strong / Moderate / Suggestive / Weak) reflecting sample size, effect size, and replication across multiple cuts of the data.

---

## 1. Macro shape: extreme concentration, very long tail

| Concentration metric | Value | Anchor |
|---|---:|---|
| Top-1 share | 15.21% | `ACCOUNT_SERVICE_MANAGEMENT` |
| Top-5 share | 41.72% | + `ask_product_features`, `filter_by_criteria`, `ask_about_fees`, `escalate_to_human` |
| Top-10 share | 59.64% | adds `transfer_funds`, `ONBOARDING_KYC`, `EXECUTION_TRANSACTIONS` (parent), `check_order_status`, `PRODUCT_DISCOVERY` (parent) |
| Top-20 share | 76.21% | covers practically all the assistant's working modes |
| HHI (×10⁴) | 54,830 | "highly concentrated" by any standard (US antitrust threshold = 2,500) |
| Gini coefficient | 0.7235 | strong inequality among intents |
| Long tail | 23.79% spread across 67+ leaves | every leaf below rank 50 has < 0.5% share |

### Finding 1 — The intent distribution is heavy-headed and Zipfian. [Bedrock]

A handful of intents do almost all of the work. Counts vs rank for the top 30 leaves are consistent with a power-law / Zipfian decay. The implication is that any compliance overlay can cover roughly **80% of the production workload by addressing only the top 20 intents** — a small surface relative to the 87 leaves of the taxonomy.

### Finding 2 — Top-tier "intents" include several parent-category labels acting as classifier hedges. [Strong]

`PRODUCT_DISCOVERY` (rank 10), `EXECUTION_TRANSACTIONS` (rank 8), `FINANCIAL_EDUCATION`, `PORTFOLIO_MONITORING`, `ONBOARDING_KYC`, `ACCOUNT_SERVICE_MANAGEMENT` and `REGULATORY_COMPLIANCE` are top-level labels — yet they account for ~30% of turns. Strong asymmetry by speaker confirms they are hedges:

| Parent label appearing as turn intent | User | Assistant | Asst/User ratio |
|---|---:|---:|---:|
| `PRODUCT_DISCOVERY` | 892 | 13,752 | 15.4× |
| `EXECUTION_TRANSACTIONS` | 2,664 | 15,902 | 6.0× |
| `FINANCIAL_EDUCATION` | 882 | 4,347 | 4.9× |
| `ACCOUNT_SERVICE_MANAGEMENT` | 24,883 | 53,396 | 2.1× |
| `PORTFOLIO_MONITORING` | 3,170 | 6,019 | 1.9× |

When the classifier is unsure of the leaf for a long, multi-purpose assistant turn, it falls back to the parent. **For compliance work this matters:** any overlay rule that depends on a leaf-level intent will silently fail on these parent-labelled assistant turns unless the overlay explicitly handles parent labels too.

---

## 2. The conversation is short, mono-topic, and sticky

### 2.1 Length — 63.25% of conversations are exactly 2 turns

| Bucket | Count | Share |
|---:|---:|---:|
| 1 turn | 18 | 0.01% |
| 2 turns | 92,433 | 63.25% |
| 3–5 turns | 30,196 | 20.66% |
| 6–10 turns | 19,068 | 13.05% |
| 11–20 turns | 3,668 | 2.51% |
| 21–50 turns | 682 | 0.47% |
| 51–100 turns | 61 | 0.04% |
| > 100 turns | 7 | < 0.01% |

p25 = p50 = 2 · p75 = 4 · p90 = 6 · mean = 3.52 · max = 378.

#### Finding 3 — The median interaction is one user message + one assistant reply. [Bedrock]

83.91% of conversations end at or before turn 5. There is no real "session" in this corpus; almost all interactions are one-shot Q&A. Three consequences:

- **State accumulation in chat is a fiction.** With 2-turn median, the assistant cannot collect a profile, learn objectives, or build context across turns. Compliance state must be hydrated from the firm's systems-of-record, not from chat memory.
- **First-turn quality is decisive.** Whatever the assistant decides on turn 1 is, statistically, the entire interaction. Errors in the first answer are not corrected later.
- **Multi-turn flows** (suitability test, gradual disclosure, layered KID delivery) cannot rely on chat continuation — they must be self-contained per turn or kicked out to a dedicated UI flow.

### 2.2 Most conversations stay on a single topic

| Distinct leaf intents per conversation | Count | Share |
|---:|---:|---:|
| 1 | 43,477 | 29.75% |
| 2 | 80,749 | 55.26% |
| 3 | 13,167 | 9.01% |
| 4–5 | 7,039 | 4.82% |
| 6–10 | 1,608 | 1.10% |
| > 10 | 93 | 0.06% |

Mean 1.96, median 2, p99 = 6.

#### Finding 4 — 85% of conversations involve at most two distinct intents. [Bedrock]

A conversation with two distinct labels is typically `(user_intent, assistant_intent)` where the user asks one thing and the assistant labels its reply with a different (often parent) label — same topic. So in semantic terms, the figure understates topical concentration: **conversations are almost always single-topic**.

### 2.3 Self-transition rates: once a topic starts, it persists

P(next intent same as current) for the high-volume top-level/leaf labels:

| Intent | Self-transition rate |
|---|---:|
| `closing` | 84.0% |
| `explain_tax_implications` | 75.5% |
| `ask_product_features` | 74.4% |
| `ACCOUNT_SERVICE_MANAGEMENT` | 73.4% |
| `ONBOARDING_KYC` | 71.9% |
| `compare_products` | 67.8% |
| `verify_identity` | 67.8% |
| `ask_service_hours` | 65.6% |
| `check_performance` | 64.6% |
| `ask_product_performance` | 61.7% |
| `report_suspicious_activity` | 60.9% |
| `escalate_to_human` | 60.7% |
| `filter_by_criteria` | 60.1% |

#### Finding 5 — Conversations are highly sticky topically. [Bedrock]

The Markov chain over intents is dominated by self-loops. Combined with the short-length finding, this means that the per-turn classification is, in effect, a per-conversation classification: getting the first label right is essentially getting all labels right. Multi-topic interleaving is statistically rare.

A subtle implication for active learning and evaluation: **bigram entropy over intents is low**, so models cannot rely on transition information to disambiguate. The label of turn N+1 is correlated with N to a degree that makes "context-aware" classification roughly as easy/hard as single-turn classification — the upside of cascading-context classification is small in this corpus.

### 2.4 Caveat on per-conversation HHI metric [Flag]

A computed per-conversation HHI on intent shares produced anomalous results (median = 0, p75 = 10,000), which disagree with the clean mono-topic finding from §2.2. The discrepancy likely reflects either a normalisation issue in the metric definition or a different definition than expected. This synthesis does **not** rely on the HHI metric; the "distinct intents per conversation" distribution (§2.2) is used instead for the same conclusion.

---

## 3. The assistant is dominantly a customer-service agent — not an investment advisor

### 3.1 Top-level distribution by speaker

| Top-level | Total turns | % of all | User % | Asst % |
|---|---:|---:|---:|---:|
| ACCOUNT_SERVICE_MANAGEMENT | 170,552 | 33.13% | 32.4% | 33.8% |
| PRODUCT_DISCOVERY | 130,659 | 25.38% | 23.3% | 27.3% |
| EXECUTION_TRANSACTIONS | 77,113 | 14.98% | 17.0% | 13.1% |
| ONBOARDING_KYC | 37,383 | 7.26% | 7.7% | 6.9% |
| PORTFOLIO_MONITORING | 34,439 | 6.69% | 7.1% | 6.3% |
| FINANCIAL_EDUCATION | 22,982 | 4.46% | 4.3% | 4.6% |
| OUT_OF_SCOPE | 10,875 | 2.11% | 1.8% | 2.4% |
| RECOMMENDATION_ADVISORY | 9,741 | 1.89% | 1.7% | 2.0% |
| GREETING | 7,119 | 1.38% | 1.6% | 1.1% |
| UNKNOWN | 5,142 | 1.00% | 1.3% | 0.7% |
| REGULATORY_COMPLIANCE | 4,583 | 0.89% | 0.9% | 0.9% |
| INVESTOR_PROFILING | 511 | 0.10% | 0.2% | 0.05% |

#### Finding 6 — Investment advisory is a < 2% activity; investor profiling is < 0.2%. [Bedrock]

Combined `RECOMMENDATION_ADVISORY` + `INVESTOR_PROFILING` is ~2% of all turns. By contrast, the top three operational categories (ACCOUNT_SERVICE, PRODUCT_DISCOVERY, EXECUTION) account for 73.5% of the workload. The assistant is structurally a **post-trade / operational chatbot with information-discovery capabilities**, not an advisor. This is consistent with a self-directed brokerage front-end (e.g., MyInvestor / Bankinter ING-style platforms).

### 3.2 Assistant-side dominance

Top assistant intents (n = 268,277):

1. `ACCOUNT_SERVICE_MANAGEMENT` 19.90%
2. `ask_product_features` 11.75%
3. `EXECUTION_TRANSACTIONS` (parent) 5.93%
4. `PRODUCT_DISCOVERY` (parent) 5.13%
5. `escalate_to_human` 4.84%

**Five labels carry 47.55% of assistant output.** The top 20 carry 76%. The model is operating a small number of well-trodden response modes.

### 3.3 Users do not initiate execution

First-turn distribution (what users come for):

| First-turn intent | First-turn share |
|---|---:|
| ACCOUNT_SERVICE_MANAGEMENT | 10.73% |
| ask_product_features | 8.94% |
| ask_about_fees | 7.68% |
| transfer_funds | 6.56% |
| check_order_status | 5.74% |
| filter_by_criteria | 5.12% |
| ONBOARDING_KYC | 4.86% |
| terminate_account | 4.34% |
| ask_security | 3.18% |
| change_personal_details | 2.28% |
| escalate_to_human | 2.25% |
| open_account | 2.04% |
| buy_investment | 2.02% |
| explore_product_types | 1.90% |

`sell_investment`, `withdraw_funds`, `set_recurring_investment` do not appear in the top 15.

#### Finding 7 — Users open conversations to ask, fix or move money — not to trade. [Strong]

"Money movement" (`transfer_funds` + `withdraw_funds`) is a different cluster from "investment trading" (`buy_investment` / `sell_investment`); the former is much more common. Most of the operational risk concentrates on **payment-instrument flows (PSD2 SCA, AML)**, not on **investment-product execution (MiFID II appropriateness, PRIIPs KID)**. Both regimes apply, but the volume mix tilts toward payments.

---

## 4. The advisory tail — when conversations get long, they are about advisory work

Average conversation length when the dominant intent is X:

| Dominant intent | Avg turn count |
|---|---:|
| `reject_recommendation` | 11.0 |
| `request_portfolio_suggestion` | 9.30 |
| `request_alternative` | 8.41 |
| `filter_by_criteria` | 7.84 |
| `request_rebalance_advice` | 7.50 |
| `check_holdings` | 7.49 |
| `check_performance` | 7.43 |
| `request_recommendation` | 6.48 |
| `state_experience_level` | 6.40 |
| `ask_product_risk` | 6.04 |

Compare to the **median of 2** for the corpus.

#### Finding 8 — Real advisory work explodes conversation length 3–6×. [Strong]

When the dominant intent is in the recommendation / portfolio / rebalance / advanced-filtering family, the conversation runs ~7–11 turns instead of 2. Two interpretations are consistent with the data:

- **Genuine advisory iteration:** the user explores, refuses, requests alternatives, drills into risk — a real consultative loop.
- **Advisor-side / professional use:** the long-tail conversations may be advisors using the assistant to assemble proposals for their clients, not retail investors.

Either way, the operational implication is sharp: the high-stakes work is concentrated in a small fraction of conversations (these classes total < 5% of conversations), but each one of them carries 3–6× the regulatory exposure per turn. **Compliance-overlay engineering effort should weight by exposure × length, not by raw conversation count.**

---

## 5. The escalation funnel

`escalate_to_human` is the 5th most common intent — 24,735 turns, 4.80% of all.

### 5.1 What precedes an escalation

Top intents in the 1–2 turns before `escalate_to_human` fires:

| Preceding intent | Count |
|---|---:|
| `escalate_to_human` (consecutive) | 17,663 |
| `ACCOUNT_SERVICE_MANAGEMENT` | 5,183 |
| `check_order_status` | 1,914 |
| `file_complaint` | 1,610 |
| `transfer_funds` | 1,442 |
| `ask_about_fees` | 897 |
| `ask_security` | 824 |
| `ONBOARDING_KYC` | 730 |

### 5.2 What the assistant does when the user asks for a human

P(assistant intent | user `escalate_to_human`):

| Assistant response | Share |
|---|---:|
| `escalate_to_human` (honoured) | 39.18% |
| `ACCOUNT_SERVICE_MANAGEMENT` | 37.32% |
| `ask_service_hours` | 14.31% |
| `ask_about_fees` | 2.41% |
| `file_complaint` | 1.64% |

#### Finding 9 — Escalations are driven by operational friction, not advisory complexity. [Strong]

The 5,183 + 1,914 + 1,610 + 1,442 = 10,149 turns immediately preceding an escalation are dominated by service issues, order status, complaints, and money movement — not by recommendation requests. Escalations to advisors over advisory needs are statistically rare. Combined with Finding 8, this means the live human channel exists primarily to clean up operational failures.

#### Finding 10 — In ~14% of escalation requests, the assistant responds with service hours. [Strong]

When the user says "I want a person", giving the contact channel and hours is responsive — but this indicates the **escalation handoff is shallow**: the assistant doesn't capture the user's reason or pre-package the case for the human, just hands off the phone number. For compliance traceability this is a gap — every escalation should carry a structured handoff record.

### 5.3 Escalation × high-risk co-occurrence

From the 10×10 high-stakes co-occurrence matrix:

- `escalate_to_human` × `ACCOUNT_SERVICE_MANAGEMENT`: 4,386 conversations
- `escalate_to_human` × `transfer_funds`: 1,013 (8.7% of `transfer_funds` conversations)
- `escalate_to_human` × `buy_investment`: 435 (11.4% of `buy_investment` conversations)
- `escalate_to_human` × `file_complaint`: 1,096 (29.1% of `file_complaints` escalate)
- `escalate_to_human` × `report_suspicious_activity`: 140 (11.2% of SAR conversations)

#### Finding 11 — Complaint conversations escalate at ~3× the baseline rate. [Strong]

Almost a third of `file_complaint` conversations end up requesting a human. This identifies `file_complaint` as the strongest "deflection-failure" signal in the dataset and a natural place for the compliance overlay to enforce CNMV complaint-procedure routing instead of defaulting to escalation chatter.

---

## 6. Classifier reliability heat-map

`% rows below 0.7 confidence` for high-volume intents:

### Reliable (< 25% < 0.7)

| Intent | Median conf | % < 0.7 |
|---|---:|---:|
| `ACCOUNT_SERVICE_MANAGEMENT` | 0.86 | 0.95% |
| `EXECUTION_TRANSACTIONS` (parent) | 0.86 | 0.85% |
| `ONBOARDING_KYC` (parent) | 0.86 | 2.53% |
| `PRODUCT_DISCOVERY` (parent) | 0.78 | 3.44% |
| `PORTFOLIO_MONITORING` (parent) | 0.78 | 6.22% |
| `FINANCIAL_EDUCATION` (parent) | 0.78 | 8.19% |
| `compare_products` | 0.86 | 14.98% |
| `filter_by_criteria` | 0.81 | 20.70% |
| `terminate_account` | 0.86 | 23.76% |
| `explain_tax_implications` | 0.80 | 23.31% |

### Unreliable (> 50% < 0.7)

| Intent | Median conf | % < 0.7 |
|---|---:|---:|
| `UNKNOWN.none` | 0.62 | 99.98% |
| `file_complaint` | 0.65 | 71.40% |
| `check_holdings` | 0.64 | 69.03% |
| `buy_investment` | 0.67 | 67.47% |
| `explore_product_types` | 0.64 | 64.78% |
| `ask_about_fees` | 0.63 | 63.81% |
| `ask_security` | 0.67 | 59.94% |
| `open_account` | 0.67 | 59.70% |
| `ask_service_hours` | 0.67 | 54.30% |
| `ask_product_performance` | 0.67 | 53.10% |
| `change_personal_details` | 0.69 | 52.67% |
| `transfer_funds` | 0.70 | 46.67% |
| `request_statement` | 0.70 | 43.83% |
| `check_performance` | 0.70 | 43.55% |

#### Finding 12 — The classifier is bimodal: parents and operational labels are reliable, several high-stakes leaves are not. [Bedrock]

ACCOUNT_SERVICE, EXECUTION, ONBOARDING and PRODUCT_DISCOVERY parent labels are at >95% reliability. Several **compliance-load-bearing** leaves are not: `buy_investment` (67% < 0.7), `transfer_funds` (47% < 0.7), `ask_about_fees` (64% < 0.7), `file_complaint` (71% < 0.7), `change_personal_details` (53% < 0.7).

This is a problem for the compliance overlay: the very labels the overlay most needs to be confident about (because they fire HIGH-risk gates: AML, MiFID II 24(4) costs, PSD2 SCA, complaint routing) are the ones the classifier is least sure about. Mitigation: latent-trigger detection in raw text must operate as the primary signal for these labels, with the intent label as a confirming hint, not the driver.

#### Finding 13 — Confidence is stable across position within a conversation. [Strong]

Mean confidence at early/middle/late position differs by < 0.04 for the top 15 intents. There is no degradation as conversations progress. The classifier doesn't get "lost" in long conversations; it just deals with intrinsically harder labels.

---

## 7. Position bias — what fires early vs late

Mean relative position (0 = first, 1 = last) for top intents:

| Intent | Mean rel pos | Std |
|---|---:|---:|
| `PRODUCT_DISCOVERY` (parent) | 0.0322 | 0.13 |
| `EXECUTION_TRANSACTIONS` (parent) | 0.0585 | 0.20 |
| `PORTFOLIO_MONITORING` (parent) | 0.1379 | 0.27 |
| `terminate_account` | 0.1612 | 0.28 |
| `escalate_to_human` | 0.1773 | 0.22 |
| `check_order_status` | 0.2162 | 0.31 |
| `ACCOUNT_SERVICE_MANAGEMENT` | 0.2259 | 0.37 |
| `ask_about_fees` | 0.2331 | 0.31 |
| `ask_security` | 0.2368 | 0.33 |
| `compare_products` | 0.2420 | 0.31 |
| `filter_by_criteria` | 0.2413 | 0.27 |
| `open_account` | 0.2494 | 0.34 |
| `transfer_funds` | 0.2651 | 0.35 |
| `ask_product_features` | 0.3072 | 0.33 |
| `ONBOARDING_KYC` (parent) | 0.3287 | 0.44 |

#### Finding 14 — Parent labels concentrate at conversation start. [Strong]

`PRODUCT_DISCOVERY` and `EXECUTION_TRANSACTIONS` parent labels appear with mean relative position ≈ 0.03–0.06. This corroborates that they are classifier hedges on the first assistant turn — when the model has to respond to the user's opener and the leaf isn't crisp, it falls to the parent label. By contrast `ONBOARDING_KYC` parent has mean position 0.33 because onboarding flows are multi-turn and span the conversation.

#### Finding 15 — Last-turn distribution is collapsed onto operational closure. [Bedrock]

Last-turn share for `ACCOUNT_SERVICE_MANAGEMENT` is 29.51%, dwarfing its 15.21% overall share. `EXECUTION_TRANSACTIONS` (parent) closes 9.74% of conversations vs 3.61% overall. Conversations end on operational ground regardless of where they started — consistent with a service-channel chatbot that resolves things and signs off.

---

## 8. Co-occurrence findings worth flagging

From the 10×10 high-stakes matrix:

| Pair | Conversations with both | Anchor population | Co-occurrence rate |
|---|---:|---:|---:|
| `ask_about_fees` × `transfer_funds` | 312 | 11,660 transfer convs | 2.7% |
| `ask_about_fees` × `escalate_to_human` | 856 | 12,026 escalation convs | 7.1% |
| `ask_about_fees` × `file_complaint` | 424 | 3,762 complaint convs | 11.3% |
| `transfer_funds` × `escalate_to_human` | 1,013 | 11,660 transfer convs | 8.7% |
| `buy_investment` × `escalate_to_human` | 435 | 3,828 buy convs | 11.4% |
| `update_risk_profile` × `state_risk_tolerance` | 3 | 246 update convs | 1.2% |
| `report_suspicious_activity` × everything | < 200 each | 1,253 SAR convs | low |

#### Finding 16 — Profile updates do not co-occur with explicit risk-tolerance statements. [Strong]

Of 246 conversations that contain `update_risk_profile`, only 3 also contain `state_risk_tolerance`. Users updating their profile in chat almost never state the new value explicitly in the conversation — they're routed to the questionnaire UI. This confirms that suitability state cannot be inferred in-channel: the chat is a surface for asking *to* update, not for completing the update.

#### Finding 17 — `report_suspicious_activity` is statistically isolated. [Strong]

Suspicious-activity reports rarely co-occur with other high-stakes intents in the same conversation. They are short, focused incidents. This argues for treating them as **single-turn workflows** — captured, routed, acknowledged, exited — not as conversational threads to develop.

---

## 9. Consolidated table of findings

| # | Finding | Strength | Implication |
|---:|---|---|---|
| 1 | Top-20 intents = 76% of all turns; HHI 54,830, Gini 0.7235 | Bedrock | Overlay scope: ~20 rewrite skeletons cover 80% of work |
| 2 | Several "intents" are parent-category classifier hedges with strong assistant-side bias | Strong | Overlay must treat parent labels explicitly, not only leaves |
| 3 | 63.25% of conversations are exactly 2 turns; median = 2 | Bedrock | State must be hydrated externally, not from chat |
| 4 | 85% of conversations have ≤ 2 distinct intents | Bedrock | Single-topic compliance handling per conversation |
| 5 | Self-transition rates 60–84% | Bedrock | Cascading-context classification gives little uplift |
| 6 | Advisory < 2%, profiling < 0.2% of turns | Bedrock | Most compliance gates fire on operational turns, not advisory ones |
| 7 | Users open with money-movement, not trading | Strong | PSD2/AML weight ≥ MiFID II/PRIIPs weight by volume |
| 8 | Advisory-dominant conversations are 3–6× longer | Strong | Weight overlay effort by exposure × length |
| 9 | Escalations driven by operational friction | Strong | Live-human channel cleans up operational failures |
| 10 | 14% of escalation requests answered with service hours | Strong | Escalation handoff lacks structured case context |
| 11 | 29% of `file_complaint` conversations escalate | Strong | Complaint flow needs CNMV-grade routing |
| 12 | Compliance-load-bearing leaves are unreliable (47–71% < 0.7 confidence) | Bedrock | Latent-trigger text detection must dominate over intent label |
| 13 | Confidence stable across conversation position | Strong | Classifier doesn't degrade with depth |
| 14 | Parent labels concentrate at conversation start | Strong | Parent-label rule firing must be position-aware |
| 15 | Last-turn distribution collapsed on operational closure | Bedrock | Conversations resolve on operational ground |
| 16 | Profile updates don't co-occur with stated values | Strong | In-chat state accumulation structurally impossible |
| 17 | SAR reports statistically isolated | Strong | Build SAR as single-turn workflow, not a thread |

---

## 10. What the data does not support

A few claims that might seem implied are not actually supported by these statistics:

- **"Users are mostly retail investors"** — not supported. The advisory tail (>7 turns) plus advisor-style language observed in real samples ("preparame una cartera para mi cliente", "tinc un altre client") suggests a non-trivial fraction of advisor / professional usage. Distribution is plausibly mixed.
- **"Long conversations are evidence of better engagement"** — not supported. Long conversations correlate with high-stakes advisory and with persistent abusive content (`HARMFUL_UNETHICAL_COMMUNICATION` average 7.33 turns). Length is a feature of the workload, not a quality signal.
- **"The classifier is broadly reliable"** — partially supported only. It is reliable for high-volume parent labels and for the most stable leaves; it is not reliable for several compliance-critical leaves; treating it as uniformly trustworthy would mislead the overlay.
- **"REGULATORY_COMPLIANCE intents capture the regulatory load"** — actively contradicted. At 0.89% of turns, that branch carries a small fraction of the regulatory exposure. The exposure lives in the operational and product-discovery majority.

---

## 11. Caveats and methodological notes

- **Per-conversation HHI metric (§2.4)** produced anomalous results that disagree with the mono-topic finding from §2.2. The synthesis uses §2.2 instead. A re-implementation of HHI on normalised within-conversation intent shares is recommended for completeness.
- **Confidence percentiles** include uniform buckets (median values like 0.7020, 0.7800 repeat across many intents): this likely reflects discretisation in the classifier output (cascading_context with rounded scores). Confidence comparisons are valid for relative ordering, less so for fine-grained calibration.
- **Single-turn conversations (n=18)** are too few to support strong inference about "drive-by" usage; they are noted but not load-bearing.
- **Long conversations (n=68 with > 50 turns)** are similarly small in absolute count; their characterisation as "advisory tail" is supported by both intent composition and conversation-length stratification, but individual numbers should be treated as suggestive.
- **Top-level vs leaf rollup**: where the agent's data shows parent-labelled rows, those represent classifier hedges (Finding 2). Some statistics double-count (e.g., a `PRODUCT_DISCOVERY` parent assistant turn responding to an `ask_product_features` user turn). The "distinct intents" metric in §2.2 explicitly counts those as two intents. Findings rely on this consistently throughout.
- **Single classification run**: this analysis is grounded on run 4 using the FII v1 taxonomy. Re-classification with a refined taxonomy would shift specific leaf-level numbers but not the macro findings.
