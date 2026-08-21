"""
Marketing Posts Engine
Generates daily marketing post drafts from deterministic templates,
customizable by company name, industry, tone, channel, and CTA.

No LLM calls — pure template generation so it works in published pplx.app sites.
"""

import os
import sqlite3
import json
import random
from datetime import datetime, date
from typing import Dict, Any, List, Optional

# Use db.py abstraction when available
try:
    import db as _db
except ImportError:
    _db = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data.db")

# ---------------------------------------------------------------------------
# Channel formats: character limits and formatting conventions
# ---------------------------------------------------------------------------

CHANNELS = {
    "facebook":  {"max_chars": 2000, "emoji_friendly": True,  "hashtag_limit": 5},
    "instagram": {"max_chars": 2200, "emoji_friendly": True,  "hashtag_limit": 10},
    "linkedin":  {"max_chars": 3000, "emoji_friendly": False, "hashtag_limit": 3},
    "email":     {"max_chars": 5000, "emoji_friendly": False, "hashtag_limit": 0},
    "sms":       {"max_chars": 160,  "emoji_friendly": True,  "hashtag_limit": 0},
    "google":    {"max_chars": 300,  "emoji_friendly": False,  "hashtag_limit": 0},
}

TONES = ["professional", "friendly", "educational", "promotional", "storytelling", "urgent"]

# ---------------------------------------------------------------------------
# Daily themes — 7-day rotation so each day of the week has a focus
# ---------------------------------------------------------------------------

DAILY_THEMES = [
    {"day": "Monday",    "theme": "Educational Tip",       "focus": "Share a useful tip related to your industry"},
    {"day": "Tuesday",   "theme": "Customer Spotlight",    "focus": "Highlight a success story or testimonial"},
    {"day": "Wednesday", "theme": "Behind the Scenes",     "focus": "Show your process, team, or workspace"},
    {"day": "Thursday",  "theme": "FAQ / Common Question",  "focus": "Answer a question your customers often ask"},
    {"day": "Friday",    "theme": "Special Offer",         "focus": "Promote a deal, discount, or seasonal offer"},
    {"day": "Saturday",  "theme": "Community Involvement", "focus": "Share local events, charity work, or community ties"},
    {"day": "Sunday",    "theme": "Week Ahead Preview",    "focus": "Tease upcoming projects, services, or availability"},
]

# ---------------------------------------------------------------------------
# Template library — each template uses {placeholders}
# Placeholders: {company}, {industry}, {offer}, {cta}, {tip}, {question},
#               {answer}, {testimonial}, {event}, {preview}, {phone}, {location}
# ---------------------------------------------------------------------------

TEMPLATES = {
    "Educational Tip": [
        "💡 Did you know? {tip}\n\nAt {company}, we help {industry} clients every day with exactly this. {cta}",
        "Here's a quick {industry} tip for your home or business:\n\n{tip}\n\nWant expert help? {cta}",
        "🧠 Knowledge drop: {tip}\n\nThis is one of the most common things we see as a {industry} company. {cta}",
    ],
    "Customer Spotlight": [
        "⭐ Customer Spotlight:\n\n\"{testimonial}\"\n\nThank you for trusting {company} with your {industry} needs! {cta}",
        "Another happy {company} customer!\n\n\"{testimonial}\"\n\nThis is what we love about serving the {industry} community. {cta}",
        "Real results, real people:\n\n{testimonial}\n\n— another successful {industry} project by {company}. {cta}",
    ],
    "Behind the Scenes": [
        "🔧 Behind the scenes at {company}:\n\n{tip}\n\nQuality {industry} work takes preparation and the right team. {cta}",
        "Ever wonder what goes into a {industry} project? Here's a look at what our team does behind the scenes:\n\n{tip}\n\n{cta}",
        "📸 A day in the life at {company}:\n\n{tip}\n\nWe take pride in every {industry} job we do. {cta}",
    ],
    "FAQ / Common Question": [
        "❓ FAQ: {question}\n\n{answer}\n\nHave more questions? {cta}",
        "We get asked this all the time:\n\nQ: {question}\nA: {answer}\n\n{company} is here to help. {cta}",
        "Common {industry} question: \"{question}\"\n\nHere's the answer: {answer}\n\nStill curious? {cta}",
    ],
    "Special Offer": [
        "🔥 Special Offer from {company}!\n\n{offer}\n\n{cta}",
        "Limited time: {offer}\n\nDon't miss out — {cta}",
        "🎉 Deal alert!\n\n{offer}\n\nFrom your local {industry} experts at {company}. {cta}",
    ],
    "Community Involvement": [
        "🏡 Proud to be part of the {location} community!\n\n{event}\n\n{company} — your local {industry} partner. {cta}",
        "We love supporting our community:\n\n{event}\n\nAt {company}, {industry} is our business but community is our heart. {cta}",
        "Community matters to us:\n\n{event}\n\nThanks for supporting {company} and our {industry} neighbors. {cta}",
    ],
    "Week Ahead Preview": [
        "📅 Looking ahead this week at {company}:\n\n{preview}\n\nBook your {industry} project early — {cta}",
        "What's coming up:\n\n{preview}\n\n{company} is ready to serve your {industry} needs. {cta}",
        "Here's what's on our schedule:\n\n{preview}\n\nNeed {industry} services this week? {cta}",
    ],
}

# ---------------------------------------------------------------------------
# Default content — used when no customization is provided
# ---------------------------------------------------------------------------

DEFAULTS = {
    "tip": "Regular maintenance inspections can catch small issues before they become expensive repairs.",
    "testimonial": "They showed up on time, did excellent work, and cleaned up perfectly. Highly recommend!",
    "question": "How often should I get an inspection?",
    "answer": "We recommend at least once a year, or before any major season change. Regular inspections catch problems early and save you money.",
    "offer": "Schedule a free consultation this month and get 10% off your first project!",
    "event": "We're sponsoring the local community fair this weekend — come say hi!",
    "preview": "We have openings for new project estimates and our team is ready to help with spring repairs.",
    "cta": "Call us today to schedule your free estimate!",
    "phone": "(303) 555-0100",
    "location": "Aurora",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_db_conn():
    """Get a database connection (Postgres or SQLite)."""
    if _db and _db.DB_TYPE == "postgres":
        return _db.get_conn()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _return_db_conn(conn):
    """Return a connection to the pool (Postgres only)."""
    if _db and _db.DB_TYPE == "postgres":
        _db.return_conn(conn)
        return
    conn.close()

def _get_business_config() -> Dict[str, Any]:
    """Load business config from database."""
    try:
        conn = _get_db_conn()
        row = conn.execute("SELECT * FROM business_config WHERE id=1").fetchone()
        _return_db_conn(conn)
        if row:
            return dict(row)
    except Exception:
        pass
    return {
        "business_name": "Your Company",
        "industry": "Home Services",
        "primary_objective": "Grow revenue",
    }

def _fill_template(template: str, ctx: Dict[str, str]) -> str:
    """Replace all {placeholders} in a template string."""
    result = template
    for key, value in ctx.items():
        result = result.replace(f"{{{key}}}", value)
    # Clean up any unfilled placeholders
    for key in ["company", "industry", "offer", "cta", "tip", "question",
                "answer", "testimonial", "event", "preview", "phone", "location"]:
        result = result.replace(f"{{{key}}}", DEFAULTS.get(key, ""))
    return result.strip()

def _truncate(text: str, max_chars: int) -> str:
    """Truncate text to max_chars, adding ellipsis if needed."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars - 3].rsplit(" ", 1)[0] + "..."

def _add_hashtags(text: str, industry: str, channel: str, limit: int) -> str:
    """Add relevant hashtags based on industry and channel."""
    if limit == 0:
        return text
    base_tags = [industry.lower().replace(" ", "").replace("&", "and"),
                 "localbusiness", "homedesign", "colorado"]
    tags = [f"#{t}" for t in base_tags[:limit]]
    return f"{text}\n\n{' '.join(tags)}"

# ---------------------------------------------------------------------------
# Main generation function
# ---------------------------------------------------------------------------

def generate_daily_posts(
    company: Optional[str] = None,
    industry: Optional[str] = None,
    tone: str = "friendly",
    channel: str = "facebook",
    cta: Optional[str] = None,
    offer: Optional[str] = None,
    target_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate 7 daily marketing posts (one per day of the week).
    Returns a dict with posts array and metadata.
    """
    config = _get_business_config()
    company = company or config.get("business_name", "Your Company")
    industry = industry or config.get("industry", "Home Services")
    cta = cta or DEFAULTS["cta"]
    offer = offer or DEFAULTS["offer"]

    # Parse target date or use today
    if target_date:
        try:
            base_date = datetime.strptime(target_date, "%Y-%m-%d").date()
        except ValueError:
            base_date = date.today()
    else:
        base_date = date.today()

    channel_info = CHANNELS.get(channel, CHANNELS["facebook"])

    # Build context for templates
    ctx = {
        "company": company,
        "industry": industry,
        "offer": offer,
        "cta": cta,
        "tip": DEFAULTS["tip"],
        "question": DEFAULTS["question"],
        "answer": DEFAULTS["answer"],
        "testimonial": DEFAULTS["testimonial"],
        "event": DEFAULTS["event"],
        "preview": DEFAULTS["preview"],
        "phone": DEFAULTS["phone"],
        "location": DEFAULTS["location"],
    }

    posts = []
    for i, day_theme in enumerate(DAILY_THEMES):
        # Calculate the date for this day
        post_date = base_date + __import__("datetime").timedelta(days=i)
        day_name = post_date.strftime("%A")

        # Find the theme for this day
        theme_entry = next((t for t in DAILY_THEMES if t["day"] == day_name), DAILY_THEMES[i])

        theme = theme_entry["theme"]
        focus = theme_entry["focus"]

        # Pick a template for this theme
        templates = TEMPLATES.get(theme, TEMPLATES["Educational Tip"])
        template = random.choice(templates)

        # Generate the post content
        content = _fill_template(template, ctx)

        # Apply channel formatting
        if channel_info["emoji_friendly"] is False:
            # Strip emoji for LinkedIn/email
            import re
            content = re.sub(r'[\U0001F300-\U0001F9FF\U00002600-\U000027BF]+', '', content).strip()

        # Add hashtags
        content = _add_hashtags(content, industry, channel, channel_info["hashtag_limit"])

        # Truncate to channel limit
        content = _truncate(content, channel_info["max_chars"])

        posts.append({
            "id": f"post-{post_date.strftime('%Y%m%d')}-{i}",
            "date": post_date.isoformat(),
            "day": day_name,
            "theme": theme,
            "focus": focus,
            "channel": channel,
            "tone": tone,
            "content": content,
            "char_count": len(content),
            "max_chars": channel_info["max_chars"],
            "status": "draft",
        })

    return {
        "status": "ok",
        "company": company,
        "industry": industry,
        "channel": channel,
        "tone": tone,
        "generated_at": datetime.now().isoformat(),
        "week_start": base_date.isoformat(),
        "posts": posts,
    }

def get_marketing_config() -> Dict[str, Any]:
    """Return available channels, tones, and themes for the frontend."""
    config = _get_business_config()
    return {
        "status": "ok",
        "company": config.get("business_name", "Your Company"),
        "industry": config.get("industry", "Home Services"),
        "channels": list(CHANNELS.keys()),
        "channel_info": CHANNELS,
        "tones": TONES,
        "themes": [t["theme"] for t in DAILY_THEMES],
        "daily_themes": DAILY_THEMES,
    }

def customize_post(
    post_id: str,
    content: str,
    company: Optional[str] = None,
    channel: str = "facebook",
) -> Dict[str, Any]:
    """Save a customized version of a post (returns the updated post)."""
    channel_info = CHANNELS.get(channel, CHANNELS["facebook"])
    content = _truncate(content, channel_info["max_chars"])
    return {
        "status": "ok",
        "post_id": post_id,
        "content": content,
        "char_count": len(content),
        "max_chars": channel_info["max_chars"],
        "channel": channel,
    }
