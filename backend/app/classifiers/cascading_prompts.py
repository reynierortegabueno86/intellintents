"""
Cascading Intent Classifier — Prompt Loader

Loads Stage 1 (top-level category) and Stage 2 (sub-intent) system prompts
from external .txt files in the ``prompts/`` directory.  Prompts are read once
at import time and cached in module-level constants.

File layout expected under ``prompts/``:
    stage1_system.txt
    stage2_onboarding_kyc.txt
    stage2_investor_profiling.txt
    stage2_product_discovery.txt
    stage2_recommendation_advisory.txt
    stage2_execution_transactions.txt
    stage2_portfolio_monitoring.txt
    stage2_financial_education.txt
    stage2_account_service_management.txt
    stage2_regulatory_compliance.txt
    stage2_greeting.txt
    stage2_small_talk.txt
    stage2_out_of_scope.txt
    stage2_harmful_unethical_communication.txt
    stage2_unknown.txt
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt directory — sibling ``prompts/`` folder next to this module
# ---------------------------------------------------------------------------
_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def _load_prompt(filename: str) -> str:
    """Read a prompt file from the prompts directory.

    Raises ``FileNotFoundError`` with a clear message if the file is missing.
    """
    path = _PROMPTS_DIR / filename
    if not path.is_file():
        raise FileNotFoundError(
            f"Prompt file not found: {path}. "
            f"Ensure the 'prompts/' directory exists alongside the classifiers package."
        )
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"Prompt file is empty: {path}")
    logger.debug("Loaded prompt from %s (%d chars)", path, len(text))
    return text


# ---------------------------------------------------------------------------
# Stage 1
# ---------------------------------------------------------------------------
STAGE1_SYSTEM_PROMPT: str = _load_prompt("stage1_system.txt")

# ---------------------------------------------------------------------------
# Stage 2 — one prompt per top-level category
# ---------------------------------------------------------------------------
_STAGE2_FILES = {
    "ONBOARDING_KYC": "stage2_onboarding_kyc.txt",
    "INVESTOR_PROFILING": "stage2_investor_profiling.txt",
    "PRODUCT_DISCOVERY": "stage2_product_discovery.txt",
    "RECOMMENDATION_ADVISORY": "stage2_recommendation_advisory.txt",
    "EXECUTION_TRANSACTIONS": "stage2_execution_transactions.txt",
    "PORTFOLIO_MONITORING": "stage2_portfolio_monitoring.txt",
    "FINANCIAL_EDUCATION": "stage2_financial_education.txt",
    "ACCOUNT_SERVICE_MANAGEMENT": "stage2_account_service_management.txt",
    "REGULATORY_COMPLIANCE": "stage2_regulatory_compliance.txt",
    "GREETING": "stage2_greeting.txt",
    "SMALL_TALK": "stage2_small_talk.txt",
    "OUT_OF_SCOPE": "stage2_out_of_scope.txt",
    "HARMFUL_UNETHICAL_COMMUNICATION": "stage2_harmful_unethical_communication.txt",
    "UNKNOWN": "stage2_unknown.txt",
}

STAGE2_PROMPTS: dict[str, str] = {
    category: _load_prompt(filename)
    for category, filename in _STAGE2_FILES.items()
}

# ---------------------------------------------------------------------------
# Valid sub-intents per category (for response validation)
# ---------------------------------------------------------------------------
CATEGORY_INTENTS: dict[str, list[str]] = {
    "ONBOARDING_KYC": [
        "open_account", "verify_identity", "upload_document",
        "check_eligibility", "age_limit", "link_bank_account",
    ],
    "INVESTOR_PROFILING": [
        "state_risk_tolerance", "state_investment_goal", "state_investment_horizon",
        "state_financial_situation", "state_experience_level", "state_esg_preference",
        "update_risk_profile", "refuse_to_answer_profiling",
    ],
    "PRODUCT_DISCOVERY": [
        "explore_product_types", "compare_products", "ask_product_features",
        "ask_product_risk", "ask_product_performance", "ask_product_eligibility",
        "filter_by_criteria", "ask_esg_classification",
    ],
    "RECOMMENDATION_ADVISORY": [
        "request_recommendation", "request_portfolio_suggestion", "ask_why_recommended",
        "request_alternative", "accept_recommendation", "reject_recommendation",
        "request_human_advisor", "request_rebalance_advice",
    ],
    "EXECUTION_TRANSACTIONS": [
        "buy_investment", "sell_investment", "set_recurring_investment",
        "cancel_order", "check_order_status", "transfer_funds", "withdraw_funds",
    ],
    "PORTFOLIO_MONITORING": [
        "check_portfolio_value", "check_holdings", "check_performance",
        "check_gains_losses", "set_alert", "request_statement", "ask_dividend_info",
    ],
    "FINANCIAL_EDUCATION": [
        "explain_concept", "explain_instrument", "explain_risk",
        "explain_strategy", "explain_market_event", "explain_regulation",
        "explain_tax_implications",
    ],
    "ACCOUNT_SERVICE_MANAGEMENT": [
        "change_personal_details", "change_password", "ask_about_fees",
        "file_complaint", "escalate_to_human", "terminate_account",
        "ask_service_hours", "ask_security",
    ],
    "REGULATORY_COMPLIANCE": [
        "request_risk_disclaimer", "request_data_access", "request_data_deletion",
        "confirm_suitability", "ask_about_investor_protection",
        "ask_about_conflicts_of_interest", "report_suspicious_activity",
    ],
    "GREETING": [
        "opening", "closing", "phatic",
    ],
    "SMALL_TALK": [
        "agent_identity", "agent_personality", "user_feelings",
        "chitchat", "app_feedback",
    ],
    "OUT_OF_SCOPE": [
        "non_financial_topic", "unsupported_financial_domain",
        "technical_capability_limit", "legal_or_policy_restricted",
        "noise_unintelligible",
    ],
    "HARMFUL_UNETHICAL_COMMUNICATION": [
        "harm_hate_lgbtiqphobia", "harm_hate_gender_based",
        "harm_hate_stereotypes_prejudice", "harm_toxic_insults_general",
    ],
    "UNKNOWN": [
        "none",
    ],
}
