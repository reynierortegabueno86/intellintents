import logging
import os
import random
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# ── Logging configuration ─────────────────────────────────────────
# Set LOGLEVEL env var to control verbosity: DEBUG, INFO, WARNING (default)
_log_level = os.getenv("LOGLEVEL", "WARNING").upper()
logging.basicConfig(
    level=_log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import Base, engine, get_db
from app.models.models import (
    Classification,
    Conversation,
    Dataset,
    IntentCategory,
    IntentTaxonomy,
    Turn,
)
from app.models.models import Run
from app.routers import analytics, classification, datasets, experiments, taxonomy
from app.classifiers.rule_based import RuleBasedClassifier

_logger = logging.getLogger(__name__)


async def _migrate_taxonomy_columns(conn):
    """Add new taxonomy/category columns to existing tables (safe, idempotent)."""

    def _sync_migrate(connection):
        raw = connection.connection.dbapi_connection
        cur = raw.cursor()

        def _has_column(table, column):
            cur.execute(f"PRAGMA table_info({table})")
            return any(row[1] == column for row in cur.fetchall())

        # IntentTaxonomy new columns
        for col, ddl in [
            ("tags", "TEXT"),
            ("metadata_json", "TEXT"),
            ("priority", "INTEGER DEFAULT 0"),
            ("version", "INTEGER DEFAULT 1 NOT NULL"),
            ("updated_at", "DATETIME"),
        ]:
            if not _has_column("intent_taxonomies", col):
                cur.execute(f"ALTER TABLE intent_taxonomies ADD COLUMN {col} {ddl}")

        # IntentCategory new columns
        for col, ddl in [
            ("priority", "INTEGER DEFAULT 0"),
            ("examples", "TEXT"),
        ]:
            if not _has_column("intent_categories", col):
                cur.execute(f"ALTER TABLE intent_categories ADD COLUMN {col} {ddl}")

        raw.commit()

    await conn.run_sync(_sync_migrate)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Migrate existing tables to add new columns
    async with engine.begin() as conn:
        await _migrate_taxonomy_columns(conn)

    # Clean up orphaned runs (stuck as "running" or "pending" from a previous crash)
    from app.database import async_session
    async with async_session() as db:
        from sqlalchemy import update
        result = await db.execute(
            update(Run)
            .where(Run.status.in_(["running", "pending"]))
            .values(status="failed", results_summary='{"error": "Server restarted while run was in progress"}')
        )
        if result.rowcount > 0:
            await db.commit()
            _logger.info("Marked %d orphaned run(s) as failed on startup", result.rowcount)

    yield


app = FastAPI(
    title="IntelliIntents API",
    description="Conversation Intelligence & Intent Analytics Platform",
    version="1.0.0",
    lifespan=lifespan,
)

_cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all routers under /api so they work both:
# - In dev: Vite proxy rewrites /api/... -> /... (backend sees /api/datasets)
# - In prod: frontend calls /api/... directly (same server)
# We mount on BOTH /api and / for backward compatibility with dev proxy.
from fastapi import APIRouter as _APIRouter

_api_router = _APIRouter(prefix="/api")
_api_router.include_router(datasets.router)
_api_router.include_router(taxonomy.router)
_api_router.include_router(classification.router)
_api_router.include_router(analytics.router)
_api_router.include_router(experiments.router)
app.include_router(_api_router)

# Also mount without prefix so existing dev proxy (which strips /api) still works
app.include_router(datasets.router)
app.include_router(taxonomy.router)
app.include_router(classification.router)
app.include_router(analytics.router)
app.include_router(experiments.router)


@app.get("/")
async def root():
    return {
        "name": "IntelliIntents API",
        "version": "1.0.0",
        "description": "Conversation Intelligence & Intent Analytics Platform",
        "endpoints": {
            "datasets": "/datasets",
            "taxonomies": "/taxonomies",
            "classification": "/classify",
            "analytics": "/analytics",
            "experiments": "/experiments",
            "docs": "/docs",
        },
    }


# ---------------------------------------------------------------------------
# Seed demo data
# ---------------------------------------------------------------------------

DEMO_TAXONOMY_CATEGORIES = [
    {
        "name": "Greeting",
        "description": "Initial greetings and salutations at the start of a conversation",
        "color": "#4CAF50",
    },
    {
        "name": "Information Request",
        "description": "Asking for details, documentation, or how-to guidance",
        "color": "#2196F3",
    },
    {
        "name": "Technical Problem",
        "description": "Reporting errors, crashes, slowness, or technical difficulties",
        "color": "#F44336",
    },
    {
        "name": "Bug Report",
        "description": "Formally reporting a software defect with reproduction steps",
        "color": "#E91E63",
    },
    {
        "name": "Purchase Intent",
        "description": "Interest in buying, upgrading, pricing, or subscription plans",
        "color": "#9C27B0",
    },
    {
        "name": "Cancellation",
        "description": "Requesting to cancel subscription, close account, or unsubscribe",
        "color": "#FF9800",
    },
    {
        "name": "Complaint",
        "description": "Expressing dissatisfaction, frustration, or negative feedback",
        "color": "#795548",
    },
    {
        "name": "Feedback",
        "description": "Providing suggestions, positive feedback, or feature requests",
        "color": "#00BCD4",
    },
    {
        "name": "Configuration Help",
        "description": "Asking for help with setup, installation, integration, or configuration",
        "color": "#607D8B",
    },
    {
        "name": "Account Issue",
        "description": "Problems with login, password reset, access permissions, or authentication",
        "color": "#FF5722",
    },
]

# Realistic conversation templates: each is a list of (speaker, text) tuples
# that will be randomly selected and varied.
_CONVERSATION_TEMPLATES = [
    # Greeting -> Info Request -> Feedback
    [
        ("customer", "Hello, I'm hoping you can help me with something."),
        ("agent", "Hi there! Of course, I'd be happy to help. What can I do for you?"),
        ("customer", "Can you tell me about your enterprise plan pricing and what features are included?"),
        ("agent", "Our enterprise plan starts at $99/month and includes unlimited users, priority support, and advanced analytics. Would you like a detailed breakdown?"),
        ("customer", "That sounds great, thanks for the detailed information!"),
    ],
    # Greeting -> Technical Problem -> Configuration Help
    [
        ("customer", "Hi, good morning. I'm having a terrible time with your application."),
        ("agent", "Good morning! I'm sorry to hear that. Could you describe the issue you're experiencing?"),
        ("customer", "The app keeps crashing whenever I try to export a report. I get a timeout error every single time."),
        ("agent", "That sounds like it could be a configuration issue. Let me walk you through adjusting the export timeout setting."),
        ("customer", "How do I configure the timeout setting? I looked in the settings but couldn't find it."),
        ("agent", "Go to Settings > Advanced > API Configuration and increase the timeout value to 120 seconds. That should resolve the export crashes."),
        ("customer", "Got it, I'll try that now. Thanks for the help."),
    ],
    # Greeting -> Account Issue
    [
        ("customer", "Hey, I can't log in to my account. It says my password is incorrect but I'm sure it's right."),
        ("agent", "Hello! I'm sorry about the login trouble. Let me look into your account. Can you provide your email?"),
        ("customer", "Sure, it's john.doe@example.com. I've tried resetting my password twice with no luck."),
        ("agent", "I can see your account was temporarily locked due to multiple failed attempts. I've unlocked it and sent a fresh password reset link to your email."),
        ("customer", "Thank you, I just got the email and I'm back in!"),
    ],
    # Purchase Intent -> Information Request
    [
        ("customer", "Hi, I'm interested in upgrading from the free tier to a paid plan."),
        ("agent", "Great to hear! We have three paid plans. What's the size of your team?"),
        ("customer", "We're about 25 people. What would you recommend? Also, is there a discount for annual billing?"),
        ("agent", "For a team of 25, the Business plan at $49/user/month would be ideal. Annual billing gets you a 20% discount."),
        ("customer", "That sounds reasonable. Can I get a trial of the Business plan before we commit to purchasing?"),
        ("agent", "Absolutely! I can set up a 14-day free trial right now. You'll have full access to all Business features."),
    ],
    # Complaint -> Bug Report
    [
        ("customer", "I'm extremely frustrated with your service. This is unacceptable."),
        ("agent", "I'm really sorry to hear you're frustrated. Please tell me what happened and I'll do my best to resolve it."),
        ("customer", "I've found a bug where the dashboard shows wrong data. When I click on the weekly view, it shows last month's data instead. This is a serious defect."),
        ("agent", "Thank you for reporting this. I can reproduce the issue. I'll file this as a high-priority bug report. Can you tell me which browser you're using?"),
        ("customer", "Chrome version 120 on Windows 11. The expected behavior is to show this week's data but actual shows October data."),
        ("agent", "I've documented the steps to reproduce and escalated this to our engineering team. You should see a fix within 48 hours."),
    ],
    # Cancellation
    [
        ("customer", "Hello, I'd like to cancel my subscription please."),
        ("agent", "I'm sorry to see you go. May I ask what's prompting you to cancel?"),
        ("customer", "The price is too high for what we're getting and we've had too many issues with reliability."),
        ("agent", "I understand your concerns. Would you be interested in a 50% discount for the next 3 months while we address the reliability issues?"),
        ("customer", "No thanks, I've already decided. Please just cancel my account and stop all billing."),
        ("agent", "I've processed your cancellation. Your account will remain active until the end of your current billing period. You'll receive a confirmation email shortly."),
    ],
    # Configuration Help -> Technical Problem
    [
        ("customer", "Hi, I need help setting up the API integration with our Salesforce instance."),
        ("agent", "Sure! Do you have your API key and the Salesforce credentials ready?"),
        ("customer", "Yes, I have the API key. Where do I enter the credentials for the integration?"),
        ("agent", "Navigate to Integrations > Salesforce > Configure. Enter your Salesforce org URL, username, and the security token."),
        ("customer", "I did that but now I'm getting an error that says 'Connection refused'. The integration doesn't work."),
        ("agent", "That error usually means your firewall is blocking the connection. You'll need to whitelist our IP range: 10.0.1.0/24."),
        ("customer", "OK I'll ask our IT team to update the firewall rules. Thanks."),
    ],
    # Feedback
    [
        ("customer", "Hi, I just wanted to say that the new dashboard redesign is awesome!"),
        ("agent", "Thank you so much! We're glad you're enjoying it. Any specific features you love?"),
        ("customer", "The real-time analytics are amazing. I do have a suggestion though - it would be nice if you could add a dark mode option."),
        ("agent", "That's great feedback! Dark mode is actually on our roadmap. I'll make sure your request is noted. Would you like to be notified when it launches?"),
        ("customer", "Yes please, that would be great. Keep up the good work!"),
    ],
    # Technical Problem -> Complaint
    [
        ("customer", "Your app has been incredibly slow for the past three days. What's going on?"),
        ("agent", "I apologize for the performance issues. We've been experiencing higher than normal load. Can you tell me which features are slowest?"),
        ("customer", "Everything is slow but especially the search function. It takes over 30 seconds to return results. This is completely unacceptable for a paid product."),
        ("agent", "I completely understand your frustration. Our team is actively working on optimizing the search infrastructure. We expect improvements within 24 hours."),
        ("customer", "I'm very disappointed with this service. If it's not fixed soon, I'll be looking at alternatives."),
    ],
    # Information Request -> Purchase Intent -> Greeting
    [
        ("customer", "Good afternoon! Could you explain the difference between your Standard and Pro plans?"),
        ("agent", "Good afternoon! The Standard plan includes 10GB storage and basic analytics. The Pro plan offers 100GB, advanced analytics, and priority support."),
        ("customer", "What about the API rate limits? We process about 10,000 requests per day."),
        ("agent", "Standard allows 5,000 requests/day and Pro allows 50,000. For your volume, Pro would be the right choice."),
        ("customer", "Perfect, I'd like to purchase the Pro plan for our team of 15 users."),
        ("agent", "Excellent choice! I'll get that set up right away. You'll receive the invoice via email."),
        ("customer", "Thank you so much for the help, have a great day!"),
        ("agent", "You too! Welcome aboard and don't hesitate to reach out if you need anything."),
    ],
    # Account Issue -> Configuration Help
    [
        ("customer", "I can't access the admin panel. It keeps saying I don't have permission."),
        ("agent", "Let me check your account permissions. What's your username?"),
        ("customer", "It's admin@ourcompany.com. I should have full admin access."),
        ("agent", "I see the issue - your role was accidentally changed to 'viewer' during a recent system update. I've restored your admin permissions."),
        ("customer", "Thanks! Now that I'm in, how do I configure the SSO settings for our team?"),
        ("agent", "Go to Admin > Security > Single Sign-On. You'll need your identity provider's metadata URL and certificate."),
    ],
    # Bug Report -> Technical Problem
    [
        ("customer", "I want to report a bug. When I upload a CSV file with more than 1000 rows, the application crashes."),
        ("agent", "Thank you for the report. Can you share the exact error message you see?"),
        ("customer", "The error says 'Memory allocation failed: exceeded maximum buffer size'. Steps to reproduce: go to Import, select any CSV over 1000 rows, click Upload."),
        ("agent", "I've reproduced this. It's a known limitation we're patching. As a workaround, you can split your CSV into chunks of 500 rows."),
        ("customer", "That's not ideal but I'll use the workaround for now. When will the fix be deployed?"),
    ],
    # Greeting -> Cancellation -> Feedback
    [
        ("customer", "Hi there, I need to discuss my subscription."),
        ("agent", "Hello! Of course, what would you like to discuss?"),
        ("customer", "I'm thinking about cancelling. The tool is good but we simply don't use it enough to justify the cost."),
        ("agent", "I understand. Have you considered our Pay-As-You-Go plan? You'd only be charged for actual usage."),
        ("customer", "Oh, I didn't know that existed. That could work for us actually. Can you switch me to that plan?"),
        ("agent", "Done! You're now on the Pay-As-You-Go plan. Your next bill will only reflect actual usage."),
        ("customer", "That's a much better fit. Thanks for the suggestion. You should make that option more visible on your pricing page."),
    ],
]

# Additional varied customer messages for randomization
_EXTRA_OPENINGS = [
    ("customer", "Hello! I need some assistance please."),
    ("customer", "Hi, is anyone available to help?"),
    ("customer", "Good morning, I have a quick question."),
    ("customer", "Hey there, hoping you can help me out."),
    ("customer", "Hi, I'm a new customer and need some guidance."),
]

_EXTRA_TECH_PROBLEMS = [
    ("customer", "The notification system is completely broken. I haven't received any alerts in two days."),
    ("customer", "Every time I save a document, it corrupts the formatting. This is really frustrating."),
    ("customer", "The mobile app crashes on startup since the last update. I've tried reinstalling twice."),
    ("customer", "Our webhooks stopped firing yesterday. No errors in the logs, they just silently fail."),
    ("customer", "The file upload feature returns a 502 error for any file larger than 5MB."),
]

_EXTRA_INFO_REQUESTS = [
    ("customer", "Can you explain how the billing cycle works? When exactly do charges appear?"),
    ("customer", "What's the difference between team workspaces and shared projects?"),
    ("customer", "How does the data retention policy work? How long do you keep our data?"),
    ("customer", "I'm looking for documentation on the REST API. Where can I find that?"),
]

_EXTRA_COMPLAINTS = [
    ("customer", "I'm really unhappy with the response time from your support team. This is the third time I've reached out."),
    ("customer", "Your product quality has declined significantly since the last major update. Very disappointed."),
    ("customer", "The downtime this week has been ridiculous. We lost revenue because of your service being unavailable."),
]


def _build_varied_conversation(rng: random.Random, idx: int) -> list:
    """Build a slightly varied conversation by selecting a template and optionally modifying it."""
    template = rng.choice(_CONVERSATION_TEMPLATES)
    # Deep copy
    conv = [(s, t) for s, t in template]

    # Occasionally prepend an extra opening
    if rng.random() < 0.3:
        opening = rng.choice(_EXTRA_OPENINGS)
        conv.insert(0, opening)

    # Occasionally append extra turns
    if rng.random() < 0.25:
        extra_pool = _EXTRA_TECH_PROBLEMS + _EXTRA_INFO_REQUESTS + _EXTRA_COMPLAINTS
        extra = rng.choice(extra_pool)
        conv.append(extra)
        conv.append(("agent", "Thank you for letting us know. I'll look into that right away and follow up with you."))

    # Occasionally truncate for shorter convos
    if rng.random() < 0.15 and len(conv) > 3:
        conv = conv[: rng.randint(3, len(conv) - 1)]

    return conv


@app.post("/api/seed-demo")
@app.post("/seed-demo")
async def seed_demo(db: AsyncSession = Depends(get_db)):
    """Create demo taxonomy and dataset with ~50 conversations, then auto-classify."""
    # Check if demo data already exists
    existing = await db.execute(
        select(IntentTaxonomy).where(IntentTaxonomy.name == "Customer Support Intents")
    )
    if existing.scalar_one_or_none():
        return {"detail": "Demo data already exists. Delete existing data first to re-seed."}

    # --- Create taxonomy ---
    taxonomy = IntentTaxonomy(
        name="Customer Support Intents",
        description="Standard taxonomy for classifying customer support conversation intents",
    )
    db.add(taxonomy)
    await db.flush()

    cat_objects = []
    for cat_data in DEMO_TAXONOMY_CATEGORIES:
        cat = IntentCategory(
            taxonomy_id=taxonomy.id,
            name=cat_data["name"],
            description=cat_data["description"],
            color=cat_data["color"],
        )
        db.add(cat)
        cat_objects.append(cat)
    await db.flush()

    # --- Create dataset with ~50 conversations ---
    dataset = Dataset(
        name="Demo Support Conversations",
        description="Auto-generated demo dataset with 50 realistic customer support conversations",
        file_type="json",
        row_count=0,
    )
    db.add(dataset)
    await db.flush()

    rng = random.Random(42)
    total_turns = 0
    all_turns = []

    for i in range(50):
        conv_turns = _build_varied_conversation(rng, i)
        conversation = Conversation(
            dataset_id=dataset.id,
            external_id=f"demo-conv-{i + 1:03d}",
            turn_count=len(conv_turns),
        )
        db.add(conversation)
        await db.flush()

        for turn_idx, (speaker, text) in enumerate(conv_turns):
            turn = Turn(
                conversation_id=conversation.id,
                turn_index=turn_idx,
                speaker=speaker,
                text=text,
            )
            db.add(turn)
            all_turns.append(turn)
            total_turns += 1

    dataset.row_count = total_turns
    await db.flush()

    # --- Auto-classify using rule-based classifier ---
    taxonomy_categories = [
        {"name": c.name, "description": c.description or ""} for c in cat_objects
    ]
    classifier = RuleBasedClassifier()

    for turn in all_turns:
        label, confidence, explanation = classifier.classify_turn(
            turn.text, taxonomy_categories
        )
        cls = Classification(
            turn_id=turn.id,
            taxonomy_id=taxonomy.id,
            intent_label=label,
            confidence=confidence,
            method="rule_based",
            explanation=explanation,
        )
        db.add(cls)

    await db.commit()

    return {
        "detail": "Demo data created successfully",
        "taxonomy_id": taxonomy.id,
        "dataset_id": dataset.id,
        "conversations": 50,
        "total_turns": total_turns,
        "classifications": total_turns,
    }


# ---------------------------------------------------------------------------
# Serve frontend static build (production mode)
# ---------------------------------------------------------------------------
# When the frontend is built (npm run build -> frontend/dist/), serve it
# from the same FastAPI server so only ONE port is needed.
_FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

if _FRONTEND_DIST.is_dir():
    # Serve static assets (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=_FRONTEND_DIST / "assets"), name="static-assets")

    # Catch-all: serve index.html for any non-API route (SPA client-side routing)
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # If the file exists in dist, serve it (e.g. favicon, manifest)
        file_path = _FRONTEND_DIST / full_path
        if full_path and file_path.is_file():
            return FileResponse(file_path)
        # Otherwise serve index.html for client-side routing
        return FileResponse(_FRONTEND_DIST / "index.html")
