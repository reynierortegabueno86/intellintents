# Compliance Risk Analysis

**Subject:** GPTAdvisor conversational assistant for a Spanish investment firm
**Dataset analysed:** `GPTAdvisorProcessedConv` (id 4) classified by run 4 against taxonomy `(FII)-Financial Investment Intents` v1
**Volume:** 146,127 conversations / 514,814 turns / 246,537 user turns / 268,277 assistant turns
**Language:** Spanish (Spain)
**Regulatory perimeter:** MiFID II, MiFIR, PRIIPs, SFDR, EU Taxonomy, MAR, AML/CFT (Ley 10/2010), GDPR + LOPDGDD, DORA, PSD2, TR LMV, CNMV Circulars, FOGAIN, LIRPF, Retail Investment Strategy (transposing 2026–2027)
**Date:** April 2026

---

## 1. Executive summary

The conversational assistant operates at production scale on real client conversations of a Spanish investment firm. A grounded analysis of run 4 reveals a structural compliance gap: **MiFID II suitability assessment is functionally absent from the conversation flow**, and the assistant produces answers that — in multiple representative cases — fall short of the legal floor required by MiFID II, RIS, GDPR, AML or PSD2.

The single most consequential metric in this analysis:

> **81.5% of conversations containing a high-risk recommendation, advisory or transactional intent contain no suitability signal anywhere in the conversation** (neither explicit profiling intents nor implicit profile information in user text).

The exposure concentrates on:

- `transfer_funds` (88.0% of conversations without profile signal)
- `sell_investment` (88.0%)
- `buy_investment` (83.6%)
- `set_recurring_investment` (82.8%)
- `withdraw_funds` (77.0%)
- `request_recommendation` (49.4%)
- `request_rebalance_advice` (45.7%)
- `request_portfolio_suggestion` (34.1%)

In addition to the gating gap, the production dataset contains specific assistant behaviours that are direct or near-direct compliance breaches, including:

- Accepting a user's refusal to complete the suitability test and proceeding to construct a portfolio anyway (MiFID II Art. 25(2)/(3) violation).
- Categorical statements of tax effect ("este proceso no tiene impacto fiscal") that constitute personalised tax advice (LIRPF).
- Past-performance tables shown without standardised PRIIPs disclaimers and without RIS-aligned balanced presentation.
- Conflict-of-interest answers that deny existence of conflicts while simultaneously describing in-house product preference (MiFID II Art. 23).
- Suspicious-activity reports redirected to "review your statement" instead of triggering the fraud / AML / PSD2 unauthorised-transaction process.
- GDPR erasure requests deflected to a help page instead of opened as a SAR with the statutory 1-month clock.

This document quantifies the exposure, maps each FII v1 intent to its applicable regulatory triggers, identifies the user-side compliance concerns, and pairs real production assistant answers with compliance-prioritized rewrites that satisfy all simultaneously applicable obligations.

---

## 2. Quantitative risk findings

### 2.1 Suitability dimensions — explicit signals (intent-labeled)

Across 246,537 user turns, the INVESTOR_PROFILING branch of the FII v1 taxonomy carries:

| Suitability dimension | Intent leaf | User-turn count | Avg confidence | Below 0.7 |
|---|---|---:|---:|---:|
| Update of profile | `update_risk_profile` | 280 | 0.735 | 36% |
| Risk tolerance | `state_risk_tolerance` | 97 | 0.697 | 53% |
| Investment objectives | `state_investment_goal` | 43 | 0.712 | 40% |
| Financial situation | `state_financial_situation` | 41 | 0.625 | 73% |
| Knowledge & experience | `state_experience_level` | 24 | 0.633 | 67% |
| Investment horizon | `state_investment_horizon` | 16 | 0.703 | 44% |
| Refusal of profiling | `refuse_to_answer_profiling` | 9 | 0.59 | 89% |
| Sustainability preferences | `state_esg_preference` | **1** | 0.577 | 100% |
| **All INVESTOR_PROFILING** | | **511 (0.21% of user turns)** | | |

Conversations containing any explicit profiling intent: **422 of 146,127 (0.29%)**.
Conversations explicitly covering all 5 core MiFID II dimensions (K&E + financial + objectives + horizon + risk tolerance): **0**.

### 2.2 Suitability dimensions — implicit signals (text patterns outside the profiling branch)

| Dimension | User-turn count | % of user turns | Top intents where signal leaks |
|---|---:|---:|---|
| Financial situation | 18,168 | 7.37% | `ask_product_features`, `ask_about_fees`, `filter_by_criteria`, `compare_products`, `request_statement` |
| Horizon | 6,788 | 2.75% | `ask_about_fees`, `ask_product_features`, `filter_by_criteria`, `request_recommendation` |
| Risk tolerance | 2,497 | 1.01% | `ask_product_features`, `filter_by_criteria`, `compare_products`, `request_portfolio_suggestion`, `request_recommendation`, `ask_product_risk` |
| Knowledge & experience | 2,404 | 0.97% | `ACCOUNT_SERVICE_MANAGEMENT`, `ask_security`, `verify_identity` |
| Sustainability / ESG | 2,165 | 0.88% | `filter_by_criteria`, `ask_product_features`, `request_recommendation`, `compare_products` |
| Investment objectives | 413 | 0.17% | `withdraw_funds`, `request_statement`, `request_portfolio_suggestion` |

Implicit-signal counts include lexical noise (`seguro` = safe vs. insurance; `€` matches any euro amount; `años / meses` matches any time mention). The true implicit coverage is lower than these figures, which makes the gating gap more severe, not less.

### 2.3 Conversation-level coverage (explicit OR implicit)

| Dimensions covered in the conversation | Conversations | Share |
|---:|---:|---:|
| 0 | 122,845 | 84.1% |
| 1 | 20,025 | 13.7% |
| 2 | 2,660 | 1.8% |
| 3 | 467 | 0.32% |
| 4 | 89 | 0.06% |
| 5 | 32 | 0.02% |
| 6 (incl. sustainability) | 9 | 0.006% |

**84.1% of conversations carry no suitability signal of any kind.** The two profiling-rich conversations identified in the dataset (IDs 240153 and 349192) show the structure expected of a real advisory flow but appear to be advisor-side or test scenarios, not typical client interactions.

### 2.4 The gating gap — high-risk intents without profile context

| High-risk intent | Conversations with the intent | Conversations also carrying any suitability signal | Conversations without any suitability signal | Gating gap |
|---|---:|---:|---:|---:|
| `transfer_funds` | 11,660 | 1,399 | 10,261 | **88.0%** |
| `sell_investment` | 1,745 | 210 | 1,535 | **88.0%** |
| `buy_investment` | 3,828 | 629 | 3,199 | **83.6%** |
| `set_recurring_investment` | 1,423 | 245 | 1,178 | **82.8%** |
| `withdraw_funds` | 1,443 | 332 | 1,111 | **77.0%** |
| `request_recommendation` | 1,861 | 942 | 919 | **49.4%** |
| `request_rebalance_advice` | 186 | 101 | 85 | **45.7%** |
| `request_portfolio_suggestion` | 1,073 | 707 | 366 | **34.1%** |
| **Total (any of the above)** | **22,205** | **4,101** | **18,104** | **81.5%** |

The gating gap is the dominant operational metric for compliance remediation.

### 2.5 RIS readiness gap — sustainability preferences

`state_esg_preference` has a single user turn in 246,537 (0.0004%). The Retail Investment Strategy reinforces sustainability preferences as a mandatory dimension of the suitability questionnaire (already set out in MiFID II Delegated Reg. 2021/1253). The questionnaire either does not collect this dimension or does not surface it through the conversational channel; either way, it is a remediation item independent of any overlay.

---

## 3. Regulatory framework matrix

The assistant must comply with all of the following simultaneously when speaking to a client of a Spanish investment firm.

| Framework | Source | Operative obligations on a chat assistant |
|---|---|---|
| **MiFID II** | Dir. 2014/65/EU + Del. Reg. 2017/565 | Suitability for advice/portfolio mgmt (Art. 25(2)); Appropriateness for complex products outside execution-only (Art. 25(3)); Execution-only conditions on non-complex (Art. 25(4)); Suitability statement (Art. 25(6)); Best execution; Conflicts of interest (Art. 23); Inducements quality-enhancement test (Art. 24); Recording of communications (Art. 16(7)) |
| **MiFIR** | Reg. 600/2014 | Transaction reporting; transparency |
| **PRIIPs** | Reg. 1286/2014 | KID delivery before transaction for any packaged retail product; SRI 1–7 risk indicator; performance scenarios; cost & charges section |
| **SFDR** | Reg. 2019/2088 | Article 6 / 8 / 9 disclosure when product presented as ESG/sustainable; pre-contractual + periodic; PAI consideration where applicable |
| **EU Taxonomy** | Reg. 2020/852 | Alignment disclosure when "verde" / "sostenible" is claimed |
| **MAR** | Reg. 596/2014 | Refusal to act on inside information; market-manipulation prohibition |
| **AML/CFT** | Dir. (EU) 2015/849 + Ley 10/2010 + RD 304/2014 | KYC, source-of-funds, PEP screen, sanctions screen; suspicious-transaction reporting (SEPBLAC); **tipping-off prohibition**; reinforced measures for high-risk |
| **GDPR + LOPDGDD 3/2018** | Reg. 2016/679 + LOPDGDD | Right of access (Art. 15), rectification (Art. 16), erasure (Art. 17), portability (Art. 20), objection (Art. 21), automated-decision opt-out (Art. 22); data minimisation; lawful basis; transparent information (Art. 12); SAR procedure with 1-month default response window |
| **DORA** | Reg. 2022/2554 | Operational/ICT resilience; incident classification & reporting |
| **PSD2** | Dir. (EU) 2015/2366 | Strong Customer Authentication for payment changes/initiation; unauthorised-transaction refund rights |
| **TR LMV** | RDL 4/2015 | Spanish securities-law floor; CNMV authorisation references |
| **CNMV Circulars** | various | Marketing communications; complaint procedures via Defensor del Cliente |
| **FOGAIN** | RD 948/2001 | Standard investor-compensation language (up to 100,000 €) |
| **Tax — IRPF** | LIRPF + Reglamento | Bar on personalised tax advice unless authorised; only general régime statements |
| **RIS** | Dir. amending MiFID II/IDD/UCITS/AIFMD; Reg. amending PRIIPs (adopted 2024, transposing 2026–2027) | Value-for-money tests; tightened inducements + best-interest test; standardised ESMA risk warnings; marketing-communication identification + balanced view; tightened professional-on-request criteria; sustainability preferences reinforced; layered/digital disclosures; personalised cost-effect projections |
| **Vulnerable-client doctrine** | ESMA Guidelines + CNMV criteria | Heightened duty of care; restrict execution-only on complex; cooling language; never push transactions |

---

## 4. Three-layer trigger framework

Intent labels alone are insufficient to drive compliance behaviour. The framework operates on three layers, each independent and combinable.

### 4.1 Layer 1 — Hard triggers (fire regardless of conversation state)

| Trigger | Frameworks | What it forces |
|---|---|---|
| Personalised-recommendation request (explicit `request_recommendation` / `_portfolio_suggestion` / `_rebalance_advice`, or latent personalisation detector firing in any other intent) | MiFID II Art. 25(2), RIS best-interest | GATE unless suitability profile is complete and current; never produce a single named product as "for you" without it |
| Execution intent (`buy_investment`, `sell_investment`, `set_recurring_investment`) on complex instrument | MiFID II Art. 25(3); PRIIPs KID; AML | BLOCK unless appropriateness + KID delivery + costs disclosure are satisfied |
| `transfer_funds`, `withdraw_funds` | AML/Ley 10/2010, PSD2 | AML pattern check, channel-bound identity confirmation, no chat-only execution |
| `terminate_account`, `request_data_deletion`, `request_data_access` | GDPR Art. 15/17, MiFID II record-keeping | Open the formal procedure with statutory clock; state retention exceptions explicitly |
| `report_suspicious_activity` | AML, MAR, PSD2 unauthorised-transaction | Acknowledge without tipping off; route to fraud/AML; never confirm a SAR was filed |
| `harm_*` (entire branch) | Safety | BLOCK |
| `legal_or_policy_restricted`, `unsupported_financial_domain` | Scope | BLOCK with reason |
| `ask_about_conflicts_of_interest` | MiFID II Art. 23, RIS inducements | Disclose actual policy; never deny existence of conflicts |
| MNPI / insider information mentioned in user text | MAR | Refuse to act; log; do not engage on the substance |
| User offers to opt up to professional client status | MiFID II Annex II + RIS tightening | Cannot self-categorise via chat — formal flow only |
| `explain_tax_implications` with personalisation | LIRPF | General régime only; no personalised tax advice |

### 4.2 Layer 2 — Conditional triggers (depend on conversation-level suitability state)

Most "MEDIUM-risk in isolation" intents become HIGH the moment they're asked **without an underlying profile**.

- **Surfacing specific products with comparative/superlative framing** (`ask_product_features`, `compare_products`, `filter_by_criteria` with personalisation in user text): MEDIUM by default, **HIGH when no suitability signal is on file**, BLOCKING if user explicitly demands a single recommendation without profile.
- **Portfolio context present** (any `[Portfolio Report:]` artifact in the conversation, plus `check_holdings` / `check_performance` / `check_gains_losses`): turns the entire downstream conversation into portfolio-management territory; suitability bar is full Art. 25(2).
- **Assistant-shown past-performance** (any chart/return number): forces past-performance disclaimer + RIS-aligned balanced presentation, regardless of intent.
- **Profile staleness**: when `update_risk_profile` fires, all subsequent recommendations in the conversation must use the new profile, and any prior reasoning anchored on the old profile is invalidated.
- **`refuse_to_answer_profiling`**: user has affirmatively declined profiling. Advice is hard-blocked; only execution-only on non-complex instruments remains, with the explicit "no assessment" warning.

### 4.3 Layer 3 — Latent / implicit triggers (text-pattern, intent-independent)

Suitability information leaks into non-profiling intents at low rates but high stakes. The compliance overlay needs a dimension-typed implicit-signal extractor running on every user turn, independent of the intent classifier.

| Implicit signal | Verbatim Spanish patterns from real turns | Where it lands today | What the assistant must do |
|---|---|---|---|
| Risk-tolerance leak | "Quiero invertir a largo plazo con un riesgo medio"; "perfil de riesgo agresivo"; "premium moderado"; "volatilidad a 3a sea 29,19" | `ask_product_features`, `filter_by_criteria`, `request_recommendation`, `compare_products`, `request_portfolio_suggestion` | Capture into SuitabilitySignals.risk_tol = implicit; offer questionnaire; do not treat as binding profile |
| Horizon leak | "horizonte 2029"; "5 años"; "dentro de 3 meses"; "cuando me jubile"; "lo necesito en"; "corto/medio plazo" | `ask_about_fees`, `ask_product_features`, `filter_by_criteria`, `withdraw_funds` | Capture; flag short-horizon + risky-product mismatch; force horizon-product alignment check |
| Financial-situation leak | "Tengo poco dinero"; "tengo unos 4000€ en myinvestor"; "salario anual"; "todos mis ahorros"; "hipoteca"; "jubilado"; "paro" | `request_statement`, `withdraw_funds`, `file_complaint`, advisory prompts | Capture as informational; trigger capacity-for-loss + concentration check; vulnerability flags |
| Objectives leak | "Voy a comprar un piso y…"; "para complementar la pensión"; "estudios de mis hijos"; "para emergencias"; "ingresos pasivos" | `withdraw_funds`, `request_statement`, `request_portfolio_suggestion` | Capture; objective ↔ horizon ↔ risk consistency check |
| Sustainability leak | "fondos sostenibles"; "ISR"; "ESG"; explicit ESG-class queries | `filter_by_criteria`, `ask_product_features`, `request_recommendation` | Capture; trigger SFDR Article 6/8/9 disclosure |
| K&E leak | "no tengo experiencia"; "primera vez"; "no entiendo"; "soy novato"; "ya he invertido en X" | `ask_security`, `ACCOUNT_SERVICE_MANAGEMENT`, `verify_identity` | Capture; if conversation later asks for a complex product, raise appropriateness gate |
| Vulnerability leak | "jubilado"; "paro"; "todos mis ahorros"; "necesito el dinero pronto"; distress language | Various | Heightened duty-of-care; suspend execution-only on complex; never push transactions |
| Personalisation leak (converts a benign intent into HIGH) | "¿qué me recomiendas?"; "para mí"; "si fueras yo"; "dame uno"; "el mejor para mi caso"; "en mi situación" | Pervasive across `ask_product_features`/`compare_products`/`filter_by_criteria` | Promote turn to HIGH; gate to profile-missing/stale/complete branch |
| Forecast / guarantee leak | "va a subir"; "rentabilidad asegurada"; "seguro" (return-context) | `ask_product_performance`, `request_recommendation` | Forbid in assistant output; correct user expectation; balanced-presentation rule |
| MNPI / AML leak | "me han dicho que la empresa va a anunciar"; "para mi primo"; PEP-related | Various | Hard refuse on MNPI; AML routing (silent) on AML signals; never tip off |

### 4.4 Layer 4 — Operational / escalation triggers

- `escalate_to_human` (24,735 turns, ~5% of corpus): not a legal trigger by itself, but a strong proxy for complexity; useful for active-learning queue and quality monitoring.
- `file_complaint`: triggers CNMV / Defensor del Cliente complaint procedure and retention obligations.
- `request_human_advisor`: must be honoured; record reason and prior context.

---

## 5. Intent compliance-trigger map across the FII v1 taxonomy

Trigger types: **LF** legal floor · **PG** profile-gated · **AG** appropriateness-gated · **DG** disclosure-gated · **AML** AML pattern check · **MAR** market-abuse screen · **TAX** tax-personalisation prohibited · **GDPR** data-rights handling · **IG** identity-gated · **CoI** conflicts-of-interest disclosure · **SG** safety/scope block · **COMP** complaint procedure · **ESC** escalation honoured · **NONE** operational/no direct trigger

| Top-level → leaf intent | Trigger types | Key frameworks |
|---|---|---|
| **REGULATORY_COMPLIANCE.confirm_suitability** | LF, DG | MiFID II 25(2), 25(6) |
| **REGULATORY_COMPLIANCE.request_risk_disclaimer** | DG | MiFID II, PRIIPs |
| **REGULATORY_COMPLIANCE.ask_about_conflicts_of_interest** | LF, CoI | MiFID II 23, RIS |
| **REGULATORY_COMPLIANCE.ask_about_investor_protection** | DG | FOGAIN, CNMV, MiFID II |
| **REGULATORY_COMPLIANCE.report_suspicious_activity** | LF, AML, ESC | AML/CFT, MAR, tipping-off |
| **REGULATORY_COMPLIANCE.request_data_access** | LF, GDPR | GDPR Art. 15 |
| **REGULATORY_COMPLIANCE.request_data_deletion** | LF, GDPR | GDPR Art. 17 + MiFID II Art. 16 retention exception |
| **RECOMMENDATION_ADVISORY.request_recommendation** | LF, PG, DG | MiFID II 25(2), PRIIPs KID, RIS best-interest |
| **RECOMMENDATION_ADVISORY.request_portfolio_suggestion** | LF, PG, DG, AML (size) | MiFID II 25(2), PRIIPs, RIS, AML |
| **RECOMMENDATION_ADVISORY.request_rebalance_advice** | LF, PG | MiFID II 25(2) (portfolio mgmt) |
| **RECOMMENDATION_ADVISORY.ask_why_recommended** | DG | MiFID II 25(6), RIS |
| **RECOMMENDATION_ADVISORY.accept_recommendation / reject_recommendation** | DG | MiFID II 25(6) |
| **RECOMMENDATION_ADVISORY.request_alternative** | PG, DG | MiFID II 25(2) |
| **RECOMMENDATION_ADVISORY.request_human_advisor** | ESC | — |
| **EXECUTION_TRANSACTIONS.buy_investment** | LF, AG (complex), PG (advice), DG, AML, IG | MiFID II 25(3)/(4), PRIIPs, AML, MiFIR |
| **EXECUTION_TRANSACTIONS.sell_investment** | LF, DG, IG | MiFID II 25(6) costs, MiFIR |
| **EXECUTION_TRANSACTIONS.set_recurring_investment** | LF, AG, PG (if advised), DG, IG | MiFID II, PRIIPs |
| **EXECUTION_TRANSACTIONS.transfer_funds** | LF, AML, IG, PSD2 | AML, PSD2, Ley 10/2010 |
| **EXECUTION_TRANSACTIONS.withdraw_funds** | LF, AML, IG, PSD2 | AML, PSD2 |
| **EXECUTION_TRANSACTIONS.cancel_order / check_order_status** | DG (best-ex), IG | MiFID II Art. 27 |
| **PRODUCT_DISCOVERY.ask_product_features** | DG, conditional PG (if personalisation latent) | MiFID II marketing, PRIIPs, RIS |
| **PRODUCT_DISCOVERY.compare_products** | DG, conditional PG | MiFID II, PRIIPs, RIS, SFDR if ESG |
| **PRODUCT_DISCOVERY.filter_by_criteria** | DG, conditional PG | same as above |
| **PRODUCT_DISCOVERY.explore_product_types** | DG | MiFID II marketing |
| **PRODUCT_DISCOVERY.ask_product_performance** | DG (past-perf) | PRIIPs, RIS standardised warnings |
| **PRODUCT_DISCOVERY.ask_product_risk** | DG | PRIIPs SRI |
| **PRODUCT_DISCOVERY.ask_product_eligibility** | DG, AG | MiFID II target market |
| **PRODUCT_DISCOVERY.ask_esg_classification** | DG | SFDR Art. 6/8/9, Taxonomy |
| **PORTFOLIO_MONITORING.* (all leaves)** | IG, DG (fees), conditional PG (if rebalance follow-up) | MiFID II costs, GDPR |
| **PORTFOLIO_MONITORING.set_alert** | DG | MiFID II |
| **INVESTOR_PROFILING.state_*** | LF, GDPR | MiFID II 25(2)/(3); GDPR consent |
| **INVESTOR_PROFILING.refuse_to_answer_profiling** | **LF** (advice barred) | MiFID II 25(2)/(3) |
| **INVESTOR_PROFILING.update_risk_profile** | LF | MiFID II 25(2) — invalidates prior reasoning |
| **ONBOARDING_KYC.open_account / verify_identity / upload_document / link_bank_account** | LF, IG, AML | AML KYC, GDPR |
| **ONBOARDING_KYC.age_limit / check_eligibility** | LF | Suitability of retail vs professional |
| **ACCOUNT_SERVICE_MANAGEMENT.ask_about_fees** | DG | MiFID II 24(4) ex-ante costs, RIS inducement breakdown |
| **ACCOUNT_SERVICE_MANAGEMENT.ask_security** | DG, IG | DORA, GDPR |
| **ACCOUNT_SERVICE_MANAGEMENT.ask_service_hours** | NONE | — |
| **ACCOUNT_SERVICE_MANAGEMENT.change_password / change_personal_details** | LF, IG, GDPR, PSD2 | PSD2 SCA, GDPR |
| **ACCOUNT_SERVICE_MANAGEMENT.escalate_to_human / file_complaint** | ESC, COMP | CNMV complaint procedure |
| **ACCOUNT_SERVICE_MANAGEMENT.terminate_account** | LF, GDPR | GDPR Art. 17, MiFID II Art. 16 retention exception |
| **FINANCIAL_EDUCATION.explain_concept / instrument / market_event / strategy / risk** | DG (light) | MiFID II marketing |
| **FINANCIAL_EDUCATION.explain_regulation** | DG | — |
| **FINANCIAL_EDUCATION.explain_tax_implications** | **LF, TAX** | LIRPF — no personalised tax advice |
| **HARMFUL_UNETHICAL_COMMUNICATION.*** | **SG (BLOCK)** | Safety policy |
| **OUT_OF_SCOPE.legal_or_policy_restricted** | SG | Scope |
| **OUT_OF_SCOPE.unsupported_financial_domain** | SG (soft) | Scope |
| **OUT_OF_SCOPE.non_financial_topic / noise / technical_capability_limit** | NONE | — |
| **GREETING.* / SMALL_TALK.*** | NONE | — |
| **UNKNOWN.none** | DG (caution) | Fail-safe to clarification, never to advice |

---

## 6. Compliance violations identified in production data — paired with rewrites

The following twelve cases are verbatim user→assistant pairs from run 4. Each is paired with the specific compliance issues identified (with framework citations) and a Spanish rewrite that satisfies all simultaneously applicable obligations. The rewrites are written for an in-product assistant that can route to formal flows; they assume the firm has a profiling questionnaire URL, an MLRO/fraud channel, and a GDPR-rights endpoint.

### 6.1 — `refuse_to_answer_profiling` followed by portfolio construction (CRITICAL violation)

**Conversation 234604 · pair 13a**

```
USER:  Skip these steps
A:     Understood! Let's move forward with creating your portfolio. Since
       you've decided on a 50% allocation to equity funds and 50% to fixed
       income funds, we'll focus on selecting products from these
       categories. I'll prioritize products on the focus list to ensure
       quality and alignment with Andbank's recommendations.
       1. Equity Funds Selection: I'll find equity funds...
       2. Fixed Income Funds Selection: I'll also select fixed income funds.
       3. Total Investment Amount: Please let me know the total amount...
```

**Compliance issues**

- MiFID II Art. 25(2)/(3): user explicitly refused profiling; the firm cannot provide investment advice (suitability) nor recommend specific products. The assistant proceeds to construct a portfolio anyway.
- RIS best-interest: a recommendation drawn from "focus list" without profile is structurally ineligible.
- PRIIPs: no KID delivery referenced for products to be selected.
- The "I'll prioritize products on the focus list" sentence creates an undisclosed inducement / CoI concern (RIS).

**Compliant rewrite**

```
Entiendo que prefieres no completar el test de idoneidad ahora.
Sin completar ese test no podemos darte una recomendación
personalizada de productos, ni proponer una composición de cartera
adaptada a tu caso (MiFID II, art. 25). Esto aplica también a los
productos de la lista de seguimiento de la entidad.

Puedo ayudarte de tres formas, ninguna constituye recomendación
personalizada:

1. Reanudar el test de idoneidad cuando quieras (≈5–10 minutos).
   Tras completarlo podríamos proponerte una cartera adecuada a
   tu perfil, considerando objetivos, horizonte, tolerancia al
   riesgo, conocimientos y experiencia, capacidad de pérdida y
   preferencias de sostenibilidad.

2. Información general sobre clases de activos (renta variable,
   renta fija, fondos indexados, ETF) sin individualizar productos
   concretos para tu caso.

3. Derivarte a un asesor humano.

Esta respuesta es informativa y no constituye asesoramiento
financiero personalizado. Rentabilidades pasadas no garantizan
rentabilidades futuras. Toda inversión conlleva riesgo, incluida
la pérdida del capital invertido.

¿Qué prefieres?
```

### 6.2 — `request_recommendation` "revisar y opinar sobre una cartera" (latent advice)

**Conversation 216331 · pair 1a**

```
USER:  vos podes revisar y darme tu opinión sobre una cartera?
A:     Puedo ayudarte a revisar la composición de una cartera y
       proporcionarte información detallada sobre los fondos y productos
       que la componen. Sin embargo, no puedo dar opiniones o
       asesoramiento financiero. Si tienes una cartera específica que
       te gustaría que revisara, por favor indícame el nombre de la
       cartera o cualquier detalle relevante, y con gusto te
       proporcionaré la información disponible.
```

**Compliance issues**

- The disclaimer "no puedo dar opiniones o asesoramiento" is correct, but in the very next turn the assistant goes on to characterise the portfolio's performance ("la mayoría … rentabilidad negativa, excepto …") — borderline assessment language. The disclaimer must be followed by behaviour that matches it.
- Missing: explicit legal grounding (MiFID II), missing past-performance and risk disclaimers, missing route to human advisor.

**Compliant rewrite**

```
Por norma (MiFID II) no puedo emitir juicios de valor ni
recomendaciones personalizadas sobre una cartera concreta sin un
test de idoneidad vigente a tu nombre. Sí puedo proporcionarte
información objetiva sobre los productos que la compongan: ISIN,
política de inversión, indicador de riesgo (SRI 1–7), comisiones
totales (TER), clasificación SFDR, divisa y rentabilidades
pasadas (cuando estén disponibles).

Para que pueda revisar la cartera con esa óptica informativa,
indícame los ISIN o nombres de los productos.

Si quieres una valoración personalizada de la cartera (idoneidad,
diversificación, alineación con tu objetivo y tolerancia al
riesgo), necesito un test de idoneidad vigente. Puedo iniciarlo
contigo o derivarte a un asesor humano.

Esta respuesta es informativa y no constituye asesoramiento
financiero personalizado. Rentabilidades pasadas no garantizan
rentabilidades futuras.
```

### 6.3 — `request_portfolio_suggestion` for €2 millones without profile (high-stakes + AML-relevant amount)

**Conversation 216335 · pair 2a**

```
USER:  dame una idea cartera conservadora para proponer via fondos
       alternativa a un deposito de 2 millones de euros
A:     Para una cartera conservadora que sirva como alternativa a un
       depósito de 2 millones de euros, podemos considerar una cartera
       modelo conservadora de Andbank. Esta cartera está diseñada para
       priorizar la preservación del capital con inversiones de bajo
       riesgo, como bonos y equivalentes de efectivo. Aquí tienes un
       ejemplo de cómo podría estar compuesta esta cartera:
       Voy a cargar la información de la base de datos de carteras
       modelo para mostrarte los fondos incluidos y sus respectivos
       pesos. Un momento, por favor.
```

**Compliance issues**

- MiFID II Art. 25(2): portfolio proposal without profile.
- RIS best-interest: "podemos considerar una cartera modelo conservadora de Andbank" steers to in-house product without considering an "appropriate range" or cost-efficiency.
- AML / Ley 10/2010: at €2M, source-of-funds and reinforced due diligence are mandatory before any product placement.
- PRIIPs: no KID for the constituent funds; "preservación del capital" risks being read as a guarantee — RIS forbids reward-only framing.
- "Bajo riesgo" is informal; the standard is the SRI (1–7) of each constituent.

**Compliant rewrite**

```
Una operación por importe equivalente a 2.000.000 € requiere, por
normativa de prevención de blanqueo (Ley 10/2010), un proceso de
diligencia reforzada y verificación del origen de los fondos
**antes** de cualquier propuesta de inversión, así como un test
de idoneidad vigente para que podamos proponer una composición
adaptada a tu caso (MiFID II, art. 25).

Dado el importe, te derivamos a un gestor humano que coordinará:
1. Verificación del origen de los fondos.
2. Test de idoneidad y, si aplica, categorización del cliente.
3. Propuesta de cartera con análisis de coste-eficiencia entre
   alternativas de gama propia y de terceros, entrega del KID
   (PRIIPs) de cada fondo y desglose ex-ante de costes y
   gastos (incluidos incentivos percibidos por la entidad).

Mientras tanto, sí puedo ofrecerte información general sobre
clases de activos típicamente utilizadas en perfiles
conservadores (deuda pública a corto plazo, monetarios, renta
fija de calidad), sin individualizar productos concretos para
tu caso.

"Conservadora" no equivale a "sin riesgo": cada fondo tiene un
indicador de riesgo (SRI 1–7) y rentabilidades no garantizadas.
Esta respuesta es informativa y no constituye asesoramiento
financiero personalizado.

¿Quieres que te conecte con un gestor humano?
```

### 6.4 — `buy_investment` "cómo adquirir bonos del tesoro" (no KID, no costs, no appropriateness)

**Conversation 216630 · pair 4a**

```
USER:  como puedo adquirir en un plan Platinum bonos del tesoro?
A:     Para adquirir bonos del tesoro en un plan Platinum, generalmente
       necesitarías seguir estos pasos:
       1. Consulta con tu Asesor Financiero...
       2. Revisión de los Modelos de Portafolio...
       3. Plataforma de Inversión...
```

**Compliance issues**

- PRIIPs: bonos del tesoro plain-vanilla are typically out of PRIIPs scope (sovereign debt exception), but if structured/repackaged → KID required. The assistant doesn't establish which.
- MiFID II 25(3)/(4): no appropriateness check or execution-only warning.
- MiFID II 24(4): no ex-ante costs disclosure mentioned.
- MiFID II 25(2): "Revisión de los Modelos de Portafolio" implicitly individuates.

**Compliant rewrite**

```
Para invertir en bonos del Tesoro a través de un plan Platinum
debes:

1. Tener una cuenta y servicio operativo activo, con identidad
   verificada y los consentimientos correspondientes.

2. Consultar el folleto y, en su caso, el Documento de Datos
   Fundamentales (KID) cuando el producto entre en el ámbito
   PRIIPs (instrumentos empaquetados). Los bonos soberanos
   "plain vanilla" en mercado primario suelen estar fuera de
   ese ámbito, pero te indicaremos la documentación aplicable
   al producto concreto en el momento de la operación.

3. Recibir el desglose ex-ante de costes y gastos (MiFID II
   art. 24(4)) antes de confirmar la orden, incluyendo
   comisiones del intermediario, custodia y, si proceden,
   incentivos.

4. Completar, si procede, el test de conveniencia (MiFID II
   art. 25(3)) para productos que no se consideren no complejos.

Esta información es general y no constituye recomendación
personalizada. Si quieres valorar si una inversión en bonos del
Tesoro es adecuada para tu caso (objetivo, horizonte, tolerancia
al riesgo, capacidad de pérdida), necesitamos un test de
idoneidad vigente o derivarte a un asesor humano.

¿Cómo prefieres continuar?
```

### 6.5 — `transfer_funds` "traerme mi fondo desde ING" (tax-statement issue + identity)

**Conversation 216423 · pair 6a**

```
USER:  Puedo traerme mi fondo de inversión desde ing a myinvestor?
A:     Sí, puedes traspasar tus fondos de inversión desde ING a
       MyInvestor sin ningún problema. Este proceso no tiene impacto
       fiscal y es bastante sencillo. ...
```

**Compliance issues**

- TAX (LIRPF): "no tiene impacto fiscal" is **personalised tax advice**. The régimen de traspasos del art. 94 LIRPF tiene condiciones (FI español o equivalente, mínimo de partícipes, no haber transmitido…). Categórico → infracción.
- AML: traspasos entre entidades exigen verificación de titularidad y control de blanqueo.
- MiFID II 24(4): no mention of any costs differential between origin and destination products.

**Compliant rewrite**

```
Sí, MyInvestor admite el traspaso de fondos de inversión desde
ING. El proceso lo inicias desde la app de MyInvestor y el banco
de origen tiene un plazo legal para ejecutarlo.

Sobre la fiscalidad: el régimen de **diferimiento por traspaso**
(art. 94 LIRPF) permite no tributar por la plusvalía latente
**siempre que se cumplan las condiciones legales del régimen**
(fondo origen y destino aptos, mínimos de partícipes, no
mediación de reembolso a tu nombre, etc.). No podemos confirmarte
en este canal si tu caso concreto cumple todas las condiciones,
ni proporcionarte asesoramiento fiscal personalizado. Para una
valoración fiscal de tu situación, consulta a un asesor fiscal o
a tu gestor en MyInvestor.

Antes del traspaso te recomendamos comparar el coste total (TER
y, si aplica, comisiones de suscripción/reembolso) y el
indicador de riesgo (SRI 1–7) del fondo origen y destino,
disponibles en su KID.

Para iniciar el traspaso necesitamos verificar tu identidad y
los datos de la cuenta y posiciones en origen. ¿Quieres que te
indique los pasos en la app o que te conecte con un gestor?

Esta respuesta es informativa y no constituye asesoramiento
financiero ni fiscal personalizado.
```

### 6.6 — `filter_by_criteria` "mejores fondos globales" (past-perf + personalisation)

**Conversation 216303 · pair 8b**

```
USER:  mejores fondos globales
A:     Aquí tienes los mejores fondos globales disponibles:
       | WORLD GOLD FUND CLASS A2 EUR | LU0171305526 | 32,48% | EUR | Muy Alto |
       | DWS TOP DIVIDENDE LD DIS EUR | DE0009848119 | 5,30%  | EUR | Muy Alto |
       | AMUNDI EUROPEAN EQ TARGET INC A2 DIS EUR | LU1883311653 | 3,89% | EUR | Alto |
       Todos estos fondos pertenecen a la Selección análisis.
```

**Compliance issues**

- "Mejores" individuates products as best — personalised recommendation framing without profile (MiFID II 25(2)).
- Past-performance numbers shown without PRIIPs standardised disclaimer.
- "Muy Alto / Alto" are firm-specific labels; the standard is PRIIPs SRI (1–7).
- Selección análisis is a focus-list — its inclusion creates a CoI / inducement disclosure obligation under MiFID II Art. 23–24 and RIS.
- SFDR article not stated.
- Marketing communication identification (RIS): not labelled as such.

**Compliant rewrite**

```
"Mejor" depende de cada inversor. Sin un test de idoneidad
vigente no podemos individualizar productos como adecuados
para ti. A continuación, te muestro **información** sobre fondos
globales de nuestro catálogo de análisis, ordenados por
rentabilidad en el último año (no es un ranking de calidad ni
una recomendación):

| Fondo                                     | ISIN          | Rent. último año | Divisa | SRI (1–7) | SFDR  |
| WORLD GOLD FUND CLASS A2 EUR             | LU0171305526  | 32,48%           | EUR    | 7         | Art.6 |
| DWS TOP DIVIDENDE LD DIS EUR             | DE0009848119  | 5,30%            | EUR    | 6         | Art.8 |
| AMUNDI EUROPEAN EQ TARGET INC A2 DIS EUR | LU1883311653  | 3,89%            | EUR    | 6         | Art.8 |

(Indicador de riesgo SRI conforme a PRIIPs; clasificación SFDR
del propio folleto. Verifica los datos en el KID del fondo.)

Estos fondos están incluidos en la **Selección análisis** de la
entidad. La inclusión en esa lista refleja criterios internos
de seguimiento; no implica que sean adecuados para tu caso. La
entidad puede percibir incentivos de la gestora, cuyo desglose
se detalla en el documento ex-ante de costes y en la sección
de transparencia de la web.

Rentabilidades pasadas no garantizan rentabilidades futuras.
Estos fondos son productos de inversión con riesgo, incluida la
pérdida del capital invertido. Antes de invertir consulta el KID
y el folleto.

Comunicación de carácter informativo y promocional. No constituye
recomendación personalizada.

Si quieres una recomendación adaptada a tu perfil (objetivo,
horizonte, tolerancia, capacidad de pérdida, preferencias de
sostenibilidad), iniciemos el test de idoneidad o te derivo a
un asesor humano.
```

### 6.7 — `ask_about_conflicts_of_interest` "sesgo hacia productos de la casa?" (CoI question with revealing answer)

**Conversation 334603 · pair 22b**

```
USER:  tienes algun tipo de sesgo hacia productos de la casa?
A:     No tengo ningún sesgo hacia productos de la casa. Mi objetivo es
       proporcionar información precisa y objetiva ... Sin embargo, los
       productos de la casa (denominados como "Producto de la casa" o
       "P360") suelen tener relevancia en las recomendaciones debido a
       su alineación con los estándares de la entidad y a la confianza
       que generan en los clientes. Además, algunos de estos productos
       pueden estar incluidos en las Focus Lists, como "Favoritos
       Andbank"... Si deseas que excluya cualquier producto de la casa
       en mi análisis o recomendaciones, puedo hacerlo sin problema.
```

**Compliance issues**

- The first sentence ("No tengo ningún sesgo") is contradicted by the same answer — MiFID II Art. 23 + 24: actual conflicts must be disclosed clearly, not denied and then partially admitted.
- RIS best-interest test: in-house relevance must be justified by client benefit, not by "alignment with the entity's standards" or "confidence".
- The offer to "exclude house products if you want" is not how CoI law works — disclosure and best-interest are obligations of the firm, not options of the client.

**Compliant rewrite**

```
Buena pregunta. Te respondo con transparencia:

La entidad puede ofrecerte productos de gestión propia ("Producto
de la casa", "P360") y productos de terceros. La existencia de
producto propio constituye un **conflicto de interés potencial**,
que la entidad gestiona conforme a la política de conflictos de
interés (MiFID II, art. 23) publicada en su web.

Cuando se te proponga un producto, debes saber:

1. Si es producto de la casa o de tercero (lo indicamos siempre).
2. Si la entidad percibe **incentivos** por su distribución y
   en qué cuantía (desglose ex-ante de costes; MiFID II art. 24(4)).
3. Si en la categoría existen alternativas equivalentes y, en su
   caso, **más coste-eficientes** (test del mejor interés del
   cliente, RIS).

La inclusión de un producto en una Focus List ("Favoritos
Andbank") refleja criterios internos; no es por sí sola garantía
de adecuación a tu caso ni razón suficiente para preferirlo a
otro equivalente más barato.

¿Quieres que te explique los criterios de la política de
conflictos o que te muestre la sección de incentivos de un
producto concreto?
```

### 6.8 — `explain_tax_implications` "fiscalidad fondos" (general info OK, missing disclaimer)

**Conversation 216378 · pair 10a**

```
USER:  fiscalidad fondos
A:     La fiscalidad de los fondos de inversión en España está regulada
       principalmente por el IRPF. ... 1. Ganancias y Pérdidas
       Patrimoniales ... 2. Tributación Diferida ... 3. Retenciones:
       En el momento de la venta, el intermediario financiero retiene
       un 19% del importe de la ganancia ...
```

**Compliance issues**

- Content is general régime, which is acceptable, but it lacks the explicit "no constituye asesoramiento fiscal personalizado" framing required when crossing into tax content.
- The retention rate "19%" is correct for the first tranche but reads as universal; standard practice is to clarify it is the cuota inicial.

**Compliant rewrite**

```
A título informativo, así funciona el régimen fiscal general de
los fondos de inversión para personas físicas residentes en
España (IRPF):

1. Ganancia/pérdida patrimonial: diferencia entre el valor de
   reembolso y el de suscripción.
2. Tributación diferida: no tributas hasta que reembolses (con
   excepciones, p. ej. ETF).
3. Retención en origen sobre la ganancia: tipo inicial del 19%
   con carácter general; la cuota efectiva depende de tu base
   del ahorro y los tramos en vigor.
4. Compensación de pérdidas y reglas anti-aplicación
   (recompras): aplican según normativa.

Esta información describe el **régimen general** y puede no
ajustarse a tu situación concreta (residencia, herencias,
contratos privados, traspasos, productos extranjeros, etc.).

No estamos autorizados a darte asesoramiento fiscal
personalizado en este canal. Para una valoración aplicada a tu
caso consulta a un asesor fiscal o, si procede, a tu gestor.

¿Quieres que te explique alguno de estos puntos o el régimen de
traspasos (art. 94 LIRPF)?
```

### 6.9 — `report_suspicious_activity` "movimiento que no reconozco" (failed fraud handling)

**Conversation 225789 · pair 15a**

```
USER:  Tengo un movimiento en cuenta que no reconozco
A:     Para ayudarte con un movimiento en tu cuenta que no reconoces, te
       recomiendo revisar los detalles del movimiento en tu extracto
       bancario. Si necesitas más información sobre cómo proceder, puedo
       buscar en los documentos que has subido o en nuestras fuentes
       oficiales. Por favor, indícame si deseas que realice una
       búsqueda específica o si necesitas orientación adicional.
```

**Compliance issues**

- AML/Fraud: an unrecognised transaction on a client's account is a potential fraud incident and triggers the firm's fraud-incident process; "review your statement" is not a compliant response.
- PSD2 unauthorised-transaction: the user has rights to a refund within strict deadlines if reported promptly; the assistant must not let those clocks run silently.
- DORA: ICT/incident logging.
- Tipping-off prohibition (AML): if the firm later determines the movement is AML-relevant, no information about the SAR should be conveyed; the user-facing channel must remain neutral.

**Compliant rewrite**

```
Lo siento. Un movimiento que no reconoces en tu cuenta lo
tratamos como un posible incidente de fraude o uso no autorizado.
Es importante actuar con rapidez.

Para protegerte y cumplir con los plazos legales (PSD2):

1. **Informo ya** a nuestro equipo de fraude/seguridad para que
   abran un expediente con tu cuenta. Recibirás confirmación
   por canal seguro.
2. Te recomiendo, como medida preventiva inmediata, **bloquear
   tarjetas y revocar dispositivos** desde la app o por
   teléfono al 910 005 981.
3. **No compartas** datos sensibles por chat (IBAN completo,
   códigos SMS, contraseñas). Si recibiste algún mensaje o
   correo pidiendo datos, no respondas y guárdalo como prueba.

Para acelerar el expediente, indícame **únicamente**: fecha
aproximada del movimiento, importe aproximado y si reconoces o
no el comercio/destinatario. No incluyas tu número de cuenta
completo.

Tienes derecho a la devolución de operaciones no autorizadas si
las notificas en plazo (en general, sin demora indebida y
máximo 13 meses; consulta condiciones específicas).

¿Procedo a abrir el expediente?
```

### 6.10 — `request_data_deletion` GDPR, frustrated user (passive handling)

**Conversation 232966 · pair 17b**

```
USER:  Me he quedado a medias con la activacion de mi cuenta, he llamado
       por telefono, he contactado via email e incluso he solicitado la
       baja de mis datos personales, pero jamas habia visto tanta
       dejadez en lo que respecta a la atencion al cliente... Podrian
       por lo menos dar de baja todos mis datos de sus servicios, creo
       que me ampara la ley en esta solicitud. Un saludo.
A:     Lamento mucho la experiencia que has tenido y entiendo tu
       frustración. Respecto a la solicitud de baja de tus datos
       personales, tienes derecho a solicitar la eliminación de tus
       datos conforme a la normativa de protección de datos vigente,
       como el Reglamento General de Protección de Datos (RGPD). Para
       proceder con esta solicitud, es necesario que sigas el
       procedimiento establecido por nosotros. Te recomiendo que
       consultes la información específica sobre cómo realizar esta
       solicitud en nuestra página de ayuda...
```

**Compliance issues**

- GDPR Art. 17 (right to erasure): must be actioned, not redirected to a help page. The assistant should open a SAR/erasure request and confirm the 1-month statutory response window.
- GDPR Art. 12: information must be provided in concise, transparent and easily accessible form.
- MiFID II Art. 16 + Del. Reg. 2017/565 art. 72 retention exception (5 years for communications/transactional records) must be stated, not hidden.
- Complaint handling (CNMV): the user is also expressing a complaint about service — separate procedure must be triggered.

**Compliant rewrite**

```
Lamento mucho la situación. Voy a tramitar dos cosas en paralelo
porque son procedimientos distintos:

1. **Derecho de supresión (RGPD, art. 17)**: estás en tu
   derecho. Abro tu solicitud de supresión a partir de los datos
   que tenemos asociados a tu identidad. Plazo legal de
   respuesta: hasta 1 mes (prorrogable 2 meses adicionales en
   casos complejos, con notificación previa). Recibirás
   confirmación por correo. Importante: para los datos que
   tenemos por obligación legal de conservación (registros de
   contratación y comunicaciones — MiFID II y normativa de
   blanqueo, mínimo 5 años), no podemos suprimirlos hasta que
   expire el plazo legal; te indicaremos qué se suprime ahora,
   qué se anonimiza y qué se conserva con esa base legal.

2. **Reclamación por la atención recibida**: la traslado al
   Servicio de Atención al Cliente (Defensor del Cliente). En
   caso de no recibir respuesta o no estar conforme con ella,
   podrás dirigirte al Servicio de Reclamaciones de la CNMV o
   del Banco de España según el producto.

¿Confirmo el envío de ambos trámites a tu nombre?

Si quieres ejercer también acceso (art. 15), rectificación
(art. 16), portabilidad (art. 20) u oposición (art. 21),
indícamelo y los incluyo.
```

### 6.11 — `update_risk_profile` "cambiar perfil Indie a Metal" (profile change deflected)

**Conversation 218839 · pair 14a**

```
USER:  Quiero cambiar el perfil de mi cartera de Indie a Metal
A:     La información sobre carteras automatizadas, incluyendo cambios
       de perfil como de "Indie" a "Metal", no está disponible por el
       momento, pero será añadida próximamente.
```

**Compliance issues**

- MiFID II Art. 25(2): a profile change is legally consequential — it invalidates prior suitability and may make the existing portfolio mismatched with the new profile until rebalanced. "Información no disponible" misses the legal weight entirely.
- "Metal" is the firm's most aggressive automated portfolio (100% RV); the change implies a higher-risk allocation requiring a re-test of suitability.

**Compliant rewrite**

```
El cambio de perfil de cartera automatizada (de Indie a Metal)
no es solo administrativo: implica un cambio en el nivel de
riesgo de la inversión y exige actualizar el test de idoneidad
(MiFID II, art. 25). Pasar a Metal supone una asignación de
mayor riesgo (mayor exposición a renta variable y, por tanto,
mayor volatilidad y posibles pérdidas).

Para tramitar el cambio:

1. Realiza un nuevo test de idoneidad (≈5–10 minutos). El
   resultado debe ser compatible con el perfil "Metal"; si no
   lo es, no podremos asignarte esa cartera.
2. Recibirás el documento de **idoneidad actualizado** y el
   detalle de la composición prevista, con SRI, SFDR y costes
   ex-ante.
3. Confirmarás el cambio. La cartera se rebalanceará a la nueva
   composición; los movimientos generados pueden tener efectos
   fiscales (consulta a tu asesor fiscal sobre tu caso).

¿Quieres que te indique cómo iniciar el test ahora o prefieres
hablar con un asesor humano antes de cambiar el perfil?

Toda inversión conlleva riesgo, incluida la pérdida del capital
invertido. Rentabilidades pasadas no garantizan rentabilidades
futuras.
```

### 6.12 — `change_personal_details` activation/SMS not received (PSD2/SCA)

**Conversation 216544 · pair 20a**

```
USER:  Hola mi nombre es niurel Mendoza Espinosa he abierto una cuenta
       de my investor hace poco ayer me salió que me la activaron y que
       me mandaron un SMS al número de teléfono pero tengo problemas
       para recibir los SMS y me gustaría que me lo manden por correo
       electrónico ...
A:     Lamentablemente, no podemos enviar la información de activación
       de tu cuenta por correo electrónico. La activación de la cuenta
       y la firma electrónica se envían exclusivamente a través de SMS
       al número de teléfono que proporcionaste durante el registro. ...
       Si necesitas más ayuda, puedes comunicarte con nuestro servicio
       de atención al cliente al 910 005 981.
```

**Compliance issues**

- GDPR / minimisation: the user has put their full name in chat; the assistant should not echo PII back nor use it to respond.
- PSD2 SCA: the original answer is correct in principle (out-of-band channel) but should explain that this is a regulatory requirement (Strong Customer Authentication), not a firm preference.
- Fraud / impersonation: the request to redirect activation to email is a known account-takeover vector. The assistant must treat the request cautiously.

**Compliant rewrite**

```
Por motivos de seguridad y por la normativa europea de pagos
(PSD2, autenticación reforzada del cliente), las claves de
activación y la firma electrónica solo pueden enviarse al canal
verificado durante el registro (en tu caso, el teléfono móvil).
No podemos sustituir ese canal por email, ni siquiera de forma
puntual: ese cambio es precisamente uno de los vectores
habituales de fraude.

Te propongo dos vías seguras:

1. Recibir el SMS en el mismo número desde otro dispositivo o
   tras reiniciar el móvil, o solicitar reenvío desde la app.
2. Si el problema persiste, llama al 910 005 981 desde el
   número registrado para verificar tu identidad y, si es
   necesario, actualizar el teléfono asociado a tu cuenta por
   el procedimiento formal (con verificación reforzada de
   identidad).

Por tu seguridad, no compartas en este chat datos como DNI
completo, número de cuenta, claves SMS o contraseñas. La
información que ya has compartido la trataremos conforme a
nuestra política de privacidad.
```

---

## 7. Compliant-answer schema

Across the twelve cases, the rewrites follow the same skeleton. This becomes the rewriter's hard contract: every assistant turn classified MEDIUM or higher must produce output that fits this schema.

```
[1] Acknowledgment block
    Recognise the user's request without committing to a regulated act.

[2] Status block (mandatory when state is missing)
    State explicitly what is missing (profile, KYC, KID, identity, consent)
    and cite the relevant MiFID II / GDPR / AML / PSD2 article.

[3] Compliant payload (only what the state allows)
    - Information-only framing — no "para ti", no "el mejor", no
      superlatives bound to the user.
    - Standard fields (ISIN, SRI 1–7, SFDR Art., TER, currency).
    - Verbatim ESMA risk warnings (when published).
    - Past-performance + balanced presentation when returns appear.
    - Inducement disclosure when in-house product or focus-list
      mentioned.

[4] Required clauses (from the versioned library)
    Past-performance, capital-loss, KID-availability,
    no-personal-recommendation, no-tax-advice, FOGAIN, etc. —
    selected by the obligations engine, not by the LLM.

[5] Forbidden formulations check (validator)
    None of: "te recomiendo", "para ti", "el mejor", "te conviene",
    "deberías", "garantizado", "seguro" (in return-context),
    "sin riesgo", "no falla", "va a subir".

[6] Next-step routing
    Profiling flow / KID / KYC / human advisor / fraud channel /
    GDPR endpoint.

[7] Audit-log record (not user-visible)
    {service_mode_at_decision, profile_state, latent_triggers,
     personalisation_request_yes_no, frameworks_invoked,
     clauses_cited (with version IDs), forbidden_check,
     model_versions}.
```

---

## 8. Risk prioritisation and remediation

### 8.1 Severity ranking of identified risks

| Rank | Risk | Evidence | Frameworks | Severity |
|---|---|---|---|---|
| 1 | Recommendations / portfolio construction without suitability profile | 81.5% gating gap; explicit case in conv 234604 | MiFID II Art. 25 | Critical |
| 2 | Personalised tax statements ("no tiene impacto fiscal") | conv 216423 | LIRPF | High |
| 3 | Suspicious-activity reports redirected to user | conv 225789 | AML, PSD2, DORA | High |
| 4 | Conflict-of-interest denial with simultaneous in-house bias | conv 334603 | MiFID II Art. 23, RIS | High |
| 5 | GDPR erasure deflected to help page | conv 232966 | GDPR Art. 17 | High |
| 6 | Past-performance + "mejores" framing on product lists | conv 216303 | PRIIPs, MiFID II marketing, RIS | High |
| 7 | Risk-profile change deflected as "not available" | conv 218839 | MiFID II Art. 25 | High |
| 8 | High-amount portfolio proposal without AML / source-of-funds | conv 216335 | AML Ley 10/2010 | High |
| 9 | Sustainability preferences essentially absent from profiling | `state_esg_preference` = 1 in 246k | RIS, SFDR, MiFID II Del. Reg. 2021/1253 | Medium-High |
| 10 | Buy/sell flows missing ex-ante costs and KID references | conv 216630 | MiFID II Art. 24, PRIIPs | Medium |
| 11 | Account-detail change requests not framed as PSD2 SCA | conv 216544 | PSD2 | Medium |
| 12 | Firm-specific risk labels ("Muy Alto") instead of PRIIPs SRI | conv 216303 | PRIIPs | Medium |

### 8.2 Remediation priorities

1. **Profile-gate enforcement** for the eight HIGH-risk intents listed in §2.4. This is the single highest-value change: closes the 81.5% gating gap by routing every such turn through the conversation-level suitability state.
2. **Three-branch rewriter** for `request_recommendation` family (profile-missing / stale / complete). The profile-missing branch is the gold-set example in §6.1.
3. **Active firm-side action** on three deflected categories — fraud reports (§6.9), GDPR erasure (§6.10), CoI questions (§6.7) — replacing passive handling.
4. **Forbidden-formulations validator** as a deterministic post-check on every assistant output: blocks "te recomiendo", "para ti", "el mejor", "te conviene", "deberías", return-context "seguro" / "garantizado" / "sin riesgo".
5. **PRIIPs and SFDR data plumbing**: every product surfaced must carry SRI (1–7), SFDR article (6/8/9), TER and KID availability — not firm-specific labels.
6. **Sustainability-preferences capture** in the suitability questionnaire and surfacing in the chat (RIS readiness).
7. **Tax-personalisation guard**: every `explain_tax_implications` answer must include the "régimen general — no asesoramiento fiscal personalizado" closer.
8. **AML pattern checks** on size, destination, and source for `transfer_funds` / `withdraw_funds` / `request_portfolio_suggestion` over thresholds.
9. **PSD2 SCA framing** for any account-detail / payment-instrument / device change request.
10. **Audit-log enrichment** with the seven fields in §7[7] for regulator-ready records.

### 8.3 Operational metrics for ongoing monitoring

- **Gating-fidelity SLO**: for every conversation containing a HIGH-risk intent, the assistant's answer must reflect the SuitabilitySignals state at that turn. Target ≥ 99% on a held-out evaluation set.
- **Forbidden-token rate**: must be 0 on the curated negative list.
- **Compliance-fidelity**: ≥ 98% of HIGH-risk turns where the rewritten answer contains every required clause.
- **Implicit-to-explicit elevation rate**: fraction of conversations where an implicit signal in turn N caused the assistant to invite explicit profiling completion in turn N+1.
- **Forbidden-personalisation rate** in product-discovery turns: should be 0 post-rewrite.
- **Active firm-side action rate** on fraud / GDPR / CoI questions: target ≥ 95% (vs. deflection).
- **Information utility**: ≥ 4/5 in human review — rewrites must still answer the user's underlying question whenever the regulatory floor allows it.

---

## 9. Caveats

- Implicit-signal counts in §2.2 carry lexical noise (`seguro`, `€`, `años`/`meses`) that inflate them; true coverage is lower, which makes the gating gap more severe.
- Classifier confidence on profiling intents is moderate (several leaves with majority of rows < 0.7); a low-confidence detector firing on `refuse_to_answer_profiling` text must fail safe to gating, not to advice.
- The two profiling-rich conversations identified (IDs 240153, 349192) are advisor-side or test scenarios, not typical client interactions.
- The Retail Investment Strategy is in transposition; ESMA standardised risk-warning wording is being published progressively and must be incorporated verbatim into the clause library as it is released.
- This analysis is grounded on a single classification run (run 4) using the FII v1 taxonomy. Re-classification with a refined taxonomy (e.g., a sub-classifier for `report_suspicious_activity` to separate true SAR-relevant content from generic "I have a problem") is recommended.
