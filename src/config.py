"""System configuration, policy rules, and operational constraints for STAGE."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Any, List

# Timezones
UTC = timezone.utc
IST = timezone(timedelta(hours=5, minutes=30))

# Operational Limits & Budgets
MAX_MODEL_CALLS = 8
MAX_TOOL_CALLS = 20
LATENCY_BUDGET_MS = 60_000   # 60 seconds
HARD_LATENCY_LIMIT_MS = 300_000 # 5 minutes

# Offline Buffering Threshold
# If the delay between occurred_at (device clock) and received_at (server clock)
# or age exceeds 600 seconds (10 minutes), the app open was buffered offline.
MAX_LIVE_SESSION_DELAY_S = 600

# Home Page Rules
HOME_PAGE_TTL_MINUTES = 120
MAX_HOME_PAGE_ROWS = 6
MIN_TITLES_PER_ROW = 3
MAX_TITLES_PER_ROW = 10
ALLOWED_ROW_TYPES = [
    "next_episode",
    "because_you_watched",
    "popular_in_dialect",
    "new_releases",
    "genre"
]

# Messaging Constraints
QUIET_HOURS_START_IST = 22  # 22:00 IST
QUIET_HOURS_END_IST = 8     # 08:00 IST
MAX_MESSAGES_PER_IST_DAY = 1

PUSH_MAX_TITLE_CHARS = 40
PUSH_MAX_BODY_CHARS = 120
FORBIDDEN_PUSH_PHRASES = [
    "last chance",
    "hurry",
    "only today",
    "free forever",
    "guaranteed"
]

# Approved Pricing from config/pricing.json
VALID_PRICES_INR = [1, 149, 399]
VALID_PLANS = {
    "P_TRIAL": {"price_inr": 1, "days": 3, "renews_to": "P_MONTH"},
    "P_MONTH": {"price_inr": 149, "days": 30},
    "P_QUARTER": {"price_inr": 399, "days": 90}
}

# Approved WhatsApp Templates
APPROVED_WA_TEMPLATES = {
    "wa_new_episode_v2": {
        "variables": ["title_name", "episode_number"],
        "template": "Naya episode aa gaya! {title_name} ka episode {episode_number} ab dekhiye."
    },
    "wa_recommend_title_v1": {
        "variables": ["title_name", "dialect_name"],
        "template": "Aapke liye {dialect_name} mein: {title_name}. Abhi dekhiye."
    },
    "wa_trial_ending_v1": {
        "variables": ["plan_price"],
        "template": "Aapka trial jald khatam ho raha hai. {plan_price} mein dekhte rahiye."
    }
}

# Dialect Names Mapping for Messaging
DIALECT_DISPLAY_NAMES = {
    "d1": "Bhojpuri",
    "d2": "Haryanvi",
    "d3": "Rajasthani",
    "d4": "Maithili",
    "d5": "Magahi",
    "d6": "Bundeli"
}


def is_quiet_hours(dt: datetime) -> bool:
    """Return True if datetime falls in India quiet hours (22:00 to 08:00 IST)."""
    ist_time = dt.astimezone(IST)
    h = ist_time.hour
    return h >= QUIET_HOURS_START_IST or h < QUIET_HOURS_END_IST


def get_ist_date_str(dt: datetime) -> str:
    """Return YYYY-MM-DD representing the IST calendar day."""
    return dt.astimezone(IST).strftime("%Y-%m-%d")


def parse_iso(ts_str: str) -> datetime:
    """Safely parse ISO timestamp into UTC datetime."""
    if not ts_str:
        return None
    # Handle trailing Z
    clean = ts_str.replace("Z", "+00:00")
    dt = datetime.fromisoformat(clean)
    return dt.astimezone(UTC)


def to_iso(dt: datetime) -> str:
    """Format datetime as UTC ISO8601 string with milliseconds."""
    if not dt:
        return ""
    utc_dt = dt.astimezone(UTC)
    return utc_dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
